import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlmodel import Session, select
from app.db.session import engine
from app.core.agent_engine import run_agent, FetchCache
from app.agents.nodes import research_single_world, summarize_universe, db_integrator_node, consolidation_node, architecture_node
from app.db.schema import Setting

@pytest.mark.asyncio
async def test_research_single_world_success():
    run_id = "test-run"
    world_name = "TestWorld"
    
    with patch("app.agents.nodes.run_agent", new=AsyncMock()) as mock_run_agent:
        # First call: Researcher returns results
        # Second call: Critic returns SUCCESS
        mock_run_agent.side_effect = [
            ("Research findings", None),  # Researcher result
            ("SUCCESS", None)             # Critic result
        ]
        
        result = await research_single_world(world_name, run_id)
        
        assert result == "Research findings"
        assert mock_run_agent.call_count == 2

@pytest.mark.asyncio
async def test_research_single_world_max_iterations_reached():
    run_id = "test-run"
    world_name = "TestWorld"
    
    with patch("app.agents.nodes.run_agent", new=AsyncMock()) as mock_run_agent:
        # Always return failure from critic
        mock_run_agent.return_value = ("FAILURE", None)
        
        with pytest.raises(Exception, match="Max iterations reached"):
            await research_single_world(world_name, run_id)
        
        # max_iterations is 3. 
        # Each iteration does 1 researcher call and 1 critic call.
        # Total 6 calls.
        assert mock_run_agent.call_count == 6

@pytest.mark.asyncio
async def test_summarize_universe_success(ephemeral_db):
    from app.db.schema import Universe
    
    u = Universe(name="TestUniverse", summary="Initial summary")
    ephemeral_db.add(u)
    ephemeral_db.commit()
    ephemeral_db.refresh(u)
    
    from app.agents.nodes import summarize_universe
    with patch("app.agents.nodes.run_agent", new=AsyncMock()) as mock_run_agent:
        mock_run_agent.return_value = ("Summarized content", None)
        
        result = await summarize_universe(u.id, "run-sum")
        
        assert result == "Summarized content"
        
        # Verify DB update
        ephemeral_db.refresh(u)
        assert u.summary == "Summarized content"

@pytest.mark.asyncio
async def test_db_integrator_node_success(seeded_db):
    from app.agents.nodes import db_integrator_node
    ephemeral_db, u, p, r = seeded_db
    
    run_id = "test-run-db"
    research_results = [
        {"name": u.name, "summary": "Verified summary"}
    ]
    state = {
        "run_id": run_id,
        "research_results": research_results,
        "verified_worlds": [u.name]
    }
    
    with patch("app.agents.nodes.run_agent", new=AsyncMock()) as mock_run_agent:
        # Two calls: one for research integration, one for cleanup
        mock_run_agent.side_effect = [
            ("Integrated successfully", None),
            ("Cleanup successful", None)
        ]
        
        result = await db_integrator_node(state)
        
        assert result == {"active_task": "SUMMARY"}
        assert mock_run_agent.call_count == 2
        
        # Verify world is marked as explored
        ephemeral_db.refresh(u)
        assert u.is_explored is True

@pytest.mark.asyncio
async def test_consolidation_node_success(seeded_db):
    from app.agents.nodes import consolidation_node
    ephemeral_db, u, p, r = seeded_db
    
    run_id = "test-run-con"
    # We need a setting CONSOLIDATED_DATASET to exist for the node to work
    from app.db.schema import Setting
    setting = Setting(key="CONSOLIDATED_DATASET", value="some data")
    ephemeral_db.add(setting)
    ephemeral_db.commit()

    state = {
        "run_id": run_id,
        "verified_worlds": [u.name],
        "research_results": [{"name": u.name, "summary": "some summary"}]
    }
    
    with patch("app.agents.nodes.run_agent", new=AsyncMock()) as mock_run_agent:
        mock_run_agent.return_value = ("consolidated data", None)
        
        result = await consolidation_node(state)
        
        assert result == {"active_task": "ARCHITECTURE"}
        
        # Verify setting was updated
        ephemeral_db.refresh(setting)
        assert setting.value == "consolidated data"

@pytest.mark.asyncio
async def test_architecture_node_success(seeded_db):
    from app.agents.nodes import architecture_node
    ephemeral_db, u, p, r = seeded_db
    
    run_id = "test-run-arch"
    
    setting = Setting(key="CONSOLIDATED_DATASET", value="some data")
    ephemeral_db.add(setting)
    ephemeral_db.commit()

    state = {
        "run_id": run_id,
        "anomalies": [],
        "system_stable": True
    }
    
    with patch("app.agents.nodes.run_agent", new=AsyncMock()) as mock_run_agent:
        # Architect call
        # Auditor call (returning SUCCESS)
        mock_run_agent.side_effect = [
            ("Tier system definition", None),
            ("SUCCESS", None)
        ]
        
        result = await architecture_node(state)
        
        assert result["active_task"] == "EXTRAPOLATION"
        assert result["system_stable"] is True
        assert result["current_tier_system"] == "Tier system definition"
        assert mock_run_agent.call_count == 2

@pytest.mark.asyncio
async def test_extrapolation_node_success(seeded_db):
    from app.agents.nodes import extrapolation_node
    ephemeral_db, u, p, r = seeded_db
    
    run_id = "test-run-extrap"
    
    state = {
        "run_id": run_id,
        "anomalies": ["anomaly1"],
        "system_stable": True,
        "verified_worlds": [u.name]
    }
    
    with patch("app.agents.nodes.run_agent", new=AsyncMock()) as mock_run_agent:
        # First call: Speculation
        # Second call: Audit (must return VERIFIED)
        mock_run_agent.side_effect = [
            ("Theories: theory1", None), # speculation
            ("VERIFIED", None)           # audit
        ]
        
        result = await extrapolation_node(state)
        
        assert result["generated_theories"][0]["theory"] == "Theories: theory1"
        assert result["active_task"] == "FINISHED"
        assert mock_run_agent.call_count == 2

@pytest.mark.asyncio
async def test_architecture_node_tier_mapping(seeded_db):
    from app.agents.nodes import architecture_node
    ephemeral_db, u, p, r = seeded_db
    
    run_id = "test-tier-map"
    
    # Need CONSOLIDATED_DATASET for the node to proceed
    from app.db.schema import Setting
    setting = Setting(key="CONSOLIDATED_DATASET", value="some data")
    ephemeral_db.add(setting)
    ephemeral_db.commit()
    
    state = {
        "run_id": run_id,
        "anomalies": [],
        "system_stable": True,
        "verified_worlds": [u.name]
    }
    
    # First call: no persistent rubric exists yet, so this bootstraps one
    # (Architect + Logic Auditor) and then slots the world (Stability Unit).
    with patch("app.agents.nodes.run_agent", new=AsyncMock()) as mock_run_agent:
        mock_run_agent.side_effect = [
            ("Tier system definition", None),  # 1. Architect (bootstrap)
            ("SUCCESS", None),                  # 2. Logic Auditor (bootstrap audit)
            ("STATUS: STABLE\nTIER: 5", None)   # 3. Stability Unit
        ]
        
        await architecture_node(state)
        
        with Session(engine) as session:
            from app.db.schema import WorldTier, TierSystem
            wt = session.exec(select(WorldTier).where(WorldTier.universe_id == u.id)).first()
            assert wt is not None
            assert wt.tier_number == 5

            rubric = session.exec(select(TierSystem).where(TierSystem.is_active == True)).first()
            assert rubric is not None
            assert rubric.version == 1

    # Second call: the rubric from above is now persistent/active, so this
    # should SKIP the Architect/Auditor bootstrap entirely and go straight
    # to a single Stability Unit call — this is what keeps tiering
    # consistent across runs instead of redesigning the rubric each time.
    with patch("app.agents.nodes.run_agent", new=AsyncMock()) as mock_run_agent:
        mock_run_agent.side_effect = [
            ("STATUS: STABLE\nTIER: UNTIERED", None)
        ]
        
        await architecture_node(state)
        
        assert mock_run_agent.call_count == 1
        with Session(engine) as session:
            from app.db.schema import WorldTier
            wt = session.exec(select(WorldTier).where(WorldTier.universe_id == u.id)).first()
            assert wt is not None
            assert wt.tier_number == -1

    # Third call: clamp 0-10 (e.g. 15 -> 10). Still just a single Stability
    # Unit call against the same persistent rubric.
    with patch("app.agents.nodes.run_agent", new=AsyncMock()) as mock_run_agent:
        mock_run_agent.side_effect = [
            ("STATUS: STABLE\nTIER: 15", None)
        ]
        
        await architecture_node(state)
        
        assert mock_run_agent.call_count == 1
        with Session(engine) as session:
            from app.db.schema import WorldTier
            wt = session.exec(select(WorldTier).where(WorldTier.universe_id == u.id)).first()
            assert wt is not None
            assert wt.tier_number == 10


@pytest.mark.asyncio
async def test_architecture_node_amends_rubric_on_anomaly(seeded_db):
    """
    When a world doesn't fit any tier in the persistent rubric, the node
    should escalate to a minimal Rubric Steward amendment (not a full
    redesign), version the rubric, and re-slot only the anomalous world.
    """
    from app.agents.nodes import architecture_node
    from app.db.schema import Setting, TierSystem, WorldTier
    ephemeral_db, u, p, r = seeded_db

    run_id = "test-tier-amend"

    setting = Setting(key="CONSOLIDATED_DATASET", value="some data")
    ephemeral_db.add(setting)
    ephemeral_db.commit()

    # Pre-seed an existing active rubric (as if a prior run already bootstrapped one)
    existing_rubric = TierSystem(system_definition="Original rubric v1", version=1, is_active=True)
    ephemeral_db.add(existing_rubric)
    ephemeral_db.commit()
    ephemeral_db.refresh(existing_rubric)

    state = {
        "run_id": run_id,
        "anomalies": [],
        "system_stable": True,
        "verified_worlds": [u.name],
        "architecture_retries": 0
    }

    with patch("app.agents.nodes.run_agent", new=AsyncMock()) as mock_run_agent:
        mock_run_agent.side_effect = [
            ("STATUS: ANOMALY\nTIER: \nJUSTIFICATION: doesn't fit\nANOMALY_DETAILS: exceeds all tiers", None),  # 1. Stability check -> anomaly
            ("YES, amendment needed. Amended rubric v2", None),  # 2. Rubric Steward amendment
            ("SUCCESS", None),  # 3. Logic Auditor audits amendment
            ("STATUS: STABLE\nTIER: 10", None),  # 4. Re-slot the anomalous world under amended rubric
        ]

        result = await architecture_node(state)

        assert result["system_stable"] is True
        assert result["active_task"] == "EXTRAPOLATION"

        with Session(engine) as session:
            active_rubrics = session.exec(select(TierSystem).where(TierSystem.is_active == True)).all()
            assert len(active_rubrics) == 1
            assert active_rubrics[0].version == 2
            assert active_rubrics[0].parent_id == existing_rubric.id

            old = session.get(TierSystem, existing_rubric.id)
            assert old.is_active is False

            wt = session.exec(select(WorldTier).where(WorldTier.universe_id == u.id)).first()
            assert wt is not None
            assert wt.tier_number == 10
            assert wt.system_id == active_rubrics[0].id
