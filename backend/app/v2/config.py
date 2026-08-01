# Configuration diagnostics are operator-facing and intentionally explicit.
# ruff: noqa: TRY003

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[2]

# Persistence file for UI-controlled settings
_PERSISTENCE_FILE = _BACKEND / "data" / "ui_persistence.json"


def _load_persistence() -> dict:
    if _PERSISTENCE_FILE.exists():
        try:
            with _PERSISTENCE_FILE.open() as f:
                return json.load(f)
        except Exception:
            pass
    return {}


_PERSISTENCE = _load_persistence()


def _path(name: str, default: Path) -> Path:
    value = Path(os.environ.get(name, default))
    return value if value.is_absolute() else _BACKEND / value


def _bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        value = _PERSISTENCE.get(name)
    return default if value is None else value.casefold() in {"1", "true", "yes", "on"}


def _str(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None:
        value = _PERSISTENCE.get(name)
    return default if value is None else value


@dataclass(frozen=True, slots=True)
class V2Config:
    database_path: Path
    blob_path: Path
    credentials_path: Path
    seed_path: Path
    logging_root: Path = _BACKEND
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
    browser_profile_path: Path = _BACKEND / "data" / "v2-secrets" / "browser-profile"
    browser_search_timeout_seconds: float = 45.0
    pdf_max_pages: int = 100
    pdf_max_characters: int = 200_000
    ocr_max_bytes: int = 10_000_000
    ocr_max_pixels: int = 25_000_000
    ocr_timeout_seconds: float = 15.0
    preprocessor_enabled: bool = True
    preprocessor_base_url: str = "http://192.168.1.30:8080"
    preprocessor_model: str = "MiniCPM5-1B"
    preprocessor_timeout_seconds: float = 10.0
    preprocessor_concurrency: int = 2
    preprocessor_ssh_host: str = "192.168.1.30"
    preprocessor_ssh_user: str = "max"
    preprocessor_ssh_port: int = 22
    preprocessor_ssh_key_path: str = ""
    preprocessor_ssh_credential_id: str = ""
    preprocessor_config_path: str = "/home/max/minicpm5_config.json"
    preprocessor_remote_script: str = "/home/max/start-minicpm.sh"
    preprocessor_pgrep_pattern: str = "llama-server"
    remote_model_lifecycle_enabled: bool = False
    qwen_base_url: str = "http://192.168.1.30:8081"
    qwen_model: str = "/home/max/Downloads/Qwen3.5-4B-IQ4_XS.gguf"
    qwen_context_window: int = 81_920
    qwen_remote_script: str = "/home/max/start-qwen35.sh"
    log_path: str | None = None
    access_log_path: str = "logs/access.log"
    error_log_path: str = "logs/error.log"
    client_log_path: str = "logs/client.log"

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
            logging_root=_path("OMNIVERSE_V2_LOG_ROOT", backend),
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
            browser_profile_path=_path(
                "OMNIVERSE_V2_BROWSER_PROFILE_PATH",
                backend / "data" / "v2-secrets" / "browser-profile",
            ),
            browser_search_timeout_seconds=float(
                os.environ.get("OMNIVERSE_V2_BROWSER_SEARCH_TIMEOUT_SECONDS", "45")
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
            preprocessor_enabled=_bool("OMNIVERSE_V2_PREPROCESSOR_ENABLED", True),
            preprocessor_base_url=os.environ.get(
                "OMNIVERSE_V2_PREPROCESSOR_BASE_URL", "http://192.168.1.30:8080"
            ),
            preprocessor_model=os.environ.get(
                "OMNIVERSE_V2_PREPROCESSOR_MODEL", "MiniCPM5-1B"
            ),
            preprocessor_timeout_seconds=float(
                os.environ.get("OMNIVERSE_V2_PREPROCESSOR_TIMEOUT_SECONDS", "10")
            ),
            preprocessor_concurrency=int(
                os.environ.get("OMNIVERSE_V2_PREPROCESSOR_CONCURRENCY", "2")
            ),
            preprocessor_ssh_host=os.environ.get(
                "OMNIVERSE_V2_PREPROCESSOR_SSH_HOST", "192.168.1.30"
            ),
            preprocessor_ssh_user=os.environ.get(
                "OMNIVERSE_V2_PREPROCESSOR_SSH_USER", "max"
            ),
            preprocessor_ssh_port=int(
                os.environ.get("OMNIVERSE_V2_PREPROCESSOR_SSH_PORT", "22")
            ),
            preprocessor_ssh_key_path=os.environ.get(
                "OMNIVERSE_V2_PREPROCESSOR_SSH_KEY_PATH", ""
            ),
            preprocessor_ssh_credential_id=os.environ.get(
                "OMNIVERSE_V2_PREPROCESSOR_SSH_CREDENTIAL_ID", ""
            ),
            preprocessor_config_path=os.environ.get(
                "OMNIVERSE_V2_PREPROCESSOR_CONFIG_PATH",
                "/home/max/minicpm5_config.json",
            ),
            preprocessor_remote_script=os.environ.get(
                "OMNIVERSE_V2_PREPROCESSOR_REMOTE_SCRIPT",
                "/home/max/start-minicpm.sh",
            ),
            preprocessor_pgrep_pattern=os.environ.get(
                "OMNIVERSE_V2_PREPROCESSOR_PGREP_PATTERN", "llama-server"
            ),
            remote_model_lifecycle_enabled=_bool(
                "OMNIVERSE_V2_REMOTE_MODEL_LIFECYCLE_ENABLED", True
            ),
            qwen_base_url=os.environ.get(
                "OMNIVERSE_V2_QWEN_BASE_URL", "http://192.168.1.30:8081"
            ),
            qwen_model=os.environ.get(
                "OMNIVERSE_V2_QWEN_MODEL",
                "/home/max/Downloads/Qwen3.5-4B-IQ4_XS.gguf",
            ),
            qwen_context_window=int(
                os.environ.get("OMNIVERSE_V2_QWEN_CONTEXT_WINDOW", "81920")
            ),
            qwen_remote_script=os.environ.get(
                "OMNIVERSE_V2_QWEN_REMOTE_SCRIPT", "/home/max/start-qwen35.sh"
            ),
            log_path=_str("OMNIVERSE_V2_LOG_PATH"),
            access_log_path=os.environ.get(
                "OMNIVERSE_V2_ACCESS_LOG_PATH", "logs/access.log"
            ),
            error_log_path=os.environ.get(
                "OMNIVERSE_V2_ERROR_LOG_PATH", "logs/error.log"
            ),
            client_log_path=os.environ.get(
                "OMNIVERSE_V2_CLIENT_LOG_PATH", "logs/client.log"
            ),
        )

    def validate(self) -> None:
        if self.worker_concurrency < 1:
            raise ValueError("worker concurrency must be positive")
        if self.browser_concurrency < 1:
            raise ValueError("browser concurrency must be positive")
        if self.browser_search_timeout_seconds <= 0:
            raise ValueError("browser search timeout must be positive")
        if self.preprocessor_concurrency < 1:
            raise ValueError("preprocessor concurrency must be positive")
        if self.preprocessor_timeout_seconds <= 0:
            raise ValueError("preprocessor timeout must be positive")
        if self.qwen_context_window <= 0:
            raise ValueError("Qwen context window must be positive")
        if self.require_loopback and self.bind_host not in {
            "127.0.0.1",
            "::1",
            "localhost",
        }:
            raise ValueError("v2 runtime is configured for loopback-only binding")
