import time
from pathlib import Path
from typing import Callable

from loop.loop_config import AGENT_LOG_FILE


class LogMonitor:
    def __init__(self, log_path: Path = AGENT_LOG_FILE, poll_interval: float = 1.0):
        self.log_path = log_path
        self.poll_interval = poll_interval
        self._last_position = 0
        self._lines: list[str] = []

    def tail(self) -> list[str]:
        if not self.log_path.exists():
            return []
        content = self.log_path.read_text(encoding="utf-8")
        lines = content.splitlines()
        new_lines = lines[self._last_position:]
        self._last_position = len(lines)
        self._lines.extend(new_lines)
        return new_lines

    def get_all(self) -> str:
        if not self.log_path.exists():
            return ""
        return self.log_path.read_text(encoding="utf-8")

    def has_error(self) -> tuple[bool, str]:
        new = self.tail()
        for line in new:
            if "ERROR" in line.upper() or "FAILED" in line.upper() or "CRITICAL" in line.upper():
                return True, line
        return False, ""

    def has_completion(self, run_id: str | None = None) -> bool:
        new = self.tail()
        for line in new:
            if run_id:
                if run_id in line and ("COMPLETED" in line or "FINISHED" in line):
                    return True
            if "[COMPLETED]" in line or "[FINISHED]" in line:
                if "FAILED" not in line:
                    return True
        return False

    def has_failure(self, run_id: str | None = None) -> tuple[bool, str]:
        new = self.tail()
        for line in new:
            if run_id and run_id not in line:
                continue
            if "[FAILED]" in line:
                return True, line
        return False, ""

    def wait_for_completion_or_error(
        self,
        timeout: float = 600.0,
        poll_interval: float = 2.0,
        callback: Callable[[str], None] | None = None,
    ) -> dict:
        deadline = time.time() + timeout
        errors = []
        completed = False

        while time.time() < deadline:
            new = self.tail()
            for line in new:
                if callback:
                    callback(line)
                if "[FAILED]" in line:
                    errors.append(line)
                if "[COMPLETED]" in line and "[FAILED]" not in line:
                    completed = True

            if errors:
                return {"status": "error", "errors": errors, "log": self.get_all()}
            if completed:
                return {"status": "completed", "log": self.get_all()}

            time.sleep(poll_interval)

        return {"status": "timeout", "log": self.get_all()}
