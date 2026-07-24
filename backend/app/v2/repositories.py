from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.v2.domain import GraphEdge, ensure_valid_graph
from app.v2.models import (
    RelationshipAssertion,
    RelationshipEvidence,
    RelationshipRevision,
)


def add_relationship(
    session: Session,
    assertion_id: str,
    source_node_id: str,
    target_node_id: str,
    relation_type: str,
    scope: dict[str, str],
    evidence_fragment_id: str,
) -> RelationshipAssertion:
    existing = session.execute(
        select(
            RelationshipAssertion.source_node_id,
            RelationshipAssertion.target_node_id,
            RelationshipRevision.relation_type,
        ).join(RelationshipRevision)
    ).all()
    edges = tuple(GraphEdge(source, target, kind) for source, target, kind in existing)
    ensure_valid_graph(
        (*edges, GraphEdge(source_node_id, target_node_id, relation_type))
    )

    assertion = RelationshipAssertion(
        id=assertion_id, source_node_id=source_node_id, target_node_id=target_node_id
    )
    revision_id = f"relationship-revision-{uuid4()}"
    revision = RelationshipRevision(
        id=revision_id,
        assertion_id=assertion_id,
        revision_number=1,
        relation_type=relation_type,
        scope_json=scope,
    )
    link = RelationshipEvidence(
        relationship_revision_id=revision_id,
        evidence_fragment_id=evidence_fragment_id,
        field_name="relationship",
    )
    session.add(assertion)
    session.flush()
    session.add(revision)
    session.flush()
    session.add(link)
    session.flush()
    return assertion
