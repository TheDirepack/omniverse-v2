import json
import shutil
from datetime import UTC, datetime, timezone
from pathlib import Path

import httpx
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from app.core.router import router as model_router
from app.core.templates import templates
from app.db.notebook_schema import Snapshot
from app.db.notebook_session import notebook_engine
from app.db.operational_session import operational_engine
from app.db.schema import CandidateHealth
from app.db.settings_session import settings_engine
from app.repositories.settings import SettingsRepository
from app.services.settings_service import PROVIDER_PRESETS, SettingsService

router = APIRouter(tags=["settings_views"])


def _render_providers(
    request: Request,
    data: dict,
    active_provider_id: int | None = None,
) -> HTMLResponse:
    from app.agents.agent_names import AGENT_NAMES

    active_provider = None
    if active_provider_id is not None:
        active_provider = next(
            (p for p in data["providers"] if p["id"] == active_provider_id), None
        )
    elif data["providers"]:
        active_provider = data["providers"][0]
        active_provider_id = active_provider["id"]

    template = templates.env.get_template("components/settings_providers.html")
    return HTMLResponse(
        content=template.render(
            request=request,
            providers=data["providers"],
            routes=data["agent_routes"],
            agent_names=AGENT_NAMES,
            presets=PROVIDER_PRESETS,
            active_provider=active_provider,
            active_provider_id=active_provider_id,
        )
    )


@router.get("/", response_class=HTMLResponse)
async def settings_page(request: Request):
    template = templates.env.get_template("pages/settings.html")
    return HTMLResponse(content=template.render(
        request=request, current_path=str(request.url.path)
    ))


@router.get("/tab/general", response_class=HTMLResponse)
async def settings_tab_general(request: Request):
    service = SettingsService()
    data = service.get_all_settings()
    template = templates.env.get_template("components/settings_general.html")
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
    template = templates.env.get_template("components/settings_general.html")
    response = HTMLResponse(
        content=template.render(request=request, settings=data["general_settings"])
    )
    response.headers["HX-Trigger"] = (
        '{"showToast": {"value": "Setting updated", "type": "info"}}'
    )
    return response


@router.post("/general/delete", response_class=HTMLResponse)
async def settings_general_delete(request: Request, key: str = Form(...)):
    service = SettingsService()
    service.update_general_setting(key, None)
    data = service.get_all_settings()
    template = templates.env.get_template("components/settings_general.html")
    return HTMLResponse(
        content=template.render(request=request, settings=data["general_settings"])
    )


@router.get("/tab/providers", response_class=HTMLResponse)
async def settings_tab_providers(request: Request):
    service = SettingsService()
    data = service.get_all_settings()
    return _render_providers(request, data)


@router.get("/providers/new", response_class=HTMLResponse)
async def settings_providers_new(request: Request):
    service = SettingsService()
    data = service.get_all_settings()
    return _render_providers(request, data, active_provider_id=-1)


@router.get("/providers/{provider_id}", response_class=HTMLResponse)
async def settings_provider_detail(request: Request, provider_id: int):
    service = SettingsService()
    provider = service.get_provider_by_id(provider_id)
    if not provider:
        return HTMLResponse("Provider not found", status_code=404)

    from sqlmodel import Session

    from app.db.settings_session import settings_engine
    from app.repositories.settings import SettingsRepository
    with Session(settings_engine) as session:
        repo = SettingsRepository(session)
        api_keys = repo.get_keys_for_provider(provider_id)

    template = templates.env.get_template("components/provider_form.html")
    return HTMLResponse(content=template.render(
        request=request, active_provider=provider, api_keys=api_keys, presets=PROVIDER_PRESETS
    ))


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
    result = service.upsert_provider(payload)
    data = service.get_all_settings()
    response = _render_providers(request, data, active_provider_id=result["provider"]["id"])
    response.headers["HX-Trigger"] = (
        '{"showToast": {"value": "Provider updated", "type": "info"}}'
    )
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
    return _render_providers(request, data, active_provider_id=provider_id)


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
    return _render_providers(request, data, active_provider_id=provider_id)


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
    return _render_providers(request, data, active_provider_id=provider_id)


@router.post(
    "/providers/{provider_id}/keys/{key_id}/delete", response_class=HTMLResponse
)
async def settings_provider_delete_key(
    request: Request, provider_id: int, key_id: int
):
    service = SettingsService()
    service.delete_provider_key(key_id)
    data = service.get_all_settings()
    return _render_providers(request, data, active_provider_id=provider_id)


@router.post("/providers/{provider_id}/delete", response_class=HTMLResponse)
async def settings_provider_delete(request: Request, provider_id: int):
    service = SettingsService()
    service.delete_provider(provider_id)
    data = service.get_all_settings()
    return _render_providers(request, data)


@router.post("/providers/{provider_id}/sync", response_class=HTMLResponse)
async def settings_provider_sync(_request: Request, provider_id: int):
    service = SettingsService()
    try:
        models = service.sync_provider_models(provider_id)
        return HTMLResponse(content=models)
    except (ValueError, TypeError, KeyError, ConnectionError, OSError, httpx.HTTPStatusError, httpx.RequestError) as e:
        return HTMLResponse(f"Sync failed: {e!s}", status_code=500)


@router.post("/providers/{provider_id}/sync-models", response_class=HTMLResponse)
async def settings_provider_sync_models(_request: Request, provider_id: int):
    try:
        result = await model_router.sync_provider_models(provider_id)
        if result["errors"]:
            summary = (
                f"Sync: {result['total']} found, {result['active']} active, "
                f"{result['blacklisted']} blacklisted. Errors: {'; '.join(result['errors'][:3])}"
            )
        else:
            summary = (
                f"Sync: {result['total']} models found, "
                f"{result['active']} active, {result['blacklisted']} blacklisted"
            )
        import json
        return HTMLResponse(
            content="",
            headers={
                "HX-Trigger": json.dumps({"showToast": {"value": summary, "type": "info"}})
            },
        )
    except Exception as e:
        import json
        return HTMLResponse(
            content="",
            status_code=500,
            headers={
                "HX-Trigger": json.dumps({"showToast": {"value": f"Sync failed: {e!s}", "type": "error"}})
            },
        )


@router.get("/tab/routes", response_class=HTMLResponse)
async def settings_tab_routes(request: Request):
    service = SettingsService()
    data = service.get_all_settings()
    from app.agents.agent_names import AGENT_NAMES

    template = templates.env.get_template("components/settings_routes.html")
    return HTMLResponse(
        content=template.render(
            request=request,
            routes=data["agent_routes"],
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

    template = templates.env.get_template("components/settings_routes.html")
    response = HTMLResponse(
        content=template.render(
            request=request,
            routes=data["agent_routes"],
            providers=data["providers"],
            agent_names=AGENT_NAMES,
        )
    )
    response.headers["HX-Trigger"] = (
        '{"showToast": {"value": "Route updated", "type": "info"}}'
    )
    return response


@router.post("/routes/{route_id}/delete", response_class=HTMLResponse)
async def settings_route_delete(request: Request, route_id: int):
    service = SettingsService()
    service.delete_agent_route(route_id)
    data = service.get_all_settings()
    from app.agents.agent_names import AGENT_NAMES

    template = templates.env.get_template("components/settings_routes.html")
    return HTMLResponse(
        content=template.render(
            request=request,
            routes=data["agent_routes"],
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

    template = templates.env.get_template("components/settings_routes.html")
    return HTMLResponse(
        content=template.render(
            request=request,
            routes=data["agent_routes"],
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

    template = templates.env.get_template("components/settings_routes.html")
    return HTMLResponse(
        content=template.render(
            request=request,
            routes=data["agent_routes"],
            providers=data["providers"],
            agent_names=AGENT_NAMES,
        )
    )


@router.get("/routes/new", response_class=HTMLResponse)
async def settings_routes_new(request: Request):
    service = SettingsService()
    providers = service.get_providers()
    template = templates.env.get_template("components/route_form.html")
    return HTMLResponse(content=template.render(request=request, active_route=None, providers=providers))


@router.get("/routes/{route_id}", response_class=HTMLResponse)
async def settings_route_detail(request: Request, route_id: int):
    service = SettingsService()
    route = service.get_agent_route_by_id(route_id)
    if not route:
        return HTMLResponse("Route not found", status_code=404)

    providers = service.get_providers()
    template = templates.env.get_template("components/route_form.html")
    return HTMLResponse(content=template.render(request=request, active_route=route, providers=providers))


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
                        provider and provider.provider_type
                    ),
                    "provider": provider.name if provider else None,
                    "models": route.models,
                }
            )
        return {"initialized": True, "routes": route_status}


def _ensure_utc(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _get_circuit_breakers():
    with Session(operational_engine) as session:
        breakers = session.exec(
            select(CandidateHealth).order_by(CandidateHealth.failure_count.desc())
        ).all()
        for b in breakers:
            b.disabled_until = _ensure_utc(b.disabled_until)
        return breakers


@router.get("/tab/health", response_class=HTMLResponse)
async def settings_tab_health(request: Request):
    status = _get_model_status()
    circuit_breakers = _get_circuit_breakers()
    template = templates.env.get_template("components/settings_health.html")

    with Session(notebook_engine) as session:
        snapshots = session.exec(select(Snapshot)).all()

    now = datetime.now(UTC)
    return HTMLResponse(
        content=template.render(
            request=request,
            status=status,
            snapshots=snapshots,
            circuit_breakers=circuit_breakers,
            now=now,
        )
    )


@router.post("/reset-db", response_class=HTMLResponse)
async def settings_reset_db(_request: Request, db_name: str = Form(...)):
    from app.db.extrapolation_session import reset_extrapolation_db
    from app.db.notebook_session import reset_notebook_db
    from app.db.operational_session import reset_operational_db
    from app.db.session import reset_main_db
    from app.db.settings_session import reset_settings_db

    db_map = {
        "main": reset_main_db,
        "settings": reset_settings_db,
        "operational": reset_operational_db,
        "notebook": reset_notebook_db,
        "extrapolation": reset_extrapolation_db,
    }

    if db_name not in db_map and db_name != "all":
        return HTMLResponse(
            "<div class='p-4 bg-red-900 text-white rounded'>"
            f"Unknown database: {db_name}</div>",
        )

    if db_name == "all":
        for fn in db_map.values():
            fn()
    else:
        db_map[db_name]()

    return HTMLResponse(
        content=(
            f'<div class="p-4 bg-green-900 text-white rounded">'
            f'Database "{db_name}" reset successfully. '
            f'Page will reload.</div>'
        ),
        headers={"HX-Refresh": "true"}
    )


@router.post("/reset-health", response_class=HTMLResponse)
async def settings_reset_health(request: Request):
    service = SettingsService()
    service.reset_candidate_health()
    status = _get_model_status()
    circuit_breakers = _get_circuit_breakers()
    template = templates.env.get_template("components/settings_health.html")

    with Session(notebook_engine) as session:
        snapshots = session.exec(select(Snapshot)).all()

    now = datetime.now(UTC)
    return HTMLResponse(
        content=template.render(
            request=request,
            status=status,
            snapshots=snapshots,
            circuit_breakers=circuit_breakers,
            now=now,
        )
    )


@router.post("/reset-health/{candidate_hash}", response_class=HTMLResponse)
async def settings_reset_single_health(request: Request, candidate_hash: str):
    with Session(operational_engine) as session:
        health = session.get(CandidateHealth, candidate_hash)
        if health:
            session.delete(health)
            session.commit()

    status = _get_model_status()
    circuit_breakers = _get_circuit_breakers()
    template = templates.env.get_template("components/settings_health.html")

    with Session(notebook_engine) as session:
        snapshots = session.exec(select(Snapshot)).all()

    now = datetime.now(UTC)
    return HTMLResponse(
        content=template.render(
            request=request,
            status=status,
            snapshots=snapshots,
            circuit_breakers=circuit_breakers,
            now=now,
        )
    )


@router.get("/snapshots", response_class=HTMLResponse)
async def settings_snapshots_fragment(request: Request):
    with Session(notebook_engine) as session:
        snapshots = session.exec(select(Snapshot)).all()

    template = templates.env.get_template("components/world_snapshots.html")
    return HTMLResponse(content=template.render(request=request, snapshots=snapshots, snapshot_url_prefix="/settings"))


@router.post("/snapshots/create", response_class=HTMLResponse)
async def settings_snapshots_create_action(
    request: Request,
    name: str = Form(...),
    snapshot_type: str = Form("FULL")
):
    data_dir = Path(__file__).parent.parent.parent / "data"
    snapshot_dir = data_dir / "snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    with Session(notebook_engine) as session:
        snapshot = Snapshot(
            name=name,
            snapshot_type=snapshot_type,
            metadata="Database state captured via UI."
        )
        session.add(snapshot)
        session.commit()
        session.refresh(snapshot)

        s_dir = snapshot_dir / str(snapshot.id)
        s_dir.mkdir(exist_ok=True)
        for db_file in [
            "omniverse_v2.db",
            "settings.db",
            "operational.db",
            "notebook.db",
            "extrapolation.db",
        ]:
            src = data_dir / db_file
            if src.exists():
                shutil.copy2(src, s_dir / db_file)

    return await settings_snapshots_fragment(request)


@router.delete("/snapshots/{snapshot_id}", response_class=HTMLResponse)
async def settings_snapshots_delete_action(request: Request, snapshot_id: int):
    data_dir = Path(__file__).parent.parent.parent / "data"

    with Session(notebook_engine) as session:
        snapshot = session.get(Snapshot, snapshot_id)
        if snapshot:
            s_dir = data_dir / "snapshots" / str(snapshot.id)
            if s_dir.exists():
                shutil.rmtree(s_dir)
            session.delete(snapshot)
            session.commit()

    return await settings_snapshots_fragment(request)


@router.post("/snapshots/{snapshot_id}/restore", response_class=HTMLResponse)
async def settings_snapshots_restore_action(_request: Request, snapshot_id: int):
    data_dir = Path(__file__).parent.parent.parent / "data"

    with Session(notebook_engine) as session:
        snapshot = session.get(Snapshot, snapshot_id)
        if not snapshot:
            return HTMLResponse(
                "<p class='text-red-500'>Snapshot not found.</p>", status_code=404
            )

        s_dir = data_dir / "snapshots" / str(snapshot.id)
        if not s_dir.exists():
            return HTMLResponse(
                "<p class='text-red-500'>Snapshot files missing.</p>", status_code=404
            )

        for db_file in [
            "omniverse_v2.db",
            "settings.db",
            "operational.db",
            "notebook.db",
            "extrapolation.db",
        ]:
            src = s_dir / db_file
            if src.exists():
                shutil.copy2(src, data_dir / db_file)

    return HTMLResponse(
        content=(
            f'<div class="p-4 bg-green-900 text-white rounded">'
            f'Snapshot "{snapshot.name}" restored successfully. '
            f'Page will reload.</div>'
        ),
        headers={"HX-Refresh": "true"}
    )
