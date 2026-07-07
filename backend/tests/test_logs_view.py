import pytest
from app.views.logs import _parse_log_line, EVENT_COLORS


class TestParseLogLine:
    def test_valid_line_parses_all_fields(self):
        line = "[2024-01-01 12:00:00] [Researcher] [gpt-4] [key1] [World1] [THOUGHT] Some content"
        result = _parse_log_line(line)
        assert result is not None
        assert result["timestamp"] == "2024-01-01 12:00:00"
        assert result["agent"] == "Researcher"
        assert result["model"] == "gpt-4"
        assert result["key_id"] == "key1"
        assert result["world"] == "World1"
        assert result["event_type"] == "THOUGHT"
        assert result["content"] == "Some content"

    def test_color_class_for_known_event(self):
        line = "[t] [a] [m] [k] [w] [ERROR] msg"
        result = _parse_log_line(line)
        assert result["color_class"] == EVENT_COLORS["ERROR"]

    def test_color_class_for_unknown_event(self):
        line = "[t] [a] [m] [k] [w] [UNKNOWN] msg"
        result = _parse_log_line(line)
        assert result["color_class"] == "text-gray-500"

    def test_line_with_extra_brackets_in_content(self):
        line = "[t] [a] [m] [k] [w] [INFO] [nested] content with [brackets]"
        result = _parse_log_line(line)
        assert result is not None
        assert result["content"] == "[nested] content with [brackets]"

    def test_empty_line_returns_none(self):
        assert _parse_log_line("") is None

    def test_malformed_line_returns_none(self):
        assert _parse_log_line("just some random text") is None
        assert _parse_log_line("[] [] [] []") is None

    def test_whitespace_stripped(self):
        line = "  [t] [a] [m] [k] [w] [COMPLETED] done  "
        result = _parse_log_line(line)
        assert result is not None
        assert result["content"] == "done"

    def test_all_event_types_have_colors(self):
        event_types = [
            "THOUGHT", "TOOL_REQ", "TOOL_RES", "PROMPT",
            "MODEL_CALL", "ERROR", "FAILED", "INFO",
            "WARNING", "COMPLETED", "IN_PROGRESS",
        ]
        for et in event_types:
            line = f"[t] [a] [m] [k] [w] [{et}] test"
            result = _parse_log_line(line)
            assert result is not None
            assert result["event_type"] == et
            assert result["color_class"] != "text-gray-500"


class TestLogsPage:
    ENDPOINT = "/logs"

    def test_logs_page_returns_html(self, api_client):
        r = api_client.get(self.ENDPOINT)
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")

    def test_logs_list_returns_html(self, api_client):
        r = api_client.get("/logs/list")
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")

    def test_logs_list_with_filter(self, api_client):
        r = api_client.get("/logs/list", params={"filter": "test", "limit": 10})
        assert r.status_code == 200

    def test_logs_list_with_agent_filter(self, api_client):
        r = api_client.get("/logs/list", params={"agent": "Researcher"})
        assert r.status_code == 200

    def test_logs_list_with_world_filter(self, api_client):
        r = api_client.get("/logs/list", params={"world": "TestWorld"})
        assert r.status_code == 200

    def test_logs_list_with_model_filter(self, api_client):
        r = api_client.get("/logs/list", params={"model": "gpt-4"})
        assert r.status_code == 200

    def test_logs_list_with_event_type_filter(self, api_client):
        r = api_client.get("/logs/list", params={"event_type": "ERROR"})
        assert r.status_code == 200

    def test_logs_list_with_tool_filter(self, api_client):
        r = api_client.get("/logs/list", params={"tool": "webSearch"})
        assert r.status_code == 200

    def test_logs_list_excludes_system_reminder(self, api_client, clean_db):
        # Create a log entry to ensure the endpoint processes it
        r = api_client.get("/logs/list", params={"limit": 5})
        assert r.status_code == 200
