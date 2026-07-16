import json
from pathlib import Path

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates


def compute_resolved_fallback(
    routes: list[dict], providers: list[dict]
) -> list[dict]:
    resolved = []
    seen = set()
    sorted_routes = sorted(routes, key=lambda r: r.get("priority", 0) or 0)
    for route in sorted_routes:
        provider = next(
            (p for p in providers if p.get("id") == route.get("provider_id")), None
        )
        if not provider:
            continue
        models_str = (route.get("models") or provider.get("models") or "").strip()
        models = [m.strip() for m in models_str.split(",") if m.strip()]
        keys = provider.get("keys") or [{}]
        for k_idx in range(len(keys)):
            for model in models:
                dedup_key = f"{provider['id']}:{k_idx}:{model}"
                if dedup_key not in seen:
                    resolved.append(
                        {
                            "provider": provider.get("name", "?"),
                            "key_label": f"Key {k_idx + 1}"
                            if provider.get("keys")
                            else "No Key",
                            "model": model,
                        }
                    )
                    seen.add(dedup_key)
    return resolved


def json_decode(value):
    if isinstance(value, str):
        return json.loads(value)
    return value or []


def init_jinja(env):
    env.globals["compute_resolved_fallback"] = compute_resolved_fallback
    env.filters["json_decode"] = json_decode


templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))
templates.env.auto_reload = True
init_jinja(templates.env)


def render_worlds_table(
    request: Request, worlds, q=None, explored=None, franchise=None,
    batch_started=False,
) -> HTMLResponse:
    from fastapi.responses import HTMLResponse

    template = templates.env.get_template("components/database_worlds.html")
    return HTMLResponse(
        content=template.render(
            request=request,
            worlds=worlds,
            q=q,
            explored=explored,
            franchise=franchise,
            batch_started=batch_started,
        )
    )


def render_error(request: Request, status: int, message: str) -> HTMLResponse:
    from fastapi.responses import HTMLResponse
    template = templates.env.get_template("pages/error.html")
    current_path = str(request.url.path) if hasattr(request, 'url') else '/'
    return HTMLResponse(
        content=template.render(request=request, status=status, message=message, current_path=current_path),
        status_code=status,
    )
