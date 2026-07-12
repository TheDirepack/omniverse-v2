from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# from app.api.routers.inference import router as inference_router
from app.api.routers.providers import router as providers_router
from app.api.routers.research import router as research_router
from app.api.routers.routes import router as routes_router
from app.api.routers.runs import router as runs_router
from app.api.routers.settings import router as settings_router
from app.api.routers.unconfirmed import router as unconfirmed_router
from app.api.routers.worlds import router as worlds_router
from app.core.browser import browser_manager
from app.db.session import init_db
from app.views.flow import router as flow_views_router
from app.views.index import router as index_views_router
from app.views.knowledge import router as knowledge_views_router
from app.views.logs import router as logs_views_router
from app.views.provenance import router as provenance_views_router
from app.views.research import router as research_views_router
from app.views.settings import router as settings_views_router
from app.views.theory import router as theory_views_router
from app.views.validation import router as validation_views_router
from app.views.worlds import router as worlds_views_router

BASE_DIR = Path(__file__).resolve().parent

@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()

    # DB Connectivity check
    try:
        from sqlmodel import Session, text

        from app.db.session import engine
        with Session(engine) as session:
            session.exec(text("SELECT 1"))
        import logging
        logging.getLogger("startup").info("Database connectivity verified.")
    except Exception:
        import logging
        logging.getLogger("startup").exception("Database connectivity check failed")

    # Reconcile stale runs on startup
    from app.services.execution_service import ExecutionService
    exec_service = ExecutionService()
    exec_service.reconcile_stale_runs()
    exec_service.close()

    # Validate settings on startup
    from app.services.settings_service import SettingsService
    settings_service = SettingsService()
    issues = settings_service.validate_settings()
    for issue in issues:
        import logging
        level = logging.ERROR if issue["severity"] == "ERROR" else logging.WARNING
        logging.getLogger("startup").log(
            level, "Settings Validation %s: %s", issue["severity"], issue["message"]
        )

    await browser_manager.start()
    yield
    await browser_manager.stop()

app = FastAPI(
    title="Omniverse Tier List 2.0 API",
    description=(
        "Asynchronous multi-agent LangGraph platform for "
        "fictional power tiering"
    ),
    version="2.0.0",
    lifespan=lifespan,
)

# Set up CORS so frontend can communicate smoothly
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
# CSRF removed — local dev tool, cookie/header check adds friction without
# proportional benefit

@app.get("/api/health")
async def health():
    return {"status": "ok"}

app.include_router(index_views_router)
app.include_router(research_views_router, prefix="/research")
app.include_router(settings_views_router, prefix="/settings")
app.include_router(validation_views_router, prefix="/validation")
app.include_router(provenance_views_router, prefix="/provenance")
app.include_router(worlds_views_router, prefix="/worlds")
app.include_router(knowledge_views_router, prefix="/knowledge")
app.include_router(theory_views_router, prefix="/theory")

app.include_router(flow_views_router, prefix="/flow")
app.include_router(logs_views_router, prefix="/logs")
app.include_router(research_router, prefix="/api")
app.include_router(unconfirmed_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(routes_router, prefix="/api")
app.include_router(providers_router, prefix="/api")
app.include_router(worlds_router, prefix="/api")
app.include_router(runs_router, prefix="/api")
# app.include_router(inference_router, prefix="/api")
