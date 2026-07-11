from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from app.core.dependencies import get_main_session, get_unconfirmed_session
from app.core.templates import templates
from app.db.schema import (
    Artifact,
)

router = APIRouter(tags=["flow_views"])

@router.get("/", response_class=HTMLResponse)
async def flow_page(request: Request):
    template = templates.env.get_template("pages/flow.html")
    return HTMLResponse(content=template.render(request=request))

@router.get("/trace", response_class=HTMLResponse)
async def trace_claim_query(
    request: Request,
    claim_id: int,
    main_session: Annotated[Session, Depends(get_main_session)],
    unconfirmed_session: Annotated[Session, Depends(get_unconfirmed_session)],
):
    return await trace_claim(request, claim_id, main_session, unconfirmed_session)

@router.get("/{claim_id}", response_class=HTMLResponse)
async def trace_claim(
    request: Request,
    claim_id: int,
    main_session: Annotated[Session, Depends(get_main_session)],
    _unconfirmed_session: Annotated[Session, Depends(get_unconfirmed_session)],
):
    artifact = main_session.get(Artifact, claim_id)
    if not artifact:
        return HTMLResponse("Artifact not found", status_code=404)

    # Simplified trace for now to avoid broken logic
    template = templates.env.get_template("fragments/flow_step.html")
    return HTMLResponse(content=template.render(
        request=request,
        claim=artifact,
        source=None,
        unconfirmed=None,
        inferences=[],
        subject=None,
        predicate=None,
        object_name=None
    ))

