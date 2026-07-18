"""Research Results Viewer views."""

from collections.abc import Sequence
from datetime import datetime
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from app.core.dependencies import get_main_session
from app.core.enums import RunPhase
from app.db.schema import Artifact, Evidence, Universe
from app.services.execution_service import ExecutionService

router = APIRouter(tags=["research_results"])


def get_execution_service(session: Session = Depends(get_main_session)):
    """Get execution service instance."""
    return ExecutionService(session)


async def get_artifacts_with_details(
    session: Session,
    artifact_ids: list[int]
) -> list[dict]:
    """Fetch artifacts with their related universe names and evidence."""
    artifacts = session.exec(
        select(Artifact).where(Artifact.id.in_(artifact_ids))
    ).all()
    
    result = []
    for artifact in artifacts:
        # Get universe name
        universe = session.get(Universe, artifact.universe_id)
        universe_name = universe.name if universe else "Unknown"
        
        # Get related evidence
        evidence_items = session.exec(
            select(Evidence).where(Evidence.artifact_id == artifact.id)
        ).all()
        
        # Parse evidence_refs from artifact
        try:
            evidence_refs = artifact.evidence_refs_parsed
        except:
            evidence_refs = []
        
        result.append({
            "id": artifact.id,
            "name": artifact.name or "",
            "type": artifact.type,
            "description": artifact.description or "",
            "confidence": artifact.confidence.value if artifact.confidence else "N/A",
            "freshness": artifact.freshness.value if artifact.freshness else "N/A",
            "verification_status": artifact.verification_status,
            "support_count": artifact.support_count,
            "payload_json": artifact.payload_json,
            "universe_id": artifact.universe_id,
            "universe_name": universe_name,
            "source_reference": artifact.source_reference or "",
            "source_wiki": artifact.source_wiki or "",
            "created_at": artifact.created_at.strftime("%Y-%m-%d %H:%M:%S") if artifact.created_at else "",
            "evidence": [
                {
                    "id": e.id,
                    "section": e.section or "",
                    "source_url": e.source_url,
                    "source_name": e.source_name or ""
                }
                for e in evidence_items
            ],
            "raw_evidence_refs": evidence_refs
        })
    
    return result


@router.get("/{run_id}", response_class=HTMLResponse)
async def view_research_results(
    run_id: str,
    request: Request,
    session: Session = Depends(get_main_session),
    service: ExecutionService = Depends(get_execution_service)
):
    """View all results from a specific research run."""
    
    # Get run state from execution logs
    states = service.repo.get_logs_for_run(run_id, 0)
    
    if not states:
        raise HTTPException(status_code=404, detail=f"Research run {run_id} not found")
    
    # Determine run status based on latest state
    latest_state = states[-1] if states else None
    status_map = {
        RunPhase.FINISHED: "completed",
        RunPhase.RESEARCHING: "in_progress",
        RunPhase.DB_INTEGRATION: "integrating",
        RunPhase.SUMMARY: "summarizing",
        RunPhase.COMPLETED: "completed",
        RunPhase.QUEUED: "queued",
        RunPhase.FAILED: "failed",
    }
    
    status = status_map.get(latest_state.status, "unknown")
    
    # Extract run metadata from states
    run_metadata = {
        "run_id": run_id,
        "target_worlds": [],
        "started_at": "",
        "completed_at": "",
        "active_task": latest_state.node_name if latest_state else "",
        "thought": latest_state.thought[:200] if latest_state and latest_state.thought else "",
        "total_duration_ms": sum(s.duration_ms or 0 for s in states),
        "total_token_usage": sum(s.token_usage or 0 for s in states),
    }
    
    # Parse target worlds from first state
    if states and states[0].state_snapshot:
        try:
            import json
            state_dict = json.loads(states[0].state_snapshot)
            if "research_target" in state_dict:
                run_metadata["target_worlds"] = [
                    w for w in state_dict["research_target"] 
                    if isinstance(w, str) and w.strip()
                ]
            if "started_at" in state_dict:
                run_metadata["started_at"] = state_dict["started_at"].strftime("%Y-%m-%d %H:%M:%S")
            if "completed_at" in state_dict:
                run_metadata["completed_at"] = state_dict["completed_at"].strftime("%Y-%m-%d %H:%M:%S")
        except (json.JSONDecodeError, Exception):
            pass
    
    # Fetch artifacts - check both run_id field and evidence_refs
    artifact_ids = set()
    
    # Method 1: Check Artifact.run_id (if column exists)
    # Method 2: Check evidence_refs in Evidence table for this run's states
    
    # Get unique universe IDs from research states
    universe_ids = set()
    for state in states:
        if state.state_snapshot:
            try:
                state_dict = json.loads(state.state_snapshot)
                if "universe_id" in state_dict:
                    universe_ids.add(state_dict["universe_id"])
            except:
                pass
    
    # Fetch artifacts for these universes that were created during this run
    # We'll fetch all artifacts and filter by checking their creation context
    # For now, get artifacts by universe that might be related to this run
    artifacts_raw = []
    if universe_ids:
        artifacts_raw = session.exec(
            select(Artifact).where(Artifact.universe_id.in_(list(universe_ids)))
        ).all()
    
    # Filter artifacts by matching with research states
    artifacts_with_details = []
    processed_artifact_ids = set()
    
    for artifact in artifacts_raw:
        # Check if this artifact was created during this run
        # Look at the state snapshot for artifact creation
        for state in states:
            if state.state_snapshot:
                try:
                    state_dict = json.loads(state.state_snapshot)
                    if "artifact_id" in state_dict and state_dict["artifact_id"] == artifact.id:
                        # Fetch artifact details directly instead of recursive call
                        universe = session.get(Universe, artifact.universe_id)
                        universe_name = universe.name if universe else "Unknown"
                        
                        evidence_items = session.exec(
                            select(Evidence).where(Evidence.artifact_id == artifact.id)
                        ).all()
                        
                        try:
                            evidence_refs = artifact.evidence_refs_parsed
                        except:
                            evidence_refs = []
                        
                        artifacts_with_details.append({
                            "id": artifact.id,
                            "name": artifact.name or "",
                            "type": artifact.type,
                            "description": artifact.description or "",
                            "confidence": artifact.confidence.value if artifact.confidence else "N/A",
                            "freshness": artifact.freshness.value if artifact.freshness else "N/A",
                            "verification_status": artifact.verification_status,
                            "support_count": artifact.support_count,
                            "payload_json": artifact.payload_json,
                            "universe_id": artifact.universe_id,
                            "universe_name": universe_name,
                            "source_reference": artifact.source_reference or "",
                            "source_wiki": artifact.source_wiki or "",
                            "created_at": artifact.created_at.strftime("%Y-%m-%d %H:%M:%S") if artifact.created_at else "",
                            "evidence": [
                                {
                                    "id": e.id,
                                    "section": e.section or "",
                                    "source_url": e.source_url,
                                    "source_name": e.source_name or ""
                                }
                                for e in evidence_items
                            ],
                            "raw_evidence_refs": evidence_refs
                        })
                        processed_artifact_ids.add(artifact.id)
                        break
                except:
                    continue
        
        # Also check if artifact references any universe from this run
        if artifact.id not in processed_artifact_ids and artifact.universe_id in universe_ids:
            # Fetch details directly instead of recursive call
            universe = session.get(Universe, artifact.universe_id)
            universe_name = universe.name if universe else "Unknown"
            
            evidence_items = session.exec(
                select(Evidence).where(Evidence.artifact_id == artifact.id)
            ).all()
            
            try:
                evidence_refs = artifact.evidence_refs_parsed
            except:
                evidence_refs = []
            
            artifacts_with_details.append({
                "id": artifact.id,
                "name": artifact.name or "",
                "type": artifact.type,
                "description": artifact.description or "",
                "confidence": artifact.confidence.value if artifact.confidence else "N/A",
                "freshness": artifact.freshness.value if artifact.freshness else "N/A",
                "verification_status": artifact.verification_status,
                "support_count": artifact.support_count,
                "payload_json": artifact.payload_json,
                "universe_id": artifact.universe_id,
                "universe_name": universe_name,
                "source_reference": artifact.source_reference or "",
                "source_wiki": artifact.source_wiki or "",
                "created_at": artifact.created_at.strftime("%Y-%m-%d %H:%M:%S") if artifact.created_at else "",
                "evidence": [
                    {
                        "id": e.id,
                        "section": e.section or "",
                        "source_url": e.source_url,
                        "source_name": e.source_name or ""
                    }
                    for e in evidence_items
                ],
                "raw_evidence_refs": evidence_refs
            })
            processed_artifact_ids.add(artifact.id)
    
    # Sort artifacts by creation date
    artifacts_with_details.sort(key=lambda x: x.get("created_at", ""))
    
    return {
        "run": run_metadata,
        "artifacts": artifacts_with_details,
        "artifact_count": len(artifacts_with_details),
        "status": status,
        "states": states,
        "current_path": str(request.url.path),
    }


@router.post("/{run_id}/delete")
async def delete_research_run(
    run_id: str,
    world_names: str = Form(""),  # Required for HTMX form
    session: Session = Depends(get_main_session),
    service: ExecutionService = Depends(get_execution_service)
):
    """Delete a completed research run."""
    
    try:
        # Clear execution logs for this run
        service.repo.clear_logs_for_run(run_id)
        
        # Note: We don't delete artifacts directly to preserve knowledge graph integrity
        # Users should manually delete artifacts they no longer need
        
        return {
            "success": True,
            "message": f"Research run {run_id} has been deleted. Execution logs cleared."
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to delete run: {str(e)}")
