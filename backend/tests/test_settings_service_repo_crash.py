from unittest.mock import AsyncMock, patch

import pytest
from app.db.schema import Setting
from app.services.settings_service import SettingsService


class TestSettingsServiceGetSetting:
    """The actual root-cause fix: SettingsService lost its eager .repo
    attribute in the session-leak refactor, but three call sites elsewhere
    still reached into settings_service.repo.get_setting(...) directly,
    crashing with AttributeError the moment they ran (as seen in production:
    'Critical Execution Failure: SettingsService object has no attribute
    repo'). This adds a proper session-scoped passthrough method instead of
    re-exposing .repo."""

    def test_get_setting_returns_none_when_missing(self, ephemeral_db):
        svc = SettingsService()
        assert svc.get_setting("DOES_NOT_EXIST") is None

    def test_get_setting_returns_value(self, ephemeral_db):
        from app.db.settings_session import settings_engine
        from sqlmodel import Session

        with Session(settings_engine) as s:
            s.add(Setting(key="MAX_PARALLEL_AGENTS", value="7"))
            s.commit()

        svc = SettingsService()
        setting = svc.get_setting("MAX_PARALLEL_AGENTS")
        assert setting is not None
        assert setting.value == "7"

    def test_settings_service_has_no_repo_attribute(self):
        """Documents the actual API shape post-refactor -- .repo is gone on
        purpose (it was the eager-session-leak pattern), so any future call
        site must use get_setting() or another proper method, not .repo."""
        svc = SettingsService()
        assert not hasattr(svc, "repo")


@pytest.mark.asyncio
class TestResearchNodeSettingsLookup:
    """Reproduces the exact crash from the production log: 'Manager
    [IN_PROGRESS] Starting parallel research phase' immediately followed by
    'Critical Execution Failure: SettingsService object has no attribute
    repo', which happened at the MAX_PARALLEL_AGENTS lookup in research_node
    before any actual research/network call occurred."""

    async def test_research_node_reads_batch_size_without_crashing(self, ephemeral_db):
        from app.agents.nodes import research_node
        from app.db.settings_session import settings_engine
        from sqlmodel import Session

        with Session(settings_engine) as s:
            s.add(Setting(key="MAX_PARALLEL_AGENTS", value="2"))
            s.commit()

        state = {
            "run_id": "test-run-settings-crash",
            "target_worlds": ["TestWorldA", "TestWorldB"],
            "focused_features": None,
            "research_results": [],
            "verified_worlds": [],
            "errors": [],
        }

        fake_result = {
            "name": "TestWorldA",
            "summary": "stub summary",
            "status": "VERIFIED",
        }
        with patch(
            "app.agents.nodes.research_single_world",
            new=AsyncMock(return_value=fake_result),
        ):
            # Before the fix, this raised AttributeError before even reaching
            # research_single_world -- the crash happened at the settings
            # lookup, not in the research call itself.
            result = await research_node(state)

        assert "research_results" in result
        assert len(result["research_results"]) == 2

    async def test_research_node_defaults_batch_size_when_setting_absent(
        self, ephemeral_db
    ):
        """No MAX_PARALLEL_AGENTS row at all -- must default to 5, not crash."""
        from app.agents.nodes import research_node

        state = {
            "run_id": "test-run-no-setting",
            "target_worlds": ["SoloWorld"],
            "focused_features": None,
            "research_results": [],
            "verified_worlds": [],
            "errors": [],
        }

        with patch(
            "app.agents.nodes.research_single_world",
            new=AsyncMock(
                return_value={"name": "SoloWorld", "summary": "s", "status": "VERIFIED"}
            ),
        ):
            result = await research_node(state)

        assert len(result["research_results"]) == 1
