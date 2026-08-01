"""Add DB-backed configurable logging settings."""

from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "v2_0003_runtime_logging"
down_revision = "v2_0002_freshness_scope"
branch_labels = None
depends_on = None

DEFAULT_LOGGING = {
    "enabled": True,
    "folder": "logs",
    "server_level": "INFO",
    "agent_level": "INFO",
    "server_max_bytes": 5_000_000,
    "agent_max_bytes": 5_000_000,
    "server_backup_count": 5,
    "agent_backup_count": 5,
}


def upgrade() -> None:
    bind = op.get_bind()
    if "runtime_setting" not in inspect(bind).get_table_names():
        op.create_table(
            "runtime_setting",
            sa.Column("key", sa.String(), primary_key=True),
            sa.Column("value_json", sa.JSON(), nullable=False),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
        )
    bind.execute(
        sa.text(
            "INSERT OR IGNORE INTO runtime_setting (key, value_json, updated_at) "
            "VALUES ('logging', :value, CURRENT_TIMESTAMP)"
        ),
        {"value": json.dumps(DEFAULT_LOGGING)},
    )


def downgrade() -> None:
    # The dynamic v2_0001 baseline imports current metadata and expects this table
    # to exist during its own downgrade. It will remove the table at base.
    pass
