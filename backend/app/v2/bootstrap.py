from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import Field, TypeAdapter
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.v2.contracts import Contract
from app.v2.models import PolicyDefinition, SeedRun, World

IMPORTER_VERSION = "world-json.v1"


class SeedListRequiredError(ValueError):
    def __init__(self) -> None:
        super().__init__("world seed must contain a JSON list")


class DuplicateWorldError(ValueError):
    def __init__(self) -> None:
        super().__init__("world seed contains duplicate ids")


class UnknownParentError(ValueError):
    def __init__(self, parent_id: str, world_id: str) -> None:
        super().__init__(f"unknown parent {parent_id!r} for world {world_id!r}")


class ParentCycleError(ValueError):
    def __init__(self) -> None:
        super().__init__("world parent cycle detected")


BUILTIN_POLICIES = (
    PolicyDefinition(
        id="canon.default.v1",
        policy_type="CANON",
        version=1,
        definition_json={
            "source_ranks": ["primary", "official", "licensed", "index", "lead"],
            "high_impact_fields": [
                "quantity",
                "yield",
                "range",
                "speed",
                "offense",
                "defense",
                "deployment_scale",
            ],
            "promotion_sources": {
                "eligible_classes": [
                    "PRIMARY",
                    "OFFICIAL",
                    "LICENSED",
                    "SECONDARY",
                    "MIRROR",
                ],
                "high_impact_min_independent": 2,
            },
        },
        active=True,
    ),
    PolicyDefinition(
        id="research.default.v1",
        policy_type="RESEARCH_COMPLETION",
        version=1,
        definition_json={
            "overall_threshold": 0.8,
            "domain_threshold": 0.6,
            "domains": {
                "identity_scope": {
                    "required_indicators": ["identity", "scope"],
                    "critical_questions": ["What is the subject and applicable scope?"],
                },
                "mechanisms_capabilities": {
                    "required_indicators": ["effect", "activation", "limits"],
                    "critical_questions": [
                        "What mechanism produces each capability and under what limits?"
                    ],
                },
                "energy_resources": {
                    "required_indicators": [
                        "energy_source",
                        "resource_cost",
                        "sustainment",
                    ],
                    "critical_questions": ["What powers and sustains the subject?"],
                },
                "industry_logistics": {
                    "required_indicators": [
                        "production",
                        "supply_chain",
                        "maintenance",
                    ],
                    "critical_questions": [
                        "How is capability produced, supplied, and maintained?"
                    ],
                },
                "mobility": {
                    "required_indicators": ["range", "speed", "access"],
                    "critical_questions": [
                        "Where and how quickly can the subject move?"
                    ],
                },
                "offense": {
                    "required_indicators": ["effect", "delivery", "constraints"],
                    "critical_questions": [
                        "What offensive effects are demonstrated and constrained?"
                    ],
                },
                "defense": {
                    "required_indicators": ["protection", "recovery", "failure_modes"],
                    "critical_questions": [
                        "What protection and recovery are evidenced?"
                    ],
                },
                "information_control": {
                    "required_indicators": ["sensing", "communications", "control"],
                    "critical_questions": [
                        "How is information sensed, communicated, and controlled?"
                    ],
                },
                "biology": {
                    "required_indicators": [
                        "physiology",
                        "adaptation",
                        "vulnerabilities",
                    ],
                    "critical_questions": [
                        "What biological traits and vulnerabilities matter?"
                    ],
                },
                "exotic": {
                    "required_indicators": [
                        "modality",
                        "effect",
                        "activation",
                        "cost",
                        "control",
                        "reliability",
                        "limits",
                        "counters",
                        "causal_temporal_rules",
                    ],
                    "critical_questions": [
                        "What non-conventional modality, effects, and "
                        "constraints are evidenced?"
                    ],
                },
                "deployment_scale": {
                    "required_indicators": ["quantity", "distribution", "readiness"],
                    "critical_questions": [
                        "At what scale and readiness is capability deployed?"
                    ],
                },
                "chronology": {
                    "required_indicators": ["timepoint", "sequence", "branch"],
                    "critical_questions": ["When and in which branch do claims apply?"],
                },
                "counters_limits": {
                    "required_indicators": ["limits", "counters", "failure_modes"],
                    "critical_questions": [
                        "What limits, counters, and failures are documented?"
                    ],
                },
            },
            "aliases": {
                "mechanisms": "mechanisms_capabilities",
                "limits": "counters_limits",
            },
        },
        active=True,
    ),
)


class WorldSeed(Contract):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    franchise: str = Field(min_length=1)
    category: str = Field(min_length=1)
    continuity: str | None
    era: str | None
    parent: str | None
    aliases: tuple[str, ...]
    tags: tuple[str, ...]


class SeedResult(Contract):
    source_hash: str
    importer_version: str
    imported_count: int


def _load_and_validate(seed_path: Path) -> tuple[bytes, tuple[WorldSeed, ...]]:
    raw = Path(seed_path).read_bytes()
    payload = json.loads(raw)
    if not isinstance(payload, list):
        raise SeedListRequiredError
    worlds = tuple(TypeAdapter(list[WorldSeed]).validate_json(raw))
    ids = [world.id for world in worlds]
    if len(ids) != len(set(ids)):
        raise DuplicateWorldError
    known = set(ids)
    for world in worlds:
        if world.parent is not None and world.parent not in known:
            raise UnknownParentError(world.parent, world.id)
    return raw, worlds


def import_world_seed(engine: Engine, seed_path: Path) -> SeedResult:
    raw, worlds = _load_and_validate(Path(seed_path))
    source_hash = hashlib.sha256(raw).hexdigest()
    with Session(engine) as session, session.begin():
        existing = session.scalar(
            select(SeedRun).where(SeedRun.source_hash == source_hash)
        )
        if existing is not None:
            return SeedResult(
                source_hash=source_hash,
                importer_version=existing.importer_version,
                imported_count=0,
            )

        remaining = {world.id: world for world in worlds}
        inserted: set[str] = set(session.scalars(select(World.id)))
        while remaining:
            ready = [
                world
                for world in remaining.values()
                if world.parent is None
                or world.parent == world.id
                or world.parent in inserted
            ]
            if not ready:
                raise ParentCycleError
            for world in ready:
                session.add(
                    World(
                        id=world.id,
                        name=world.name,
                        franchise=world.franchise,
                        category=world.category,
                        continuity=world.continuity,
                        era=world.era,
                        parent_id=None if world.parent == world.id else world.parent,
                        aliases_json=list(world.aliases),
                        tags_json=list(world.tags),
                    )
                )
                inserted.add(world.id)
                del remaining[world.id]
            session.flush()
        session.add(
            SeedRun(
                source_hash=source_hash,
                importer_version=IMPORTER_VERSION,
                imported_count=len(worlds),
            )
        )
    return SeedResult(
        source_hash=source_hash,
        importer_version=IMPORTER_VERSION,
        imported_count=len(worlds),
    )


def activate_builtin_policies(engine: Engine) -> None:
    with Session(engine) as session, session.begin():
        for definition in BUILTIN_POLICIES:
            if session.get(PolicyDefinition, definition.id) is None:
                session.add(
                    PolicyDefinition(
                        id=definition.id,
                        policy_type=definition.policy_type,
                        version=definition.version,
                        definition_json=dict(definition.definition_json),
                        active=True,
                    )
                )


def bootstrap_fresh_database(engine: Engine, seed_path: Path) -> SeedResult:
    activate_builtin_policies(engine)
    return import_world_seed(engine, seed_path)
