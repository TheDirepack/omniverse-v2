"""Persist qualified wiki inventories, queues, and reusable workspace knowledge."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "v2_0007_wiki_research_foundation"
down_revision = "v2_0006_provider_route_targets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    tables = set(inspect(op.get_bind()).get_table_names())
    if "wiki_profile" not in tables:
        op.create_table(
            "wiki_profile",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("world_id", sa.String(), sa.ForeignKey("world.id"), nullable=False),
            sa.Column("continuity", sa.String(), nullable=False),
            sa.Column("era_or_timepoint", sa.String(), nullable=False),
            sa.Column("branch_id", sa.String(), nullable=False),
            sa.Column("conditions_key", sa.String(), nullable=False),
            sa.Column("canonical_url", sa.String(), nullable=False),
            sa.Column("sitemap_url", sa.String(), nullable=False),
            sa.Column(
                "source_class", sa.String(), nullable=False, server_default="SECONDARY"
            ),
            sa.Column("publisher", sa.String()),
            sa.Column("lineage_id", sa.String()),
            sa.Column("qualified_at", sa.DateTime(), nullable=False),
            sa.Column("inventory_fetched_at", sa.DateTime()),
            sa.UniqueConstraint(
                "world_id",
                "continuity",
                "era_or_timepoint",
                "branch_id",
                "conditions_key",
                name="uq_wiki_profile_scope",
            ),
        )
    if "wiki_inventory_page" not in tables:
        op.create_table(
            "wiki_inventory_page",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column(
                "profile_id", sa.String(), sa.ForeignKey("wiki_profile.id"), nullable=False
            ),
            sa.Column("canonical_url", sa.String(), nullable=False),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("aliases_json", sa.JSON(), nullable=False),
            sa.Column("section_terms_json", sa.JSON(), nullable=False),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("last_modified", sa.String()),
            sa.Column("indexed_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint(
                "profile_id",
                "canonical_url",
                name="uq_wiki_inventory_page_profile_url",
            ),
        )
        op.create_index(
            "ix_wiki_inventory_page_profile_active",
            "wiki_inventory_page",
            ["profile_id", "active"],
        )
    if "wiki_page_queue" not in tables:
        op.create_table(
            "wiki_page_queue",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column(
                "workspace_id",
                sa.String(),
                sa.ForeignKey("research_workspace.id"),
                nullable=False,
            ),
            sa.Column(
                "inventory_page_id",
                sa.String(),
                sa.ForeignKey("wiki_inventory_page.id"),
                nullable=False,
            ),
            sa.Column("question_ids_json", sa.JSON(), nullable=False),
            sa.Column("priority", sa.Integer(), nullable=False),
            sa.Column("score", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="PENDING"),
            sa.Column("selected_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint(
                "workspace_id",
                "inventory_page_id",
                name="uq_wiki_page_queue_workspace_page",
            ),
        )
        op.create_index(
            "ix_wiki_page_queue_workspace_status_order",
            "wiki_page_queue",
            ["workspace_id", "status", "priority", "score"],
        )
    if "workspace_knowledge_publication" not in tables:
        op.create_table(
            "workspace_knowledge_publication",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column(
                "workspace_id",
                sa.String(),
                sa.ForeignKey("research_workspace.id"),
                nullable=False,
            ),
            sa.Column(
                "evidence_fragment_id",
                sa.String(),
                sa.ForeignKey("evidence_fragment.id"),
                nullable=False,
            ),
            sa.Column("published_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint(
                "workspace_id",
                "evidence_fragment_id",
                name="uq_workspace_knowledge_publication_fragment",
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(inspect(bind).get_table_names())
    for table in (
        "workspace_knowledge_publication",
        "wiki_page_queue",
        "wiki_inventory_page",
        "wiki_profile",
    ):
        if table in tables:
            op.drop_table(table)
