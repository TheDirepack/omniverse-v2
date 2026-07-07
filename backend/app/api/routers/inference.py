import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from app.core.runtime_state import add_active_run, remove_run
from app.services.inference_engine_service import InferenceEngineService
from app.services.inference_rule_service import InferenceRuleService

router = APIRouter(prefix="/inference", tags=["inference"])


class DepthPayload(BaseModel):
    max_composition_depth: int = Field(..., ge=1, le=10)


async def run_rule_proposal_in_background(run_id: str):
    await add_active_run(run_id)
    try:
        service = InferenceRuleService()
        await service.run_rule_proposal_pass(run_id=run_id)
    except Exception as e:
        print(f"[API] Error running rule proposal pass: {e}")
    finally:
        await remove_run(run_id)


@router.post("/rules/propose")
def trigger_rule_proposal(background_tasks: BackgroundTasks):
    """Manual trigger only — scans for frequent predicate-pair patterns and
    runs the proposer/critic loop. Never runs automatically after research,
    since a bad composition rule has universe-wide blast radius."""
    run_id = str(uuid.uuid4())
    background_tasks.add_task(run_rule_proposal_in_background, run_id)
    return {"status": "started", "run_id": run_id}


@router.get("/rules")
def list_rules(status: str | None = None):
    service = InferenceRuleService()
    if status:
        return service.get_rules_by_status(status)
    return {
        "proposed": service.get_rules_by_status("PROPOSED"),
        "critiqued": service.get_rules_by_status("CRITIQUED"),
        "approved": service.get_rules_by_status("APPROVED"),
        "rejected": service.get_rules_by_status("REJECTED"),
    }


@router.post("/rules/{rule_id}/approve")
def approve_rule(rule_id: int):
    service = InferenceRuleService()
    rule = service.approve_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule


@router.post("/rules/{rule_id}/reject")
def reject_rule(rule_id: int):
    service = InferenceRuleService()
    rule = service.reject_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule


@router.post("/materialize")
def trigger_materialization():
    """Manual trigger only — walks approved rules up to the configured
    max_composition_depth and materializes InferredClaims, flagging
    contradictions for human/semantic review (never auto-resolved)."""
    engine_service = InferenceEngineService()
    created = engine_service.materialize_inferred_claims()
    return {"status": "completed", "created_count": len(created)}


@router.get("/contradictions")
def list_unreviewed_contradictions():
    engine_service = InferenceEngineService()
    return engine_service.get_unreviewed_contradictions()


@router.get("/depth")
def get_depth():
    engine_service = InferenceEngineService()
    return {"max_composition_depth": engine_service.get_max_depth()}


@router.put("/depth")
def set_depth(payload: DepthPayload):
    engine_service = InferenceEngineService()
    engine_service.set_max_depth(payload.max_composition_depth)
    return {"max_composition_depth": payload.max_composition_depth}
