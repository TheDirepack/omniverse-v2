from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.v2.api import build_router
from app.v2.config import V2Config
from app.v2.runtime import V2Runtime
from app.v2.views import router as views_router

APP_DIR = Path(__file__).resolve().parents[1]


def create_app(
    config: V2Config | None = None,
    *,
    runtime: V2Runtime | None = None,
    start_worker: bool | None = None,
) -> FastAPI:
    injected_runtime = runtime is not None
    value = runtime or V2Runtime.build(config or V2Config.from_env())
    should_start_worker = not injected_runtime if start_worker is None else start_worker

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.runtime = value
        await value.startup(start_worker=should_start_worker)
        try:
            yield
        finally:
            await value.shutdown()

    app = FastAPI(title="Omniverse V2", lifespan=lifespan)
    app.state.runtime = value
    app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
    app.include_router(views_router)
    app.include_router(build_router(value))
    return app


app = create_app()
