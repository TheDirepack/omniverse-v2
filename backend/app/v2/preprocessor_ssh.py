# Validation messages are intentionally returned to the local operator.
# ruff: noqa: TRY003

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import time
from urllib.parse import urlsplit

import httpx

from app.v2.config import V2Config
from app.v2.credentials import CredentialService

_SAFE_HOST = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9.-]{0,252}[A-Za-z0-9])?$")
_SAFE_USER = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]{0,63}$")
_SAFE_PATH = re.compile(r"^/[A-Za-z0-9_./-]+$")


class PreprocessorSSH:
    def __init__(
        self,
        config: V2Config,
        credentials: CredentialService | None = None,
        *,
        logger=None,
        remote_model: str = "",
    ) -> None:
        self.config = config
        self.credentials = credentials
        self.logger = logger
        self.remote_model = remote_model

    @staticmethod
    def _require_safe(value: str, pattern: re.Pattern[str], name: str) -> str:
        if not pattern.fullmatch(value) or ".." in value.split("/"):
            raise ValueError(f"unsafe {name}")
        return value

    def _credential_password(self) -> str | None:
        credential_id = self.config.preprocessor_ssh_credential_id
        if not credential_id or self.credentials is None:
            return None
        metadata = next(
            (
                item
                for item in self.credentials.list()
                if item.credential_id == credential_id
            ),
            None,
        )
        if metadata is None:
            raise ValueError("unsafe or unknown SSH credential")
        return self.credentials.store.resolve(metadata.opaque_ref)

    def _build_cmd(
        self, remote_argv: tuple[str, ...], *, password: str | None = None
    ) -> list[str]:
        ssh_args: list[str] = []

        host = self._require_safe(
            self.config.preprocessor_ssh_host, _SAFE_HOST, "SSH host"
        )
        user = self._require_safe(
            self.config.preprocessor_ssh_user, _SAFE_USER, "SSH user"
        )

        if password is not None:
            ssh_args = ["sshpass", "-e"]

        ssh_args.append("ssh")
        ssh_args.extend(["-p", str(self.config.preprocessor_ssh_port)])
        ssh_args.extend(["-o", "ConnectTimeout=5"])
        ssh_args.extend(["-o", "StrictHostKeyChecking=accept-new"])
        if ssh_args[0] != "sshpass":
            ssh_args.extend(["-o", "BatchMode=yes"])

        if self.config.preprocessor_ssh_key_path:
            key_path = self._require_safe(
                self.config.preprocessor_ssh_key_path, _SAFE_PATH, "SSH key path"
            )
            ssh_args.extend(["-i", key_path])

        ssh_args.append(f"{user}@{host}")
        ssh_args.append(shlex.join(remote_argv))

        return ssh_args

    def run(self, *remote_argv: str) -> subprocess.CompletedProcess:
        password = self._credential_password()
        cmd = self._build_cmd(remote_argv, password=password)
        options = {
            "capture_output": True,
            "text": True,
            "timeout": 10,
            "check": False,
        }
        if password is not None:
            options["env"] = {**os.environ, "SSHPASS": password}
        result = subprocess.run(
            cmd,
            **options,
        )
        if self.logger is not None:
            self.logger.log_event(
                "remote-server",
                "INFO" if result.returncode == 0 else "ERROR",
                "remote.command.completed",
                "remote_model",
                "Remote model command completed",
                data={
                    "model": self.remote_model,
                    "remote_argv": list(remote_argv),
                    "returncode": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                },
            )
        return result

    def check_running(self) -> bool:
        try:
            resp = httpx.get(
                f"{self.config.preprocessor_base_url}/health",
                timeout=3.0,
            )
        except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError):
            return False
        else:
            return resp.status_code == 200

    def start_server(self) -> tuple[bool, str]:
        if self.check_running():
            return False, "Server is already running"
        try:
            script = self._require_safe(
                self.config.preprocessor_remote_script, _SAFE_PATH, "remote script"
            )
            result = self.run("bash", "--", script)
        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        if result.returncode != 0:
            return False, result.stderr.strip() or f"Exit code {result.returncode}"
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if self.check_running():
                return True, result.stdout.strip() or "Server started"
            time.sleep(1)
        return False, "Server process launched but health check timed out"

    def stop_server(self) -> tuple[bool, str]:
        try:
            endpoint = urlsplit(self.config.preprocessor_base_url)
            if endpoint.scheme not in {"http", "https"} or not endpoint.hostname:
                raise ValueError("unsafe preprocessor base URL")
            port = endpoint.port or (443 if endpoint.scheme == "https" else 80)
            if not 1 <= port <= 65_535:
                raise ValueError("unsafe preprocessor port")
            result = self.run("fuser", "-k", f"{port}/tcp")
        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        if result.returncode == 0:
            return True, "Server stopped"
        return False, result.stderr.strip() or f"Exit code {result.returncode}"

    def fetch_config_json(self) -> dict | None:
        try:
            config_path = self._require_safe(
                self.config.preprocessor_config_path, _SAFE_PATH, "config path"
            )
            result = self.run("cat", "--", config_path)
        except (subprocess.TimeoutExpired, json.JSONDecodeError):
            return None
        if result.returncode != 0:
            return None
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return None

    def fetch_model_name(self) -> str | None:
        config = self.fetch_config_json()
        if config is None:
            return None
        return config.get("model")
