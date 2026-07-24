"""Create the isolated Omniverse v2 baseline schema."""

from __future__ import annotations

from alembic import op

from app.v2.models import Base

revision = "v2_0001_baseline"
down_revision = None
branch_labels = None
depends_on = None

IMMUTABLE_TABLES = (
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
)


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, checkfirst=False)
    for table in IMMUTABLE_TABLES:
        for operation in ("UPDATE", "DELETE"):
            name = f"immutable_{table}_{operation.casefold()}"
            bind.exec_driver_sql(
                f"CREATE TRIGGER {name} BEFORE {operation} ON {table} "
                f"BEGIN SELECT RAISE(ABORT, '{table} is immutable'); END"
            )


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind(), checkfirst=False)
