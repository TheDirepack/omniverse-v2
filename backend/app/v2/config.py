# Configuration diagnostics are operator-facing and intentionally explicit.
# ruff: noqa: TRY003

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[2]


def _path(name: str, default: Path) -> Path:
    value = Path(os.environ.get(name, default))
    return value if value.is_absolute() else _BACKEND / value


def _bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    return default if value is None else value.casefold() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class V2Config:
    database_path: Path
    blob_path: Path
    credentials_path: Path
    seed_path: Path
    sqlite_busy_timeout_ms: int = 5_000
    worker_poll_seconds: float = 1.0
    worker_concurrency: int = 1
    worker_reclaim_seconds: float = 30.0
    require_loopback: bool = True
    bind_host: str = "127.0.0.1"
    http_timeout_seconds: float = 15.0
    max_body_bytes: int = 5_000_000
    browser_enabled: bool = True
    browser_concurrency: int = 2
    pdf_max_pages: int = 100
    pdf_max_characters: int = 200_000
    ocr_max_bytes: int = 10_000_000
    ocr_max_pixels: int = 25_000_000
    ocr_timeout_seconds: float = 15.0

    @classmethod
    def from_env(cls) -> V2Config:
        backend = _BACKEND
        return cls(
            database_path=_path(
                "OMNIVERSE_V2_DATABASE_PATH", backend / "data" / "omniverse-v2.db"
            ),
            blob_path=_path("OMNIVERSE_V2_BLOB_PATH", backend / "data" / "v2-blobs"),
            credentials_path=_path(
                "OMNIVERSE_V2_CREDENTIALS_PATH",
                backend / "data" / "v2-secrets" / "credentials.json",
            ),
            seed_path=_path(
                "OMNIVERSE_V2_SEED_PATH", backend / "app" / "db" / "default_worlds.json"
            ),
            sqlite_busy_timeout_ms=int(
                os.environ.get("OMNIVERSE_V2_SQLITE_BUSY_TIMEOUT_MS", "5000")
            ),
            worker_poll_seconds=float(
                os.environ.get("OMNIVERSE_V2_WORKER_POLL_SECONDS", "1")
            ),
            worker_concurrency=int(
                os.environ.get("OMNIVERSE_V2_WORKER_CONCURRENCY", "1")
            ),
            worker_reclaim_seconds=float(
                os.environ.get("OMNIVERSE_V2_WORKER_RECLAIM_SECONDS", "30")
            ),
            require_loopback=_bool("OMNIVERSE_V2_REQUIRE_LOOPBACK", True),
            bind_host=os.environ.get("OMNIVERSE_V2_BIND_HOST", "127.0.0.1"),
            http_timeout_seconds=float(
                os.environ.get("OMNIVERSE_V2_HTTP_TIMEOUT_SECONDS", "15")
            ),
            max_body_bytes=int(
                os.environ.get("OMNIVERSE_V2_MAX_BODY_BYTES", "5000000")
            ),
            browser_enabled=_bool("OMNIVERSE_V2_BROWSER_ENABLED", True),
            browser_concurrency=int(
                os.environ.get("OMNIVERSE_V2_BROWSER_CONCURRENCY", "2")
            ),
            pdf_max_pages=int(os.environ.get("OMNIVERSE_V2_PDF_MAX_PAGES", "100")),
            pdf_max_characters=int(
                os.environ.get("OMNIVERSE_V2_PDF_MAX_CHARACTERS", "200000")
            ),
            ocr_max_bytes=int(os.environ.get("OMNIVERSE_V2_OCR_MAX_BYTES", "10000000")),
            ocr_max_pixels=int(
                os.environ.get("OMNIVERSE_V2_OCR_MAX_PIXELS", "25000000")
            ),
            ocr_timeout_seconds=float(
                os.environ.get("OMNIVERSE_V2_OCR_TIMEOUT_SECONDS", "15")
            ),
        )

    def validate(self) -> None:
        if self.worker_concurrency < 1:
            raise ValueError("worker concurrency must be positive")
        if self.browser_concurrency < 1:
            raise ValueError("browser concurrency must be positive")
        if self.require_loopback and self.bind_host not in {
            "127.0.0.1",
            "::1",
            "localhost",
        }:
            raise ValueError("v2 runtime is configured for loopback-only binding")
