import json
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest
from sqlmodel import Session, select

from app.core.acquisition_cache import acquisition_cache
from app.core.context import set_current_universe
from app.core.tools import (
    AGENT_TOOLS,
    _get_run_id,
    _get_universe_uuid,
    _store_artifact,
    build_freshness_comparison_report,
    tool_compare_source_freshness,
    tool_delete_unconfirmed_claim,
    tool_link_entity_to_canonical,
    tool_link_universes,
    tool_save_unconfirmed_claim,
    tool_upsert_claims,
)
from app.db.schema import Entity, Universe
from app.db.session import engine
from app.db.unconfirmed_schema import UnconfirmedClaim, UnconfirmedUniverse
from app.db.unconfirmed_session import unconfirmed_engine


@pytest.fixture(autouse=True)
def _clear_active_context():
    set_current_universe(None)
    yield


class TestBuildFreshnessReport:
    def test_all_available(self):
        report = build_freshness_comparison_report({
            "http://a.com": "[SOURCE FRESHNESS SIGNALS]\nStaleness warning: none detected\n[END SIGNALS]\nBody",
            "http://b.com": "[SOURCE FRESHNESS SIGNALS]\nLast-Modified: 2024\n[END SIGNALS]\nOther",
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
            "http://dict.com": {"main_content": "[SOURCE FRESHNESS SIGNALS]\nFresh\n[END SIGNALS]"},
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
                    raise RuntimeError("nope")
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
        e = Entity(name="Hero", entity_type="Person", universe_id=u.id)
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
        e1 = Entity(name="HeroCanon", entity_type="Person", universe_id=u.id)
        e2 = Entity(name="HeroLink", entity_type="Person", universe_id=u.id)
        ephemeral_db.add_all([e1, e2])
        ephemeral_db.commit()
        ephemeral_db.refresh(e1)
        set_current_universe("ELink")
        result = await tool_link_entity_to_canonical({
            "entity_name": "HeroLink",
            "canonical_entity_id": e1.id,
        })
        assert "linked to canonical" in result


class TestToolSaveUnconfirmedClaim:
    async def test_no_active_context(self):
        result = await tool_save_unconfirmed_claim({"items": []})
        assert "No active universe context" in result

    async def test_single_item(self):
        set_current_universe("SaveTest")
        result = await tool_save_unconfirmed_claim({
            "subject": "S",
            "predicate": "P",
            "object_val": "O",
        })
        assert "Saved 1 unconfirmed claim" in result
        with Session(unconfirmed_engine) as s:
            uc = s.exec(
                select(UnconfirmedClaim).where(UnconfirmedClaim.subject == "S")
            ).first()
            assert uc is not None

    async def test_missing_fields_in_single_item(self):
        set_current_universe("Missing")
        result = await tool_save_unconfirmed_claim({
            "subject": "S",
            "predicate": "",
            "object_val": "",
        })
        assert "Skipped claim" in result
        assert "Errors" in result

    async def test_batch_items(self):
        set_current_universe("Batch")
        result = await tool_save_unconfirmed_claim({
            "items": [
                {"subject": "S1", "predicate": "P1", "object_val": "O1"},
                {"subject": "S2", "predicate": "P2", "object_val": "O2"},
            ]
        })
        assert "2 unconfirmed claim" in result

    async def test_partial_batch_items(self):
        set_current_universe("Partial")
        result = await tool_save_unconfirmed_claim({
            "items": [
                {"subject": "S1", "predicate": "P1", "object_val": "O1"},
                {"subject": "S2", "predicate": "", "object_val": "O2"},
            ]
        })
        assert "1 unconfirmed claim" in result
        assert "Errors" in result


class TestToolDeleteUnconfirmedClaim:
    async def test_no_claim_id(self):
        result = await tool_delete_unconfirmed_claim({})
        assert "Missing" in result

    async def test_no_active_context(self):
        result = await tool_delete_unconfirmed_claim({"claim_id": 1})
        assert "No active universe context" in result

    async def test_delete_nonexistent(self):
        set_current_universe("DelTest")
        u = UnconfirmedUniverse(name="DelTest")
        with Session(unconfirmed_engine) as s:
            s.add(u)
            s.commit()
        result = await tool_delete_unconfirmed_claim({"claim_ids": [999]})
        assert "not found" in result

    async def test_delete_wrong_universe(self):
        u1 = UnconfirmedUniverse(name="DelA")
        u2 = UnconfirmedUniverse(name="DelB")
        with Session(unconfirmed_engine) as s:
            s.add_all([u1, u2])
            s.commit()
            s.refresh(u1)
            c = UnconfirmedClaim(universe_id=u1.id, subject="S", predicate="P", object_val="O")
            s.add(c)
            s.commit()
            cid = c.id
        set_current_universe("DelB")
        result = await tool_delete_unconfirmed_claim({"claim_ids": [cid]})
        assert "does not belong" in result

    async def test_delete_success(self):
        set_current_universe("DelOk")
        with Session(unconfirmed_engine) as s:
            u = s.exec(select(UnconfirmedUniverse).where(UnconfirmedUniverse.name == "DelOk")).first()
            if not u:
                u = UnconfirmedUniverse(name="DelOk")
                s.add(u)
                s.commit()
                s.refresh(u)
            c = UnconfirmedClaim(universe_id=u.id, subject="S", predicate="P", object_val="O")
            s.add(c)
            s.commit()
            cid = c.id
        result = await tool_delete_unconfirmed_claim({"claim_id": cid})
        assert "Deleted 1" in result


class TestToolUpsertClaims:
    async def test_no_active_context(self):
        result = await tool_upsert_claims({})
        assert "No active universe context" in result

    async def test_universe_not_found(self):
        set_current_universe("NoUni")
        result = await tool_upsert_claims({"items": []})
        assert "not found" in result

    async def test_basic_upsert(self, ephemeral_db):
        u = Universe(name="UpsertBasic")
        ephemeral_db.add(u)
        ephemeral_db.commit()
        set_current_universe("UpsertBasic")
        result = await tool_upsert_claims({
            "items": [{"subject": "Char", "predicate": "has_power", "object_val": "Flight"}]
        })
        assert "Created: 1" in result

    async def test_upsert_with_evidence(self, ephemeral_db):
        u = Universe(name="UpsertEv")
        ephemeral_db.add(u)
        ephemeral_db.commit()
        set_current_universe("UpsertEv")
        result = await tool_upsert_claims({
            "items": [{
                "subject": "Char",
                "predicate": "has_power",
                "object_val": "Strength",
                "source_wiki": "http://wiki.example",
                "source_reference": "#section1",
            }]
        })
        assert "Created: 1" in result

    async def test_upsert_with_attributes(self, ephemeral_db):
        u = Universe(name="UpsertAttr")
        ephemeral_db.add(u)
        ephemeral_db.commit()
        set_current_universe("UpsertAttr")
        result = await tool_upsert_claims({
            "items": [{
                "subject": "Char",
                "predicate": "has_power",
                "object_val": "Speed",
                "attributes": {"level": "10", "type": "physical"},
            }]
        })
        assert "Created: 1" in result

    async def test_upsert_existing_updates(self, ephemeral_db):
        u = Universe(name="UpsertDup")
        ephemeral_db.add(u)
        ephemeral_db.commit()
        set_current_universe("UpsertDup")
        await tool_upsert_claims({
            "items": [{"subject": "Char", "predicate": "has_power", "object_val": "Flight"}]
        })
        result = await tool_upsert_claims({
            "items": [{"subject": "Char", "predicate": "has_power", "object_val": "Flight"}]
        })
        assert "Updated: 1" in result

    async def test_upsert_missing_fields_skipped(self, ephemeral_db):
        u = Universe(name="UpsertSkip")
        ephemeral_db.add(u)
        ephemeral_db.commit()
        set_current_universe("UpsertSkip")
        result = await tool_upsert_claims({
            "items": [{"subject": "", "predicate": "", "object_val": ""}]
        })
        assert "Skipped: 1" in result

    async def test_single_item_not_items(self, ephemeral_db):
        u = Universe(name="UpsertSingle")
        ephemeral_db.add(u)
        ephemeral_db.commit()
        set_current_universe("UpsertSingle")
        result = await tool_upsert_claims({
            "subject": "Char",
            "predicate": "is_a",
            "object_val": "Hero",
        })
        assert "Created: 1" in result


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


class TestToolQueryUnconfirmedClaims:
    async def test_no_active_context(self):
        from app.core.tools import tool_query_unconfirmed_claims
        result = await tool_query_unconfirmed_claims({})
        assert "No active universe context" in result

    async def test_no_unconfirmed_data(self):
        set_current_universe("NoData")
        from app.core.tools import tool_query_unconfirmed_claims
        result = await tool_query_unconfirmed_claims({})
        assert "No unconfirmed data" in result

    async def test_has_unconfirmed_claims(self):
        set_current_universe("HasUnc")
        with Session(unconfirmed_engine) as s:
            u = UnconfirmedUniverse(name="HasUnc")
            s.add(u)
            s.commit()
            s.refresh(u)
            s.add(UnconfirmedClaim(universe_id=u.id, subject="S", predicate="P", object_val="O"))
            s.commit()
        from app.core.tools import tool_query_unconfirmed_claims
        result = await tool_query_unconfirmed_claims({})
        assert "S" in result
        assert "P" in result
        assert "O" in result


class TestToolQueryClaimsWithFilter:
    async def test_filter_by_predicate(self, ephemeral_db):
        set_current_universe("QFilt")
        u = Universe(name="QFilt")
        ephemeral_db.add(u)
        ephemeral_db.commit()

        e = Entity(name="E1", entity_type="T", universe_id=u.id)
        ephemeral_db.add(e)
        ephemeral_db.commit()
        ephemeral_db.refresh(e)

        from app.db.schema import Claim
        ephemeral_db.add(Claim(subject_id=e.id, predicate="power", object_literal="flight", universe_scope=u.id, status="VERIFIED"))
        ephemeral_db.add(Claim(subject_id=e.id, predicate="speed", object_literal="100", universe_scope=u.id, status="VERIFIED"))
        ephemeral_db.commit()

        from app.core.tools import tool_query_claims
        result = await tool_query_claims({"predicate": "power"})
        assert "flight" in result
        assert "100" not in result

    async def test_filter_no_match(self, ephemeral_db):
        set_current_universe("QFilt2")
        u = Universe(name="QFilt2")
        ephemeral_db.add(u)
        ephemeral_db.commit()

        e = Entity(name="E1", entity_type="T", universe_id=u.id)
        ephemeral_db.add(e)
        ephemeral_db.commit()
        ephemeral_db.refresh(e)

        from app.db.schema import Claim
        ephemeral_db.add(Claim(subject_id=e.id, predicate="power", object_literal="flight", universe_scope=u.id, status="VERIFIED"))
        ephemeral_db.commit()

        from app.core.tools import tool_query_claims
        result = await tool_query_claims({"predicate": "nonexistent"})
        assert "no verified claims" in result.lower()


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
        result = await tool_web_search({"search_query": "test", "engine": "google,brave"})
        assert "test" in result

    @patch("app.core.tools.web_searcher.perform_search", new_callable=AsyncMock)
    async def test_engines_list(self, mock_search):
        mock_search.return_value = {"status": "SUCCESS", "results": []}
        from app.core.tools import tool_web_search
        result = await tool_web_search({"search_query": "test", "engine": ["google", "brave"]})
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
