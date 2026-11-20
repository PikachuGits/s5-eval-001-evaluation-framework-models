"""Evaluation runs (``eval_run``).

One run executes a suite version against one target tool/prompt/model
combination.  ``pass_rate`` is a percentage in ``[0, 100]`` and ``score_avg``
uses the same 0–100 convention; both stay NULL until the run reaches a
terminal state.  ``token_usage`` is the total token count reported by the
runtime (prompt + completion), kept as BIGINT so large nightly runs fit.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class EvalRun(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """One execution of a suite version."""

    __tablename__ = "eval_run"

    # Explicit tenant columns keep __table_args__ composite FKs visible.
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    suite_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    suite_version: Mapped[int] = mapped_column(Integer, nullable=False)
    target_tool: Mapped[str] = mapped_column(String(32), nullable=False)
    target_prompt_version: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    target_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # ci_pr | nightly | manual
    trigger: Mapped[str] = mapped_column(String(16), nullable=False)
    git_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # queued | running | succeeded | failed | cancelled
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="queued",
        server_default=text("'queued'"),
    )
    pass_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True, comment="Percentage in [0, 100]"
    )
    score_avg: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 3), nullable=True, comment="Average score on a 0–100 scale"
    )
    token_usage: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="Total prompt + completion tokens",
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["suite_id", "org_id", "site_id"],
            ["eval_suite.id", "eval_suite.org_id", "eval_suite.site_id"],
            name="fk_eval_run_suite_tenant",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "target_tool IN ('ops_assist', 'biz_ai', 'ip_content', 'intel_brief', "
            "'doc_auto', 'staff_assistant', 'kqa', 'guardrail')",
            name="ck_eval_run_target_tool_valid",
        ),
        CheckConstraint(
            "trigger IN ('ci_pr', 'nightly', 'manual')",
            name="ck_eval_run_trigger_valid",
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')",
            name="ck_eval_run_status_valid",
        ),
        CheckConstraint(
            "suite_version >= 1",
            name="ck_eval_run_suite_version_positive",
        ),
        CheckConstraint(
            "pass_rate IS NULL OR (pass_rate >= 0 AND pass_rate <= 100)",
            name="ck_eval_run_pass_rate_range",
        ),
        CheckConstraint(
            "score_avg IS NULL OR score_avg >= 0",
            name="ck_eval_run_score_avg_non_negative",
        ),
        CheckConstraint(
            "token_usage >= 0",
            name="ck_eval_run_token_usage_non_negative",
        ),
        CheckConstraint(
            "finished_at IS NULL OR finished_at >= started_at",
            name="ck_eval_run_finished_after_started",
        ),
        CheckConstraint(
            "git_sha IS NULL OR git_sha ~ '^[0-9a-f]{7,64}$'",
            name="ck_eval_run_git_sha_format",
        ),
        UniqueConstraint(
            "id",
            "suite_id",
            "org_id",
            "site_id",
            name="uq_eval_run_id_suite_tenant",
        ),
        Index("ix_eval_run_suite_started", "suite_id", "started_at"),
        Index("ix_eval_run_tenant_status", "org_id", "site_id", "status"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return (
            f"EvalRun(id={self.id!r}, suite_id={self.suite_id!r}, "
            f"status={self.status!r})"
        )
