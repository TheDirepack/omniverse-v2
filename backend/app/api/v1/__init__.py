import sys
from fastapi import APIRouter

# Import individual routers
from app.api.v1.db.artifacts import router as artifacts_router
from app.api.v1.db.notebook import router as notebook_router
from app.api.v1.db.claims import router as claims_router
from app.api.v1.execution.runs import router as runs_router
from app.api.v1.settings import router as settings_router
from app.api.v1.tools import router as tools_router

# Create main router
api_router = APIRouter()

api_router.include_router(artifacts_router, prefix="/db/artifacts")

api_router.include_router(notebook_router, prefix="/db/notebook")

api_router.include_router(claims_router, prefix="/db/claims")

api_router.include_router(runs_router, prefix="/execution/runs")

api_router.include_router(settings_router, prefix="/settings")

api_router.include_router(tools_router, prefix="/tools")

__all__ = ["api_router"]
