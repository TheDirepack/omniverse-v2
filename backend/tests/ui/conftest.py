import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Create a test client"""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def cleanup_after_test():
    """Cleanup fixture to run after each test"""
    yield
    # Cleanup can be added here if needed
