"""Add a user-controllable display-order hint to provider_model."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "v2_0008_provider_model_sort_order"
down_revision = "v2_0007_wiki_research_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in inspect(bind).get_columns("provider_model")}
    if "sort_order" not in columns:
        op.add_column(
            "provider_model",
            sa.Column(
                "sort_order", sa.Integer(), nullable=False, server_default="0"
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in inspect(bind).get_columns("provider_model")}
    if "sort_order" in columns:
        op.drop_column("provider_model", "sort_order")
