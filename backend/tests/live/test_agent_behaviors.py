import json

import pytest
from sqlmodel import Session

from app.agents.prompts import get_critic_prompt, get_extrapolation_prompt
from app.core.agent_engine import run_agent
from app.db.schema import Universe
from app.db.session import engine
from app.research.researcher import research_single_world
from app.services.universe_service import UniverseService

try:
    import tests.provider_config
except ImportError:
    pytest.importorskip("tests.provider_config")

@pytest.mark.slow
@pytest.mark.asyncio
async def test_researcher_smoke_end_to_end():
    """
    Symmetry Test: Run researcher on a real page and verify JSON round-trips.
    """
    _uni_service = UniverseService()
    # Use a real, stable wiki page for testing
    u = Universe(name="Test World Live", slug="test-world-live")
    with Session(engine) as session:
        session.add(u)
        session.commit()
        session.refresh(u)

    # This tests the whole loop: run_agent -> tools -> validator
    result = await research_single_world(u.uuid, "live-run")

    assert "name" in result
    assert "summary" in result
    # Verify it's valid JSON and matches schema
    import json
    parsed = json.loads(result["summary"])
    assert "Verified_Claims" in parsed
    assert "Knowledge_Graph" in parsed

@pytest.mark.slow
@pytest.mark.asyncio
async def test_critic_judgment_depth():
    """
    Behavioral Test: Verify Critic discriminates between shallow and deep research.
    """
    shallow_data = (
        '{"Verified_Claims": [{"subject": "Hero", "predicate": "is", '
        '"object": "strong", "reference": "wiki:1"}]}'
    )
    deep_data = (
        '{"Verified_Claims": [{"subject": "Hero", "predicate": "has_strength", '
        '"object": "100 tons", "reference": "wiki:1", '
        '"attributes": {"peak": "120 tons"}}]}'
    )

    # We test the actual prompt + real model judgment
    critic_prompt = get_critic_prompt(
        data=shallow_data, criteria="Technical specifications required"
    )
    res_shallow, _, _ = await run_agent(
        agent_name="Logic Auditor",
        system_prompt=critic_prompt["system"],
        user_prompt=critic_prompt["user"],
        step="Audit Depth",
        run_id="test-depth-1",
        tools_names=[],
        submit_tool_name="submit_audit"
    )

    critic_prompt_deep = get_critic_prompt(
        data=deep_data, criteria="Technical specifications required"
    )
    res_deep, _, _ = await run_agent(
        agent_name="Logic Auditor",
        system_prompt=critic_prompt_deep["system"],
        user_prompt=critic_prompt_deep["user"],
        step="Audit Depth",
        run_id="test-depth-2",
        tools_names=[],
        submit_tool_name="submit_audit"
    )

    # Assert deeper data likely SUCCESS, shallow REVISION_REQUIRED
    assert "REVISION_REQUIRED" in res_shallow.upper()
    assert "SUCCESS" in res_deep.upper()

@pytest.mark.slow
@pytest.mark.asyncio
async def test_theorist_no_new_powers():
    """
    Behavioral Test: Ensure Theorist does not invent powers from sparse data.
    """
    sparse_data = (
        '{"Verified_Claims": [{"subject": "Char", "predicate": "is", '
        '"object": "human"}]}'
    )
    comparison = '{"Verified_Claims": []}'

    prompt = get_extrapolation_prompt("Test Char", sparse_data, comparison)

    _success, theory, _ = await run_agent(
        agent_name="Ontological Theorist",
        system_prompt=prompt["system"],
        user_prompt=prompt["user"],
        step="Theory Check",
        run_id="test-no-powers",
        tools_names=[],
        submit_tool_name="submit_theory"
    )

    # Assert no "super" or "magic" or "power" keywords appear if not in input
    # (This is a heuristic check for prompt compliance)
    forbidden = ["superpower", "magical", "omnipotent", "god-like"]
    for word in forbidden:
        assert word not in theory.lower(), f"Theorist invented power: {word}"

@pytest.mark.slow
@pytest.mark.asyncio
async def test_db_architect_contradiction_handling():
    """
    Behavioral Test: Verify Architect handles contradictions as specified.
    """
    # Submit two conflicting claims
    data = {
        "items": [
            {"subject": "X", "predicate": "is", "object_val": "A"},
            {"subject": "X", "predicate": "is", "object_val": "B"},
        ]
    }

    # We use a real agent session to see if it identifies the contradiction in its plan
    from app.agents.prompts import get_db_agent_prompt
    prompt = get_db_agent_prompt()

    # We mock the actual DB part but use a real LLM to see if it plans a contradiction
    # Actually, just testing the tool logic is enough for the DB part,
    # but the prompt's "Intelligent Merging" is what we want to test.
    
    # For a behavioral test, we'd run the agent and check its reasoning.
    _success, res, _ = await run_agent(
        agent_name="DB Architect",
        system_prompt=prompt["system"],
        user_prompt=f"Verified Data: {json.dumps(data)}",
        step="Contradiction Check",
        run_id="test-contradiction",
        tools_names=["upsertClaims"],
        submit_tool_name="submit_integration"
    )

    assert "contradiction" in res.lower() or "duplicate" in res.lower()
