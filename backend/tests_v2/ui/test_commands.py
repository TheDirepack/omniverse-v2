from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_run_script_initializes_v2_and_defaults_to_loopback() -> None:
    script = (ROOT / "run.sh").read_text(encoding="utf-8")
    assert "python -m app.v2.initialize" in script
    assert 'HOST="${OMNIVERSE_V2_BIND_HOST:-${HOST:-127.0.0.1}}"' in script
    assert 'export OMNIVERSE_V2_BIND_HOST="$HOST"' in script
    assert "uvicorn app.main:app" in script
    assert script.index("python -m app.v2.initialize") < script.index(
        "uvicorn app.main:app"
    )


def test_test_script_is_authoritative_for_tests_v2_only() -> None:
    script = (ROOT / "test.sh").read_text(encoding="utf-8")
    assert "backend/tests_v2" in script
    assert "not network and not slow and not evaluation" in script
    assert "backend/tests/" not in script
    assert "backend/tests/ui" not in script


def _run_script(tmp_path: Path, *args: str, env: dict[str, str] | None = None):
    root = tmp_path / "project"
    (root / "backend" / ".venv" / "bin").mkdir(parents=True)
    script = (ROOT / "run.sh").read_text(encoding="utf-8")
    (root / "run.sh").write_text(script, encoding="utf-8")
    for command in ("python", "uvicorn"):
        executable = root / "backend" / ".venv" / "bin" / command
        executable.write_text(
            "#!/bin/sh\nprintf '%s\\n' \"$0 $* "
            "bind=$OMNIVERSE_V2_BIND_HOST secret=${TEST_SECRET-unset} "
            'credentials=${OMNIVERSE_V2_CREDENTIALS_PATH-unset}"\n',
            encoding="utf-8",
        )
        executable.chmod(0o755)
    (root / "backend" / ".venv" / "bin" / "activate").write_text(
        f'export PATH="{root / "backend" / ".venv" / "bin"}:$PATH"\n',
        encoding="utf-8",
    )
    return subprocess.run(
        ["bash", str(root / "run.sh"), "--prod", *args],
        cwd=root,
        env={**os.environ, **(env or {})},
        text=True,
        capture_output=True,
        check=False,
    )


def test_run_script_rejects_public_cli_bind_when_loopback_required(
    tmp_path: Path,
) -> None:
    result = _run_script(
        tmp_path,
        "--host=0.0.0.0",
        env={"OMNIVERSE_V2_REQUIRE_LOOPBACK": "true"},
    )
    assert result.returncode != 0
    assert "loopback" in result.stderr.lower()
    assert "uvicorn" not in result.stdout


def test_run_script_safely_loads_env_and_cli_host_wins(tmp_path: Path) -> None:
    env_file = tmp_path / "project" / "backend" / ".env.local"
    env_file.parent.mkdir(parents=True, exist_ok=True)
    env_file.write_text(
        "TEST_SECRET='value with spaces'\nOMNIVERSE_V2_BIND_HOST=localhost\n",
        encoding="utf-8",
    )
    result = _run_script(tmp_path, "--host=127.0.0.1")
    assert result.returncode == 0
    assert "bind=127.0.0.1 secret=value with spaces" in result.stdout
    assert "TEST_SECRET=" not in result.stdout


def test_run_script_resolves_local_data_paths_under_backend(tmp_path: Path) -> None:
    env_file = tmp_path / "project" / "backend" / ".env.local"
    env_file.parent.mkdir(parents=True, exist_ok=True)
    env_file.write_text(
        "OMNIVERSE_V2_CREDENTIALS_PATH=./data/v2-secrets/credentials.json\n",
        encoding="utf-8",
    )
    result = _run_script(tmp_path)
    expected = tmp_path / "project" / "backend" / "data/v2-secrets/credentials.json"
    assert result.returncode == 0
    assert f"credentials={expected}" in result.stdout


def test_slow_requires_explicit_evaluation_and_lint_targets_v2() -> None:
    test_script = (ROOT / "test.sh").read_text(encoding="utf-8")
    lint_script = (ROOT / "lint.sh").read_text(encoding="utf-8")
    assert "--evaluation" in test_script
    assert 'MARKER="not network and not evaluation"' in test_script
    assert "backend/app/v2" in lint_script
    assert "backend/tests_v2" in lint_script
    assert '"$BASE_DIR/backend/tests"' not in lint_script


def test_python_support_floor_matches_runtime_syntax() -> None:
    pyproject = (ROOT / "backend" / "pyproject.toml").read_text(encoding="utf-8")
    setup = (ROOT / "setup.sh").read_text(encoding="utf-8")
    assert 'requires-python = ">=3.10"' in pyproject
    assert "[tool.setuptools.packages.find]" in pyproject
    assert 'include = ["app*"]' in pyproject
    assert "sys.version_info < (3, 10)" in setup
    assert '"$VENV_DIR/bin/python" -c' in setup
    assert 'awk "BEGIN {exit !($version < 3.10)}"' not in setup
