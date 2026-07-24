from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.v2.db import bootstrap_schema, create_sqlite_engine
from app.v2.models import Provider, ResearchWorkspace, Run


def test_mutable_aggregate_mappers_use_optimistic_versions() -> None:
    assert Run.__mapper__.version_id_col is not None
    assert ResearchWorkspace.__mapper__.version_id_col is not None
    assert Provider.__mapper__.version_id_col is not None


@pytest.mark.integration
def test_concurrent_provider_command_rejects_stale_write(
    isolated_paths: dict[str, Path],
) -> None:
    engine = create_sqlite_engine(isolated_paths["database"])
    bootstrap_schema(engine)
    with Session(engine) as session, session.begin():
        session.add(Provider(id="provider", kind="OPENAI", active=True))

    with Session(engine) as first, Session(engine) as stale:
        first_row = first.get(Provider, "provider")
        stale_row = stale.get(Provider, "provider")
        assert first_row is not None and stale_row is not None
        first_row.active = False
        first.commit()
        stale_row.base_url = "https://example.invalid/v1"
        with pytest.raises(StaleDataError):
            stale.commit()
