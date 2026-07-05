from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.session import init_db
from app.api.routers.providers import router as providers_router
from app.api.routers.research import router as research_router
from app.api.routers.settings import router as settings_router
from app.api.routers.worlds import router as worlds_router
from app.api.routers.runs import router as runs_router
from app.core.browser import browser_manager

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    await browser_manager.start()
    yield
    await browser_manager.stop()

app = FastAPI(
    title="Omniverse Tier List 2.0 API",
    description="Asynchronous multi-agent LangGraph platform for fictional power tiering",
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

app.include_router(providers_router, prefix="/api")
app.include_router(research_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(worlds_router, prefix="/api")
app.include_router(runs_router, prefix="/api")
