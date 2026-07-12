import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_min_research_turns_default(client):
    """Test that MIN_RESEARCH_TURNS defaults to 6."""
    resp = client.get("/api/settings", follow_redirects=True)
    assert resp.status_code == 200
    data = resp.json()
    assert data["general_settings"]["MIN_RESEARCH_TURNS"] == "6"


def test_min_research_turns_update(client):
    """Test updating MIN_RESEARCH_TURNS setting."""
    # Update to 10
    resp = client.post(
        "/api/settings/general",
        json={"key": "MIN_RESEARCH_TURNS", "value": "10"},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    # Verify update
    resp = client.get("/api/settings", follow_redirects=True)
    assert resp.status_code == 200
    data = resp.json()
    assert data["general_settings"]["MIN_RESEARCH_TURNS"] == "10"


def test_min_research_turns_validation(client):
    """Test that MIN_RESEARCH_TURNS validation works."""
    from app.services.settings_service import SettingsService

    service = SettingsService()
    issues = service.validate_settings()

    # Should not have errors about MIN_RESEARCH_TURNS
    min_turns_issues = [
        i for i in issues
        if "MIN_RESEARCH_TURNS" in i["message"]
    ]
    # Should only have WARNING (not ERROR)
    assert all(i["severity"] == "WARNING" for i in min_turns_issues)
