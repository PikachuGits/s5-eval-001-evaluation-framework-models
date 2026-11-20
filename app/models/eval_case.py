"""Evaluation cases (``eval_case``).

A case belongs to one suite version and stores the model-facing input, optional
context, the points a good answer must hit, the points it must avoid, and an
optional reference output.  ``expected_points`` / ``forbidden_points`` are
JSONB arrays (strings or structured point objects); the database rejects
non-array values so reporting code can always iterate them.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class EvalCase(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """One test case inside a suite version."""

    __tablename__ = "eval_case"

    # Explicit tenant columns keep __table_args__ composite FKs visible.
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    suite_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    case_key: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="Stable identifier inside the suite"
    )
    input: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        comment="Prompt payload handed to the tool under test",
    )
    context: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        comment="Tenant-safe context fixtures (fictional data only)",
    )
    expected_points: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
        comment="Points a good answer must cover",
    )
    forbidden_points: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
        comment="Points or behaviours a good answer must avoid",
    )
    reference_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text()),
        nullable=False,
        default=list,
        server_default=text("'{}'::text[]"),
    )
    # easy | medium | hard
    difficulty: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="medium",
        server_default=text("'medium'"),
    )
    weight: Mapped[Decimal] = mapped_column(
        Numeric(6, 3),
        nullable=False,
        default=Decimal("1.000"),
        server_default=text("1.000"),
        comment="Relative weight inside the suite, must be > 0",
    )
    # pending | approved | rejected
    review_state: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["suite_id", "org_id", "site_id"],
            ["eval_suite.id", "eval_suite.org_id", "eval_suite.site_id"],
            name="fk_eval_case_suite_tenant",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "difficulty IN ('easy', 'medium', 'hard')",
            name="ck_eval_case_difficulty_valid",
        ),
        CheckConstraint(
            "review_state IN ('pending', 'approved', 'rejected')",
            name="ck_eval_case_review_state_valid",
        ),
        CheckConstraint(
            "weight > 0",
            name="ck_eval_case_weight_positive",
        ),
        CheckConstraint(
            "jsonb_typeof(input) = 'object'",
            name="ck_eval_case_input_object",
        ),
        CheckConstraint(
            "jsonb_typeof(context) = 'object'",
            name="ck_eval_case_context_object",
        ),
        CheckConstraint(
            "jsonb_typeof(expected_points) = 'array'",
            name="ck_eval_case_expected_points_array",
        ),
        CheckConstraint(
            "jsonb_typeof(forbidden_points) = 'array'",
            name="ck_eval_case_forbidden_points_array",
        ),
        CheckConstraint(
            "case_key ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{1,63}$'",
            name="ck_eval_case_key_format",
        ),
        UniqueConstraint("suite_id", "case_key", name="uq_eval_case_suite_case_key"),
        UniqueConstraint(
            "id",
            "suite_id",
            "org_id",
            "site_id",
            name="uq_eval_case_id_suite_tenant",
        ),
        Index("ix_eval_case_tenant_suite", "org_id", "site_id", "suite_id"),
        Index("ix_eval_case_suite_review", "suite_id", "review_state"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return (
            f"EvalCase(id={self.id!r}, suite_id={self.suite_id!r}, "
            f"key={self.case_key!r})"
        )
