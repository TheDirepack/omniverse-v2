"""Store request-specific acquisition derivatives in the freshness cache."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "v2_0004_acquisition_cache_derivatives"
down_revision = "v2_0003_runtime_logging"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {
        column["name"] for column in inspect(bind).get_columns("acquisition_cache")
    }
    if "result_json" not in columns:
        op.add_column("acquisition_cache", sa.Column("result_json", sa.JSON()))


def downgrade() -> None:
    bind = op.get_bind()
    columns = {
        column["name"] for column in inspect(bind).get_columns("acquisition_cache")
    }
    if "result_json" in columns:
        op.drop_column("acquisition_cache", "result_json")
