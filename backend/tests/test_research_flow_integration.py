import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from app.research.researcher import research_single_world
from app.core.domain import ResearchTarget
from app.db.session import Session, engine
from app.db.unconfirmed_session import Session as UnconfirmedSession, unconfirmed_engine
from app.db.schema import Universe
from app.db.unconfirmed_schema import NotebookEntry
from app.agents.prompts import get_researcher_prompt

@pytest.mark.asyncio
async def test_research_workspace_integration_flow():
    """
    Integration test: Verify that the research loop correctly:
    1. Fetches workspace indices.
    2. Reflects those changes in the subsequent turn's prompt.
    """
    # 1. Setup Universe
    with Session(engine) as session:
        u = Universe(name="IntegrationWorld")
        session.add(u)
        session.commit()
        session.refresh(u)
        target = ResearchTarget(uuid=u.uuid, name=u.name)

    run_id = "test-run-123"

    captured_prompts = []
    async def prompt_capturer(*args, **kwargs):
        captured_prompts.append(kwargs.get("system_prompt"))
        # Return a value that terminates the loop quickly
        return (True, '{"status": "complete", "Universe_Name": "IntegrationWorld", "Verified_Claims": [], "Knowledge_Graph": [], "Missing_Info": [], "Provisional_Conclusions": []}', [])

    with patch("app.research.researcher.run_agent", side_effect=prompt_capturer):
        # Pre-populate workspace
        with Session(unconfirmed_engine) as session:
            u_uuid = target.uuid
            session.add(NotebookEntry(universe_uuid=u_uuid, title="Pre-existing Note", summary="I was here before", kind="Observation"))
            session.commit()

        try:
            await research_single_world(target, run_id)
        except Exception as e:
            print(f"Research loop ended with: {e}")

    # Verify that the prompt contained the pre-existing note
    assert len(captured_prompts) > 0, "run_agent was never called"
    assert any("Pre-existing Note" in (p or "") for p in captured_prompts), f"Prompt did not contain Pre-existing Note. Prompts: {captured_prompts}"
    assert any("RESEARCH WORKSPACE" in (p or "") for p in captured_prompts)

