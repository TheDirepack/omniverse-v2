from __future__ import annotations

import threading
from collections.abc import Iterable

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.v2.bootstrap import import_world_seed
from app.v2.config import V2Config
from app.v2.credentials import CredentialService
from app.v2.initialize import ensure_qwen_development_default
from app.v2.models import (
    Base,
    CandidateHealth,
    CredentialRef,
    ProviderModel,
    RouteCandidate,
    Run,
)

_RESET_LOCK = threading.Lock()
_ACTIVE_RUN_STATUSES = {
    "PENDING",
    "RUNNING",
    "WAITING_RETRY",
    "WAITING_INPUT",
    "CANCELLING",
}
_IMMUTABLE_TABLES = {
    "source_revision",
    "evidence_fragment",
    "canon_node_revision",
    "relationship_revision",
    "audit_decision",
    "promotion_decision",
    "model_call",
    "context_manifest",
    "model_step_effect",
    "step_effect",
    "integration_effect",
    "structured_summary_revision",
}
_NOTEBOOK_TABLES = {
    "proposal_field_evidence",
    "claim_conflict",
    "audit_decision",
    "promotion_decision",
    "integration_effect",
    "material_proposal_field",
    "material_proposal",
    "research_gap",
    "coverage_record",
    "search_lead",
    "research_workspace",
    "workflow_summary",
    "structured_summary_revision",
    "model_step_effect",
    "model_call",
    "step_effect",
    "checkpoint",
    "step_attempt",
    "tool_event",
    "context_manifest",
    "outbox_event",
    "run_step",
    "run_target",
    "run",
}
_KNOWLEDGE_TABLES = _NOTEBOOK_TABLES | {
    "relationship_evidence",
    "node_evidence",
    "relationship_revision",
    "relationship_assertion",
    "canon_node_revision",
    "canon_node",
    "citation",
    "acquisition_cache",
    "evidence_fragment",
    "source_revision",
    "source",
}
_WORLD_TABLES = _KNOWLEDGE_TABLES | {
    "subject_relation",
    "subject",
    "timeline_branch",
    "continuity",
    "world",
    "seed_run",
}


class ResetBusyError(RuntimeError):
    pass


class ActiveRunsError(RuntimeError):
    pass


class ResetIntegrityError(RuntimeError):
    pass


def _delete_tables(session: Session, table_names: Iterable[str]) -> dict[str, int]:
    names = set(table_names)
    for table_name in sorted(names & _IMMUTABLE_TABLES):
        session.execute(text(f"DROP TRIGGER IF EXISTS immutable_{table_name}_delete"))
    counts: dict[str, int] = {}
    for table in reversed(Base.metadata.sorted_tables):
        if table.name in names:
            counts[table.name] = session.execute(delete(table)).rowcount
    for table_name in sorted(names & _IMMUTABLE_TABLES):
        session.execute(
            text(
                f"CREATE TRIGGER immutable_{table_name}_delete "
                f"BEFORE DELETE ON {table_name} BEGIN SELECT RAISE(ABORT, "
                f"'{table_name} is immutable'); END"
            )
        )
    if session.execute(text("PRAGMA foreign_key_check")).first() is not None:
        raise ResetIntegrityError
    return counts


def _reject_active_runs(session: Session, section: str) -> None:
    if section not in {"notebook", "knowledge", "worlds"}:
        return
    count = session.scalar(
        select(func.count()).select_from(Run).where(Run.status.in_(_ACTIVE_RUN_STATUSES))
    )
    if count:
        raise ActiveRunsError


def reset_database_section(
    section: str,
    *,
    engine,
    config: V2Config,
    credentials: CredentialService,
) -> dict[str, int]:
    if section not in {
        "providers",
        "models",
        "routes",
        "notebook",
        "knowledge",
        "worlds",
    }:
        raise KeyError(section)
    if not _RESET_LOCK.acquire(blocking=False):
        raise ResetBusyError
    credential_refs: list[str] = []
    try:
        with Session(engine) as session, session.begin():
            _reject_active_runs(session, section)
            if section == "providers":
                credential_refs = list(
                    session.scalars(select(CredentialRef.opaque_ref))
                )
                counts = _delete_tables(
                    session,
                    {
                        "provider_candidate_health",
                        "provider_route_candidate",
                        "provider_credential_health",
                        "credential_ref",
                        "provider_model",
                        "provider",
                    },
                )
            elif section == "models":
                model_candidate_ids = list(
                    session.scalars(
                        select(RouteCandidate.id).where(
                            RouteCandidate.model_id.is_not(None)
                        )
                    )
                )
                session.execute(delete(CandidateHealth))
                if model_candidate_ids:
                    session.execute(
                        delete(RouteCandidate).where(
                            RouteCandidate.id.in_(model_candidate_ids)
                        )
                    )
                counts = {
                    "provider_model": session.execute(delete(ProviderModel)).rowcount
                }
            elif section == "routes":
                counts = _delete_tables(
                    session,
                    {
                        "provider_candidate_health",
                        "provider_route_candidate",
                        "provider_route",
                    },
                )
            elif section == "notebook":
                counts = _delete_tables(session, _NOTEBOOK_TABLES)
            elif section == "knowledge":
                counts = _delete_tables(session, _KNOWLEDGE_TABLES)
            else:
                counts = _delete_tables(session, _WORLD_TABLES)
        if section == "providers":
            for opaque_ref in credential_refs:
                if not opaque_ref.startswith("env:"):
                    credentials.store.delete(opaque_ref)
        if section in {"providers", "models", "routes"}:
            ensure_qwen_development_default(config, engine)
        elif section == "worlds":
            import_world_seed(engine, config.seed_path)
        return counts
    finally:
        _RESET_LOCK.release()
