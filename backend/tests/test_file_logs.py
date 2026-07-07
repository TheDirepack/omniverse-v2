from app.core.agent_logger import LOG_FILE


def test_get_file_logs_basic(client):
    # Setup: Create a dummy log file
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("Line 1: Error\nLine 2: Success\nLine 3: Warning\n")

    # Test fetching all logs
    response = client.get("/api/runs/logs/file")
    assert response.status_code == 200
    data = response.json()
    logs = data["logs"]
    assert len(logs) == 3
    assert "Line 1: Error" in logs[0]
    assert "Line 3: Warning" in logs[2]


def test_get_file_logs_filter(client):
    # Setup: Create dummy log file
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("Line 1: Error in auth\nLine 2: Success in db\nLine 3: Error in api\n")

    # Test filtering for "Error"
    response = client.get("/api/runs/logs/file?filter=Error")
    assert response.status_code == 200
    logs = response.json()["logs"]
    assert len(logs) == 2
    assert all("Error" in line for line in logs)

    # Test filtering for "Success"
    response = client.get("/api/runs/logs/file?filter=Success")
    assert response.status_code == 200
    logs = response.json()["logs"]
    assert len(logs) == 1
    assert "Success" in logs[0]


def test_get_file_logs_limit(client):
    # Setup: Create a log file with many lines
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        for i in range(150):
            f.write(f"Log line {i}\n")

    # Test limit of 100 (default)
    response = client.get("/api/runs/logs/file")
    assert response.status_code == 200
    logs = response.json()["logs"]
    assert len(logs) == 100
    assert "Log line 149" in logs[-1]

    # Test custom limit of 10
    response = client.get("/api/runs/logs/file?limit=10")
    assert response.status_code == 200
    logs = response.json()["logs"]
    assert len(logs) == 10
    assert "Log line 149" in logs[-1]


def test_get_file_logs_no_file(client):
    # Setup: Ensure log file does not exist
    if LOG_FILE.exists():
        LOG_FILE.unlink()

    response = client.get("/api/runs/logs/file")
    assert response.status_code == 200
    assert response.json() == {"logs": [], "total": 0, "has_more": False}
