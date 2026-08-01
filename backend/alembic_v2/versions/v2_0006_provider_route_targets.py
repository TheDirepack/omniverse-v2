"""Persist provider-level route targets and remove unused route weights."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "v2_0006_provider_route_targets"
down_revision = "v2_0005_question_scoped_leads"
branch_labels = None
depends_on = None

_CHECK_NAME = "ck_provider_route_candidate_exactly_one_target"


def _columns() -> set[str]:
    return {
        column["name"]
        for column in inspect(op.get_bind()).get_columns("provider_route_candidate")
    }


def upgrade() -> None:
    if "provider_id" in _columns():
        return
    with op.batch_alter_table("provider_route_candidate", recreate="always") as batch:
        batch.add_column(sa.Column("provider_id", sa.String(), nullable=True))
        batch.alter_column("model_id", existing_type=sa.String(), nullable=True)
        batch.drop_column("weight")
        batch.create_foreign_key(
            "fk_provider_route_candidate_provider_id_provider",
            "provider",
            ["provider_id"],
            ["id"],
        )
        batch.create_check_constraint(
            _CHECK_NAME, "(provider_id IS NULL) != (model_id IS NULL)"
        )


def downgrade() -> None:
    if "provider_id" not in _columns():
        return
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "DELETE FROM provider_candidate_health WHERE candidate_id IN "
            "(SELECT id FROM provider_route_candidate WHERE provider_id IS NOT NULL)"
        )
    )
    bind.execute(
        sa.text(
            "DELETE FROM provider_route_candidate WHERE provider_id IS NOT NULL"
        )
    )
    with op.batch_alter_table("provider_route_candidate", recreate="always") as batch:
        batch.drop_constraint(_CHECK_NAME, type_="check")
        batch.alter_column("model_id", existing_type=sa.String(), nullable=False)
        batch.add_column(
            sa.Column("weight", sa.Integer(), nullable=False, server_default="1")
        )
        batch.drop_column("provider_id")
