import re

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.agents.agent_names import AGENT_NAMES
from app.core.templates import templates
from app.services.settings_service import SettingsService
from app.services.universe_service import UniverseService

router = APIRouter(tags=["logs_views"])

LOG_LINE_RE = re.compile(
    r"^\[(.+?)\] \[(.+?)\] \[(.+?)\] \[(.+?)\] \[(.+?)\] \[([\w.]+)\] (.+)$"
)

EVENT_COLORS = {
    "THOUGHT": "text-purple-600 dark:text-purple-400",
    "TOOL_REQ": "text-blue-600 dark:text-blue-400",
    "TOOL_RES": "text-green-600 dark:text-green-400",
    "PROMPT": "text-yellow-600 dark:text-yellow-400",
    "MODEL_CALL": "text-indigo-600 dark:text-indigo-400",
    "ERROR": "text-red-600 dark:text-red-400 font-bold",
    "FAILED": "text-red-700 dark:text-red-300 font-bold",
    "INFO": "text-gray-600 dark:text-gray-400",
    "WARNING": "text-orange-600 dark:text-orange-400",
    "COMPLETED": "text-emerald-600 dark:text-emerald-400",
    "IN_PROGRESS": "text-cyan-600 dark:text-cyan-400",
    "STEP": "text-pink-600 dark:text-pink-400",
}


def _parse_log_line(line: str) -> dict | None:
    m = LOG_LINE_RE.match(line.strip())
    if not m:
        return None
    timestamp, agent, model, key_id, world, event_type, content = m.groups()
    event_type = event_type.removeprefix("AgentEventType.")
    return {
        "timestamp": timestamp,
        "agent": agent,
        "model": model,
        "key_id": key_id,
        "world": world,
        "event_type": event_type,
        "content": content,
        "color_class": EVENT_COLORS.get(event_type, "text-gray-500"),
    }


def _get_filter_options():
    try:
        uni_service = UniverseService()
        worlds = uni_service.get_all_universes(limit=500)
        world_names = sorted({w.name for w in worlds})
    except Exception:
        world_names = []

    try:
        settings_service = SettingsService()
        all_settings = settings_service.get_all_settings()
        models = set()
        for p in all_settings.get("providers", []):
            if p.get("models"):
                for m in p["models"].split(","):
                    m = m.strip()
                    if m:
                        models.add(m)
        for r in all_settings.get("agent_routes", []):
            if r.get("models"):
                for m in r["models"].split(","):
                    m = m.strip()
                    if m:
                        models.add(m)
        model_names = sorted(models)
    except Exception:
        model_names = []

    return {
        "agent_names": AGENT_NAMES,
        "world_names": world_names,
        "model_names": model_names,
        "event_types": [
            "THOUGHT", "TOOL_REQ", "TOOL_RES", "PROMPT",
            "MODEL_CALL", "ERROR", "FAILED", "INFO",
            "WARNING", "COMPLETED", "IN_PROGRESS", "STEP",
        ],

    }


@router.get("/", response_class=HTMLResponse)
async def logs_page(request: Request):
    opts = _get_filter_options()
    template = templates.env.get_template("pages/logs.html")
    return HTMLResponse(
        content=template.render(
            request=request, current_path=str(request.url.path), **opts
        )
    )


@router.get("/list", response_class=HTMLResponse, name="logs_list")
async def logs_list(
    request: Request,
    limit: int = 100,
    offset: int = 0,
    filter: str | None = None,
    agent: str | None = None,
    world: str | None = None,
    model: str | None = None,
    event_type: str | None = None,
    tool: str | None = None,
):
    from fastapi import HTTPException

    from app.api.routers.runs import get_file_logs

    try:
        data = get_file_logs(
            limit=limit,
            offset=offset,
            filter=filter,
            agent=agent,
            world=world,
            model=model,
            event_type=event_type,
            tool=tool,
        )
    except HTTPException:
        data = {"logs": [], "has_more": False}

    logs = data.get("logs", [])

    # Reassemble multiline entries: lines that don't match the log format
    # are continuations of the previous entry.
    reassembled = []
    for line in logs:
        if LOG_LINE_RE.match(line.strip()):
            reassembled.append(line)
        elif reassembled:
            reassembled[-1] += "\n" + line
        else:
            reassembled.append(line)

    parsed_logs = []
    for line in reassembled:
        parsed = _parse_log_line(line)
        if parsed:
            parsed_logs.append(parsed)
        else:
            parsed_logs.append({
                "timestamp": "", "agent": "", "model": "",
                "key_id": "", "world": "", "event_type": "INFO",
                "content": line,
                "color_class": "text-gray-500",
            })
    has_more = data.get("has_more", False)
    next_offset = offset + limit

    template = templates.env.get_template("components/log_list.html")
    return HTMLResponse(
        content=template.render(
            request=request,
            parsed_logs=parsed_logs,
            has_more=has_more,
            next_offset=next_offset,
            limit=limit,
            filter=filter,
            agent=agent,
            world=world,
            model=model,
            event_type=event_type,
            tool=tool,
        )
    )
