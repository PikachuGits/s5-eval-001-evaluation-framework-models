"""AC-1: migration round-trip, schema shape and zero drift.

``alembic upgrade head`` -> ``downgrade -1`` -> ``upgrade head`` must all work,
and ``alembic check`` must report no new upgrade operations.
"""

from __future__ import annotations

from alembic import command
from sqlalchemy import inspect, text

EXPECTED_SUITE_COLUMNS = {
    "id",
    "org_id",
    "site_id",
    "suite_key",
    "tool",
    "version",
    "case_count",
    "status",
    "created_at",
    "created_by",
    "updated_at",
    "deleted_at",
}

EXPECTED_CASE_COLUMNS = {
    "id",
    "org_id",
    "site_id",
    "suite_id",
    "case_key",
    "input",
    "context",
    "expected_points",
    "forbidden_points",
    "reference_output",
    "tags",
    "difficulty",
    "weight",
    "review_state",
    "created_at",
    "created_by",
    "updated_at",
    "deleted_at",
}

EXPECTED_RUN_COLUMNS = {
    "id",
    "org_id",
    "site_id",
    "suite_id",
    "suite_version",
    "target_tool",
    "target_prompt_version",
    "target_model",
    "trigger",
    "git_sha",
    "status",
    "pass_rate",
    "score_avg",
    "token_usage",
    "started_at",
    "finished_at",
    "created_at",
    "created_by",
    "updated_at",
    "deleted_at",
}

EXPECTED_RESULT_COLUMNS = {
    "id",
    "org_id",
    "site_id",
    "run_id",
    "case_id",
    "suite_id",
    "output_text",
    "output_json",
    "score",
    "passed",
    "point_hits",
    "violations",
    "latency_ms",
    "judge_trace",
    "error",
    "created_at",
    "created_by",
    "updated_at",
    "deleted_at",
}

EXPECTED_BASELINE_COLUMNS = {
    "id",
    "org_id",
    "site_id",
    "suite_id",
    "run_id",
    "set_by",
    "set_at",
    "note",
    "created_at",
    "created_by",
    "updated_at",
    "deleted_at",
}

DELIVERY_TABLES = {
    "eval_suite",
    "eval_case",
    "eval_run",
    "eval_result",
    "eval_baseline",
}


def _columns(engine, table: str) -> dict:
    return {column["name"]: column for column in inspect(engine).get_columns(table)}


def test_tables_and_revision_are_applied(engine):
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    assert DELIVERY_TABLES <= tables
    assert "alembic_version" in tables

    with engine.connect() as connection:
        revision = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
    assert revision == "0001_eval_framework_tables"


def test_suite_columns_and_types(engine):
    columns = _columns(engine, "eval_suite")
    assert set(columns) == EXPECTED_SUITE_COLUMNS

    assert columns["id"]["nullable"] is False
    assert columns["id"]["type"].__class__.__name__ == "UUID"
    assert "gen_random_uuid" in str(columns["id"]["default"])
    assert columns["org_id"]["nullable"] is False
    assert columns["site_id"]["nullable"] is False
    assert columns["suite_key"]["type"].length == 64
    assert columns["tool"]["type"].length == 32
    assert columns["version"]["type"].__class__.__name__ == "INTEGER"
    assert columns["case_count"]["type"].__class__.__name__ == "INTEGER"
    assert columns["status"]["type"].length == 16
    assert columns["created_at"]["nullable"] is False
    assert columns["created_by"]["nullable"] is True
    assert columns["updated_at"]["nullable"] is False
    assert columns["deleted_at"]["nullable"] is True


def test_case_columns_and_types(engine):
    columns = _columns(engine, "eval_case")
    assert set(columns) == EXPECTED_CASE_COLUMNS

    assert columns["suite_id"]["nullable"] is False
    assert columns["case_key"]["type"].length == 64
    assert columns["input"]["type"].__class__.__name__ == "JSONB"
    assert columns["context"]["type"].__class__.__name__ == "JSONB"
    assert columns["expected_points"]["type"].__class__.__name__ == "JSONB"
    assert columns["forbidden_points"]["type"].__class__.__name__ == "JSONB"
    assert columns["reference_output"]["type"].__class__.__name__ == "TEXT"
    assert columns["tags"]["type"].__class__.__name__ == "ARRAY"
    assert columns["tags"]["type"].item_type.__class__.__name__ == "TEXT"
    assert columns["difficulty"]["type"].length == 16
    assert columns["weight"]["type"].precision == 6
    assert columns["weight"]["type"].scale == 3
    assert columns["review_state"]["type"].length == 16


def test_run_columns_and_types(engine):
    columns = _columns(engine, "eval_run")
    assert set(columns) == EXPECTED_RUN_COLUMNS

    assert columns["suite_id"]["nullable"] is False
    assert columns["suite_version"]["type"].__class__.__name__ == "INTEGER"
    assert columns["target_tool"]["type"].length == 32
    assert columns["target_prompt_version"]["type"].length == 64
    assert columns["target_prompt_version"]["nullable"] is True
    assert columns["target_model"]["type"].length == 64
    assert columns["target_model"]["nullable"] is True
    assert columns["trigger"]["type"].length == 16
    assert columns["git_sha"]["type"].length == 64
    assert columns["git_sha"]["nullable"] is True
    assert columns["status"]["type"].length == 16
    assert columns["pass_rate"]["type"].precision == 5
    assert columns["pass_rate"]["type"].scale == 2
    assert columns["pass_rate"]["nullable"] is True
    assert columns["score_avg"]["type"].precision == 6
    assert columns["score_avg"]["type"].scale == 3
    assert columns["score_avg"]["nullable"] is True
    assert columns["token_usage"]["type"].__class__.__name__ == "BIGINT"
    assert columns["started_at"]["nullable"] is False
    assert columns["finished_at"]["nullable"] is True


def test_result_columns_and_types(engine):
    columns = _columns(engine, "eval_result")
    assert set(columns) == EXPECTED_RESULT_COLUMNS

    assert columns["run_id"]["nullable"] is False
    assert columns["case_id"]["nullable"] is False
    assert columns["output_text"]["type"].__class__.__name__ == "TEXT"
    assert columns["output_json"]["type"].__class__.__name__ == "JSONB"
    assert columns["output_json"]["nullable"] is True
    assert columns["score"]["type"].precision == 6
    assert columns["score"]["type"].scale == 3
    assert columns["score"]["nullable"] is True
    assert columns["passed"]["type"].__class__.__name__ == "BOOLEAN"
    assert columns["passed"]["nullable"] is True
    assert columns["point_hits"]["type"].__class__.__name__ == "JSONB"
    assert columns["violations"]["type"].__class__.__name__ == "JSONB"
    assert columns["latency_ms"]["type"].__class__.__name__ == "INTEGER"
    assert columns["latency_ms"]["nullable"] is True
    assert columns["judge_trace"]["type"].__class__.__name__ == "JSONB"
    assert columns["error"]["type"].__class__.__name__ == "TEXT"


def test_baseline_columns_and_types(engine):
    columns = _columns(engine, "eval_baseline")
    assert set(columns) == EXPECTED_BASELINE_COLUMNS

    assert columns["suite_id"]["nullable"] is False
    assert columns["run_id"]["nullable"] is False
    assert columns["set_by"]["nullable"] is True
    assert columns["set_at"]["nullable"] is False
    assert columns["note"]["type"].__class__.__name__ == "TEXT"
    assert columns["note"]["nullable"] is True


def test_check_constraint_names(engine):
    inspector = inspect(engine)

    assert {
        "ck_eval_suite_tool_valid",
        "ck_eval_suite_status_valid",
        "ck_eval_suite_version_positive",
        "ck_eval_suite_case_count_non_negative",
        "ck_eval_suite_key_format",
    } <= {
        constraint["name"]
        for constraint in inspector.get_check_constraints("eval_suite")
    }

    assert {
        "ck_eval_case_difficulty_valid",
        "ck_eval_case_review_state_valid",
        "ck_eval_case_weight_positive",
        "ck_eval_case_input_object",
        "ck_eval_case_context_object",
        "ck_eval_case_expected_points_array",
        "ck_eval_case_forbidden_points_array",
        "ck_eval_case_key_format",
    } <= {
        constraint["name"]
        for constraint in inspector.get_check_constraints("eval_case")
    }

    assert {
        "ck_eval_run_target_tool_valid",
        "ck_eval_run_trigger_valid",
        "ck_eval_run_status_valid",
        "ck_eval_run_suite_version_positive",
        "ck_eval_run_pass_rate_range",
        "ck_eval_run_score_avg_non_negative",
        "ck_eval_run_token_usage_non_negative",
        "ck_eval_run_finished_after_started",
        "ck_eval_run_git_sha_format",
    } <= {
        constraint["name"]
        for constraint in inspector.get_check_constraints("eval_run")
    }

    assert {
        "ck_eval_result_score_range",
        "ck_eval_result_latency_non_negative",
        "ck_eval_result_point_hits_array",
        "ck_eval_result_violations_array",
        "ck_eval_result_judge_trace_object",
    } <= {
        constraint["name"]
        for constraint in inspector.get_check_constraints("eval_result")
    }


def test_unique_constraints(engine):
    inspector = inspect(engine)

    suite_unique = inspector.get_unique_constraints("eval_suite")
    assert any(
        constraint["name"] == "uq_eval_suite_tenant_key_version"
        and set(constraint["column_names"])
        == {"org_id", "site_id", "suite_key", "version"}
        for constraint in suite_unique
    )

    case_unique = inspector.get_unique_constraints("eval_case")
    assert any(
        constraint["name"] == "uq_eval_case_suite_case_key"
        and set(constraint["column_names"]) == {"suite_id", "case_key"}
        for constraint in case_unique
    )
    assert any(
        constraint["name"] == "uq_eval_case_id_suite"
        and set(constraint["column_names"]) == {"id", "suite_id"}
        for constraint in case_unique
    )

    run_unique = inspector.get_unique_constraints("eval_run")
    assert any(
        constraint["name"] == "uq_eval_run_id_suite"
        and set(constraint["column_names"]) == {"id", "suite_id"}
        for constraint in run_unique
    )

    result_unique = inspector.get_unique_constraints("eval_result")
    assert any(
        constraint["name"] == "uq_eval_result_run_case"
        and set(constraint["column_names"]) == {"run_id", "case_id"}
        for constraint in result_unique
    )

    baseline_unique = inspector.get_unique_constraints("eval_baseline")
    assert any(
        constraint["name"] == "uq_eval_baseline_suite_run"
        and set(constraint["column_names"]) == {"suite_id", "run_id"}
        for constraint in baseline_unique
    )


def test_unique_result_key_is_backed_by_an_index(engine):
    """AC-2 also asks for an index on ``(run_id, case_id)``."""

    with engine.connect() as connection:
        indexes = {
            row[0]
            for row in connection.execute(
                text(
                    "SELECT indexname FROM pg_indexes "
                    "WHERE schemaname = 'public' AND tablename = 'eval_result'"
                )
            )
        }
    assert "uq_eval_result_run_case" in indexes


def test_foreign_keys(engine):
    inspector = inspect(engine)

    case_fks = inspector.get_foreign_keys("eval_case")
    assert len(case_fks) == 1
    assert case_fks[0]["name"] == "fk_eval_case_suite_id"
    assert case_fks[0]["constrained_columns"] == ["suite_id"]
    assert case_fks[0]["referred_table"] == "eval_suite"
    assert case_fks[0]["options"].get("ondelete") == "RESTRICT"

    run_fks = inspector.get_foreign_keys("eval_run")
    assert len(run_fks) == 1
    assert run_fks[0]["name"] == "fk_eval_run_suite_id"
    assert run_fks[0]["constrained_columns"] == ["suite_id"]
    assert run_fks[0]["referred_table"] == "eval_suite"
    assert run_fks[0]["options"].get("ondelete") == "RESTRICT"

    result_fks = {
        foreign_key["name"]: foreign_key
        for foreign_key in inspector.get_foreign_keys("eval_result")
    }
    assert set(result_fks) == {"fk_eval_result_run", "fk_eval_result_case"}
    assert result_fks["fk_eval_result_run"]["constrained_columns"] == [
        "run_id",
        "suite_id",
    ]
    assert result_fks["fk_eval_result_run"]["referred_table"] == "eval_run"
    assert result_fks["fk_eval_result_run"]["referred_columns"] == ["id", "suite_id"]
    assert result_fks["fk_eval_result_run"]["options"].get("ondelete") == "CASCADE"
    assert result_fks["fk_eval_result_case"]["constrained_columns"] == [
        "case_id",
        "suite_id",
    ]
    assert result_fks["fk_eval_result_case"]["referred_table"] == "eval_case"
    assert result_fks["fk_eval_result_case"]["referred_columns"] == ["id", "suite_id"]
    assert result_fks["fk_eval_result_case"]["options"].get("ondelete") == "RESTRICT"

    baseline_fks = {
        foreign_key["name"]: foreign_key
        for foreign_key in inspector.get_foreign_keys("eval_baseline")
    }
    assert set(baseline_fks) == {
        "fk_eval_baseline_run",
        "fk_eval_baseline_suite",
    }
    assert baseline_fks["fk_eval_baseline_run"]["constrained_columns"] == [
        "run_id",
        "suite_id",
    ]
    assert baseline_fks["fk_eval_baseline_run"]["referred_columns"] == [
        "id",
        "suite_id",
    ]
    assert baseline_fks["fk_eval_baseline_run"]["options"].get("ondelete") == "RESTRICT"
    assert baseline_fks["fk_eval_baseline_suite"]["constrained_columns"] == ["suite_id"]
    assert baseline_fks["fk_eval_baseline_suite"]["referred_table"] == "eval_suite"
    assert (
        baseline_fks["fk_eval_baseline_suite"]["options"].get("ondelete") == "RESTRICT"
    )


def test_indexes(engine):
    inspector = inspect(engine)

    assert {
        "ix_eval_suite_tenant_status",
        "ix_eval_suite_tenant_tool",
    } <= {index["name"] for index in inspector.get_indexes("eval_suite")}

    assert {
        "ix_eval_case_tenant_suite",
        "ix_eval_case_suite_review",
    } <= {index["name"] for index in inspector.get_indexes("eval_case")}

    assert {
        "ix_eval_run_suite_started",
        "ix_eval_run_tenant_status",
    } <= {index["name"] for index in inspector.get_indexes("eval_run")}

    assert {
        "ix_eval_result_tenant_run",
        "ix_eval_result_case",
    } <= {index["name"] for index in inspector.get_indexes("eval_result")}

    assert "ix_eval_baseline_suite_set_at" in {
        index["name"] for index in inspector.get_indexes("eval_baseline")
    }


def test_upgrade_downgrade_upgrade_and_zero_drift(engine, alembic_config):
    """AC-1: both directions execute and ``alembic check`` reports no drift."""

    assert DELIVERY_TABLES <= set(inspect(engine).get_table_names())

    command.downgrade(alembic_config, "-1")

    inspector = inspect(engine)
    assert not (DELIVERY_TABLES & set(inspector.get_table_names()))

    command.upgrade(alembic_config, "head")

    inspector = inspect(engine)
    assert DELIVERY_TABLES <= set(inspector.get_table_names())

    # Raises ``AutogenerateDiffsDetected`` if the metadata and the migrated
    # schema disagree; a clean run is the acceptance evidence for "零漂移".
    command.check(alembic_config)
