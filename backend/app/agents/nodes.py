import json
import asyncio
import re
from typing import List, Dict, Any, Optional
from sqlmodel import Session, select
from app.db.session import engine
from app.db.extrapolation_session import engine as extrapolation_engine
from app.db.schema import Universe, Trait, TierSystem, WorldTier, Anomaly, ExecutionState, Setting
from app.db.extrapolation_schema import Theory
from app.core.agent_engine import run_agent, FetchCache
from app.core.state import is_aborted, ABORTED_RUNS
from app.core.context import set_current_universe
from app.agents.state import OmniverseState
from app.agents.prompts import (
    get_researcher_prompt,
    get_critic_prompt,
    get_synthesis_prompt,
    get_architect_prompt,
    get_rubric_amendment_prompt,
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
    """
    Strictly validates the audit result. Prioritizes the structured `Verification_Status` field.
    Falls back to a more precise boundary check for non-JSON outputs to avoid false positives
    from explanatory text.
    """
    try:
        parsed = json.loads(audit_result)
        status = str(parsed.get("Verification_Status", "")).strip().upper()
        if status:
            return status == "SUCCESS"
    except (json.JSONDecodeError, AttributeError, TypeError):
        pass

    upper = audit_result.upper()
    # Check for explicit status markers at the start or on their own lines
    if "REVISION_REQUIRED" in upper:
        return False
    
    # Only return True if SUCCESS/VERIFIED is the primary signal, 
    # avoiding matches inside "previously verified" or "unsuccessful"
    lines = upper.splitlines()
    for line in lines:
        line = line.strip()
        if line == "SUCCESS" or line == "VERIFIED" or line.startswith("STATUS: SUCCESS") or line.startswith("STATUS: VERIFIED"):
            return True
            
    return False


def clear_tier(universe_id: int, session: Session):
    session.exec(WorldTier.__table__.delete().where(WorldTier.universe_id == universe_id))

async def research_single_world(world_name: str, run_id: str, focus: str | None = None, fetch_cache: FetchCache | None = None) -> Dict[str, Any]:
    """Researches and verifies a single world using an incremental Patch & Refine loop."""
    if await is_aborted(run_id):
        raise RuntimeError(f"Run {run_id} was aborted by user.")
    
    with Session(engine) as session:
        universe = session.exec(select(Universe).where(Universe.name == world_name)).first()
        if universe:
            clear_tier(universe.id, session)
            session.commit()
    
    stage_label = f"{world_name} focused on {focus}" if focus else world_name
    set_current_universe(world_name)
    log_transition(run_id, "Research Unit", f"Initiating incremental research for world: {stage_label}", "IN_PROGRESS", {})

    researcher_tools = ["webSearch", "fetchPage", "compareSourceFreshness", "queryTraits", "queryUnconfirmedTraits", "saveUnconfirmedTrait"]
    auditor_tools = ["webSearch", "fetchPage", "compareSourceFreshness", "queryTraits", "queryUnconfirmedTraits"]

    feedback_history = [] # List of dicts: {"attempt": i, "corrections": [...], "status": "RESOLVED"|"OUTSTANDING"}
    max_iterations = 3
    last_result = None
    history = None

    try:
        for i in range(max_iterations):
            # 1. Extract actionable leads from previous result to prioritize in the prompt
            research_queue = ""
            if last_result:
                try:
                    data = json.loads(last_result)
                    leads = [f"- {l['Lead']} ({l.get('Expected_Value', 'Unknown')})" for l in data.get("Knowledge_Graph", [])]
                    missing = [f"- {m}" for m in data.get("Missing_Info", [])]
                    if leads or missing:
                        research_queue = "\n".join(["PRIORITY LEADS:"] + leads + ["\nUNRESOLVED GAPS:"] + missing)
                except:
                    pass

            # 2. Build the feedback summary (Resolved vs Outstanding)
            outstanding = []
            resolved = []
            for entry in feedback_history:
                for corr in entry["corrections"]:
                    if entry["status"] == "RESOLVED":
                        resolved.append(f"✓ {corr['Issue']}")
                    else:
                        outstanding.append(f"• {corr['Issue']} -> Fix: {corr['Required_Fix']}")
            
            feedback_summary = "\n".join([
                "RESOLVED:", *resolved, 
                "\nOUTSTANDING:", *outstanding
            ]) if (resolved or outstanding) else "None"

            # 3. Generate Prompts
            researcher_prompt = get_researcher_prompt(
                entity=world_name,
                requirements="Collect comprehensive canonical wiki data.",
                focus=focus,
                previous_dataset=last_result,
                outstanding_corrections=feedback_summary
            )
            
            # Append the research queue to the user prompt to make it actionable
            user_prompt = researcher_prompt["user"]
            if research_queue:
                user_prompt += f"\n\n{research_queue}\n\nPrioritize these leads in your tool use."

            # 4. Execution
            result, turn_history = await run_agent(
                agent_name="Researcher",
                system_prompt=researcher_prompt["system"],
                user_prompt=user_prompt,
                step=f"Research (Attempt {i+1})",
                run_id=run_id,
                tools_names=researcher_tools,
                submit_tool_name="submit_research",
                fetch_cache=fetch_cache,
                history=history
            )
            history = turn_history
            last_result = result
            
            # 5. Incremental Audit
            critic_prompt = get_critic_prompt(
                data=result, 
                criteria=researcher_prompt["system"], 
                previous_corrections=feedback_summary,
                is_final_attempt=(i == max_iterations - 1)
            )
            
            critique, _ = await run_agent(
                agent_name="Logic Auditor",
                system_prompt=critic_prompt["system"],
                user_prompt=critic_prompt["user"],
                step=f"Audit (Attempt {i+1})",
                run_id=run_id,
                tools_names=auditor_tools,
                submit_tool_name="submit_audit",
                fetch_cache=fetch_cache
            )
            
            if audit_success(critique):
                return {"name": world_name, "summary": result, "status": "VERIFIED"}
            
            # Parse corrections to track them
            try:
                parsed_critique = json.loads(critique)
                corrections = parsed_critique.get("Correction_Queue", [])
                
                # If this was the final attempt and we have a sifted dataset, return it as PARTIAL
                if i == max_iterations - 1 and "Sifted_Dataset" in parsed_critique:
                    sifted_data = parsed_critique["Sifted_Dataset"]
                    # Ensure it's a string for the summary field
                    if isinstance(sifted_data, (dict, list)):
                        sifted_data = json.dumps(sifted_data)
                    return {"name": world_name, "summary": sifted_data, "status": "PARTIAL"}
                    
            except:
                corrections = [{"Issue": critique, "Required_Fix": "General revision required"}]
            
            feedback_history.append({"attempt": i+1, "corrections": corrections, "status": "OUTSTANDING"})
            
        # Fallback if no Sifted_Dataset was provided on final attempt
        return {"name": world_name, "summary": last_result, "status": "PARTIAL"}
        
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
    
    # If focused search, go straight to tiering (architecture)
    if state.get("is_focused_search"):
        return {"active_task": "ARCHITECTURE"}
        
    return {"active_task": "CONSOLIDATION"}


async def db_integrator_node(state: OmniverseState) -> Dict[str, Any]:
    """Agent that integrates verified research into the database, then cleans up unconfirmed staging in a stateful session."""
    run_id = state.get("run_id")
    research_results = state.get("research_results", [])
    
    log_transition(run_id, "DB Integrator", f"Integrating data for {len(research_results)} worlds", "IN_PROGRESS", state)
    
    for result in research_results:
        world_name = result["name"]
        verified_data = result["summary"]
        status = result.get("status", "VERIFIED")
        
        # Phase 1: Write confirmed data to main database
        from app.agents.prompts import get_db_agent_prompt, get_cleanup_prompt
        prompt = get_db_agent_prompt()
        
        # Append status to the prompt so the DB Architect knows if it's partially verified
        user_prompt_data = f"Universe: {world_name}\nVerification Status: {status}\n\nVerified Research Data:\n{verified_data}"
        
        set_current_universe(world_name)
        
        final_ans, history = await run_agent(
            agent_name="DB Architect",
            system_prompt=prompt["system"],
            user_prompt=user_prompt_data,
            step=f"Integrate {world_name}",
            run_id=run_id,
            tools_names=["queryTraits", "upsertTrait"],
            submit_tool_name="submit_integration"
        )
        
        # Phase 2: Clean up unconfirmed staging — remove only promoted traits
        # We pass the history from the integration phase to maintain context,
        # but we omit the 'upsertTrait' tool to ensure the agent cannot modify the main DB.
        cleanup_prompt = get_cleanup_prompt()

        await run_agent(
            agent_name="DB Architect",
            system_prompt=cleanup_prompt["system"],
            user_prompt=f"Clean up unconfirmed staging for {world_name}",
            step=f"Cleanup {world_name}",
            run_id=run_id,
            tools_names=["queryTraits", "queryUnconfirmedTraits", "deleteUnconfirmedTrait"],
            submit_tool_name="submit_cleanup",
            history=history
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
    if await is_aborted(run_id):
        raise RuntimeError(f"Run {run_id} was aborted by user.")
    target_worlds = state.get("target_worlds", [])
    focused_features = state.get("focused_features")
    
    log_transition(run_id, "Manager", f"Starting parallel research phase for {len(target_worlds)} worlds", "IN_PROGRESS", state)
    
    successful_results = []
    errors = []
    verified_worlds = []
    
    cache = FetchCache()
    
    with Session(engine) as session:
        setting = session.get(Setting, "MAX_PARALLEL_AGENTS")
        batch_size = int(setting.value) if setting and setting.value else 5
    
    # Join features into a single string for the 'focus' parameter if they exist
    focus_str = ", ".join(focused_features) if focused_features else None

    for i in range(0, len(target_worlds), batch_size):
        batch = target_worlds[i:i + batch_size]
        tasks = [research_single_world(world, run_id, focus=focus_str, fetch_cache=cache) for world in batch]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for r in batch_results:
            if isinstance(r, Exception):
                errors.append(str(r))
            else:
                successful_results.append(r)
                verified_worlds.append(r["name"])
    
    log_transition(run_id, "Manager", "Completed parallel research phase", "COMPLETED", state)
    
    if not verified_worlds:
        log_transition(
            run_id, "Manager",
            f"All {len(target_worlds)} world(s) failed research; nothing to consolidate. Errors: {errors}",
            "FAILED", state
        )
        return {
            "research_results": successful_results,
            "verified_worlds": verified_worlds,
            "errors": errors,
            "active_task": "FINISHED"
        }

    # If this is a focused search, we go straight to DB integration and then potentially to Architecture
    # Otherwise, we follow the standard flow (Consolidation -> Architecture)
    next_task = "DB_INTEGRATION" if state.get("is_focused_search") else "CONSOLIDATION"

    return {
        "research_results": successful_results,
        "verified_worlds": verified_worlds,
        "errors": errors,
        "active_task": next_task
    }


async def manager_node(state: OmniverseState) -> Dict[str, Any]:
    run_id = state.get("run_id")
    log_transition(run_id, "Manager", "Routing pipeline state", "COMPLETED", state)
    return {"active_task": state.get("active_task", "RESEARCH")}


async def consolidation_node(state: OmniverseState) -> Dict[str, Any]:
    """LangGraph node to synthesize multiple research results into a unified dataset."""
    run_id = state.get("run_id")
    if await is_aborted(run_id):
        raise RuntimeError(f"Run {run_id} was aborted by user.")
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


async def _audit_tier_system(tier_system_definition: str, dataset: str, run_id: str, cache: FetchCache) -> tuple[bool, str]:
    """Shared adversarial audit for a proposed/amended rubric. Used both at bootstrap and on amendment."""
    critic_system_prompt = """### ROLE
Strict Logic Auditor. Your goal is to find flaws in the proposed Tier System.

PROCESS
1. Analyze the provided Tier System and the consolidated dataset.
2. Use `fetchPage` and `webSearch` to verify specific threshold claims.
3. Look for semantic overlaps, gaps in scaling, or contradictions with canonical data.
4. Check that thresholds are phrased as durable, measurable properties (not as lists of specific worlds), since this rubric must remain valid for worlds not yet in the database.
5. Specifically check if the relative progression (Tier 0 lowest, Tier 10 highest) is logically sound.

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
    return audit_success(audit_result), audit_result


def _get_active_rubric(session: Session) -> Optional[TierSystem]:
    return session.exec(
        select(TierSystem).where(TierSystem.is_active == True).order_by(TierSystem.version.desc())
    ).first()


def _parse_stability_result(stability_result: str) -> Dict[str, Any]:
    upper = stability_result.upper()
    status = "UNKNOWN"
    if "STATUS: STABLE" in upper:
        status = "STABLE"
    elif "STATUS: ANOMALY" in upper:
        status = "ANOMALY"
    elif "STATUS: INSUFFICIENT_DATA" in upper:
        status = "INSUFFICIENT"
    
    tier_num = None
    tier_match = re.search(r"TIER:\s*(\d+)", stability_result, re.IGNORECASE)
    if tier_match:
        try:
            tier_num = max(0, min(10, int(tier_match.group(1))))
        except Exception:
            pass
            
    return {"status": status, "tier": tier_num, "justification": stability_result}


MAX_ARCHITECTURE_ATTEMPTS = 5


async def architecture_node(state: OmniverseState) -> Dict[str, Any]:
    """
    LangGraph node responsible for tiering. This maintains ONE persistent,
    versioned rubric (TierSystem.is_active) rather than redesigning a fresh
    hierarchy every run:
      - Bootstrap (no active rubric yet): design + adversarially audit a new
        rubric from scratch, exactly as before.
      - Steady state (active rubric exists): skip the design/audit entirely
        and go straight to slotting each verified world into it. This is
        what keeps the SAME world landing in the SAME tier across runs, and
        avoids paying for a full re-architecture LLM call on every run.
      - Amendment (a world genuinely doesn't fit): only the specific anomaly
        is escalated to a minimal rubric amendment, versioned and audited,
        rather than a full redesign. Only worlds that were anomalous are
        re-slotted afterward.
    """
    run_id = state.get("run_id")
    if await is_aborted(run_id):
        raise RuntimeError(f"Run {run_id} was aborted by user.")
    anomalies = state.get("anomalies", [])
    attempt = state.get("architecture_attempts", 0) + 1
    cache = FetchCache()

    if attempt > MAX_ARCHITECTURE_ATTEMPTS:
        log_transition(
            run_id, "Manager",
            f"Architecture/critic loop exceeded {MAX_ARCHITECTURE_ATTEMPTS} attempts without reaching a stable, "
            f"audited tier system. Aborting run to avoid an unbounded retry loop. Last anomalies: {anomalies}",
            "FAILED", state
        )
        raise RuntimeError(
            f"Architecture design failed to stabilize after {MAX_ARCHITECTURE_ATTEMPTS} attempts."
        )

    dataset = ""
    with Session(engine) as session:
        setting = session.get(Setting, "CONSOLIDATED_DATASET")
        if setting:
            dataset = setting.value
        active_rubric = _get_active_rubric(session)

    if active_rubric is None:
        # ---- BOOTSTRAP: design the rubric from scratch, once ----
        log_transition(run_id, "Tier Architect", f"No persistent rubric found. Bootstrapping tier rubric from scratch (attempt {attempt}/{MAX_ARCHITECTURE_ATTEMPTS}).", "IN_PROGRESS", state)

        architect_prompts = get_architect_prompt(dataset, anomalies)
        tier_system_definition, _ = await run_agent(
            agent_name="Tier Architect",
            system_prompt=architect_prompts["system"],
            user_prompt=architect_prompts["user"],
            step="Architecture",
            run_id=run_id,
            tools_names=[],
            submit_tool_name="submit_architecture"
        )

        is_success, audit_result = await _audit_tier_system(tier_system_definition, dataset, run_id, cache)
        log_transition(run_id, "Logic Auditor", f"Audited bootstrap Tier Rubric. Status: {'SUCCESS' if is_success else 'REVISION_REQUIRED'}", "IN_PROGRESS", state)

        if not is_success:
            return {
                "anomalies": [f"System Design Error: {audit_result}"],
                "system_stable": False,
                "active_task": "RE_ARCHITECTURE",
                "architecture_attempts": attempt
            }

        with Session(engine) as session:
            tier_system = TierSystem(system_definition=tier_system_definition, version=1, is_active=True)
            session.add(tier_system)
            session.commit()
            session.refresh(tier_system)
            active_rubric = tier_system

    rubric_id = active_rubric.id
    rubric_text = active_rubric.system_definition

    # ---- SLOT verified worlds into the persistent rubric ----
    log_transition(run_id, "Stability Unit", f"Slotting worlds into persistent rubric v{active_rubric.version}", "IN_PROGRESS", state)

    world_tier_mappings = []
    anomalous = []  # list of (universe, stability_result)

    with Session(engine) as session:
        verified_world_names = state.get("verified_worlds", [])
        universes = session.exec(select(Universe).where(Universe.name.in_(verified_world_names))).all()
        world_anomalies = []
        for universe in universes:
            traits = session.exec(select(Trait).where(Trait.universe_id == universe.id)).all()
            if not traits:
                continue # Skip unresearched

            traits_text = "\n".join([f"- {t.name}: {t.value}" for t in traits])
            stability_prompts = get_stability_prompt(traits_text, rubric_text)

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
            
            # Parse the STATUS field explicitly rather than doing loose substring
            # matching. A raw "ANOMALY" substring check is unreliable because the
            # required output format always includes an "ANOMALY_DETAILS:" field
            # label, so that substring is present even on genuinely stable results.
            status_match = re.search(r"STATUS:\s*(STABLE|ANOMALY|INSUFFICIENT_DATA)", stability_result, re.IGNORECASE)
            status = status_match.group(1).upper() if status_match else "UNKNOWN"
            is_stable = status == "STABLE"
            
            tier_num = 11
            tier_match = re.search(r"TIER:\s*(\d+)", stability_result, re.IGNORECASE)
            if tier_match:
                try:
                    tier_num = int(tier_match.group(1))
                except ValueError:
                    log_transition(run_id, "Stability Unit", f"Could not parse TIER value for {universe.name}, defaulting to Tier 11.", "IN_PROGRESS", state)
            else:
                log_transition(run_id, "Stability Unit", f"No TIER field found in stability output for {universe.name}, defaulting to Tier 11.", "IN_PROGRESS", state)

            if is_stable:
                world_tier_mappings.append({
                    "universe_id": universe.id,
                    "tier": tier_num,
                    "justification": stability_result
                })
            elif status == "INSUFFICIENT_DATA":
                continue # Skip untiered/insufficient data, do not escalate
            else:
                world_anomalies.append(f"{universe.name}: Anomaly detected during tiering: {stability_result}")
                db_anomaly = Anomaly(universe_id=universe.id, description=stability_result)
                session.add(db_anomaly)
                anomalous.append((universe, stability_result))

    # ---- Amend the rubric minimally if any world couldn't be slotted ----
    if anomalous:
        retries = state.get("architecture_retries", 0) + 1
        anomaly_descriptions = [f"{u.name}: {res}" for u, res in anomalous]

        if retries >= 3:
            log_transition(run_id, "Manager", f"Max amendment attempts reached for {len(anomalous)} anomalies. Recording as untiered and proceeding.", "IN_PROGRESS", state)
            with Session(engine) as session:
                for universe, res in anomalous:
                    session.exec(WorldTier.__table__.delete().where(WorldTier.universe_id == universe.id))
                    session.add(WorldTier(universe_id=universe.id, system_id=rubric_id, tier_number=-1, justification=res))
                for wt in world_tier_mappings:
                    session.exec(WorldTier.__table__.delete().where(WorldTier.universe_id == wt["universe_id"]))
                    session.add(WorldTier(universe_id=wt["universe_id"], system_id=rubric_id, tier_number=wt["tier"], justification=wt["justification"]))
                session.commit()
            return {
                "anomalies": anomaly_descriptions,
                "system_stable": False,
                "current_tier_system": rubric_text,
                "active_task": "EXTRAPOLATION",
                "architecture_retries": retries
            }

        log_transition(run_id, "Rubric Steward", f"{len(anomalous)} world(s) don't fit the persistent rubric. Proposing minimal amendment.", "IN_PROGRESS", state)

        amendment_prompt = get_rubric_amendment_prompt(rubric_text, dataset, anomaly_descriptions)
        amended_definition, _ = await run_agent(
            agent_name="Rubric Steward",
            system_prompt=amendment_prompt["system"],
            user_prompt=amendment_prompt["user"],
            step="Rubric Amendment",
            run_id=run_id,
            tools_names=[],
            submit_tool_name="submit_architecture"
        )

        is_success, audit_result = await _audit_tier_system(amended_definition, dataset, run_id, cache)
        log_transition(run_id, "Logic Auditor", f"Audited rubric amendment. Status: {'SUCCESS' if is_success else 'REVISION_REQUIRED'}", "IN_PROGRESS", state)

        if not is_success:
            return {
                "anomalies": [f"Rubric Amendment Error: {audit_result}"] + anomaly_descriptions,
                "system_stable": False,
                "active_task": "RE_ARCHITECTURE",
                "architecture_attempts": attempt
            }

        # Persist confirmed (non-anomalous) worlds under the OLD rubric version first,
        # since they were validated against it and remain valid.
        with Session(engine) as session:
            for wt in world_tier_mappings:
                session.exec(WorldTier.__table__.delete().where(WorldTier.universe_id == wt["universe_id"]))
                session.add(WorldTier(universe_id=wt["universe_id"], system_id=rubric_id, tier_number=wt["tier"], justification=wt["justification"]))

            # Version the rubric: deactivate old, activate amended
            old_rubric = session.get(TierSystem, rubric_id)
            old_rubric.is_active = False
            session.add(old_rubric)
            new_rubric = TierSystem(
                system_definition=amended_definition,
                version=(old_rubric.version or 1) + 1,
                is_active=True,
                parent_id=rubric_id,
                amendment_reason="; ".join(anomaly_descriptions)[:2000]
            )
            session.add(new_rubric)
            session.commit()
            session.refresh(new_rubric)
            new_rubric_id = new_rubric.id
            new_rubric_text = new_rubric.system_definition
            new_rubric_version = new_rubric.version

        # Re-slot only the worlds that were anomalous, against the amended rubric
        log_transition(run_id, "Stability Unit", f"Re-slotting {len(anomalous)} world(s) against amended rubric v{new_rubric_version}", "IN_PROGRESS", state)
        with Session(engine) as session:
            for universe, _prev_result in anomalous:
                stability_prompts = get_stability_prompt(universe.summary or "", new_rubric_text)
                stability_result, _ = await run_agent(
                    agent_name="Stability Unit",
                    system_prompt=stability_prompts["system"],
                    user_prompt=stability_prompts["user"],
                    step="Stability Re-check",
                    run_id=run_id,
                    tools_names=["webSearch", "fetchPage"],
                    submit_tool_name="submit_stability",
                    fetch_cache=cache
                )
                parsed = _parse_stability_result(stability_result)
                tier_val = parsed["tier"] if parsed["tier"] is not None else -1
                session.exec(WorldTier.__table__.delete().where(WorldTier.universe_id == universe.id))
                session.add(WorldTier(universe_id=universe.id, system_id=new_rubric_id, tier_number=tier_val, justification=parsed["justification"]))
            session.commit()

        log_transition(run_id, "Manager", f"Rubric amended to v{new_rubric_version}. Tiering complete.", "COMPLETED", state)
        
        next_task = "EXTRAPOLATION" if not state.get("is_focused_search") else "FINISHED"
        
        return {
            "current_tier_system": new_rubric_text,
            "system_stable": True,
            "active_task": next_task
        }

    # ---- No anomalies: persist mappings under the existing rubric, done ----
    with Session(engine) as session:
        for wt in world_tier_mappings:
            session.exec(WorldTier.__table__.delete().where(WorldTier.universe_id == wt["universe_id"]))
            session.add(WorldTier(universe_id=wt["universe_id"], system_id=rubric_id, tier_number=wt["tier"], justification=wt["justification"]))
        session.commit()

    log_transition(run_id, "Manager", "Completed tiering under persistent rubric.", "COMPLETED", state)
    
    next_task = "EXTRAPOLATION" if not state.get("is_focused_search") else "FINISHED"

    return {
        "current_tier_system": rubric_text,
        "system_stable": True,
        "active_task": next_task,
        "architecture_attempts": 0
    }



async def extrapolation_node(state: OmniverseState) -> Dict[str, Any]:
    """LangGraph node to generate and audit speculative scaling theories."""
    run_id = state.get("run_id")
    if await is_aborted(run_id):
        raise RuntimeError(f"Run {run_id} was aborted by user.")
    log_transition(run_id, "Ontological Theorist", "Starting theoretical scaling projections", "IN_PROGRESS", state)
    
    generated_theories = []
    
    with Session(engine) as session:
        verified_world_names = state.get("verified_worlds", [])
        universes = session.exec(select(Universe).where(Universe.name.in_(verified_world_names))).all()
        
        # Pre-fetch all traits for all verified universes to avoid N+1 in the loop
        all_verified_ids = [u.id for u in universes]
        all_traits = session.exec(select(Trait).where(Trait.universe_id.in_(all_verified_ids))).all()
        trait_map = {}
        for t in all_traits:
            trait_map.setdefault(t.universe_id, []).append(f"- {t.name}: {t.value}")

        for universe in universes:
            set_current_universe(universe.name)
            
            # Context for this universe (using traits, not summary)
            uni_traits = trait_map.get(universe.id, [])
            uni_context = "\n".join(uni_traits) if uni_traits else "No specific traits recorded."
            
            # Context from other universes (using traits)
            comparison_texts = []
            for other in universes:
                if other.id == universe.id:
                    continue
                other_traits = trait_map.get(other.id, [])
                traits_text = "\n".join(other_traits) if other_traits else "No traits recorded."
                comparison_texts.append(f"World: {other.name}\nTraits:\n{traits_text}")
            
            comparison_context = "\n\n---\n\n".join(comparison_texts)

            theory_prompt = get_extrapolation_prompt(universe.name, uni_context, comparison_context)
            
            speculation, _ = await run_agent(
                agent_name="Ontological Theorist",
                system_prompt=theory_prompt["system"],
                user_prompt=theory_prompt["user"],
                step="Extrapolation",
                run_id=run_id,
                tools_names=[],
                submit_tool_name="submit_theory"
            )
            
            audit_prompt = get_theory_auditor_prompt(speculation)
            
            audit_result, _ = await run_agent(
                agent_name="Theoretical Auditor",
                system_prompt=audit_prompt["system"],
                user_prompt=audit_prompt["user"],
                step="Theory Audit",
                run_id=run_id,
                tools_names=[],
                submit_tool_name="submit_audit"
            )
            
            is_verified = audit_result.strip().upper().startswith("VERIFIED")
            if not is_verified:
                log_transition(run_id, "Theoretical Auditor", f"Rejected theory for {universe.name}", "REVISION_REQUIRED", {"audit": audit_result})
                continue
            
            with Session(extrapolation_engine) as extra_session:
                extra_session.exec(Theory.__table__.delete().where(Theory.universe_id == universe.id))
                
                db_theory = Theory(
                    universe_id=universe.id,
                    theory_text=speculation,
                    auditor_feedback=audit_result
                )
                extra_session.add(db_theory)
                extra_session.commit()
            
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
