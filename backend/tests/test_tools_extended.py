from unittest.mock import AsyncMock, patch

import pytest
from sqlmodel import Session, select

from app.core.context import set_current_universe
from app.core.runtime_state import set_current_run_id
from app.core.tools import (
    _get_run_id,
    _get_universe_uuid,
    _store_artifact,
    build_freshness_comparison_report,
    tool_compare_source_freshness,
    tool_delete_unconfirmed_artifact,
    tool_link_entity_to_canonical,
    tool_link_universes,
    tool_save_notebook_entry,
    tool_upsert_artifacts,
)
from app.db.schema import Artifact, Universe
from app.db.unconfirmed_schema import NotebookEntry, UnconfirmedUniverse
from app.db.unconfirmed_session import unconfirmed_engine


@pytest.fixture(autouse=True)
def _clear_active_context():
    set_current_universe(None)
    set_current_run_id(None)
    yield


class TestBuildFreshnessReport:
    def test_all_available(self):
        report = build_freshness_comparison_report({
            "http://a.com": (
                "[SOURCE FRESHNESS SIGNALS]\nStaleness warning: none detected"
                "\n[END SIGNALS]\nBody"
            ),
            "http://b.com": (
                "[SOURCE FRESHNESS SIGNALS]\nLast-Modified: 2024\n[END SIGNALS]"
                "\nOther"
            ),
        })
        assert "CANDIDATE: http://a.com" in report
        assert "CANDIDATE: http://b.com" in report

    def test_mixed_availability(self):
        report = build_freshness_comparison_report({
            "http://good.com": "[SOURCE FRESHNESS SIGNALS]\nFresh\n[END SIGNALS]",
            "http://bad.com": None,
        })
        assert "Unavailable" in report
        assert "Fresh" in report

    def test_content_is_dict(self):
        report = build_freshness_comparison_report({
            "http://dict.com": {
                "main_content": "[SOURCE FRESHNESS SIGNALS]\nFresh\n[END SIGNALS]"
            },
        })
        assert "Fresh" in report

    def test_no_signals_block_falls_back_to_first_500_chars(self):
        content = "A" * 600
        report = build_freshness_comparison_report({
            "http://long.com": content,
        })
        assert len(report) > 0

    def test_unsliceable_content_raises_typeerror(self):
        class BadSlice:
            def __contains__(self, item):
                return False
            def __getitem__(self, key):
                if isinstance(key, slice):
                    raise TypeError("nope")
                return "x"

        with pytest.raises(TypeError):
            build_freshness_comparison_report({
                "http://bad.com": BadSlice(),
            })


class TestToolCompareSourceFreshness:
    async def test_missing_urls(self):
        result = await tool_compare_source_freshness({})
        assert "Missing or invalid urls" in result

    async def test_invalid_urls_type(self):
        result = await tool_compare_source_freshness({"urls": "not-list"})
        assert "Missing or invalid urls" in result

    @patch("app.core.tools.web_fetcher.fetch_page", new_callable=AsyncMock)
    async def test_fetch_failure_returns_none(self, mock_fetch):
        mock_fetch.side_effect = RuntimeError("fail")
        result = await tool_compare_source_freshness({"urls": ["http://x.com", "http://y.com"]})
        assert "CANDIDATE: http://x.com" in result
        assert "Unavailable" in result


class TestToolLinkUniverses:
    async def test_missing_params(self):
        result = await tool_link_universes({})
        assert "Missing" in result

    async def test_universes_not_found(self):
        set_current_universe("U1")
        result = await tool_link_universes({
            "target_universe_name": "U2",
            "relation_type": "ALT",
        })
        assert "not found" in result

    async def test_success(self, ephemeral_db):
        u1 = Universe(name="LinkSrc")
        u2 = Universe(name="LinkTgt")
        ephemeral_db.add_all([u1, u2])
        ephemeral_db.commit()
        set_current_universe("LinkSrc")
        result = await tool_link_universes({
            "target_universe_name": "LinkTgt",
            "relation_type": "PRECEDES",
            "description": "test",
        })
        assert "Linked" in result
        assert "PRECEDES" in result


class TestToolLinkEntityToCanonical:
    async def test_missing_params(self):
        result = await tool_link_entity_to_canonical({})
        assert "Missing" in result

    async def test_entity_not_found(self, ephemeral_db):
        u = Universe(name="ETest")
        ephemeral_db.add(u)
        ephemeral_db.commit()
        set_current_universe("ETest")
        result = await tool_link_entity_to_canonical({
            "entity_name": "Ghost",
        })
        assert "not found" in result

    async def test_mark_as_canonical(self, ephemeral_db):
        u = Universe(name="ECanon")
        ephemeral_db.add(u)
        ephemeral_db.commit()
        e = Artifact(name="Hero", type="entity", universe_id=u.id)
        ephemeral_db.add(e)
        ephemeral_db.commit()
        set_current_universe("ECanon")
        result = await tool_link_entity_to_canonical({
            "entity_name": "Hero",
        })
        assert "marked as canonical" in result
        assert "Hero" in result

    async def test_link_to_canonical(self, ephemeral_db):
        u = Universe(name="ELink")
        ephemeral_db.add(u)
        ephemeral_db.commit()
        e1 = Artifact(name="HeroCanon", type="entity", universe_id=u.id)
        e2 = Artifact(name="HeroLink", type="entity", universe_id=u.id)
        ephemeral_db.add_all([e1, e2])
        ephemeral_db.commit()
        ephemeral_db.refresh(e1)
        set_current_universe("ELink")
        result = await tool_link_entity_to_canonical({
            "entity_name": "HeroLink",
            "canonical_entity_id": e1.id,
        })
        assert "linked to canonical" in result


class TestToolSaveNotebookEntry:
    async def test_no_active_context(self):
        result = await tool_save_notebook_entry({"title": "T", "summary": "S"})
        assert "No active universe context" in result

    async def test_single_item(self, ephemeral_db):
        u = Universe(name="SaveTest")
        ephemeral_db.add(u)
        ephemeral_db.commit()
        set_current_universe("SaveTest")
        result = await tool_save_notebook_entry({
            "title": "S",
            "summary": "O",
            "details": "P",
        })
        assert "saved successfully" in result
        with Session(unconfirmed_engine) as s:
            ne = s.exec(
                select(NotebookEntry).where(NotebookEntry.title == "S")
            ).first()
            assert ne is not None

    async def test_missing_fields(self, ephemeral_db):
        u = Universe(name="Missing")
        ephemeral_db.add(u)
        ephemeral_db.commit()
        set_current_universe("Missing")
        result = await tool_save_notebook_entry({
            "title": "S",
            "summary": "",
        })
        assert "Error: Missing title or summary" in result


class TestToolDeleteUnconfirmedArtifact:
    async def test_no_artifact_id(self):
        result = await tool_delete_unconfirmed_artifact({})
        assert "Missing" in result

    async def test_no_active_context(self):
        result = await tool_delete_unconfirmed_artifact({"claim_id": 1})
        assert "No active universe context" in result

    async def test_delete_nonexistent(self):
        set_current_universe("DelTest")
        u = UnconfirmedUniverse(name="DelTest")
        with Session(unconfirmed_engine) as s:
            s.add(u)
            s.commit()
        result = await tool_delete_unconfirmed_artifact({"claim_ids": [999]})
        assert "Deleted 0" in result

    async def test_delete_wrong_universe(self):
        u1 = UnconfirmedUniverse(name="DelA", universe_uuid="uuid-a")
        u2 = UnconfirmedUniverse(name="DelB", universe_uuid="uuid-b")
        with Session(unconfirmed_engine) as s:
            s.add_all([u1, u2])
            s.commit()
            s.refresh(u1)
            ne = NotebookEntry(
                universe_uuid=u1.universe_uuid, title="S", summary="O", kind="Observation"
            )


            s.add(ne)
            s.commit()
            nid = ne.id
        set_current_universe("DelB")
        result = await tool_delete_unconfirmed_artifact({"claim_ids": [nid]})
        assert "Deleted 0" in result
        assert "does not belong to current universe" in result

    async def test_delete_success(self):
        set_current_universe("DelOk")
        with Session(unconfirmed_engine) as s:
            u = s.exec(
                select(UnconfirmedUniverse).where(UnconfirmedUniverse.name == "DelOk")
            ).first()
            if not u:
                u = UnconfirmedUniverse(name="DelOk", universe_uuid="uuid-ok")
                s.add(u)
                s.commit()
                s.refresh(u)
            ne = NotebookEntry(
                universe_uuid=u.universe_uuid, title="S", summary="O", kind="Observation"
            )


            s.add(ne)
            s.commit()
            nid = ne.id
        result = await tool_delete_unconfirmed_artifact({"claim_ids": [nid]})
        assert "Deleted 1" in result


class TestToolUpsertArtifacts:
    async def test_no_active_context(self):
        result = await tool_upsert_artifacts({})
        assert "No active universe context" in result

    async def test_universe_not_found(self):
        set_current_universe("NoUni")
        result = await tool_upsert_artifacts({"items": [{"type": "entity", "name": "E"}]})
        assert "not found" in result

    async def test_basic_upsert(self, ephemeral_db):
        u = Universe(name="UpsertBasic")
        ephemeral_db.add(u)
        ephemeral_db.commit()
        set_current_universe("UpsertBasic")
        result = await tool_upsert_artifacts({
            "items": [
                {"type": "entity", "name": "Char", "payload": {"power": "Flight"}}
            ]
        })
        assert "Integrated 1 new" in result

    async def test_upsert_with_evidence(self, ephemeral_db):
        u = Universe(name="UpsertEv")
        ephemeral_db.add(u)
        ephemeral_db.commit()
        set_current_universe("UpsertEv")
        result = await tool_upsert_artifacts({
            "items": [{
                "type": "entity",
                "name": "Char",
                "confidence": "High",
                "source_wiki": "http://wiki.example",
                "source_reference": "#section1",
                "payload": {"power": "Strength"},
            }]
        })
        assert "Integrated 1 new" in result

    async def test_upsert_with_attributes(self, ephemeral_db):
        u = Universe(name="UpsertAttr")
        ephemeral_db.add(u)
        ephemeral_db.commit()
        set_current_universe("UpsertAttr")
        result = await tool_upsert_artifacts({
            "items": [{
                "type": "entity",
                "name": "Char",
                "payload": {"level": "10", "type": "physical"},
            }]
        })
        assert "Integrated 1 new" in result

    async def test_upsert_existing_updates(self, ephemeral_db):
        u = Universe(name="UpsertDup")
        ephemeral_db.add(u)
        ephemeral_db.commit()
        set_current_universe("UpsertDup")
        await tool_upsert_artifacts({
            "items": [
                {"type": "entity", "name": "Char", "payload": {"power": "Flight"}}
            ]
        })
        result = await tool_upsert_artifacts({
            "items": [
                {"type": "entity", "name": "Char", "payload": {"power": "Flight"}}
            ]
        })
        assert "1 updated" in result

    async def test_upsert_missing_fields_skipped(self, ephemeral_db):
        u = Universe(name="UpsertSkip")
        ephemeral_db.add(u)
        ephemeral_db.commit()
        set_current_universe("UpsertSkip")
        result = await tool_upsert_artifacts({
            "items": [{"name": "NoType"}]
        })
        assert "Integrated 0 new and 0 updated" in result

    async def test_single_item_not_items(self, ephemeral_db):
        u = Universe(name="UpsertSingle")
        ephemeral_db.add(u)
        ephemeral_db.commit()
        set_current_universe("UpsertSingle")
        result = await tool_upsert_artifacts({
            "type": "entity",
            "name": "Char",
            "payload": {"role": "Hero"},
        })
        assert "Error: Missing `items` list" in result


class TestStoreArtifact:
    def test_store_and_dedup(self):
        cid = _store_artifact(
            content_type="test",
            content_text="unique content here",
            source_url="http://src",
            engine_name="test",
        )
        assert cid is not None

        # Same hash -> return existing id
        cid2 = _store_artifact(
            content_type="test",
            content_text="unique content here",
            source_url="http://src",
            engine_name="test",
        )
        assert cid2 == cid


class TestGetRunIdAndUniverseUuid:
    def test_get_run_id(self):
        assert _get_run_id() is None

    def test_get_universe_uuid_no_context(self):
        assert _get_universe_uuid() is None

    def test_get_universe_uuid_with_context(self, ephemeral_db):
        u = Universe(name="UUIDTest")
        ephemeral_db.add(u)
        ephemeral_db.commit()
        set_current_universe("UUIDTest")
        uuid_val = _get_universe_uuid()
        assert uuid_val is not None


class TestToolQueryArtifacts:
    async def test_query_all(self, ephemeral_db):
        set_current_universe("QAll")
        u = Universe(name="QAll")
        ephemeral_db.add(u)
        ephemeral_db.commit()

        e = Artifact(name="E1", type="entity", universe_id=u.id)
        ephemeral_db.add(e)
        ephemeral_db.commit()

        import json
        c = Artifact(
            name="E1 HAS_POWER Flying",
            type="claim",
            universe_id=u.id,
            payload_json=json.dumps({
                "subject_id": e.id,
                "predicate": "HAS_POWER",
                "object_literal": "Flying"
            })
        )
        ephemeral_db.add(c)
        ephemeral_db.commit()

        from app.core.tools import tool_query_artifacts
        result = await tool_query_artifacts({})
        assert "E1" in result

    async def test_filter_by_type(self, ephemeral_db):
        set_current_universe("QFilt")
        u = Universe(name="QFilt")
        ephemeral_db.add(u)
        ephemeral_db.commit()

        e = Artifact(name="E1", type="entity", universe_id=u.id)
        lit1 = Artifact(name="flight", type="literal", universe_id=u.id)
        ephemeral_db.add_all([e, lit1])
        ephemeral_db.commit()

        import json
        c = Artifact(
            name="E1 HAS_POWER Flying",
            type="claim",
            universe_id=u.id,
            payload_json=json.dumps({
                "subject_id": e.id,
                "predicate": "HAS_POWER",
                "object_literal": "Flying"
            })
        )
        ephemeral_db.add(c)
        ephemeral_db.commit()

        from app.core.tools import tool_query_artifacts
        result = await tool_query_artifacts({"type": "entity"})
        assert "E1" in result
        assert "flight" not in result


    async def test_filter_no_match(self, ephemeral_db):
        set_current_universe("QFilt2")
        u = Universe(name="QFilt2")
        ephemeral_db.add(u)
        ephemeral_db.commit()

        from app.core.tools import tool_query_artifacts
        result = await tool_query_artifacts({"name": "nonexistent"})
        assert "no verified claims found" in result.lower()


class TestToolFetchPageErrors:
    @patch("app.core.tools.web_fetcher.fetch_page", new_callable=AsyncMock)
    async def test_string_response(self, mock_fetch):
        mock_fetch.return_value = "plain string response"
        from app.core.tools import tool_fetch_page
        result = await tool_fetch_page({"urls": ["http://example.com"]})
        assert "plain string response" in result

    @patch("app.core.tools.web_fetcher.fetch_page", new_callable=AsyncMock)
    async def test_error_dict_response(self, mock_fetch):
        mock_fetch.return_value = {"error": "not found"}
        from app.core.tools import tool_fetch_page
        result = await tool_fetch_page({"urls": ["http://example.com"]})
        assert "Error fetching" in result

    @patch("app.core.tools.web_fetcher.fetch_page", new_callable=AsyncMock)
    async def test_exception_during_fetch(self, mock_fetch):
        mock_fetch.side_effect = RuntimeError("network error")
        from app.core.tools import tool_fetch_page
        result = await tool_fetch_page({"urls": ["http://example.com"]})
        assert "Error fetching" in result


class TestToolWebSearchDetailed:
    @patch("app.core.tools.web_searcher.perform_search", new_callable=AsyncMock)
    async def test_single_query(self, mock_search):
        mock_search.return_value = {"status": "SUCCESS", "results": []}
        from app.core.tools import tool_web_search
        result = await tool_web_search({"search_query": "test"})
        assert "test" in result

    @patch("app.core.tools.web_searcher.perform_search", new_callable=AsyncMock)
    async def test_multi_query(self, mock_search):
        mock_search.return_value = {"status": "SUCCESS", "results": []}
        from app.core.tools import tool_web_search
        result = await tool_web_search({"queries": ["q1", "q2"]})
        assert "q1" in result
        assert "q2" in result

    @patch("app.core.tools.web_searcher.perform_search", new_callable=AsyncMock)
    async def test_error_status(self, mock_search):
        mock_search.return_value = {"status": "ERROR", "message": "rate limited"}
        from app.core.tools import tool_web_search
        result = await tool_web_search({"search_query": "test"})
        assert "Error" in result

    @patch("app.core.tools.web_searcher.perform_search", new_callable=AsyncMock)
    async def test_blocked_status(self, mock_search):
        mock_search.return_value = {"status": "BLOCKED", "message": "blocked"}
        from app.core.tools import tool_web_search
        result = await tool_web_search({"search_query": "test"})
        assert "BLOCKED" in result

    @patch("app.core.tools.web_searcher.perform_search", new_callable=AsyncMock)
    async def test_no_results_status(self, mock_search):
        mock_search.return_value = {"status": "NO_RESULTS", "message": "no results"}
        from app.core.tools import tool_web_search
        result = await tool_web_search({"search_query": "test"})
        assert "No results" in result

    @patch("app.core.tools.web_searcher.perform_search", new_callable=AsyncMock)
    async def test_unexpected_status(self, mock_search):
        mock_search.return_value = {"status": "UNKNOWN_STATUS"}
        from app.core.tools import tool_web_search
        result = await tool_web_search({"search_query": "test"})
        assert "Unexpected" in result

    @patch("app.core.tools.web_searcher.perform_search", new_callable=AsyncMock)
    async def test_engines_string(self, mock_search):
        mock_search.return_value = {"status": "SUCCESS", "results": []}
        from app.core.tools import tool_web_search
        result = await tool_web_search({
            "search_query": "test", "engine": "google,brave"
        })
        assert "test" in result

    @patch("app.core.tools.web_searcher.perform_search", new_callable=AsyncMock)
    async def test_engines_list(self, mock_search):
        mock_search.return_value = {"status": "SUCCESS", "results": []}
        from app.core.tools import tool_web_search
        result = await tool_web_search({
            "search_query": "test", "engine": ["google", "brave"]
        })
        assert "test" in result

    @patch("app.core.tools.web_searcher.perform_search", new_callable=AsyncMock)
    async def test_none_result(self, mock_search):
        mock_search.return_value = None
        from app.core.tools import tool_web_search
        result = await tool_web_search({"search_query": "test"})
        assert isinstance(result, str)
class TestToolWebSearchMissingQuery:
    async def test_no_query(self):
        from app.core.tools import tool_web_search
        result = await tool_web_search({})
        assert "Missing" in result

