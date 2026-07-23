import asyncio
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx

from loop.loop_config import SERVER_URL, SERVER_PORT


class ServerManager:
    def __init__(self):
        self.process: subprocess.Popen | None = None
        self.base_dir = Path(__file__).resolve().parent.parent
        self.venv_dir = self._find_venv()

    def _find_venv(self) -> Path:
        for venv_name in [".venv", "venv"]:
            p = self.base_dir / venv_name
            if p.exists():
                return p
            p2 = self.base_dir / "backend" / venv_name
            if p2.exists():
                return p2
        raise RuntimeError("No venv found")

    def start(self, timeout: float = 60.0, log_file: str | None = None) -> bool:
        env = os.environ.copy()
        env["PYTHONPATH"] = f"{self.base_dir / 'backend'}:{env.get('PYTHONPATH', '')}"
        env["APP_LOG_LEVEL"] = "DEBUG"

        cmd = [
            str(self.venv_dir / "bin" / "uvicorn"),
            "app.main:app",
            "--app-dir", str(self.base_dir / "backend"),
            "--host", "127.0.0.1",
            "--port", str(SERVER_PORT),
        ]
        if log_file:
            stdout = open(log_file, "w")
            stderr = subprocess.STDOUT
        else:
            stdout = asyncio.subprocess.DEVNULL
            stderr = asyncio.subprocess.DEVNULL

        self.process = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                r = httpx.get(f"{SERVER_URL}/api/health", timeout=2)
                if r.status_code == 200:
                    return True
            except (httpx.ConnectError, httpx.TimeoutException):
                pass
            time.sleep(0.5)
        return False

    def stop(self):
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None

    def is_alive(self) -> bool:
        try:
            r = httpx.get(f"{SERVER_URL}/api/health", timeout=2)
            return r.status_code == 200
        except Exception:
            return False

    def restart(self, timeout: float = 60.0) -> bool:
        self.stop()
        time.sleep(1)
        return self.start(timeout=timeout)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stop()
