from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.session import init_db
from app.api.routes import router
from app.core.browser import browser_manager

app = FastAPI(
    title="Omniverse Tier List 2.0 API",
    description="Asynchronous multi-agent LangGraph platform for fictional power tiering",
    version="2.0.0"
)

# Set up CORS so frontend can communicate smoothly
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def on_startup():
    # Automatically initialize SQLModel tables in SQLite
    init_db()
    await browser_manager.start()

@app.on_event("shutdown")
async def on_shutdown():
    await browser_manager.stop()

app.include_router(router, prefix="/api")
