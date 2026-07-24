"""Complete research freshness scope and add lookup indexes."""

from __future__ import annotations

from alembic import op
from sqlalchemy import inspect

revision = "v2_0002_freshness_scope"
down_revision = "v2_0001_baseline"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {item["name"] for item in inspect(op.get_bind()).get_columns(table)}


def _indexes(table: str) -> set[str]:
    return {item["name"] for item in inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    workspace = _columns("research_workspace")
    coverage = _columns("coverage_record")
    with op.batch_alter_table("research_workspace") as batch:
        if "era_or_timepoint" not in workspace:
            batch.add_column(
                __import__("sqlalchemy").Column(
                    "era_or_timepoint",
                    __import__("sqlalchemy").String(),
                    nullable=False,
                    server_default="unspecified",
                )
            )
        if "branch_id" not in workspace:
            batch.add_column(
                __import__("sqlalchemy").Column(
                    "branch_id",
                    __import__("sqlalchemy").String(),
                    nullable=False,
                    server_default="main",
                )
            )
        if "conditions_key" not in workspace:
            batch.add_column(
                __import__("sqlalchemy").Column(
                    "conditions_key",
                    __import__("sqlalchemy").String(),
                    nullable=False,
                    server_default="[]",
                )
            )
    with op.batch_alter_table("coverage_record") as batch:
        if "era_or_timepoint" not in coverage:
            batch.add_column(
                __import__("sqlalchemy").Column(
                    "era_or_timepoint",
                    __import__("sqlalchemy").String(),
                    nullable=False,
                    server_default="unspecified",
                )
            )
        if "branch_id" not in coverage:
            batch.add_column(
                __import__("sqlalchemy").Column(
                    "branch_id",
                    __import__("sqlalchemy").String(),
                    nullable=False,
                    server_default="main",
                )
            )
        if "conditions_key" not in coverage:
            batch.add_column(
                __import__("sqlalchemy").Column(
                    "conditions_key",
                    __import__("sqlalchemy").String(),
                    nullable=False,
                    server_default="[]",
                )
            )
    if "ix_coverage_freshness_scope" not in _indexes("coverage_record"):
        op.create_index(
            "ix_coverage_freshness_scope",
            "coverage_record",
            [
                "world_id",
                "continuity",
                "era_or_timepoint",
                "branch_id",
                "conditions_key",
                "status",
            ],
        )
    if "ix_evidence_freshness_scope" not in _indexes("evidence_fragment"):
        op.create_index(
            "ix_evidence_freshness_scope",
            "evidence_fragment",
            ["world_id", "continuity", "era_or_timepoint", "branch_id"],
        )


def downgrade() -> None:
    if "ix_evidence_freshness_scope" in _indexes("evidence_fragment"):
        op.drop_index("ix_evidence_freshness_scope", table_name="evidence_fragment")
    if "ix_coverage_freshness_scope" in _indexes("coverage_record"):
        op.drop_index("ix_coverage_freshness_scope", table_name="coverage_record")
    coverage = _columns("coverage_record")
    workspace = _columns("research_workspace")
    with op.batch_alter_table("coverage_record") as batch:
        for name in ("conditions_key", "branch_id", "era_or_timepoint"):
            if name in coverage:
                batch.drop_column(name)
    with op.batch_alter_table("research_workspace") as batch:
        for name in ("conditions_key", "branch_id", "era_or_timepoint"):
            if name in workspace:
                batch.drop_column(name)
