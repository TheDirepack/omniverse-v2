from fastapi import APIRouter

# Import individual routers
from app.api.v1.db.artifacts import router as artifacts_router
from app.api.v1.db.claims import router as claims_router
from app.api.v1.db.notebook import router as notebook_router
from app.api.v1.db.worlds import router as worlds_router
from app.api.v1.execution.runs import router as runs_router
from app.api.v1.settings import router as settings_router
from app.api.v1.tools import router as tools_router

# Create main router
api_router = APIRouter()

# DB operations
api_router.include_router(worlds_router, prefix="/db/worlds")
api_router.include_router(artifacts_router, prefix="/db/artifacts")

api_router.include_router(notebook_router, prefix="/db/notebook")

api_router.include_router(claims_router, prefix="/db/claims")

# Execution operations
api_router.include_router(runs_router, prefix="/execution/runs")

# Settings
api_router.include_router(settings_router, prefix="/settings")

# Tools
api_router.include_router(tools_router, prefix="/tools")

__all__ = ["api_router"]
