"""Evaluation suite registry (``eval_suite``).

A suite is a versioned set of cases for one AI tool.  ``suite_key`` is a
stable dotted identifier such as ``kqa.retrieval``; changing the cases creates
a new ``version`` instead of mutating history.  ``case_count`` is a
denormalised counter maintained by the application when cases are added or
removed — the database enforces it as non-negative but deliberately does not
recount child rows with a trigger.
"""

from __future__ import annotations

import uuid

from sqlalchemy import (
    UUID,
    CheckConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class EvalSuite(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """A versioned evaluation suite."""

    __tablename__ = "eval_suite"

    # Repeated explicitly (instead of only inheriting from TenantMixin) so the
    # tenant columns are visible to __table_args__ composite constraints.
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    suite_key: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="Stable dotted identifier, e.g. kqa.retrieval",
    )
    tool: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="ops_assist | biz_ai | ip_content | intel_brief | doc_auto | "
        "staff_assistant | kqa | guardrail",
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    case_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="Denormalised counter maintained by the application",
    )
    # draft | active | retired
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="draft",
        server_default=text("'draft'"),
    )

    __table_args__ = (
        CheckConstraint(
            "tool IN ('ops_assist', 'biz_ai', 'ip_content', 'intel_brief', "
            "'doc_auto', 'staff_assistant', 'kqa', 'guardrail')",
            name="ck_eval_suite_tool_valid",
        ),
        CheckConstraint(
            "status IN ('draft', 'active', 'retired')",
            name="ck_eval_suite_status_valid",
        ),
        CheckConstraint(
            "version >= 1",
            name="ck_eval_suite_version_positive",
        ),
        CheckConstraint(
            "case_count >= 0",
            name="ck_eval_suite_case_count_non_negative",
        ),
        CheckConstraint(
            "suite_key ~ '^[a-z0-9][a-z0-9_.-]{1,63}$'",
            name="ck_eval_suite_key_format",
        ),
        UniqueConstraint(
            "org_id",
            "site_id",
            "suite_key",
            "version",
            name="uq_eval_suite_tenant_key_version",
        ),
        UniqueConstraint(
            "id",
            "org_id",
            "site_id",
            name="uq_eval_suite_id_tenant",
        ),
        Index("ix_eval_suite_tenant_status", "org_id", "site_id", "status"),
        Index("ix_eval_suite_tenant_tool", "org_id", "site_id", "tool"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return (
            f"EvalSuite(id={self.id!r}, key={self.suite_key!r}, "
            f"version={self.version!r}, status={self.status!r})"
        )
