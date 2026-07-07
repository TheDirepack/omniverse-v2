from app.db.schema import Universe
from app.db.session import engine as main_engine
from app.main import app
from fastapi.testclient import TestClient
from sqlmodel import Session, select

client = TestClient(app)
