from __future__ import annotations

import socket
from pathlib import Path

import pytest


class ExternalNetworkDisabledError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("external network is disabled in tests_v2")


@pytest.fixture(autouse=True)
def deny_external_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def blocked_connect(self: socket.socket, _address: object) -> None:
        if self.family != socket.AF_UNIX:
            raise ExternalNetworkDisabledError

    monkeypatch.setattr(socket.socket, "connect", blocked_connect)


@pytest.fixture
def isolated_paths(tmp_path: Path) -> dict[str, Path]:
    paths = {
        "database": tmp_path / "data" / "omniverse.db",
        "blobs": tmp_path / "blobs",
        "credentials": tmp_path / "secrets" / "credentials.json",
    }
    paths["database"].parent.mkdir()
    paths["blobs"].mkdir()
    paths["credentials"].parent.mkdir()
    return paths
