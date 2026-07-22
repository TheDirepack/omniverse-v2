import json
from unittest.mock import MagicMock, patch

import pytest
from sqlmodel import Session

from app.agents.prompts import get_critic_prompt, get_researcher_prompt
from app.core.agent_engine import run_agent
from app.db.schema import Universe
from app.db.session import engine
from app.services.universe_service import UniverseService


# Setup a test universe for these tests
@pytest.fixture
def test_universe():
    _uni_service = UniverseService()
    import uuid
    u_name = "Warhammer 40k"
    u_slug = f"warhammer-40k-{uuid.uuid4().hex[:8]}"
    u = Universe(name=u_name, slug=u_slug)
    with Session(engine) as session:
        session.add(u)
        session.commit()
        session.refresh(u)
        return {"name": u.name, "uuid": u.uuid, "slug": u.slug}

@pytest.mark.slow
@pytest.mark.asyncio
async def test_json_syntax_recovery(test_universe):
    """
    Scenario: Agent returns malformed JSON.
    Expectation: The system should catch the JSONDecodeError and allow for a retry.
    """
    # Use actual researcher prompt
    prompt = get_researcher_prompt(
        entity=test_universe["name"], requirements="Test JSON recovery"
    )

    responses = [
        MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(content="I am not JSON!", tool_calls=None)
                )
            ]
        ),
        MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(content='{"status": "success"}', tool_calls=None)
                )
            ]
        ),
    ]

    with patch(
        "app.core.router.router.run_model",
        side_effect=lambda **_kwargs: (
            responses.pop(0) if responses else responses[-1], "model", "key"
        ),
    ) as mock_run:
        _success, _final_ans, _history = await run_agent(
            agent_name="Researcher",
            system_prompt=prompt["system"],
            user_prompt=prompt["user"],
            step="test",
            run_id="test-json-recover",
            tools_names=[
                "webSearch", "fetchPage", "queryClaims",
                "upsertClaims", "queryNotebookClaims", "saveNotebookClaim",
                "deleteNotebookClaim"
            ],
            submit_tool_name="submit",
            max_retries=1
        )
        assert mock_run.call_count >= 1


@pytest.mark.slow
@pytest.mark.asyncio
async def test_schema_violation_recovery(_test_universe):
    """
    Scenario: Agent returns valid JSON but violates the RESEARCH_SCHEMA.
    Expectation: The Critic (LogicAuditor) should identify the violation and
    request revision.
    """
    # Bad data: missing 'Verified_Claims'
    bad_data = '{"Universe_Name": "Test", "Knowledge_Graph": []}'

    critic_prompt = get_critic_prompt(
        data=bad_data, criteria="Strictly follow RESEARCH_SCHEMA"
    )
    _success, res, history = await run_agent(
        agent_name="Logic Auditor",
        system_prompt=critic_prompt["system"],
        user_prompt=critic_prompt["user"],
        step="test-schema",
        run_id="test-schema-violation",
        tools_names=[
            "fetchPage", "queryClaims",
            "queryNotebookClaims"
        ],
        submit_tool_name="submit_audit",
        max_turns=10
    )

    # The agent might return the answer in 'res' (if it submitted) or in
    # the last message of 'history'
    final_ans = res or (history[-1]["content"] if history[-1].get("content") else "")

    assert "REVISION_REQUIRED" in final_ans.upper()
    assert "Schema" in final_ans or "missing" in final_ans.lower()

@pytest.mark.slow
@pytest.mark.asyncio
async def test_headcanon_rejection(_test_universe):
    """
    Scenario: Agent provides ungrounded claims (no references).
    Expectation: LogicAuditor flags it as Revision_Required.
    """
    # Data with a claim that has no reference
    headcanon_data = json.dumps({
        "Verified_Claims": [
            {
                "subject": "Hero",
                "predicate": "is",
                "object_val": "the strongest",
                "reference": None,
            }
        ]
    })

    critic_prompt = get_critic_prompt(
        data=headcanon_data, criteria="Strict grounding required"
    )
    _success, res, history = await run_agent(
        agent_name="Logic Auditor",
        system_prompt=critic_prompt["system"],
        user_prompt=critic_prompt["user"],
        step="test-headcanon",
        run_id="test-headcanon",
        tools_names=[
            "fetchPage", "queryClaims",
            "queryNotebookClaims"
        ],
        submit_tool_name="submit_audit",
        max_turns=10
    )

    final_ans = res or (history[-1]["content"] if history[-1].get("content") else "")

    assert "REVISION_REQUIRED" in final_ans.upper()
    assert "reference" in final_ans.lower() or "grounding" in final_ans.lower()

@pytest.mark.slow
@pytest.mark.asyncio
async def test_power_scaling_rejection(_test_universe):
    """
    Scenario: Agent provides relative strength comparisons (Power-Scaling).
    Expectation: LogicAuditor flags it as a violation of core directives.
    """
    scaling_data = json.dumps({
        "Verified_Claims": [
            {
                "subject": "Char A",
                "predicate": "is stronger than",
                "object_val": "Char B",
                "reference": "wiki:1",
            }
        ]
    })

    critic_prompt = get_critic_prompt(
        data=scaling_data, criteria="No power-scaling allowed"
    )
    _success, res, history = await run_agent(
        agent_name="Logic Auditor",
        system_prompt=critic_prompt["system"],
        user_prompt=critic_prompt["user"],
        step="test-scaling",
        run_id="test-scaling",
        tools_names=[
            "fetchPage", "queryClaims",
            "queryNotebookClaims"
        ],
        submit_tool_name="submit_audit",
        max_turns=10
    )

    final_ans = res or (history[-1]["content"] if history[-1].get("content") else "")

    assert "REVISION_REQUIRED" in final_ans.upper()
    assert "scaling" in final_ans.lower() or "comparison" in final_ans.lower()

@pytest.mark.slow
@pytest.mark.asyncio
async def test_premature_submission_blocking(test_universe):
    """
    Scenario: Agent calls submit tool before min_turns.
    Expectation: Agent engine rejects the call and tells the agent to continue.
    """
    prompt = get_researcher_prompt(
        entity=test_universe["name"], requirements="Fast submission test"
    )

    # Mock the model to immediately call the submit tool
    mock_message = MagicMock()
    mock_message.content = None
    tc = MagicMock()
    tc.id = "call_1"
    tc.type = "function"
    tc.function = MagicMock()
    tc.function.name = "submit"
    tc.function.arguments = '{"dataset": "{}"}'
    mock_message.tool_calls = [tc]

    with patch("app.core.router.router.run_model") as mock_run:
        mock_run.return_value = (
            MagicMock(choices=[MagicMock(message=mock_message)]),
            "model",
            "key",
        )

        _success, _final_ans, _history = await run_agent(
            agent_name="Researcher",
            system_prompt=prompt["system"],
            user_prompt=prompt["user"],
            step="test",
            run_id="test-premature",
            tools_names=[
                "webSearch", "fetchPage", "queryClaims",
                "upsertClaims", "queryNotebookClaims", "saveNotebookClaim",
                "deleteNotebookClaim"
            ],
            submit_tool_name="submit",
            min_turns=5
        )

        # Check that at least one tool response in history contains
        # the rejection message
        rejections = [
            m["content"]
            for m in _history
            if m["role"] == "tool"
            and "Minimum research turns not yet reached" in m["content"]
        ]
        assert len(rejections) > 0, (
            "Expected a 'Minimum research turns' rejection in history"
        )

