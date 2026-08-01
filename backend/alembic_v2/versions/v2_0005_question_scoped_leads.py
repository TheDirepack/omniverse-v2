"""Scope search-lead identity to each planned question."""

from __future__ import annotations

from alembic import op
from sqlalchemy import inspect

revision = "v2_0005_question_scoped_leads"
down_revision = "v2_0004_acquisition_cache_derivatives"
branch_labels = None
depends_on = None

_NAMING_CONVENTION = {"uq": "uq_%(table_name)s_%(column_0_name)s"}


def _unique_columns() -> set[tuple[str, ...]]:
    return {
        tuple(constraint["column_names"])
        for constraint in inspect(op.get_bind()).get_unique_constraints("search_lead")
    }


def upgrade() -> None:
    old_columns = ("workspace_id", "canonical_url")
    if old_columns not in _unique_columns():
        return
    with op.batch_alter_table(
        "search_lead", recreate="always", naming_convention=_NAMING_CONVENTION
    ) as batch:
        batch.drop_constraint("uq_search_lead_workspace_id", type_="unique")
        batch.create_unique_constraint(
            "uq_search_lead_workspace_question_url",
            ["workspace_id", "question_id", "canonical_url"],
        )


def downgrade() -> None:
    new_columns = ("workspace_id", "question_id", "canonical_url")
    if new_columns not in _unique_columns():
        return
    with op.batch_alter_table(
        "search_lead", recreate="always", naming_convention=_NAMING_CONVENTION
    ) as batch:
        batch.drop_constraint("uq_search_lead_workspace_question_url", type_="unique")
        batch.create_unique_constraint(
            "uq_search_lead_workspace_id", ["workspace_id", "canonical_url"]
        )
