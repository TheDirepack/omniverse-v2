from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles

from app.v2.api import build_router
from app.v2.config import V2Config
from app.v2.logging import V2ServerLogger
from app.v2.runtime import V2Runtime
from app.v2.views import router as views_router

APP_DIR = Path(__file__).resolve().parents[1]


def _log_middleware(server_logger: V2ServerLogger):
    async def middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        start = time.perf_counter()
        ip = request.client.host if request.client else ""
        method = request.method
        path = request.url.path
        status = 0

        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        status = response.status_code

        server_logger.log_access(method, path, status, duration_ms, ip)

        if status >= 400:
            server_logger.log_error(
                "ERROR" if status >= 500 else "WARN",
                "middleware",
                status,
                path,
                f"{method} {path} returned {status}",
            )

        return response

    return middleware


def create_app(
    config: V2Config | None = None,
    *,
    runtime: V2Runtime | None = None,
    start_worker: bool | None = None,
) -> FastAPI:
    injected_runtime = runtime is not None
    if injected_runtime:
        server_logger = runtime.server_logger or V2ServerLogger()
        value = runtime
    else:
        server_logger = V2ServerLogger()
        value = V2Runtime.build(config or V2Config.from_env(), server_logger=server_logger)
    should_start_worker = not injected_runtime if start_worker is None else start_worker

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.runtime = value
        app.state.server_logger = server_logger
        await value.startup(start_worker=should_start_worker)
        try:
            yield
        finally:
            await value.shutdown()

    app = FastAPI(title="Omniverse V2", lifespan=lifespan)
    app.state.runtime = value
    app.state.server_logger = server_logger
    app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
    app.middleware("http")(_log_middleware(app.state.server_logger))
    app.include_router(views_router)
    app.include_router(build_router(value))
    return app


app = create_app()
