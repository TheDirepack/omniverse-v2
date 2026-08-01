# Initialization refusal diagnostics are operator-facing and intentionally explicit.
# ruff: noqa: TRY003

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.v2.bootstrap import SeedResult, bootstrap_fresh_database
from app.v2.config import V2Config
from app.v2.credentials import CredentialService, JsonCredentialStore
from app.v2.db import (
    SchemaValidationError,
    bootstrap_schema,
    create_sqlite_engine,
    validate_initialized_schema,
)
from app.v2.models import (
    CredentialRef,
    Provider,
    ProviderModel,
    Route,
    RouteCandidate,
)


def ensure_qwen_development_default(config: V2Config, engine) -> None:
    with Session(engine) as session, session.begin():
        if session.get(Provider, "qwen-local") is None:
            session.add(
                Provider(
                    id="qwen-local",
                    kind="OPENAI_COMPATIBLE",
                    base_url=config.qwen_base_url,
                    active=True,
                )
            )
        model_id = "qwen-local:qwen3.5-4b-iq4-xs"
        if session.get(ProviderModel, model_id) is None:
            session.add(
                ProviderModel(
                    id=model_id,
                    provider_id="qwen-local",
                    model_name=config.qwen_model,
                    context_window=config.qwen_context_window,
                    output_limit=4_000,
                    supports_tools=False,
                    supports_structured=True,
                    supports_text=True,
                    active=True,
                )
            )
        route = session.scalar(select(Route).where(Route.task == "DEFAULT"))
        if route is None:
            route = Route(
                id="route:DEFAULT", task="DEFAULT", position=0, active=True
            )
            session.add(route)
            session.flush()
        if not session.scalar(
            select(func.count())
            .select_from(RouteCandidate)
            .where(RouteCandidate.route_id == route.id)
        ):
            session.add(
                RouteCandidate(
                    id=f"candidate:{route.id}:qwen-local",
                    route_id=route.id,
                    provider_id="qwen-local",
                    model_id=None,
                    position=0,
                )
            )
    with Session(engine) as session:
        has_credential = session.scalar(
            select(func.count())
            .select_from(CredentialRef)
            .where(CredentialRef.provider_id == "qwen-local")
        )
    if not has_credential:
        CredentialService(JsonCredentialStore(config.credentials_path), engine).add(
            "qwen-local", "Local Qwen development server", "local-development"
        )


def _seed_qwen_development_default(config: V2Config, engine) -> None:
    with Session(engine) as session, session.begin():
        for route in session.scalars(
            select(Route).where(Route.task != "DEFAULT").order_by(Route.id)
        ):
            generated_id = f"candidate:{route.id}:qwen-local"
            candidate = session.get(RouteCandidate, generated_id)
            if candidate is not None:
                session.delete(candidate)
                session.flush()
            if not session.scalar(
                select(func.count())
                .select_from(RouteCandidate)
                .where(RouteCandidate.route_id == route.id)
            ):
                session.delete(route)
    with Session(engine) as session:
        candidates = session.scalars(select(RouteCandidate)).all()
        generated = all(
            candidate.id.endswith(":qwen-local") for candidate in candidates
        )
        if candidates and not generated:
            return
    with Session(engine) as session, session.begin():
        route = session.scalar(select(Route).where(Route.task == "DEFAULT"))
        default_candidates = (
            session.scalars(
                select(RouteCandidate).where(RouteCandidate.route_id == route.id)
            ).all()
            if route is not None
            else []
        )
        if default_candidates and all(
            item.id.endswith(":qwen-local") for item in default_candidates
        ):
            default_candidates[0].provider_id = "qwen-local"
            default_candidates[0].model_id = None
    ensure_qwen_development_default(config, engine)


def _ensure_database_is_safe(path: Path) -> None:
    if not path.exists() or path.stat().st_size == 0:
        return
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
    except sqlite3.DatabaseError as error:
        raise SchemaValidationError(
            "refusing unrecognized non-empty database"
        ) from error
    if tables and "seed_run" not in tables:
        raise SchemaValidationError("refusing unrecognized non-empty database")


def initialize(config: V2Config) -> SeedResult:
    config.validate()
    _ensure_database_is_safe(config.database_path)
    config.database_path.parent.mkdir(parents=True, exist_ok=True)
    config.blob_path.mkdir(parents=True, exist_ok=True)
    config.credentials_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    engine = create_sqlite_engine(
        config.database_path, busy_timeout_ms=config.sqlite_busy_timeout_ms
    )
    try:
        bootstrap_schema(engine)
        result = bootstrap_fresh_database(engine, config.seed_path)
        _seed_qwen_development_default(config, engine)
        validate_initialized_schema(engine, seed_path=config.seed_path)
        return result
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize the Omniverse v2 runtime")
    parser.parse_args()
    result = initialize(V2Config.from_env())
    print(f"initialized v2 database; imported {result.imported_count} worlds")


if __name__ == "__main__":
    main()
