"""Evaluation results (``eval_result``).

One row per (run, case).  The unique key ``(run_id, case_id)`` makes result
writes idempotent: a retried worker cannot silently create a second judgment
for the same case, it hits the constraint and must update the existing row.

The two composite foreign keys are deliberate:

* ``(run_id, suite_id) -> eval_run (id, suite_id)`` with ``ON DELETE CASCADE``
  so deleting a run cannot leave orphan results;
* ``(case_id, suite_id) -> eval_case (id, suite_id)`` with ``ON DELETE
  RESTRICT`` so a result can only reference a case from the run's own suite.

PostgreSQL requires the referenced column pairs to be backed by unique
constraints; ``eval_run`` and ``eval_case`` therefore carry a redundant
``UNIQUE (id, suite_id)`` next to their primary keys.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class EvalResult(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Judgment of one case inside one run."""

    __tablename__ = "eval_result"

    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    suite_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        comment="Must match both the run's and the case's suite",
    )
    output_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_json: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    score: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 3), nullable=True, comment="Score on a 0–100 scale"
    )
    passed: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True, comment="NULL when the case could not be judged"
    )
    point_hits: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
        comment="Expected points actually covered",
    )
    violations: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
        comment="Forbidden points or policy violations detected",
    )
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    judge_trace: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        comment="Judge model, rubric version and intermediate reasoning",
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["run_id", "suite_id"],
            ["eval_run.id", "eval_run.suite_id"],
            name="fk_eval_result_run",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["case_id", "suite_id"],
            ["eval_case.id", "eval_case.suite_id"],
            name="fk_eval_result_case",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "score IS NULL OR (score >= 0 AND score <= 100)",
            name="ck_eval_result_score_range",
        ),
        CheckConstraint(
            "latency_ms IS NULL OR latency_ms >= 0",
            name="ck_eval_result_latency_non_negative",
        ),
        CheckConstraint(
            "jsonb_typeof(point_hits) = 'array'",
            name="ck_eval_result_point_hits_array",
        ),
        CheckConstraint(
            "jsonb_typeof(violations) = 'array'",
            name="ck_eval_result_violations_array",
        ),
        CheckConstraint(
            "jsonb_typeof(judge_trace) = 'object'",
            name="ck_eval_result_judge_trace_object",
        ),
        UniqueConstraint("run_id", "case_id", name="uq_eval_result_run_case"),
        Index("ix_eval_result_tenant_run", "org_id", "site_id", "run_id"),
        Index("ix_eval_result_case", "case_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return (
            f"EvalResult(id={self.id!r}, run_id={self.run_id!r}, "
            f"case_id={self.case_id!r}, passed={self.passed!r})"
        )
