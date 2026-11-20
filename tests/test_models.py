"""Model behaviour: defaults, enums, ranges, JSON shape and tenant isolation."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.eval_baseline import EvalBaseline
from app.models.eval_case import EvalCase
from app.models.eval_result import EvalResult
from app.models.eval_run import EvalRun
from app.models.eval_suite import EvalSuite
from tests.factories import (
    ACTOR_ID,
    ORG_ID,
    OTHER_ORG_ID,
    OTHER_SITE_ID,
    SITE_ID,
    create_case,
    create_run,
    create_suite,
    make_baseline,
    make_case,
    make_result,
    make_run,
    make_suite,
    utcnow,
)


def test_full_chain_inserts_and_reads_back(session):
    suite = create_suite(session)
    case = create_case(session, suite)
    run = create_run(session, suite)
    session.add(make_result(run, case))
    session.add(make_baseline(suite, run))
    session.commit()

    stored_suite = session.get(EvalSuite, suite.id)
    assert stored_suite is not None
    assert stored_suite.suite_key == "kqa.retrieval"
    assert stored_suite.tool == "kqa"
    assert stored_suite.version == 1

    stored_case = session.get(EvalCase, case.id)
    assert stored_case is not None
    assert stored_case.input["question"].startswith("虚构问题")
    assert stored_case.expected_points[0] == "说明虚构活动的登记入口"
    assert stored_case.tags == ["smoke", "retrieval"]
    assert stored_case.weight == Decimal("1.000")

    stored_run = session.get(EvalRun, run.id)
    assert stored_run is not None
    assert stored_run.status == "succeeded"
    assert stored_run.pass_rate == Decimal("100.00")
    assert stored_run.token_usage == 1234

    stored_result = session.scalar(select(EvalResult))
    assert stored_result is not None
    assert stored_result.passed is True
    assert stored_result.score == Decimal("95.000")
    assert stored_result.suite_id == suite.id

    stored_baseline = session.scalar(select(EvalBaseline))
    assert stored_baseline is not None
    assert stored_baseline.run_id == run.id
    assert stored_baseline.note == "虚构基线：用于回归对比"


def test_application_defaults(session):
    suite = EvalSuite(
        org_id=ORG_ID,
        site_id=SITE_ID,
        suite_key="kqa.retrieval",
        tool="kqa",
    )
    session.add(suite)
    session.flush()
    assert suite.version == 1
    assert suite.case_count == 0
    assert suite.status == "draft"

    case = EvalCase(
        org_id=ORG_ID,
        site_id=SITE_ID,
        suite_id=suite.id,
        case_key="CASE-001",
    )
    session.add(case)
    session.flush()
    assert case.input == {}
    assert case.context == {}
    assert case.expected_points == []
    assert case.forbidden_points == []
    assert case.tags == []
    assert case.difficulty == "medium"
    assert case.weight == Decimal("1.000")
    assert case.review_state == "pending"

    run = EvalRun(
        org_id=ORG_ID,
        site_id=SITE_ID,
        suite_id=suite.id,
        suite_version=1,
        target_tool="kqa",
        trigger="manual",
    )
    session.add(run)
    session.flush()
    assert run.status == "queued"
    assert run.token_usage == 0
    assert run.pass_rate is None
    assert run.started_at is not None

    result = EvalResult(
        org_id=ORG_ID,
        site_id=SITE_ID,
        run_id=run.id,
        case_id=case.id,
        suite_id=suite.id,
    )
    session.add(result)
    session.flush()
    assert result.point_hits == []
    assert result.violations == []
    assert result.judge_trace == {}
    assert result.passed is None
    assert result.score is None


def test_tenant_scope_is_required(session):
    session.add(EvalSuite(suite_key="kqa.retrieval", tool="kqa"))
    with pytest.raises(IntegrityError, match="org_id"):
        session.flush()
    session.rollback()


def test_suite_key_version_is_unique_per_tenant(session):
    first = create_suite(session)
    session.commit()

    session.add(make_suite())
    with pytest.raises(
        IntegrityError, match="uq_eval_suite_tenant_key_version"
    ):
        session.flush()
    session.rollback()

    # A new version is allowed.
    session.add(make_suite(version=2))
    session.commit()

    # The same key/version in another site is allowed.
    session.add(make_suite(site_id=OTHER_SITE_ID, version=1))
    session.commit()


def test_case_key_is_unique_inside_a_suite_only(session):
    suite = create_suite(session)
    create_case(session, suite)
    session.commit()

    session.add(make_case(suite.id))
    with pytest.raises(IntegrityError, match="uq_eval_case_suite_case_key"):
        session.flush()
    session.rollback()

    # Same case key is fine in a different suite.
    other_suite = create_suite(session, suite_key="guardrail.safety", tool="guardrail")
    session.add(
        make_case(other_suite.id, expected_points=["虚构要点"], tags=["safety"])
    )
    session.commit()


@pytest.mark.parametrize(
    ("field", "value", "constraint"),
    [
        ("tool", "search", "ck_eval_suite_tool_valid"),
        ("tool", "KQA", "ck_eval_suite_tool_valid"),
        ("status", "archived", "ck_eval_suite_status_valid"),
        ("status", "enabled", "ck_eval_suite_status_valid"),
        ("version", 0, "ck_eval_suite_version_positive"),
        ("case_count", -1, "ck_eval_suite_case_count_non_negative"),
        ("suite_key", "KQA.Retrieval", "ck_eval_suite_key_format"),
        ("suite_key", "kqa retrieval", "ck_eval_suite_key_format"),
    ],
)
def test_suite_constraints(session, field, value, constraint):
    session.add(make_suite(**{field: value}))
    with pytest.raises(IntegrityError, match=constraint):
        session.flush()
    session.rollback()


@pytest.mark.parametrize(
    ("field", "value", "constraint"),
    [
        ("difficulty", "expert", "ck_eval_case_difficulty_valid"),
        ("review_state", "draft", "ck_eval_case_review_state_valid"),
        ("weight", Decimal("0.000"), "ck_eval_case_weight_positive"),
        ("weight", Decimal("-1.000"), "ck_eval_case_weight_positive"),
        ("input", [], "ck_eval_case_input_object"),
        ("input", "text", "ck_eval_case_input_object"),
        ("context", ["locale"], "ck_eval_case_context_object"),
        ("expected_points", {"a": 1}, "ck_eval_case_expected_points_array"),
        ("forbidden_points", {"a": 1}, "ck_eval_case_forbidden_points_array"),
        ("case_key", "Case 001", "ck_eval_case_key_format"),
        ("case_key", "中文用例", "ck_eval_case_key_format"),
    ],
)
def test_case_constraints(session, field, value, constraint):
    suite = create_suite(session)
    session.add(make_case(suite.id, **{field: value}))
    with pytest.raises(IntegrityError, match=constraint):
        session.flush()
    session.rollback()


@pytest.mark.parametrize(
    ("field", "value", "constraint"),
    [
        ("target_tool", "other", "ck_eval_run_target_tool_valid"),
        ("trigger", "cron", "ck_eval_run_trigger_valid"),
        ("status", "pending", "ck_eval_run_status_valid"),
        ("suite_version", 0, "ck_eval_run_suite_version_positive"),
        ("pass_rate", Decimal("101.00"), "ck_eval_run_pass_rate_range"),
        ("pass_rate", Decimal("-1.00"), "ck_eval_run_pass_rate_range"),
        ("score_avg", Decimal("-0.001"), "ck_eval_run_score_avg_non_negative"),
        ("token_usage", -1, "ck_eval_run_token_usage_non_negative"),
        ("git_sha", "ABCDEF123", "ck_eval_run_git_sha_format"),
        ("git_sha", "xyz", "ck_eval_run_git_sha_format"),
    ],
)
def test_run_constraints(session, field, value, constraint):
    suite = create_suite(session)
    session.add(make_run(suite, **{field: value}))
    with pytest.raises(IntegrityError, match=constraint):
        session.flush()
    session.rollback()


def test_run_finished_at_must_not_precede_started_at(session):
    suite = create_suite(session)
    started = utcnow()
    session.add(
        make_run(suite, started_at=started, finished_at=started - timedelta(minutes=1))
    )
    with pytest.raises(IntegrityError, match="ck_eval_run_finished_after_started"):
        session.flush()
    session.rollback()


@pytest.mark.parametrize(
    ("field", "value", "constraint"),
    [
        ("score", Decimal("101.000"), "ck_eval_result_score_range"),
        ("score", Decimal("-0.001"), "ck_eval_result_score_range"),
        ("latency_ms", -1, "ck_eval_result_latency_non_negative"),
        ("point_hits", {"a": 1}, "ck_eval_result_point_hits_array"),
        ("violations", "none", "ck_eval_result_violations_array"),
        ("judge_trace", [], "ck_eval_result_judge_trace_object"),
    ],
)
def test_result_constraints(session, field, value, constraint):
    suite = create_suite(session)
    case = create_case(session, suite)
    run = create_run(session, suite)
    session.add(make_result(run, case, **{field: value}))
    with pytest.raises(IntegrityError, match=constraint):
        session.flush()
    session.rollback()


def test_result_rejects_case_from_another_suite(session):
    suite_one = create_suite(session)
    run = create_run(session, suite_one)
    suite_two = create_suite(session, suite_key="guardrail.safety", tool="guardrail")
    case_two = create_case(session, suite_two, case_key="CASE-002")

    # ``suite_id`` matches the run, but the case belongs to another suite;
    # the tenant-aware composite FK must reject it.
    session.add(make_result(run, case_two, suite_id=suite_one.id))
    with pytest.raises(IntegrityError, match="fk_eval_result_case_tenant"):
        session.flush()
    session.rollback()


def test_baseline_rejects_run_from_another_suite(session):
    suite_one = create_suite(session)
    suite_two = create_suite(session, suite_key="guardrail.safety", tool="guardrail")
    run_two = create_run(session, suite_two)

    session.add(make_baseline(suite_one, run_two))
    with pytest.raises(IntegrityError, match="fk_eval_baseline_run_tenant"):
        session.flush()
    session.rollback()


def test_case_rejects_suite_from_another_tenant(session):
    suite = create_suite(session)
    session.add(
        make_case(
            suite.id,
            org_id=OTHER_ORG_ID,
            site_id=SITE_ID,
            case_key="CASE-OTHER-ORG",
        )
    )
    with pytest.raises(IntegrityError, match="fk_eval_case_suite_tenant"):
        session.flush()
    session.rollback()


def test_run_rejects_suite_from_another_site(session):
    suite = create_suite(session)
    session.add(
        make_run(
            suite,
            org_id=ORG_ID,
            site_id=OTHER_SITE_ID,
            suite_version=suite.version,
        )
    )
    with pytest.raises(IntegrityError, match="fk_eval_run_suite_tenant"):
        session.flush()
    session.rollback()


def test_result_rejects_cross_tenant_links(session):
    suite = create_suite(session)
    case = create_case(session, suite)
    run = create_run(session, suite)

    session.add(
        make_result(
            run,
            case,
            org_id=OTHER_ORG_ID,
            site_id=OTHER_SITE_ID,
        )
    )
    with pytest.raises(
        IntegrityError, match=r"fk_eval_result_(run|case)_tenant"
    ):
        session.flush()
    session.rollback()


def test_baseline_rejects_cross_tenant_links(session):
    suite = create_suite(session)
    run = create_run(session, suite)

    session.add(
        make_baseline(
            suite,
            run,
            org_id=OTHER_ORG_ID,
            site_id=OTHER_SITE_ID,
        )
    )
    with pytest.raises(
        IntegrityError, match=r"fk_eval_baseline_(run|suite)_tenant"
    ):
        session.flush()
    session.rollback()


def test_deleting_a_run_cascades_results(session):
    suite = create_suite(session)
    case = create_case(session, suite)
    run = create_run(session, suite)
    result = make_result(run, case)
    session.add(result)
    session.commit()

    result_id = result.id
    session.delete(run)
    session.commit()

    session.expire_all()
    assert session.get(EvalResult, result_id) is None


def test_deleting_a_case_is_restricted_while_results_exist(session):
    suite = create_suite(session)
    case = create_case(session, suite)
    run = create_run(session, suite)
    session.add(make_result(run, case))
    session.commit()

    session.delete(case)
    with pytest.raises(IntegrityError, match="fk_eval_result_case_tenant"):
        session.flush()
    session.rollback()


def test_soft_delete_column_is_nullable_and_settable(session):
    suite = create_suite(session)
    run = create_run(session, suite)
    session.commit()

    # Soft delete is an UPDATE, not a physical DELETE.
    run.deleted_at = utcnow()
    session.commit()

    stored = session.get(EvalRun, run.id)
    assert stored is not None
    assert stored.deleted_at is not None
