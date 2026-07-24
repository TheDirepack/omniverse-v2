from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.v2.config import V2Config


@dataclass(frozen=True, slots=True)
class AppConfig:
    database_path: Path
    blob_path: Path
    credentials_path: Path
    seed_path: Path | None = None
    sqlite_busy_timeout_ms: int = 5_000
    worker_poll_seconds: float = 1.0
    worker_concurrency: int = 1

    def runtime_config(self) -> V2Config:
        default_seed = (
            Path(__file__).resolve().parents[1] / "db" / "default_worlds.json"
        )
        return V2Config(
            database_path=self.database_path,
            blob_path=self.blob_path,
            credentials_path=self.credentials_path,
            seed_path=self.seed_path or default_seed,
            sqlite_busy_timeout_ms=self.sqlite_busy_timeout_ms,
            worker_poll_seconds=self.worker_poll_seconds,
            worker_concurrency=self.worker_concurrency,
        )


def create_app(
    config: AppConfig | V2Config | None = None,
    *,
    runtime=None,
    start_worker: bool | None = None,
):
    from app.v2.main import create_app as factory

    value = config.runtime_config() if isinstance(config, AppConfig) else config
    return factory(value, runtime=runtime, start_worker=start_worker)


__all__ = ["AppConfig", "V2Config", "create_app"]
