"""initial core tables

Revision ID: 0001
Revises:
Create Date: 2026-10-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "objects",
        sa.Column("rid", sa.String(96), primary_key=True),
        sa.Column("object_type", sa.String(64), nullable=False),
        sa.Column("properties", postgresql.JSONB, nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("jsonb_typeof(properties) = 'object'", name="objects_properties_is_object"),
    )
    op.create_index(
        "ix_objects_type_live",
        "objects",
        ["object_type"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "links",
        sa.Column("link_type", sa.String(96), primary_key=True),
        sa.Column("from_rid", sa.String(96), sa.ForeignKey("objects.rid", ondelete="CASCADE"), primary_key=True),
        sa.Column("to_rid", sa.String(96), sa.ForeignKey("objects.rid", ondelete="CASCADE"), primary_key=True),
        sa.Column("properties", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("jsonb_typeof(properties) = 'object'", name="links_properties_is_object"),
    )
    op.create_index("ix_links_to_rid", "links", ["link_type", "to_rid"])
    op.create_index("ix_links_from_rid", "links", ["link_type", "from_rid"])

    op.create_table(
        "action_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("action_type", sa.String(96), nullable=False),
        sa.Column("actor", sa.String(128), nullable=False, server_default="unknown"),
        sa.Column("idempotency_key", sa.String(128), unique=True),
        sa.Column("params_hash", sa.String(64)),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("dry_run", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("params", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("result", postgresql.JSONB),
        sa.Column("error", postgresql.JSONB),
        sa.Column("proposal_rid", sa.String(96)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_action_runs_type_created", "action_runs", ["action_type", "created_at"])

    op.create_table(
        "action_edits",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("action_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("seq", sa.Integer, nullable=False),
        sa.Column("edit_kind", sa.String(32), nullable=False),
        sa.Column("object_type", sa.String(64), nullable=False),
        sa.Column("rid", sa.String(96), nullable=False),
        sa.Column("before", postgresql.JSONB),
        sa.Column("after", postgresql.JSONB),
        sa.UniqueConstraint("run_id", "seq", name="uq_action_edits_run_seq"),
    )
    op.create_index("ix_action_edits_rid", "action_edits", ["rid"])

    op.create_table(
        "agent_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_api_name", sa.String(96), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("input_text", sa.Text, nullable=False),
        sa.Column("transcript", postgresql.JSONB),
        sa.Column("tool_call_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("input_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("error", sa.Text),
        sa.Column("actor", sa.String(128), nullable=False, server_default="unknown"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_agent_runs_agent_created", "agent_runs", ["agent_api_name", "created_at"])

    op.create_table(
        "ontology_indexes",
        sa.Column("name", sa.String(128), primary_key=True),
        sa.Column("object_type", sa.String(64), nullable=False),
        sa.Column("ddl", sa.Text, nullable=False),
        sa.Column("schema_hash", sa.String(64), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("ontology_indexes")
    op.drop_table("agent_runs")
    op.drop_table("action_edits")
    op.drop_table("action_runs")
    op.drop_table("links")
    op.drop_table("objects")
