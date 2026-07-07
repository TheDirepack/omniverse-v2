from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.core.templates import templates
from app.services.theory_service import TheoryService
from app.services.universe_service import UniverseService

router = APIRouter(tags=["theory_views"])


@router.get("/", response_class=HTMLResponse)
async def theory_page(request: Request):
    theory_service = TheoryService()
    uni_service = UniverseService()

    theories = theory_service.get_all_theories()
    universes = uni_service.get_all_universes()

    template = templates.env.get_template("pages/theory.html")
    return HTMLResponse(content=template.render(
        request=request,
        theories=theories,
        universes=universes,
    ))


@router.post("/reevaluate", response_class=HTMLResponse)
async def reevaluate_theory_view(request: Request, universe_id: int = Form(...)):
    return '<div class="p-2 bg-blue-50 text-blue-700 text-sm rounded border border-blue-200">Re-evaluation triggered. This may take a few minutes.</div>'
