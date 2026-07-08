import json

import json

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from app.core.templates import templates
from app.db.settings_session import settings_engine
from app.repositories.settings import SettingsRepository
from app.services.settings_service import PROVIDER_PRESETS, SettingsService

router = APIRouter(tags=["settings_views"])


@router.get("/", response_class=HTMLResponse)
async def settings_page(request: Request):
    template = templates.env.get_template("pages/settings.html")
    return HTMLResponse(content=template.render(request=request))


@router.get("/tab/general", response_class=HTMLResponse)
async def settings_tab_general(request: Request):
    service = SettingsService()
    data = service.get_all_settings()
    template = templates.env.get_template("fragments/settings_general.html")
    return HTMLResponse(
        content=template.render(request=request, settings=data["general_settings"])
    )


@router.post("/general/update", response_class=HTMLResponse)
async def settings_general_update(
    request: Request, key: str = Form(...), value: str = Form(...)
):
    service = SettingsService()
    service.update_general_setting(key, value)
    
    # Special handling for browser pool configuration
    if key == "BROWSER_POOL_SIZE" or key == "BROWSER_MAX_CONCURRENCY_PER_INSTANCE":
        from app.core.browser import browser_manager
        settings = service.get_all_settings()
        gen = settings["general_settings"]
        pool_size = int(gen.get("BROWSER_POOL_SIZE", 2))
        max_concurrency = int(gen.get("BROWSER_MAX_CONCURRENCY_PER_INSTANCE", 5))
        await browser_manager.update_config(pool_size, max_concurrency)

    data = service.get_all_settings()
    template = templates.env.get_template("fragments/settings_general.html")
    response = HTMLResponse(
        content=template.render(request=request, settings=data["general_settings"])
    )
    response.headers["HX-Trigger"] = '{"showToast": {"value": "Setting updated", "type": "info"}}'
    return response


@router.post("/general/delete", response_class=HTMLResponse)
async def settings_general_delete(request: Request, key: str = Form(...)):
    service = SettingsService()
    service.update_general_setting(key, None)
    data = service.get_all_settings()
    template = templates.env.get_template("fragments/settings_general.html")
    return HTMLResponse(
        content=template.render(request=request, settings=data["general_settings"])
    )


@router.get("/tab/providers", response_class=HTMLResponse)
async def settings_tab_providers(request: Request):
    service = SettingsService()
    data = service.get_all_settings()
    from app.agents.agent_names import AGENT_NAMES

    template = templates.env.get_template("fragments/settings_providers.html")
    return HTMLResponse(
        content=template.render(
            request=request,
            providers=data["providers"],
            agent_routes=data["agent_routes"],
            agent_names=AGENT_NAMES,
            presets=PROVIDER_PRESETS,
        )
    )


@router.post("/providers/upsert", response_class=HTMLResponse)
async def settings_provider_upsert(
    request: Request,
    id: int = Form(default=None),
    name: str = Form(...),
    provider_type: str = Form(default=None),
    base_url: str = Form(default=None),
    models: str = Form(default=None),
):
    service = SettingsService()
    payload = {
        "id": id,
        "name": name,
        "provider_type": provider_type,
        "base_url": base_url,
        "models": models,
    }
    service.upsert_provider(payload)
    data = service.get_all_settings()
    from app.agents.agent_names import AGENT_NAMES

    template = templates.env.get_template("fragments/settings_providers.html")
    response = HTMLResponse(
        content=template.render(
            request=request,
            providers=data["providers"],
            agent_routes=data["agent_routes"],
            agent_names=AGENT_NAMES,
            presets=PROVIDER_PRESETS,
        )
    )
    response.headers["HX-Trigger"] = '{"showToast": {"value": "Provider updated", "type": "info"}}'
    return response


@router.post("/providers/{provider_id}/update", response_class=HTMLResponse)
async def settings_provider_update(
    request: Request,
    provider_id: int,
    name: str = Form(default=None),
    provider_type: str = Form(default=None),
    base_url: str = Form(default=None),
    models: str = Form(default=None),
):
    service = SettingsService()
    existing = service.get_provider_by_id(provider_id)
    if existing:
        payload = {
            "id": provider_id,
            "name": name or existing.name,
            "provider_type": provider_type or existing.provider_type,
            "base_url": base_url or existing.base_url,
            "models": models or existing.models,
        }
        service.upsert_provider(payload)
    data = service.get_all_settings()
    from app.agents.agent_names import AGENT_NAMES

    template = templates.env.get_template("fragments/settings_providers.html")
    return HTMLResponse(
        content=template.render(
            request=request,
            providers=data["providers"],
            agent_routes=data["agent_routes"],
            agent_names=AGENT_NAMES,
            presets=PROVIDER_PRESETS,
        )
    )


@router.post("/providers/{provider_id}/keys/{key_id}/edit", response_class=HTMLResponse)
async def settings_provider_edit_key(
    request: Request,
    provider_id: int,
    key_id: int,
    api_key: str = Form(...),
    priority: int = Form(default=0),
):
    service = SettingsService()
    service.upsert_provider_key(
        provider_id=provider_id, api_key=api_key, priority=priority, key_id=key_id
    )
    data = service.get_all_settings()
    from app.agents.agent_names import AGENT_NAMES

    template = templates.env.get_template("fragments/settings_providers.html")
    return HTMLResponse(
        content=template.render(
            request=request,
            providers=data["providers"],
            agent_routes=data["agent_routes"],
            agent_names=AGENT_NAMES,
            presets=PROVIDER_PRESETS,
        )
    )


@router.post("/providers/{provider_id}/keys", response_class=HTMLResponse)
async def settings_provider_add_key(
    request: Request,
    provider_id: int,
    api_key: str = Form(...),
    priority: int = Form(default=0),
):
    service = SettingsService()
    service.upsert_provider_key(
        provider_id=provider_id, api_key=api_key, priority=priority
    )
    data = service.get_all_settings()
    from app.agents.agent_names import AGENT_NAMES

    template = templates.env.get_template("fragments/settings_providers.html")
    return HTMLResponse(
        content=template.render(
            request=request,
            providers=data["providers"],
            agent_routes=data["agent_routes"],
            agent_names=AGENT_NAMES,
            presets=PROVIDER_PRESETS,
        )
    )


@router.post(
    "/providers/{provider_id}/keys/{key_id}/delete", response_class=HTMLResponse
)
async def settings_provider_delete_key(
    request: Request, provider_id: int, key_id: int
):
    service = SettingsService()
    service.delete_provider_key(key_id)
    data = service.get_all_settings()
    from app.agents.agent_names import AGENT_NAMES

    template = templates.env.get_template("fragments/settings_providers.html")
    return HTMLResponse(
        content=template.render(
            request=request,
            providers=data["providers"],
            agent_routes=data["agent_routes"],
            agent_names=AGENT_NAMES,
            presets=PROVIDER_PRESETS,
        )
    )


@router.post("/providers/{provider_id}/delete", response_class=HTMLResponse)
async def settings_provider_delete(request: Request, provider_id: int):
    service = SettingsService()
    service.delete_provider(provider_id)
    data = service.get_all_settings()
    from app.agents.agent_names import AGENT_NAMES

    template = templates.env.get_template("fragments/settings_providers.html")
    return HTMLResponse(
        content=template.render(
            request=request,
            providers=data["providers"],
            agent_routes=data["agent_routes"],
            agent_names=AGENT_NAMES,
            presets=PROVIDER_PRESETS,
        )
    )


@router.get("/tab/routes", response_class=HTMLResponse)
async def settings_tab_routes(request: Request):
    service = SettingsService()
    data = service.get_all_settings()
    from app.agents.agent_names import AGENT_NAMES

    template = templates.env.get_template("fragments/settings_routes.html")
    return HTMLResponse(
        content=template.render(
            request=request,
            agent_routes=data["agent_routes"],
            providers=data["providers"],
            agent_names=AGENT_NAMES,
        )
    )


@router.post("/routes/upsert", response_class=HTMLResponse)
async def settings_route_upsert(
    request: Request,
    task_type: str = Form(...),
    provider_id: int = Form(default=None),
    models: str = Form(default=None),
    priority: int = Form(default=0),
    route_id: int = Form(default=None),
):
    service = SettingsService()
    service.upsert_agent_route(
        task_type=task_type,
        provider_id=provider_id,
        models=models,
        priority=priority,
        route_id=route_id,
    )
    data = service.get_all_settings()
    from app.agents.agent_names import AGENT_NAMES

    template = templates.env.get_template("fragments/settings_routes.html")
    response = HTMLResponse(
        content=template.render(
            request=request,
            agent_routes=data["agent_routes"],
            providers=data["providers"],
            agent_names=AGENT_NAMES,
        )
    )
    response.headers["HX-Trigger"] = '{"showToast": {"value": "Route updated", "type": "info"}}'
    return response


@router.post("/routes/{route_id}/delete", response_class=HTMLResponse)
async def settings_route_delete(request: Request, route_id: int):
    service = SettingsService()
    service.delete_agent_route(route_id)
    data = service.get_all_settings()
    from app.agents.agent_names import AGENT_NAMES

    template = templates.env.get_template("fragments/settings_routes.html")
    return HTMLResponse(
        content=template.render(
            request=request,
            agent_routes=data["agent_routes"],
            providers=data["providers"],
            agent_names=AGENT_NAMES,
        )
    )


@router.post("/routes/{agent_name}/override", response_class=HTMLResponse)
async def settings_route_override(request: Request, agent_name: str):
    service = SettingsService()
    service.copy_default_routes_to_agent(agent_name)
    data = service.get_all_settings()
    from app.agents.agent_names import AGENT_NAMES

    template = templates.env.get_template("fragments/settings_routes.html")
    return HTMLResponse(
        content=template.render(
            request=request,
            agent_routes=data["agent_routes"],
            providers=data["providers"],
            agent_names=AGENT_NAMES,
        )
    )


@router.post("/routes/reorder", response_class=HTMLResponse)
async def settings_route_reorder(request: Request, route_ids: str = Form(...)):
    ids = json.loads(route_ids)
    service = SettingsService()
    service.reorder_routes(ids)
    data = service.get_all_settings()
    from app.agents.agent_names import AGENT_NAMES

    template = templates.env.get_template("fragments/settings_routes.html")
    return HTMLResponse(
        content=template.render(
            request=request,
            agent_routes=data["agent_routes"],
            providers=data["providers"],
            agent_names=AGENT_NAMES,
        )
    )


def _get_model_status():
    with Session(settings_engine) as session:
        repo = SettingsRepository(session)
        routes = repo.get_agent_routes()
        providers = {p.id: p for p in repo.get_providers()}
        route_status = []
        for route in routes:
            provider = providers.get(route.provider_id)
            route_status.append(
                {
                    "task_type": route.task_type,
                    "configured": bool(
                        provider and provider.provider_type and route.models
                    ),
                    "provider": provider.name if provider else None,
                    "models": route.models,
                }
            )
        return {"initialized": True, "routes": route_status}


@router.get("/tab/health", response_class=HTMLResponse)
async def settings_tab_health(request: Request):
    status = _get_model_status()
    template = templates.env.get_template("fragments/settings_health.html")
    return HTMLResponse(
        content=template.render(request=request, status=status)
    )


@router.post("/reset-health", response_class=HTMLResponse)
async def settings_reset_health(request: Request):
    service = SettingsService()
    service.reset_candidate_health()
    status = _get_model_status()
    template = templates.env.get_template("fragments/settings_health.html")
    return HTMLResponse(
        content=template.render(request=request, status=status)
    )
