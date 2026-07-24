from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.v2.models import (
    CanonNode,
    CanonNodeRevision,
    ClaimConflict,
    CoverageRecord,
    EvidenceFragment,
    NodeEvidence,
    RelationshipAssertion,
    RelationshipEvidence,
    RelationshipRevision,
    ResearchGapRecord,
    ResearchWorkspace,
    WorkflowSummary,
)


class ResearchQueryService:
    def __init__(self, engine) -> None:
        self.engine = engine

    def accepted_graph(
        self,
        world_id: str,
        *,
        continuity: str | None = None,
        era_or_timepoint: str | None = None,
        branch_id: str | None = None,
    ) -> tuple[dict[str, object], ...]:
        with Session(self.engine) as session:
            rows = session.execute(
                select(CanonNode, CanonNodeRevision)
                .join(CanonNodeRevision)
                .where(CanonNode.world_id == world_id)
                .order_by(CanonNode.id, CanonNodeRevision.revision_number.desc())
            ).all()
            latest: dict[str, dict[str, object]] = {}
            for node, revision in rows:
                scope = dict(revision.scope_json)
                if continuity is not None and scope.get("continuity") != continuity:
                    continue
                if (
                    era_or_timepoint is not None
                    and scope.get("era_or_timepoint") != era_or_timepoint
                ):
                    continue
                if branch_id is not None and scope.get("branch_id") != branch_id:
                    continue
                latest.setdefault(
                    node.id,
                    {
                        "node_id": node.id,
                        "kind": node.kind,
                        "modality": node.modality,
                        "fields": dict(revision.fields_json),
                        "field_origins": {
                            field_name: {
                                "node_id": node.id,
                                "node_revision_id": revision.id,
                            }
                            for field_name in revision.fields_json
                        },
                        "revision_id": revision.id,
                        "scope": scope,
                    },
                )
            return tuple(latest.values())

    def relationships(
        self,
        world_id: str,
        *,
        continuity: str | None = None,
        era_or_timepoint: str | None = None,
        branch_id: str | None = None,
    ) -> tuple[dict[str, object], ...]:
        with Session(self.engine) as session:
            rows = session.execute(
                select(RelationshipAssertion, RelationshipRevision)
                .join(RelationshipRevision)
                .join(
                    CanonNode,
                    CanonNode.id == RelationshipAssertion.source_node_id,
                )
                .where(CanonNode.world_id == world_id)
                .order_by(
                    RelationshipAssertion.id,
                    RelationshipRevision.revision_number.desc(),
                )
            ).all()
            latest: dict[str, dict[str, object]] = {}
            for assertion, revision in rows:
                scope = dict(revision.scope_json)
                if continuity is not None and scope.get("continuity") != continuity:
                    continue
                if (
                    era_or_timepoint is not None
                    and scope.get("era_or_timepoint") != era_or_timepoint
                ):
                    continue
                if branch_id is not None and scope.get("branch_id") != branch_id:
                    continue
                evidence_ids = session.scalars(
                    select(RelationshipEvidence.evidence_fragment_id).where(
                        RelationshipEvidence.relationship_revision_id == revision.id
                    )
                ).all()
                latest.setdefault(
                    assertion.id,
                    {
                        "assertion_id": assertion.id,
                        "revision_id": revision.id,
                        "relation_type": revision.relation_type,
                        "source_node_id": assertion.source_node_id,
                        "target_node_id": assertion.target_node_id,
                        "scope": scope,
                        "valid_from": revision.valid_from,
                        "valid_to": revision.valid_to,
                        "evidence_fragment_ids": tuple(sorted(evidence_ids)),
                    },
                )
            return tuple(latest.values())

    def provenance(
        self, node_id: str, *, branch_id: str | None = None
    ) -> tuple[dict[str, str], ...]:
        with Session(self.engine) as session:
            statement = (
                select(NodeEvidence, EvidenceFragment)
                .join(EvidenceFragment)
                .join(
                    CanonNodeRevision,
                    CanonNodeRevision.id == NodeEvidence.node_revision_id,
                )
                .where(CanonNodeRevision.node_id == node_id)
            )
            if branch_id is not None:
                statement = statement.where(
                    EvidenceFragment.branch_id == branch_id,
                    CanonNodeRevision.scope_json["branch_id"].as_string() == branch_id,
                )
            rows = session.execute(statement).all()
            return tuple(
                {
                    "field_name": link.field_name,
                    "node_revision_id": link.node_revision_id,
                    "fragment_id": fragment.id,
                    "exact_excerpt": fragment.exact_excerpt,
                    "source_revision_id": fragment.source_revision_id,
                    "branch_id": fragment.branch_id or "main",
                }
                for link, fragment in rows
            )

    def gaps_conflicts(
        self, workspace_id: str
    ) -> dict[str, tuple[dict[str, object], ...]]:
        with Session(self.engine) as session:
            gaps = session.scalars(
                select(ResearchGapRecord).where(
                    ResearchGapRecord.workspace_id.in_(
                        select(ResearchWorkspace.id).where(
                            (ResearchWorkspace.id == workspace_id)
                            | (ResearchWorkspace.run_id == workspace_id)
                        )
                    )
                )
            ).all()
            conflicts = session.scalars(
                select(ClaimConflict).where(
                    ClaimConflict.workspace_id.in_(
                        select(ResearchWorkspace.id).where(
                            (ResearchWorkspace.id == workspace_id)
                            | (ResearchWorkspace.run_id == workspace_id)
                        )
                    )
                )
            ).all()
            return {
                "gaps": tuple(dict(row.gap_json) for row in gaps),
                "conflicts": tuple(
                    {
                        "id": row.id,
                        "status": row.status,
                        "resolution": row.resolution_json,
                    }
                    for row in conflicts
                ),
            }

    def coverage(self, world_id: str, continuity: str) -> tuple[dict[str, object], ...]:
        with Session(self.engine) as session:
            rows = session.scalars(
                select(CoverageRecord).where(
                    CoverageRecord.world_id == world_id,
                    CoverageRecord.continuity == continuity,
                )
            ).all()
            return tuple(
                {
                    "domain": row.domain,
                    "status": row.status,
                    "indicators": tuple(row.indicators_json),
                }
                for row in rows
            )

    def summary(self, run_id: str) -> dict[str, object] | None:
        with Session(self.engine) as session:
            rows = session.scalars(
                select(WorkflowSummary)
                .where(WorkflowSummary.run_id == run_id)
                .order_by(WorkflowSummary.target_id)
            ).all()
            if not rows:
                return None
            if len(rows) == 1:
                return dict(rows[0].summary_json)
            return {
                "targets": [
                    {"target_id": row.target_id, "summary": dict(row.summary_json)}
                    for row in rows
                ]
            }

    def effective_knowledge(
        self,
        world_id: str,
        *,
        continuity: str | None = None,
        timepoint: str | None = None,
    ) -> tuple[dict[str, object], ...]:
        nodes = {
            str(node["node_id"]): dict(node)
            for node in self.accepted_graph(
                world_id, continuity=continuity, era_or_timepoint=timepoint
            )
            if (continuity is None or node["scope"].get("continuity") == continuity)
            and (
                timepoint is None or node["scope"].get("era_or_timepoint") == timepoint
            )
        }
        with Session(self.engine) as session:
            edges = session.execute(
                select(RelationshipAssertion, RelationshipRevision)
                .join(RelationshipRevision)
                .where(
                    RelationshipAssertion.source_node_id.in_(nodes),
                    RelationshipAssertion.target_node_id.in_(nodes),
                    RelationshipRevision.relation_type.in_(("IS_A", "INSTANCE_OF")),
                )
            ).all()
        for _pass in range(len(nodes)):
            changed = False
            for assertion, revision in edges:
                if continuity and revision.scope_json.get("continuity") != continuity:
                    continue
                if timepoint and (
                    (revision.valid_from and timepoint < revision.valid_from)
                    or (revision.valid_to and timepoint > revision.valid_to)
                ):
                    continue
                child = nodes[assertion.source_node_id]
                inherited = {
                    **nodes[assertion.target_node_id]["fields"],
                    **child["fields"],
                }
                if inherited != child["fields"]:
                    child["fields"] = inherited
                    child["field_origins"] = {
                        **nodes[assertion.target_node_id]["field_origins"],
                        **child["field_origins"],
                    }
                    changed = True
            if not changed:
                break
        return tuple(nodes[node_id] for node_id in sorted(nodes))
