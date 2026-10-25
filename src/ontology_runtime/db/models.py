"""SQLAlchemy Core table definitions for the generic ontology store."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

metadata = MetaData()


class Base(DeclarativeBase):
    metadata = metadata


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class ObjectRow(Base):
    """One row per ontology object, regardless of type."""

    __tablename__ = "objects"

    rid: Mapped[str] = mapped_column(String(96), primary_key=True)
    object_type: Mapped[str] = mapped_column(String(64), nullable=False)
    properties: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    deleted_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=_utcnow
    )

    __table_args__ = (
        CheckConstraint("jsonb_typeof(properties) = 'object'", name="objects_properties_is_object"),
        Index("ix_objects_type_live", "object_type", postgresql_where="deleted_at IS NULL"),
    )


class LinkRow(Base):
    """One row per link between two objects."""

    __tablename__ = "links"

    link_type: Mapped[str] = mapped_column(String(96), primary_key=True)
    from_rid: Mapped[str] = mapped_column(
        String(96), ForeignKey("objects.rid", ondelete="CASCADE"), primary_key=True
    )
    to_rid: Mapped[str] = mapped_column(
        String(96), ForeignKey("objects.rid", ondelete="CASCADE"), primary_key=True
    )
    properties: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("jsonb_typeof(properties) = 'object'", name="links_properties_is_object"),
        Index("ix_links_to_rid", "link_type", "to_rid"),
        Index("ix_links_from_rid", "link_type", "from_rid"),
    )


class ActionRunRow(Base):
    """Audit header for one action execution (or validated dry run)."""

    __tablename__ = "action_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    action_type: Mapped[str] = mapped_column(String(96), nullable=False)
    actor: Mapped[str] = mapped_column(String(128), nullable=False, default="unknown")
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True)
    params_hash: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    proposal_rid: Mapped[str | None] = mapped_column(String(96))
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("ix_action_runs_type_created", "action_type", "created_at"),)


class ActionEditRow(Base):
    """One row per object touched by an action run."""

    __tablename__ = "action_edits"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("action_runs.id", ondelete="CASCADE"), nullable=False
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    edit_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    object_type: Mapped[str] = mapped_column(String(64), nullable=False)
    rid: Mapped[str] = mapped_column(String(96), nullable=False)
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    __table_args__ = (
        UniqueConstraint("run_id", "seq", name="uq_action_edits_run_seq"),
        Index("ix_action_edits_rid", "rid"),
    )


class AgentRunRow(Base):
    """Audit record for one agent invocation."""

    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_api_name: Mapped[str] = mapped_column(String(96), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    transcript: Mapped[list[Any] | None] = mapped_column(JSONB)
    tool_call_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    actor: Mapped[str] = mapped_column(String(128), nullable=False, default="unknown")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("ix_agent_runs_agent_created", "agent_api_name", "created_at"),)


class OntologyIndexRow(Base):
    """Registry of DDL-created indexes so `sync-indexes` can drop stale ones."""

    __tablename__ = "ontology_indexes"

    name: Mapped[str] = mapped_column(String(128), primary_key=True)
    object_type: Mapped[str] = mapped_column(String(64), nullable=False)
    ddl: Mapped[str] = mapped_column(Text, nullable=False)
    schema_hash: Mapped[str] = mapped_column(String(64), nullable=False)
