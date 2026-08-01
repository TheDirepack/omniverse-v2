from __future__ import annotations

import re
import time
import traceback
import uuid
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles

from app.v2.api import build_router
from app.v2.config import V2Config
from app.v2.logging import V2ServerLogger, bind_request_id, reset_request_id
from app.v2.runtime import V2Runtime
from app.v2.views import router as views_router

APP_DIR = Path(__file__).resolve().parents[1]
_REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9._:-]{1,128}\Z")


def _application_traceback(error: Exception) -> str:
    frames = traceback.extract_tb(error.__traceback__)
    relevant = [
        frame
        for frame in frames
        if "/app/" in frame.filename or "/tests_v2/" in frame.filename
    ]
    return "".join(traceback.format_list(relevant or frames[-8:]))


def _log_middleware(server_logger: V2ServerLogger):
    async def middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start = time.perf_counter()
        ip = request.client.host if request.client else ""
        method = request.method
        path = request.url.path
        supplied_request_id = request.headers.get("X-Request-ID", "")
        request_id = (
            supplied_request_id
            if _REQUEST_ID_PATTERN.fullmatch(supplied_request_id)
            else str(uuid.uuid4())
        )
        token = bind_request_id(request_id)
        try:
            response = await call_next(request)
        except Exception as error:
            duration_ms = round((time.perf_counter() - start) * 1000, 1)
            server_logger.log_event(
                "server",
                "ERROR",
                "http.request.unhandled_exception",
                "middleware",
                f"Unhandled {type(error).__name__}",
                data={
                    "method": method,
                    "path": path,
                    "status": 500,
                    "duration_ms": duration_ms,
                    "client_ip": ip,
                    "exception_class": type(error).__name__,
                    "traceback": _application_traceback(error),
                },
                request_id=request_id,
            )
            raise
        else:
            duration_ms = round((time.perf_counter() - start) * 1000, 1)
            response.headers["X-Request-ID"] = request_id
            server_logger.log_access(
                method, path, response.status_code, duration_ms, ip, request_id
            )
            return response
        finally:
            reset_request_id(token)

    return middleware


def create_app(
    config: V2Config | None = None,
    *,
    runtime: V2Runtime | None = None,
    start_worker: bool | None = None,
) -> FastAPI:
    injected_runtime = runtime is not None
    if injected_runtime:
        value = runtime
    else:
        value = V2Runtime.build(config or V2Config.from_env())
    server_logger = value.server_logger
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
