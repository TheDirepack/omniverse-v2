from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.core.templates import templates

router = APIRouter(tags=["index_views"])

@router.get("/", response_class=HTMLResponse)
async def index_page(request: Request):
    template = templates.env.get_template("pages/index.html")
    return HTMLResponse(content=template.render(
        request=request, current_path=str(request.url.path)
    ))
