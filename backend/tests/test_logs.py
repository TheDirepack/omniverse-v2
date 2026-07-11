from fastapi.testclient import TestClient

from app.core.agent_logger import LOG_FILE
from app.main import app

client = TestClient(app)

def setup_module(_module):
    """Setup module-level resources."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOG_FILE.write_text("")

def teardown_module(_module):
    """Teardown module-level resources."""
    if LOG_FILE.exists():
        LOG_FILE.unlink()

def setup_function(_function):
    """Setup function-level resources."""
    LOG_FILE.write_text("")

def write_logs(lines):
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.writelines(line + "\n" for line in lines)

def test_logs_page_renders():
    resp = client.get("/logs/")
    assert resp.status_code == 200
    assert "System Agent Logs" in resp.text
    assert "log-filters" in resp.text

def test_logs_list_empty():
    resp = client.get("/logs/list")
    assert resp.status_code == 200
    assert "No logs found." in resp.text

def test_logs_list_all():
    write_logs([
        "[2026-07-07 10:00:00] [AgentA] [ModelA] [key1] [WorldA] [INFO] Message 1",
        "[2026-07-07 10:01:00] [AgentB] [ModelB] [key2] [WorldB] [ERROR] Message 2",
    ])
    resp = client.get("/logs/list")
    assert resp.status_code == 200
    assert "Message 1" in resp.text
    assert "Message 2" in resp.text
    assert "AgentA" in resp.text
    assert "AgentB" in resp.text

def test_logs_filter_agent():
    write_logs([
        "[2026-07-07 10:00:00] [AgentA] [ModelA] [key1] [WorldA] [INFO] Message 1",
        "[2026-07-07 10:01:00] [AgentB] [ModelB] [key2] [WorldB] [ERROR] Message 2",
    ])
    resp = client.get("/logs/list?agent=AgentA")
    assert resp.status_code == 200
    assert "Message 1" in resp.text
    assert "Message 2" not in resp.text

def test_logs_filter_world():
    write_logs([
        "[2026-07-07 10:00:00] [AgentA] [ModelA] [key1] [WorldA] [INFO] Message 1",
        "[2026-07-07 10:01:00] [AgentB] [ModelB] [key2] [WorldB] [ERROR] Message 2",
    ])
    resp = client.get("/logs/list?world=WorldB")
    assert resp.status_code == 200
    assert "Message 2" in resp.text
    assert "Message 1" not in resp.text

def test_logs_filter_model():
    write_logs([
        "[2026-07-07 10:00:00] [AgentA] [ModelA] [key1] [WorldA] [INFO] Message 1",
        "[2026-07-07 10:01:00] [AgentB] [ModelB] [key2] [WorldB] [ERROR] Message 2",
    ])
    resp = client.get("/logs/list?model=ModelB")
    assert resp.status_code == 200
    assert "Message 2" in resp.text
    assert "Message 1" not in resp.text

def test_logs_filter_event_type():
    write_logs([
        "[2026-07-07 10:00:00] [AgentA] [ModelA] [key1] [WorldA] [INFO] Message 1",
        "[2026-07-07 10:01:00] [AgentB] [ModelB] [key2] [WorldB] [ERROR] Message 2",
    ])
    resp = client.get("/logs/list?event_type=ERROR")
    assert resp.status_code == 200
    assert "Message 2" in resp.text
    assert "Message 1" not in resp.text

def test_logs_filter_tool():
    write_logs([
        (
            "[2026-07-07 10:00:00] [AgentA] [ModelA] [key1] [WorldA] "
            "[TOOL_RES] webSearch: result"
        ),
        "[2026-07-07 10:01:00] [AgentB] [ModelB] [key2] [WorldB] [INFO] Other message",
    ])
    resp = client.get("/logs/list?tool=webSearch")
    assert resp.status_code == 200
    assert "webSearch" in resp.text
    assert "Other message" not in resp.text

def test_logs_filter_search():
    write_logs([
        (
            "[2026-07-07 10:00:00] [AgentA] [ModelA] [key1] [WorldA] "
            "[INFO] Important message"
        ),
        (
            "[2026-07-07 10:01:00] [AgentB] [ModelB] [key2] [WorldB] "
            "[ERROR] Regular message"
        ),
    ])
    resp = client.get("/logs/list?filter=Important")
    assert resp.status_code == 200
    assert "Important message" in resp.text
    assert "Regular message" not in resp.text

def test_logs_pagination():
    write_logs([
        f"[2026-07-07 10:00:{i:02d}] [AgentA] [ModelA] [k] [W] [INFO] msg {i}"
        for i in range(15)
    ])

    # Check first page (newest logs: 5 to 14)
    resp = client.get("/logs/list?limit=10&offset=0")
    assert resp.status_code == 200
    assert "msg 14" in resp.text
    assert "msg 5" in resp.text
    assert "msg 4" not in resp.text
    assert "Load More" in resp.text

    # Check second page (older logs: 0 to 4)
    resp = client.get("/logs/list?limit=10&offset=10")
    assert resp.status_code == 200
    assert "msg 4" in resp.text
    assert "msg 0" in resp.text
    assert "msg 5" not in resp.text
    assert "Load More" not in resp.text

