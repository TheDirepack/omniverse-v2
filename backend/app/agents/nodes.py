import json
import asyncio
import re
from typing import List, Dict, Any
from sqlmodel import Session, select
from app.db.session import engine
from app.db.schema import Universe, Trait, TierSystem, WorldTier, Anomaly, Theory, ExecutionState, Setting
from app.core.agent_engine import run_agent, FetchCache
from app.core.state import is_aborted
from app.core.context import set_current_universe
from app.agents.state import OmniverseState
from app.agents.prompts import (
    get_extraction_prompt,
    get_critic_prompt,
    get_synthesis_prompt,
    get_architect_prompt,
    get_stability_prompt,
    get_extrapolation_prompt,
    get_theory_auditor_prompt,
    get_summary_prompt,
    get_cleanup_prompt
)

def log_transition(run_id: str, node_name: str, thought: str, status: str, state: dict):
    with Session(engine) as session:
        # Save snapshot of state
        snapshot_str = json.dumps({k: v for k, v in state.items() if k != "run_id"}, default=str)
        log_entry = ExecutionState(
            run_id=run_id,
            node_name=node_name,
            thought=thought,
            status=status,
            state_snapshot=snapshot_str
        )
        session.add(log_entry)
        session.commit()

def check_abort(run_id: str):
    if run_id in ABORTED_RUNS:
        raise RuntimeError(f"Run {run_id} was aborted by user.")

def audit_success(audit_result: str) -> bool:
    upper = audit_result.upper()
    if "REVISION_REQUIRED" in upper or "REVISION REQUIRED" in upper:
        return False
    return "SUCCESS" in upper or "VERIFIED" in upper


async def research_single_world(world_name: str, run_id: str, focus: str | None = None, fetch_cache: FetchCache | None = None) -> Dict[str, Any]:
    """Researches and verifies a single world using an agentic tool loop with a discovery flow."""
    await is_aborted(run_id)
    stage_label = f"{world_name} focused on {focus}" if focus else world_name
    set_current_universe(world_name)
    log_transition(run_id, "Research Unit", f"Initiating agentic research for world: {stage_label}", "IN_PROGRESS", {})

    # Discovery flow prompt
    system_prompt = f"""### ROLE
Wiki Scout & Archivist. Your goal is to build a comprehensive canonical dataset for the universe.
 
PROCESS
1. KNOWLEDGE CHECK: Start by calling `queryTraits` and `queryUnconfirmedTraits` to see what is already known about {world_name}. Avoid duplicating effort.
2. DISCOVERY: Use `webSearch` to discover wikis and authoritative sources.
   - You can specify the `engine` (google, duckduckgo, brave).
   - You can specify a `site_filter` to target specific domains (e.g. 'fandom.com').
3. DOMAIN FOCUS: Once you've identified the canonical wiki, prefer `fetchPage` and targeted `webSearch` queries scoped to that domain.
4. DRILL DOWN: Follow internal links from fetched pages to sub-articles if summaries are incomplete.
5. VERIFY: Cross-check any claim that seems central to power-tiering against at least one other source before citing it.
 
OUTPUT
Call `submit_research` only when you have a complete picture. 
Refer to the RESEARCH_SCHEMA for the structure.
Include precise references as "url: section/line".
"""

    if focus:
        system_prompt += f"\n\nFOCUSED TARGET: {focus}. Prove/disprove existence, extract mechanisms, and provide a Focused Verdict (VERIFIED/DISPROVED/INCONCLUSIVE)."

    user_prompt = f"Perform deep research on {world_name}."
    
    # Critique Loop
    feedback_history = []
    max_iterations = 3
    last_result = ""

    try:
        for i in range(max_iterations):
            current_system_prompt = system_prompt
            if feedback_history:
                current_system_prompt += f"\n\nPREVIOUS FEEDBACK TO ADDRESS:\n{chr(10).join(feedback_history)}"
            
            result, _ = await run_agent(
                agent_name="Researcher",
                system_prompt=current_system_prompt,
                user_prompt=user_prompt,
                step=f"Research (Attempt {i+1})",
                run_id=run_id,
                tools_names=["webSearch", "fetchPage", "queryTraits", "queryUnconfirmedTraits"],
                submit_tool_name="submit_research",
                fetch_cache=fetch_cache
            )

            last_result = result
            
            # Critic Agent
            from app.agents.prompts import get_critic_prompt
            critic_prompt = get_critic_prompt(data=result, criteria=system_prompt)
            
            critique, _ = await run_agent(
                agent_name="Logic Auditor",
                system_prompt=critic_prompt["system"],
                user_prompt=critic_prompt["user"],
                step=f"Audit (Attempt {i+1})",
                run_id=run_id,
                tools_names=["webSearch", "fetchPage", "queryTraits", "queryUnconfirmedTraits"],
                submit_tool_name="submit_audit",
                fetch_cache=fetch_cache
            )
            
            if "SUCCESS" in critique.upper():
                return {"name": world_name, "summary": result}
            
            feedback_history.append(f"Attempt {i+1} failed: {critique}")
            
        raise Exception(f"Max iterations reached for {world_name}. Failed to achieve valid research.")
        
    except Exception as e:
        log_transition(run_id, "Research Unit", f"Agent failed for {world_name}: {str(e)}", "FAILED", {})
        raise e


async def summarize_universe(universe_id: int, run_id: str) -> str:
    """Agent that creates a human-readable summary from structured DB data."""
    with Session(engine) as session:
        universe = session.get(Universe, universe_id)
        if not universe:
            return "Universe not found."

        set_current_universe(universe.name)

        # Collect all traits for this universe to provide full context
        traits = session.exec(select(Trait).where(Trait.universe_id == universe_id)).all()
        traits_text = "\n".join([f"- {t.name}: {t.value}" for t in traits])
        
        # We pull the raw_data field (populated by DB Architect)
        raw_data = universe.raw_data or "No structured data available."
        
        structured_context = f"Structured JSON:\n{raw_data}\n\nExtracted Traits:\n{traits_text}"
        
        prompt = get_summary_prompt(universe.name, structured_context)
        
        summary, _ = await run_agent(
            agent_name="Universe Chronicler",
            system_prompt=prompt["system"],
            user_prompt=prompt["user"],
            step="Summarization",
            run_id=run_id,
            tools_names=[],
            submit_tool_name="submit_summary"
        )
        
        # Update ONLY the summary field
        universe.summary = summary
        session.add(universe)
        session.commit()
        
        return summary

async def summary_node(state: OmniverseState) -> Dict[str, Any]:
    """LangGraph node to summarize all verified worlds."""
    run_id = state.get("run_id")
    verified_worlds = state.get("verified_worlds", [])
    
    log_transition(run_id, "Summarizer", f"Creating polished summaries for {len(verified_worlds)} worlds", "IN_PROGRESS", state)
    
    with Session(engine) as session:
        universes = session.exec(select(Universe).where(Universe.name.in_(verified_worlds))).all()
        universe_ids = [u.id for u in universes]
    
    # Summarize in parallel
    tasks = [summarize_universe(uid, run_id) for uid in universe_ids]
    await asyncio.gather(*tasks)
    
    log_transition(run_id, "Summarizer", "All summaries generated successfully.", "COMPLETED", state)
    return {"active_task": "CONSOLIDATION"}


async def db_integrator_node(state: OmniverseState) -> Dict[str, Any]:
    """Agent that integrates verified research into the database, then cleans up unconfirmed staging."""
    run_id = state.get("run_id")
    research_results = state.get("research_results", [])
    
    log_transition(run_id, "DB Integrator", f"Integrating data for {len(research_results)} worlds", "IN_PROGRESS", state)
    
    for result in research_results:
        world_name = result["name"]
        verified_data = result["summary"]
        
        # Phase 1: Write confirmed data to main database
        from app.agents.prompts import get_db_agent_prompt
        prompt = get_db_agent_prompt()

        set_current_universe(world_name)

        await run_agent(
            agent_name="DB Architect",
            system_prompt=prompt["system"],
            user_prompt=f"Universe: {world_name}\n\nVerified Research Data:\n{verified_data}",
            step=f"Integrate {world_name}",
            run_id=run_id,
            tools_names=["queryTraits", "upsertTrait"],
            submit_tool_name="submit_integration"
        )
        
        # Phase 2: Clean up unconfirmed staging — remove only promoted traits
        cleanup_prompt = get_cleanup_prompt()

        await run_agent(
            agent_name="DB Architect",
            system_prompt=cleanup_prompt["system"],
            user_prompt=f"Clean up unconfirmed staging for {world_name}",
            step=f"Cleanup {world_name}",
            run_id=run_id,
            tools_names=["queryTraits", "queryUnconfirmedTraits", "deleteUnconfirmedTrait"],
            submit_tool_name="submit_cleanup"
        )
        
        # Deterministically mark as explored after integration
        with Session(engine) as session:
            universe = session.exec(select(Universe).where(Universe.name == world_name)).first()
            if universe:
                universe.is_explored = True
                session.add(universe)
                session.commit()
    
    log_transition(run_id, "DB Integrator", "All research integrated and staging cleaned.", "COMPLETED", state)
    return {"active_task": "SUMMARY"}


async def research_node(state: OmniverseState) -> Dict[str, Any]:
    """LangGraph node to execute parallel research for all target worlds with batching to avoid overload."""
    run_id = state.get("run_id")
    await is_aborted(run_id)
    target_worlds = state.get("target_worlds", [])
    
    log_transition(run_id, "Manager", f"Starting parallel research phase for {len(target_worlds)} worlds", "IN_PROGRESS", state)
    
    successful_results = []
    errors = []
    verified_worlds = []
    
    cache = FetchCache()
    batch_size = 5
    for i in range(0, len(target_worlds), batch_size):
        batch = target_worlds[i:i + batch_size]
        tasks = [research_single_world(world, run_id, fetch_cache=cache) for world in batch]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for r in batch_results:
            if isinstance(r, Exception):
                errors.append(str(r))
            else:
                successful_results.append(r)
                verified_worlds.append(r["name"])
    
    log_transition(run_id, "Manager", "Completed parallel research phase", "COMPLETED", state)
    
    return {
        "research_results": successful_results,
        "verified_worlds": verified_worlds,
        "errors": errors,
        "active_task": "CONSOLIDATION"
    }


async def manager_node(state: OmniverseState) -> Dict[str, Any]:
    run_id = state.get("run_id")
    log_transition(run_id, "Manager", "Routing pipeline state", "COMPLETED", state)
    return {"active_task": state.get("active_task", "RESEARCH")}


async def consolidation_node(state: OmniverseState) -> Dict[str, Any]:
    """LangGraph node to synthesize multiple research results into a unified dataset."""
    run_id = state.get("run_id")
    await is_aborted(run_id)
    results = state.get("research_results", [])
    
    log_transition(run_id, "Consolidator", "Starting synthesis of target worlds", "IN_PROGRESS", state)
    
    with Session(engine) as session:
        verified_world_names = state.get("verified_worlds", [])
        universes = session.exec(select(Universe).where(Universe.name.in_(verified_world_names))).all()
        reports = [f"World: {u.name}\nSummary: {u.summary}\nStructured Data: {u.raw_data}" for u in universes]
    
    synthesis_prompts = get_synthesis_prompt(reports)
    
    consolidated_dataset, _ = await run_agent(
        agent_name="Consolidator",
        system_prompt=synthesis_prompts["system"],
        user_prompt=synthesis_prompts["user"],
        step="Synthesis",
        run_id=run_id,
        tools_names=[],
        submit_tool_name="submit_synthesis"
    )
    
    log_transition(run_id, "Consolidator", "Completed synthesis of world datasets", "COMPLETED", state)
    
    with Session(engine) as session:
        setting = session.get(Setting, "CONSOLIDATED_DATASET")
        if not setting:
            setting = Setting(key="CONSOLIDATED_DATASET", value=None)
        setting.value = consolidated_dataset
        session.add(setting)
        session.commit()
        
    return {
        "active_task": "ARCHITECTURE"
    }


async def architecture_node(state: OmniverseState) -> Dict[str, Any]:
    """LangGraph node to design and test the 11-tier hierarchy system with an adversarial critic."""
    run_id = state.get("run_id")
    await is_aborted(run_id)
    anomalies = state.get("anomalies", [])
    
    log_transition(run_id, "Tier Architect", "Starting 11-tier architecture design", "IN_PROGRESS", state)
    
    dataset = ""
    with Session(engine) as session:
        setting = session.get(Setting, "CONSOLIDATED_DATASET")
        if setting:
            dataset = setting.value
            
    architect_prompts = get_architect_prompt(dataset, anomalies)
    cache = FetchCache()
    tier_system_definition, _ = await run_agent(
        agent_name="Tier Architect",
        system_prompt=architect_prompts["system"],
        user_prompt=architect_prompts["user"],
        step="Architecture",
        run_id=run_id,
        tools_names=[],
        submit_tool_name="submit_architecture"
    )
    
    # Adversarial Critic Loop
    critic_system_prompt = """### ROLE
Strict Logic Auditor. Your goal is to find flaws in the proposed Tier System.

PROCESS
1. Analyze the provided Tier System and the consolidated dataset.
2. Use `fetchPage` and `webSearch` to verify specific threshold claims.
3. Look for semantic overlaps, gaps in scaling, or contradictions with canonical data.
4. Specifically check if the relative progression (Tier 11 lowest, Tier 1 highest) is logically sound.

OUTPUT
Call `submit_audit` with a STATUS (SUCCESS/REVISION_REQUIRED) and a detailed Correction Queue.
"""
    critic_user_prompt = f"Proposed Tier System:\n{tier_system_definition}\n\nDataset:\n{dataset}"
    
    audit_result, _ = await run_agent(
        agent_name="Logic Auditor",
        system_prompt=critic_system_prompt,
        user_prompt=critic_user_prompt,
        step="Audit",
        run_id=run_id,
        tools_names=["webSearch", "fetchPage"],
        submit_tool_name="submit_audit",
        fetch_cache=cache
    )
    
    is_success = audit_success(audit_result)
    log_transition(run_id, "Logic Auditor", f"Audited Designed Tier System. Status: {'SUCCESS' if is_success else 'REVISION_REQUIRED'}", "IN_PROGRESS", state)
    
    if not is_success:
        retries = state.get("architecture_retries", 0) + 1
        if retries >= 3:
            log_transition(run_id, "Manager", "Max re-architecture attempts reached. Forcing extrapolation with current best effort.", "IN_PROGRESS", state)
            return {
                "anomalies": [f"System Design Error: {audit_result} (Max retries reached)"],
                "system_stable": False,
                "active_task": "EXTRAPOLATION",
                "architecture_retries": retries
            }
        
        return {
            "anomalies": [f"System Design Error: {audit_result}"],
            "system_stable": False,
            "active_task": "RE_ARCHITECTURE",
            "architecture_retries": retries
        }
        
    system_id = None
    with Session(engine) as session:
        tier_system = TierSystem(system_definition=tier_system_definition)
        session.add(tier_system)
        session.commit()
        session.refresh(tier_system)
        system_id = tier_system.id
        
    log_transition(run_id, "Stability Unit", "Verifying stability and mapping worlds to tiers", "IN_PROGRESS", state)
    
    world_anomalies = []
    world_tier_mappings = []
    
    with Session(engine) as session:
        verified_world_names = state.get("verified_worlds", [])
        universes = session.exec(select(Universe).where(Universe.name.in_(verified_world_names))).all()
        for universe in universes:
            stability_prompts = get_stability_prompt(universe.summary or "", tier_system_definition)
            
            # Adversarial stability check
            stability_result, _ = await run_agent(
                agent_name="Stability Unit",
                system_prompt=stability_prompts["system"],
                user_prompt=stability_prompts["user"],
                step="Stability Check",
                run_id=run_id,
                tools_names=["webSearch", "fetchPage"],
                submit_tool_name="submit_stability",
                fetch_cache=cache
            )
            
            is_stable = "STATUS: STABLE" in stability_result.upper()
            
            tier_num = 11
            tier_match = re.search(r"TIER:\s*(\d+)", stability_result, re.IGNORECASE)
            if tier_match:
                try:
                    val = int(tier_match.group(1))
                    tier_num = max(1, min(11, val))
                except:
                    pass
                     
            if not is_stable:
                world_anomalies.append(f"{universe.name}: Anomaly detected during tiering: {stability_result}")
                db_anomaly = Anomaly(universe_id=universe.id, description=stability_result)
                session.add(db_anomaly)
                session.commit()
            else:
                world_tier_mappings.append({
                    "universe_id": universe.id,
                    "tier": tier_num,
                    "justification": stability_result
                })
                
        if len(world_anomalies) > 0:
            retries = state.get("architecture_retries", 0) + 1
            log_transition(run_id, "Manager", f"Detected {len(world_anomalies)} anomalies. Instability triggered re-architecture.", "IN_PROGRESS", state)
            return {
                "anomalies": world_anomalies,
                "system_stable": False,
                "active_task": "RE_ARCHITECTURE",
                "architecture_retries": retries
            }
            
        for wt in world_tier_mappings:
            session.exec(WorldTier.__table__.delete().where(WorldTier.universe_id == wt["universe_id"]))
            new_wt = WorldTier(
                universe_id=wt["universe_id"],
                system_id=system_id,
                tier_number=wt["tier"],
                justification=wt["justification"]
            )
            session.add(new_wt)
        session.commit()
        
    log_transition(run_id, "Manager", "Completed relative tier list architecture phase successfully.", "COMPLETED", state)
    
    return {
        "current_tier_system": tier_system_definition,
        "system_stable": True,
        "active_task": "EXTRAPOLATION"
    }


async def extrapolation_node(state: OmniverseState) -> Dict[str, Any]:
    """LangGraph node to generate and audit speculative scaling theories."""
    run_id = state.get("run_id")
    await is_aborted(run_id)
    log_transition(run_id, "Ontological Theorist", "Starting theoretical scaling projections", "IN_PROGRESS", state)
    
    generated_theories = []
    
    with Session(engine) as session:
        verified_world_names = state.get("verified_worlds", [])
        universes = session.exec(select(Universe).where(Universe.name.in_(verified_world_names))).all()
        for universe in universes:
            set_current_universe(universe.name)
            other_universes = session.exec(select(Universe).where(Universe.id != universe.id)).all()
            comparison_texts = [f"World: {ou.name}\nFeatures: {ou.summary}" for ou in other_universes]
            comparison_context = "\n\n---\n\n".join(comparison_texts)

            theory_prompt = get_extrapolation_prompt(universe.name, universe.summary or "", comparison_context)
            
            speculation, _ = await run_agent(
                agent_name="Ontological Theorist",
                system_prompt=theory_prompt["system"],
                user_prompt=theory_prompt["user"],
                step="Extrapolation",
                run_id=run_id,
                tools_names=["webSearch", "fetchPage"],
                submit_tool_name="submit_theory"
            )
            
            audit_prompt = get_theory_auditor_prompt(speculation)
            
            audit_result, _ = await run_agent(
                agent_name="Theoretical Auditor",
                system_prompt=audit_prompt["system"],
                user_prompt=audit_prompt["user"],
                step="Theory Audit",
                run_id=run_id,
                tools_names=["webSearch", "fetchPage"],
                submit_tool_name="submit_audit"
            )
            
            is_verified = audit_result.strip().upper().startswith("VERIFIED")
            if not is_verified:
                log_transition(run_id, "Theoretical Auditor", f"Rejected theory for {universe.name}", "REVISION_REQUIRED", {"audit": audit_result})
                continue
            
            session.exec(Theory.__table__.delete().where(Theory.universe_id == universe.id))
            session.commit()
            
            db_theory = Theory(
                universe_id=universe.id,
                theory_text=speculation,
                auditor_feedback=audit_result
            )
            session.add(db_theory)
            session.commit()
            
            generated_theories.append({
                "universe_name": universe.name,
                "theory": speculation,
                "feedback": audit_result
            })
            
    log_transition(run_id, "Ontological Theorist", "Completed interaction theories generation successfully", "COMPLETED", state)
    
    return {
        "generated_theories": generated_theories,
        "active_task": "FINISHED"
    }
