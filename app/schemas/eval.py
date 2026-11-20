"""Pydantic schemas for the evaluation framework tables.

The schemas mirror the database checks so API callers get a fail-fast 422
instead of an IntegrityError, but the database remains the source of truth for
tenant-level uniqueness, composite foreign keys and array/JSON shape.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.enums import (
    CaseDifficulty,
    EvalTool,
    ReviewState,
    RunStatus,
    RunTrigger,
    SuiteStatus,
)

SUITE_KEY_PATTERN = r"^[a-z0-9][a-z0-9_.-]{1,63}$"
CASE_KEY_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{1,63}$"
GIT_SHA_PATTERN = r"^[0-9a-f]{7,64}$"


class TenantFields(BaseModel):
    """Tenant scope supplied by the caller (never by a public client)."""

    model_config = ConfigDict(extra="forbid")

    org_id: uuid.UUID
    site_id: uuid.UUID
    created_by: uuid.UUID | None = None


class EvalSuiteBase(BaseModel):
    """Shared fields of ``eval_suite``."""

    model_config = ConfigDict(extra="forbid")

    suite_key: str = Field(min_length=2, max_length=64, pattern=SUITE_KEY_PATTERN)
    tool: EvalTool
    version: int = Field(default=1, ge=1)
    case_count: int = Field(default=0, ge=0)
    status: SuiteStatus = SuiteStatus.DRAFT


class EvalSuiteCreate(TenantFields, EvalSuiteBase):
    """Payload for creating a suite version."""


class EvalSuiteRead(TenantFields):
    """Row projection returned to callers."""

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: uuid.UUID
    suite_key: str
    tool: EvalTool
    version: int
    case_count: int
    status: SuiteStatus
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class EvalCaseBase(BaseModel):
    """Shared fields of ``eval_case``."""

    model_config = ConfigDict(extra="forbid")

    suite_id: uuid.UUID
    case_key: str = Field(min_length=2, max_length=64, pattern=CASE_KEY_PATTERN)
    input: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    expected_points: list[Any] = Field(default_factory=list)
    forbidden_points: list[Any] = Field(default_factory=list)
    reference_output: str | None = None
    tags: list[str] = Field(default_factory=list)
    difficulty: CaseDifficulty = CaseDifficulty.MEDIUM
    weight: Decimal = Field(default=Decimal("1.000"), gt=0, max_digits=6, decimal_places=3)
    review_state: ReviewState = ReviewState.PENDING

    @field_validator("expected_points", "forbidden_points")
    @classmethod
    def _points_are_json_values(cls, value: list[Any]) -> list[Any]:
        # ``Any`` accepts anything JSON-serialisable; reject bytes and other
        # Python objects that JSONB could not store.
        import json

        try:
            json.dumps(value)
        except TypeError as exc:
            raise ValueError("points must be JSON-serialisable") from exc
        return value

    @field_validator("tags")
    @classmethod
    def _tags_shape(cls, value: list[str]) -> list[str]:
        clean: list[str] = []
        seen: set[str] = set()
        for tag in value:
            normalised = tag.strip()
            if not normalised:
                raise ValueError("tags must not contain empty strings")
            if normalised not in seen:
                seen.add(normalised)
                clean.append(normalised)
        return clean


class EvalCaseCreate(TenantFields, EvalCaseBase):
    """Payload for creating a case."""


class EvalCaseRead(TenantFields):
    """Row projection for ``eval_case``."""

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: uuid.UUID
    suite_id: uuid.UUID
    case_key: str
    input: dict[str, Any]
    context: dict[str, Any]
    expected_points: list[Any]
    forbidden_points: list[Any]
    reference_output: str | None
    tags: list[str]
    difficulty: CaseDifficulty
    weight: Decimal
    review_state: ReviewState
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class EvalRunBase(BaseModel):
    """Shared fields of ``eval_run``."""

    model_config = ConfigDict(extra="forbid")

    suite_id: uuid.UUID
    suite_version: int = Field(ge=1)
    target_tool: EvalTool
    target_prompt_version: str | None = Field(default=None, max_length=64)
    target_model: str | None = Field(default=None, max_length=64)
    trigger: RunTrigger
    git_sha: str | None = Field(default=None, pattern=GIT_SHA_PATTERN)
    status: RunStatus = RunStatus.QUEUED
    pass_rate: Decimal | None = Field(default=None, ge=0, le=100, max_digits=5, decimal_places=2)
    score_avg: Decimal | None = Field(default=None, ge=0, max_digits=6, decimal_places=3)
    token_usage: int = Field(default=0, ge=0)
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @model_validator(mode="after")
    def _time_order(self) -> "EvalRunBase":
        if (
            self.started_at is not None
            and self.finished_at is not None
            and self.finished_at < self.started_at
        ):
            raise ValueError("finished_at must not be earlier than started_at")
        return self


class EvalRunCreate(TenantFields, EvalRunBase):
    """Payload for opening a run."""


class EvalRunRead(TenantFields):
    """Row projection for ``eval_run``."""

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: uuid.UUID
    suite_id: uuid.UUID
    suite_version: int
    target_tool: EvalTool
    target_prompt_version: str | None
    target_model: str | None
    trigger: RunTrigger
    git_sha: str | None
    status: RunStatus
    pass_rate: Decimal | None
    score_avg: Decimal | None
    token_usage: int
    started_at: datetime
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class EvalResultBase(BaseModel):
    """Shared fields of ``eval_result``."""

    model_config = ConfigDict(extra="forbid")

    run_id: uuid.UUID
    case_id: uuid.UUID
    suite_id: uuid.UUID = Field(
        description="Must equal both the run's and the case's suite_id; "
        "the database composite FKs enforce this."
    )
    output_text: str | None = None
    output_json: Any | None = None
    score: Decimal | None = Field(default=None, ge=0, le=100, max_digits=6, decimal_places=3)
    passed: bool | None = None
    point_hits: list[Any] = Field(default_factory=list)
    violations: list[Any] = Field(default_factory=list)
    latency_ms: int | None = Field(default=None, ge=0)
    judge_trace: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class EvalResultCreate(TenantFields, EvalResultBase):
    """Payload for writing a case judgment."""


class EvalResultRead(TenantFields):
    """Row projection for ``eval_result``."""

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: uuid.UUID
    run_id: uuid.UUID
    case_id: uuid.UUID
    suite_id: uuid.UUID
    output_text: str | None
    output_json: Any | None
    score: Decimal | None
    passed: bool | None
    point_hits: list[Any]
    violations: list[Any]
    latency_ms: int | None
    judge_trace: dict[str, Any]
    error: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class EvalBaselineBase(BaseModel):
    """Shared fields of ``eval_baseline``."""

    model_config = ConfigDict(extra="forbid")

    suite_id: uuid.UUID
    run_id: uuid.UUID
    set_by: uuid.UUID | None = None
    set_at: datetime | None = None
    note: str | None = None


class EvalBaselineCreate(TenantFields, EvalBaselineBase):
    """Payload for pinning a run as a baseline."""


class EvalBaselineRead(TenantFields):
    """Row projection for ``eval_baseline``."""

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: uuid.UUID
    suite_id: uuid.UUID
    run_id: uuid.UUID
    set_by: uuid.UUID | None
    set_at: datetime
    note: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
