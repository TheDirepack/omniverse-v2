from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.mark.unit
def test_domain_invariants_have_no_framework_or_orm_dependencies() -> None:
    domain_path = Path(__file__).parents[1] / "app" / "v2" / "domain.py"
    tree = ast.parse(domain_path.read_text(encoding="utf-8"))
    imports = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imports.update(
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    )
    assert imports.isdisjoint({"fastapi", "sqlalchemy", "sqlmodel", "jinja2"})


@pytest.mark.unit
def test_importing_v2_has_no_legacy_or_runtime_side_effect_imports() -> None:
    before = set(sys.modules)
    module = importlib.import_module("app.v2")
    imported = set(sys.modules) - before
    assert module is not None
    assert "app.main" not in imported
    assert not any(name == "app.db" or name.startswith("app.db.") for name in imported)
    assert not any("cloakbrowser" in name for name in imported)


@pytest.mark.unit
def test_network_is_denied_by_default() -> None:
    import socket

    with pytest.raises(RuntimeError, match="external network"):
        socket.create_connection(("example.com", 80))


@pytest.mark.parametrize("marker", ["slow", "evaluation"])
def test_non_live_markers_do_not_disable_network_guard(
    monkeypatch: pytest.MonkeyPatch, marker: str
) -> None:
    import socket

    from conftest import ExternalNetworkDisabledError, deny_external_network

    attempted = []
    monkeypatch.setattr(
        socket.socket, "connect", lambda *_args: attempted.append(True)
    )
    request = SimpleNamespace(
        node=SimpleNamespace(iter_markers=lambda: [SimpleNamespace(name=marker)])
    )
    deny_external_network.__wrapped__(monkeypatch, request)
    with socket.socket() as connection, pytest.raises(ExternalNetworkDisabledError):
        connection.connect(("203.0.113.1", 80))
    assert attempted == []
