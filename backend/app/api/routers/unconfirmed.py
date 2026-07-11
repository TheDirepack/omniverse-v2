from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.core.context import set_current_universe
from app.core.dependencies import get_unconfirmed_session

router = APIRouter(prefix="/unconfirmed", tags=["unconfirmed"])


class NotebookEntryPayload(BaseModel):
    title: str
    summary: str
    details: str | None = None
    kind: str = "Observation"
    priority: int = 0


class NotebookEntryBatchPayload(BaseModel):
    universe_name: str
    items: List[NotebookEntryPayload]


@router.post("/entries")
async def save_notebook_entries(
    payload: NotebookEntryBatchPayload,
    session: Session = Depends(get_unconfirmed_session),
):
    set_current_universe(payload.universe_name)

    from app.core.tools import tool_save_notebook_entry

    results = []
    for item in payload.items:
        res = await tool_save_notebook_entry({
            "title": item.title,
            "summary": item.summary,
            "details": item.details,
            "kind": item.kind,
            "priority": item.priority,
        })
        results.append(res)

    return {"status": "success", "results": results}


@router.delete("/entries/{entry_id}")
async def delete_notebook_entry(entry_id: int, session: Session = Depends(get_unconfirmed_session)):
    from app.core.tools import tool_delete_unconfirmed_artifact

    args = {"artifact_id": entry_id}
    result = await tool_delete_unconfirmed_artifact(args)

    if "Error" in result:
        raise HTTPException(status_code=404, detail=result)

    return {"status": "success", "message": result}

