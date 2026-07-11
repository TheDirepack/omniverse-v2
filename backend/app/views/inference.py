from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse

from app.core.templates import templates
from app.services.inference_engine_service import InferenceEngineService
from app.services.inference_rule_service import InferenceRuleService

router = APIRouter(tags=["inference_views"])


@router.get("/", response_class=HTMLResponse)
async def inference_page(request: Request):
    service = InferenceRuleService()
    # Fetch all rules by status to show on the page
    proposed = service.get_rules_by_status("PROPOSED")
    critiqued = service.get_rules_by_status("CRITIQUED")
    approved = service.get_rules_by_status("APPROVED")
    rejected = service.get_rules_by_status("REJECTED")

    template = templates.env.get_template("pages/inference.html")
    return HTMLResponse(content=template.render(
        request=request,
        proposed=proposed,
        critiqued=critiqued,
        approved=approved,
        rejected=rejected,
    ))


@router.post("/rules/{rule_id}/approve", response_class=HTMLResponse)
async def approve_rule_view(request: Request, rule_id: int):
    service = InferenceRuleService()
    rule = service.approve_rule(rule_id)
    if not rule:
        return Response(content="Rule not found", status_code=404)

    # Fetch updated lists for OOB update
    proposed = service.get_rules_by_status("PROPOSED")
    critiqued = service.get_rules_by_status("CRITIQUED")
    approved = service.get_rules_by_status("APPROVED")
    rejected = service.get_rules_by_status("REJECTED")

    template = templates.env.get_template("fragments/all_rules_updated.html")
    return HTMLResponse(content=template.render(
        request=request,
        proposed=proposed,
        critiqued=critiqued,
        approved=approved,
        rejected=rejected
    ))


@router.post("/rules/{rule_id}/reject", response_class=HTMLResponse)
async def reject_rule_view(request: Request, rule_id: int):
    service = InferenceRuleService()
    rule = service.reject_rule(rule_id)
    if not rule:
        return Response(content="Rule not found", status_code=404)

    # Fetch updated lists for OOB update
    proposed = service.get_rules_by_status("PROPOSED")
    critiqued = service.get_rules_by_status("CRITIQUED")
    approved = service.get_rules_by_status("APPROVED")
    rejected = service.get_rules_by_status("REJECTED")

    template = templates.env.get_template("fragments/all_rules_updated.html")
    return HTMLResponse(content=template.render(
        request=request,
        proposed=proposed,
        critiqued=critiqued,
        approved=approved,
        rejected=rejected
    ))


@router.post("/materialize", response_class=HTMLResponse)
async def materialize_view(_request: Request):
    engine_service = InferenceEngineService()
    created = engine_service.materialize_inferred_claims()
    return f"Successfully materialized {len(created)} new inferred claims."
