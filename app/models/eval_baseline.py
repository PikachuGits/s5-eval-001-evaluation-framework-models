"""Baseline pins (``eval_baseline``).

A baseline records that a completed run is the reference for a suite.  The
table keeps history: every pin stays as its own row, and the retention job
treats any run referenced here as permanent, even after 180 days.

The composite foreign key ``(run_id, suite_id)`` guarantees that a baseline
cannot point at a run from a different suite.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKeyConstraint,
    Index,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class EvalBaseline(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """A run pinned as a suite baseline."""

    __tablename__ = "eval_baseline"

    suite_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    set_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    set_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["run_id", "suite_id"],
            ["eval_run.id", "eval_run.suite_id"],
            name="fk_eval_baseline_run",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["suite_id"],
            ["eval_suite.id"],
            name="fk_eval_baseline_suite",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("suite_id", "run_id", name="uq_eval_baseline_suite_run"),
        Index("ix_eval_baseline_suite_set_at", "suite_id", "set_at"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return (
            f"EvalBaseline(id={self.id!r}, suite_id={self.suite_id!r}, "
            f"run_id={self.run_id!r})"
        )
