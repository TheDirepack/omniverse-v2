from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any, List

from app.core.dependencies import get_unconfirmed_session
from app.core.context import set_current_universe
from app.db.unconfirmed_schema import UnconfirmedClaim, UnconfirmedUniverse
from sqlmodel import Session, select


router = APIRouter(prefix="/unconfirmed", tags=["unconfirmed"])


class UnconfirmedClaimPayload(BaseModel):
    subject: str
    context: str | None = None
    predicate: str
    object_val: str
    artifact_id: int | None = None
    reference: str | None = None
    wiki_source: str | None = None
    confidence: float | None = None


class UnconfirmedClaimBatchPayload(BaseModel):
    universe_name: str
    items: List[UnconfirmedClaimPayload]



@router.post("/claims")
async def save_unconfirmed_claims(
    payload: UnconfirmedClaimBatchPayload,
    session: Session = Depends(get_unconfirmed_session),
):
    set_current_universe(payload.universe_name)
    
    if isinstance(payload, UnconfirmedClaimBatchPayload):
        args = {"items": [item.model_dump() for item in payload.items]}
    else:
        args = {"items": [payload.model_dump()]}
    
    from app.core.tools import tool_save_unconfirmed_claim
    result = await tool_save_unconfirmed_claim(args)
    
    if "Error" in result:
        raise HTTPException(status_code=400, detail=result)
    
    return {"status": "success", "message": result}


@router.delete("/claims/{claim_id}")
async def delete_unconfirmed_claim(claim_id: int, session: Session = Depends(get_unconfirmed_session)):
    from app.core.tools import tool_delete_unconfirmed_claim
    
    args = {"claim_id": claim_id}
    result = await tool_delete_unconfirmed_claim(args)
    
    if "Error" in result:
        raise HTTPException(status_code=404, detail=result)
        
    return {"status": "success", "message": result}
