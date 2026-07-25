from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_LOG_DIR = Path(__file__).resolve().parents[2] / "logs"


class V2ServerLogger:
    def __init__(self, log_dir: Path | str = DEFAULT_LOG_DIR) -> None:
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)

        self._access_path = self._log_dir / "access.log"
        self._error_path = self._log_dir / "error.log"
        self._client_path = self._log_dir / "client.log"
        self._agent_path = self._log_dir / "agent.log"

    @staticmethod
    def _timestamp() -> str:
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).isoformat()

    def _append(self, path: Path, line: str) -> None:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()

    def _read_log_file(
        self,
        path: Path,
        cursor: int = 0,
        limit: int = 100,
        level_filter: str = "",
        search: str = "",
    ) -> dict[str, Any]:
        if not path.exists():
            return {"lines": [], "next_cursor": 0, "total_lines": 0}

        with open(path, "r", encoding="utf-8") as f:
            all_lines = f.readlines()

        filtered: list[str] = []
        for line in all_lines:
            if level_filter and level_filter not in line:
                continue
            if search and search not in line:
                continue
            filtered.append(line)

        total = len(filtered)
        end = cursor + limit
        page = [l.rstrip("\n") for l in filtered[cursor:end]]
        return {"lines": page, "next_cursor": end if end < total else total, "total_lines": total}

    def log_access(
        self,
        method: str,
        path: str,
        status: int,
        duration_ms: float,
        client_ip: str = "",
    ) -> None:
        line = (
            f"[{self._timestamp()}] [{method}] [{path}] [{status}] "
            f"[{duration_ms}] [{client_ip}]"
        )
        self._append(self._access_path, line)

    def log_error(
        self,
        level: str,
        source: str,
        status: int,
        path: str,
        message: str,
        traceback: str = "",
    ) -> None:
        line = (
            f"[{self._timestamp()}] [{level}] [{source}] [{status}] [{path}] "
            f"[{message}] [{traceback}]"
        )
        self._append(self._error_path, line)

    def log_client(
        self,
        level: str,
        source: str,
        message: str,
        url: str = "",
        user_agent: str = "",
        stack: str = "",
    ) -> None:
        line = (
            f"[{self._timestamp()}] [{level}] [{source}] [{message}] "
            f"[{url}] [{user_agent}] [{stack}]"
        )
        self._append(self._client_path, line)

    def log_agent(
        self,
        agent_name: str,
        event_type: str,
        world_name: str = "",
        run_id: str = "",
        step_kind: str = "",
        model: str = "",
        message: str = "",
    ) -> None:
        line = (
            f"[{self._timestamp()}] [{agent_name}] [{event_type}] "
            f"[{world_name}] [{run_id}] [{step_kind}] [{model}] [{message}]"
        )
        self._append(self._agent_path, line)

    def log_settings_action(self, action: str, details: dict) -> None:
        line = f"[{self._timestamp()}] [SETTINGS] [{action}] {json.dumps(details)}"
        self._append(self._access_path, line)

    def clear_logs(self) -> dict[str, bool]:
        result: dict[str, bool] = {}
        for name, path in [
            ("access.log", self._access_path),
            ("error.log", self._error_path),
            ("client.log", self._client_path),
            ("agent.log", self._agent_path),
        ]:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.truncate(0)
                result[name] = True
            except OSError:
                result[name] = False
        return result

    def read_log(
        self,
        log_type: str,
        cursor: int = 0,
        limit: int = 100,
        level_filter: str = "",
        search: str = "",
    ) -> dict[str, Any]:
        match log_type:
            case "access":
                path = self._access_path
            case "error":
                path = self._error_path
            case "client":
                path = self._client_path
            case "agent":
                path = self._agent_path
            case _:
                raise ValueError(f"Unknown log_type: {log_type!r}, expected access/error/client/agent")
        return self._read_log_file(path, cursor, limit, level_filter, search)
