from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.v2.bootstrap import bootstrap_fresh_database, import_world_seed
from app.v2.db import bootstrap_schema, create_sqlite_engine
from app.v2.models import PolicyDefinition, SeedRun, World


def write_seed(path: Path, worlds: list[dict[str, object]]) -> None:
    path.write_text(json.dumps(worlds), encoding="utf-8")


@pytest.mark.integration
def test_seed_validates_every_record_before_atomic_write(
    isolated_paths: dict[str, Path], tmp_path: Path
) -> None:
    engine = create_sqlite_engine(isolated_paths["database"])
    bootstrap_schema(engine)
    seed = tmp_path / "worlds.json"
    write_seed(
        seed,
        [
            {
                "id": "root",
                "name": "Root",
                "franchise": "F",
                "category": "SF",
                "continuity": None,
                "era": None,
                "parent": None,
                "aliases": [],
                "tags": [],
            },
            {
                "id": "child",
                "name": "Child",
                "franchise": "F",
                "category": "SF",
                "continuity": None,
                "era": None,
                "parent": "missing",
                "aliases": [],
                "tags": [],
            },
        ],
    )
    with pytest.raises(ValueError, match="parent"):
        import_world_seed(engine, seed)
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(World)) == 0
        assert session.scalar(select(func.count()).select_from(SeedRun)) == 0


@pytest.mark.integration
def test_seed_resolves_parents_and_is_idempotent(
    isolated_paths: dict[str, Path], tmp_path: Path
) -> None:
    engine = create_sqlite_engine(isolated_paths["database"])
    bootstrap_schema(engine)
    seed = tmp_path / "worlds.json"
    write_seed(
        seed,
        [
            {
                "id": "child",
                "name": "Child",
                "franchise": "F",
                "category": "SF",
                "continuity": "C",
                "era": "E",
                "parent": "root",
                "aliases": ["Kid"],
                "tags": ["tag"],
            },
            {
                "id": "root",
                "name": "Root",
                "franchise": "F",
                "category": "SF",
                "continuity": None,
                "era": None,
                "parent": None,
                "aliases": [],
                "tags": [],
            },
        ],
    )
    first = import_world_seed(engine, seed)
    second = import_world_seed(engine, seed)
    assert first.imported_count == 2
    assert second.imported_count == 0
    with Session(engine) as session:
        child = session.get(World, "child")
        assert child is not None and child.parent_id == "root"
        run = session.scalars(select(SeedRun)).one()
        assert len(run.source_hash) == 64
        assert run.importer_version


@pytest.mark.integration
def test_full_production_seed_count_and_builtin_policy_activation(
    isolated_paths: dict[str, Path],
) -> None:
    engine = create_sqlite_engine(isolated_paths["database"])
    bootstrap_schema(engine)
    production_seed = Path(__file__).parents[1] / "app" / "db" / "default_worlds.json"
    result = bootstrap_fresh_database(engine, production_seed)
    assert result.imported_count == 1259
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(World)) == 1259
        self_parented_root = session.get(World, "marvel_legends_comics_various_eras")
        assert self_parented_root is not None and self_parented_root.parent_id is None
        policies = set(session.scalars(select(PolicyDefinition.id)))
        assert policies == {"canon.default.v1", "research.default.v1"}
