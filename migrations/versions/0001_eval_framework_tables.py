"""create evaluation framework tables

Revision ID: 0001_eval_framework_tables
Revises:
Create Date: 2026-11-20 10:00:00

Tables: eval_suite, eval_case, eval_run, eval_result, eval_baseline.

Composite foreign keys enforce two invariants that plain column-level FKs
cannot express:

* ``eval_result (run_id, suite_id) -> eval_run (id, suite_id)`` — results
  cannot point at a run from another tenant scope;
* ``eval_result (case_id, suite_id) -> eval_case (id, suite_id)`` — a result
  cannot judge a case that belongs to a different suite than its run;
* ``eval_baseline (run_id, suite_id) -> eval_run (id, suite_id)`` — a baseline
  cannot pin a run from another suite.

PostgreSQL requires unique constraints on the referenced column pairs;
``eval_run`` and ``eval_case`` therefore carry ``UNIQUE (id, suite_id)``.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_eval_framework_tables"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TENANT_COMMON = (
    sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=False),
)

TIMESTAMP_COMMON = (
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        nullable=False,
    ),
    sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        nullable=False,
    ),
    sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
)


def _id_column() -> sa.Column:
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        server_default=sa.text("gen_random_uuid()"),
        nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        "eval_suite",
        _id_column(),
        *TENANT_COMMON,
        sa.Column(
            "suite_key",
            sa.String(length=64),
            nullable=False,
            comment="Stable dotted identifier, e.g. kqa.retrieval",
        ),
        sa.Column(
            "tool",
            sa.String(length=32),
            nullable=False,
            comment="ops_assist | biz_ai | ip_content | intel_brief | doc_auto | "
            "staff_assistant | kqa | guardrail",
        ),
        sa.Column(
            "version",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column(
            "case_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
            comment="Denormalised counter maintained by the application",
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'draft'"),
            nullable=False,
        ),
        *TIMESTAMP_COMMON,
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "tool IN ('ops_assist', 'biz_ai', 'ip_content', 'intel_brief', "
            "'doc_auto', 'staff_assistant', 'kqa', 'guardrail')",
            name="ck_eval_suite_tool_valid",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'retired')",
            name="ck_eval_suite_status_valid",
        ),
        sa.CheckConstraint("version >= 1", name="ck_eval_suite_version_positive"),
        sa.CheckConstraint(
            "case_count >= 0", name="ck_eval_suite_case_count_non_negative"
        ),
        sa.CheckConstraint(
            "suite_key ~ '^[a-z0-9][a-z0-9_.-]{1,63}$'",
            name="ck_eval_suite_key_format",
        ),
        sa.UniqueConstraint(
            "org_id",
            "site_id",
            "suite_key",
            "version",
            name="uq_eval_suite_tenant_key_version",
        ),
    )
    op.create_index(
        "ix_eval_suite_tenant_status",
        "eval_suite",
        ["org_id", "site_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_eval_suite_tenant_tool",
        "eval_suite",
        ["org_id", "site_id", "tool"],
        unique=False,
    )

    op.create_table(
        "eval_case",
        _id_column(),
        *TENANT_COMMON,
        sa.Column("suite_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "case_key",
            sa.String(length=64),
            nullable=False,
            comment="Stable identifier inside the suite",
        ),
        sa.Column(
            "input",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
            comment="Prompt payload handed to the tool under test",
        ),
        sa.Column(
            "context",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
            comment="Tenant-safe context fixtures (fictional data only)",
        ),
        sa.Column(
            "expected_points",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
            comment="Points a good answer must cover",
        ),
        sa.Column(
            "forbidden_points",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
            comment="Points or behaviours a good answer must avoid",
        ),
        sa.Column("reference_output", sa.Text(), nullable=True),
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "difficulty",
            sa.String(length=16),
            server_default=sa.text("'medium'"),
            nullable=False,
        ),
        sa.Column(
            "weight",
            sa.Numeric(precision=6, scale=3),
            server_default=sa.text("1.000"),
            nullable=False,
            comment="Relative weight inside the suite, must be > 0",
        ),
        sa.Column(
            "review_state",
            sa.String(length=16),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        *TIMESTAMP_COMMON,
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["suite_id"],
            ["eval_suite.id"],
            name="fk_eval_case_suite_id",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "difficulty IN ('easy', 'medium', 'hard')",
            name="ck_eval_case_difficulty_valid",
        ),
        sa.CheckConstraint(
            "review_state IN ('pending', 'approved', 'rejected')",
            name="ck_eval_case_review_state_valid",
        ),
        sa.CheckConstraint("weight > 0", name="ck_eval_case_weight_positive"),
        sa.CheckConstraint(
            "jsonb_typeof(input) = 'object'", name="ck_eval_case_input_object"
        ),
        sa.CheckConstraint(
            "jsonb_typeof(context) = 'object'", name="ck_eval_case_context_object"
        ),
        sa.CheckConstraint(
            "jsonb_typeof(expected_points) = 'array'",
            name="ck_eval_case_expected_points_array",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(forbidden_points) = 'array'",
            name="ck_eval_case_forbidden_points_array",
        ),
        sa.CheckConstraint(
            "case_key ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{1,63}$'",
            name="ck_eval_case_key_format",
        ),
        sa.UniqueConstraint(
            "suite_id", "case_key", name="uq_eval_case_suite_case_key"
        ),
        sa.UniqueConstraint("id", "suite_id", name="uq_eval_case_id_suite"),
    )
    op.create_index(
        "ix_eval_case_tenant_suite",
        "eval_case",
        ["org_id", "site_id", "suite_id"],
        unique=False,
    )
    op.create_index(
        "ix_eval_case_suite_review",
        "eval_case",
        ["suite_id", "review_state"],
        unique=False,
    )

    op.create_table(
        "eval_run",
        _id_column(),
        *TENANT_COMMON,
        sa.Column("suite_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("suite_version", sa.Integer(), nullable=False),
        sa.Column("target_tool", sa.String(length=32), nullable=False),
        sa.Column("target_prompt_version", sa.String(length=64), nullable=True),
        sa.Column("target_model", sa.String(length=64), nullable=True),
        sa.Column("trigger", sa.String(length=16), nullable=False),
        sa.Column("git_sha", sa.String(length=64), nullable=True),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'queued'"),
            nullable=False,
        ),
        sa.Column(
            "pass_rate",
            sa.Numeric(precision=5, scale=2),
            nullable=True,
            comment="Percentage in [0, 100]",
        ),
        sa.Column(
            "score_avg",
            sa.Numeric(precision=6, scale=3),
            nullable=True,
            comment="Average score on a 0–100 scale",
        ),
        sa.Column(
            "token_usage",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
            comment="Total prompt + completion tokens",
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        *TIMESTAMP_COMMON,
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["suite_id"],
            ["eval_suite.id"],
            name="fk_eval_run_suite_id",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "target_tool IN ('ops_assist', 'biz_ai', 'ip_content', 'intel_brief', "
            "'doc_auto', 'staff_assistant', 'kqa', 'guardrail')",
            name="ck_eval_run_target_tool_valid",
        ),
        sa.CheckConstraint(
            "trigger IN ('ci_pr', 'nightly', 'manual')",
            name="ck_eval_run_trigger_valid",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')",
            name="ck_eval_run_status_valid",
        ),
        sa.CheckConstraint(
            "suite_version >= 1", name="ck_eval_run_suite_version_positive"
        ),
        sa.CheckConstraint(
            "pass_rate IS NULL OR (pass_rate >= 0 AND pass_rate <= 100)",
            name="ck_eval_run_pass_rate_range",
        ),
        sa.CheckConstraint(
            "score_avg IS NULL OR score_avg >= 0",
            name="ck_eval_run_score_avg_non_negative",
        ),
        sa.CheckConstraint(
            "token_usage >= 0", name="ck_eval_run_token_usage_non_negative"
        ),
        sa.CheckConstraint(
            "finished_at IS NULL OR finished_at >= started_at",
            name="ck_eval_run_finished_after_started",
        ),
        sa.CheckConstraint(
            "git_sha IS NULL OR git_sha ~ '^[0-9a-f]{7,64}$'",
            name="ck_eval_run_git_sha_format",
        ),
        sa.UniqueConstraint("id", "suite_id", name="uq_eval_run_id_suite"),
    )
    op.create_index(
        "ix_eval_run_suite_started",
        "eval_run",
        ["suite_id", "started_at"],
        unique=False,
    )
    op.create_index(
        "ix_eval_run_tenant_status",
        "eval_run",
        ["org_id", "site_id", "status"],
        unique=False,
    )

    op.create_table(
        "eval_result",
        _id_column(),
        *TENANT_COMMON,
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "suite_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Must match both the run's and the case's suite",
        ),
        sa.Column("output_text", sa.Text(), nullable=True),
        sa.Column(
            "output_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "score",
            sa.Numeric(precision=6, scale=3),
            nullable=True,
            comment="Score on a 0–100 scale",
        ),
        sa.Column(
            "passed",
            sa.Boolean(),
            nullable=True,
            comment="NULL when the case could not be judged",
        ),
        sa.Column(
            "point_hits",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
            comment="Expected points actually covered",
        ),
        sa.Column(
            "violations",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
            comment="Forbidden points or policy violations detected",
        ),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column(
            "judge_trace",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
            comment="Judge model, rubric version and intermediate reasoning",
        ),
        sa.Column("error", sa.Text(), nullable=True),
        *TIMESTAMP_COMMON,
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["run_id", "suite_id"],
            ["eval_run.id", "eval_run.suite_id"],
            name="fk_eval_result_run",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["case_id", "suite_id"],
            ["eval_case.id", "eval_case.suite_id"],
            name="fk_eval_result_case",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "score IS NULL OR (score >= 0 AND score <= 100)",
            name="ck_eval_result_score_range",
        ),
        sa.CheckConstraint(
            "latency_ms IS NULL OR latency_ms >= 0",
            name="ck_eval_result_latency_non_negative",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(point_hits) = 'array'",
            name="ck_eval_result_point_hits_array",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(violations) = 'array'",
            name="ck_eval_result_violations_array",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(judge_trace) = 'object'",
            name="ck_eval_result_judge_trace_object",
        ),
        sa.UniqueConstraint("run_id", "case_id", name="uq_eval_result_run_case"),
    )
    op.create_index(
        "ix_eval_result_tenant_run",
        "eval_result",
        ["org_id", "site_id", "run_id"],
        unique=False,
    )
    op.create_index(
        "ix_eval_result_case",
        "eval_result",
        ["case_id"],
        unique=False,
    )

    op.create_table(
        "eval_baseline",
        _id_column(),
        *TENANT_COMMON,
        sa.Column("suite_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("set_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "set_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("note", sa.Text(), nullable=True),
        *TIMESTAMP_COMMON,
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["run_id", "suite_id"],
            ["eval_run.id", "eval_run.suite_id"],
            name="fk_eval_baseline_run",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["suite_id"],
            ["eval_suite.id"],
            name="fk_eval_baseline_suite",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("suite_id", "run_id", name="uq_eval_baseline_suite_run"),
    )
    op.create_index(
        "ix_eval_baseline_suite_set_at",
        "eval_baseline",
        ["suite_id", "set_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_eval_baseline_suite_set_at", table_name="eval_baseline"
    )
    op.drop_table("eval_baseline")

    op.drop_index("ix_eval_result_case", table_name="eval_result")
    op.drop_index("ix_eval_result_tenant_run", table_name="eval_result")
    op.drop_table("eval_result")

    op.drop_index("ix_eval_run_tenant_status", table_name="eval_run")
    op.drop_index("ix_eval_run_suite_started", table_name="eval_run")
    op.drop_table("eval_run")

    op.drop_index("ix_eval_case_suite_review", table_name="eval_case")
    op.drop_index("ix_eval_case_tenant_suite", table_name="eval_case")
    op.drop_table("eval_case")

    op.drop_index("ix_eval_suite_tenant_tool", table_name="eval_suite")
    op.drop_index("ix_eval_suite_tenant_status", table_name="eval_suite")
    op.drop_table("eval_suite")
