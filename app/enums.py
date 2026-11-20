"""Enum values fixed by the work order.

The same literal sets are repeated in the Alembic migration because migrations
must not import application modules; ``tests/test_models.py`` asserts that the
database rejects values outside these sets and ``tests/test_schemas.py`` keeps
the Pydantic layer aligned.
"""

from __future__ import annotations

from enum import StrEnum


class EvalTool(StrEnum):
    """AI tool whose quality is measured by a suite."""

    OPS_ASSIST = "ops_assist"
    BIZ_AI = "biz_ai"
    IP_CONTENT = "ip_content"
    INTEL_BRIEF = "intel_brief"
    DOC_AUTO = "doc_auto"
    STAFF_ASSISTANT = "staff_assistant"
    KQA = "kqa"
    GUARDRAIL = "guardrail"


class SuiteStatus(StrEnum):
    """Lifecycle state of an evaluation suite."""

    DRAFT = "draft"
    ACTIVE = "active"
    RETIRED = "retired"


class CaseDifficulty(StrEnum):
    """Difficulty bucket used for reporting and sampling."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class ReviewState(StrEnum):
    """Human review state of a case's expected/forbidden points."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class RunTrigger(StrEnum):
    """What started an evaluation run."""

    CI_PR = "ci_pr"
    NIGHTLY = "nightly"
    MANUAL = "manual"


class RunStatus(StrEnum):
    """Lifecycle state of an evaluation run."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


EVAL_TOOLS = tuple(item.value for item in EvalTool)
SUITE_STATUSES = tuple(item.value for item in SuiteStatus)
CASE_DIFFICULTIES = tuple(item.value for item in CaseDifficulty)
REVIEW_STATES = tuple(item.value for item in ReviewState)
RUN_TRIGGERS = tuple(item.value for item in RunTrigger)
RUN_STATUSES = tuple(item.value for item in RunStatus)
