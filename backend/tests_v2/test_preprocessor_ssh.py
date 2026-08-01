# Test doubles intentionally accept the subprocess call signature.
# ruff: noqa: ARG001, TRY003

from __future__ import annotations

import subprocess
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.v2.config import V2Config
from app.v2.preprocessor_ssh import PreprocessorSSH


@pytest.fixture
def config(tmp_path: Path) -> V2Config:
    return V2Config(
        database_path=tmp_path / "v2.db",
        blob_path=tmp_path / "blobs",
        credentials_path=tmp_path / "credentials.json",
        seed_path=tmp_path / "seed.json",
        preprocessor_ssh_host="example.test",
        preprocessor_ssh_user="operator",
        preprocessor_remote_script="/srv/minicpm/start.sh",
        preprocessor_config_path="/srv/minicpm/config.json",
        preprocessor_pgrep_pattern="llama-server",
    )


@pytest.mark.parametrize(
    ("field", "value", "method"),
    [
        ("preprocessor_remote_script", "/tmp/start.sh;touch /tmp/pwn", "start_server"),
        ("preprocessor_config_path", "/tmp/config;id", "fetch_config_json"),
        ("preprocessor_ssh_host", "host;id", "stop_server"),
        ("preprocessor_ssh_user", "user$(id)", "stop_server"),
        ("preprocessor_ssh_key_path", "/tmp/key;id", "stop_server"),
    ],
)
def test_preprocessor_ssh_rejects_metacharacters_before_subprocess(
    config: V2Config,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: str,
    method: str,
) -> None:
    called = False

    def forbidden(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("subprocess must not run")

    monkeypatch.setattr(subprocess, "run", forbidden)
    ssh = PreprocessorSSH(replace(config, **{field: value}))
    if method == "start_server":
        monkeypatch.setattr(ssh, "check_running", lambda: False)

    with pytest.raises(ValueError, match="unsafe"):
        getattr(ssh, method)()
    assert called is False


def test_preprocessor_ssh_quotes_remote_argv_and_uses_safe_subprocess_options(
    config: V2Config, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, '{"model":"safe"}', "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert PreprocessorSSH(config).fetch_model_name() == "safe"

    command = captured["command"]
    assert command[-1] == "cat -- /srv/minicpm/config.json"
    assert "BatchMode=yes" in command
    assert captured["kwargs"]["timeout"] == 10
    assert captured["kwargs"]["check"] is False


def test_preprocessor_ssh_password_is_not_exposed_in_process_arguments(
    config: V2Config, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    class Credentials:
        store = SimpleNamespace(resolve=lambda _ref: "super-secret")

        def list(self):
            return [SimpleNamespace(credential_id="ssh-password", opaque_ref="ref")]

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["env"] = kwargs["env"]
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    ssh = PreprocessorSSH(
        replace(config, preprocessor_ssh_credential_id="ssh-password"), Credentials()
    )
    ssh.run("true")

    command = captured["command"]
    assert "super-secret" not in command
    assert command[:2] == ["sshpass", "-e"]
    assert captured["env"]["SSHPASS"] == "super-secret"


def test_preprocessor_stop_targets_only_its_configured_port(
    config: V2Config, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: list[str] = []

    def fake_run(command, **_kwargs):
        captured.extend(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    stopped, _message = PreprocessorSSH(
        replace(config, preprocessor_base_url="http://gpu.example.test:8080")
    ).stop_server()

    assert stopped is True
    assert captured[-1] == "fuser -k 8080/tcp"
    assert "pkill" not in captured


def test_runtime_imports_preprocessor_ssh_from_its_module() -> None:
    runtime_source = (Path(__file__).parents[1] / "app/v2/runtime.py").read_text(
        encoding="utf-8"
    )
    assert "from app.v2.preprocessor_ssh import PreprocessorSSH" in runtime_source
    assert "from app.v2.preprocessing import PreprocessorSSH" not in runtime_source
