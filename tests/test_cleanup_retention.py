"""AC-3: 180-day retention, with baseline runs kept forever.

Time is frozen by passing ``now`` into the cleanup function, so the test does
not depend on the wall clock.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.baseline import BaselineError, set_baseline
from app.locks import BASELINE_LOCK_KEY, acquire_baseline_lock
from app.models.eval_result import EvalResult
from app.models.eval_run import EvalRun
from app.retention import (
    RETENTION_DAYS,
    _policy_filter,
    cleanup_old_results,
    count_cleanup_candidates,
    delete_candidates,
)
from tests.factories import (
    ORG_ID,
    OTHER_ORG_ID,
    SITE_ID,
    create_case,
    create_run,
    create_suite,
    make_baseline,
    make_result,
)

BASE_DIR = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 11, 20, 12, 0, 0, tzinfo=timezone.utc)
CUTOFF = NOW - timedelta(days=RETENTION_DAYS)


def _add_run_with_result(
    session,
    suite,
    case,
    *,
    start_days_ago: int,
    finish_days_ago: int | None,
    status: str = "succeeded",
    result_deleted_days_ago: int | None = None,
):
    started_at = NOW - timedelta(days=start_days_ago)
    finished_at = (
        None if finish_days_ago is None else NOW - timedelta(days=finish_days_ago)
    )
    run = create_run(
        session,
        suite,
        started_at=started_at,
        finished_at=finished_at,
        status=status,
    )
    result = make_result(
        run,
        case,
        deleted_at=(
            None
            if result_deleted_days_ago is None
            else NOW - timedelta(days=result_deleted_days_ago)
        ),
    )
    session.add(result)
    session.flush()
    return run, result


def _build_policy_dataset(session):
    suite = create_suite(session)
    case = create_case(session, suite)

    old_normal, old_normal_result = _add_run_with_result(
        session,
        suite,
        case,
        start_days_ago=220,
        finish_days_ago=219,
        status="succeeded",
    )

    old_baseline, old_baseline_result = _add_run_with_result(
        session,
        suite,
        case,
        start_days_ago=400,
        finish_days_ago=399,
        status="succeeded",
    )
    session.add(make_baseline(suite, old_baseline))

    recent, recent_result = _add_run_with_result(
        session,
        suite,
        case,
        start_days_ago=10,
        finish_days_ago=9,
        status="succeeded",
    )

    boundary, boundary_result = _add_run_with_result(
        session,
        suite,
        case,
        start_days_ago=181,
        finish_days_ago=180,  # exactly the cutoff; "older than" is strict
        status="succeeded",
    )

    stale_running, stale_running_result = _add_run_with_result(
        session,
        suite,
        case,
        start_days_ago=300,
        finish_days_ago=None,
        status="running",
    )

    old_soft_deleted, old_soft_deleted_result = _add_run_with_result(
        session,
        suite,
        case,
        start_days_ago=260,
        finish_days_ago=259,
        status="succeeded",
        result_deleted_days_ago=200,
    )

    old_no_finish, old_no_finish_result = _add_run_with_result(
        session,
        suite,
        case,
        start_days_ago=300,
        finish_days_ago=None,
        status="failed",
    )

    old_deleted_baseline, old_deleted_baseline_result = _add_run_with_result(
        session,
        suite,
        case,
        start_days_ago=500,
        finish_days_ago=499,
        status="succeeded",
    )
    session.add(
        make_baseline(
            suite,
            old_deleted_baseline,
            deleted_at=NOW - timedelta(days=400),
        )
    )

    session.commit()

    return {
        "suite": suite,
        "case": case,
        "runs": {
            "old_normal": old_normal,
            "old_baseline": old_baseline,
            "recent": recent,
            "boundary": boundary,
            "stale_running": stale_running,
            "old_soft_deleted": old_soft_deleted,
            "old_no_finish": old_no_finish,
            "old_deleted_baseline": old_deleted_baseline,
        },
        "results": {
            "old_normal": old_normal_result,
            "old_baseline": old_baseline_result,
            "recent": recent_result,
            "boundary": boundary_result,
            "stale_running": stale_running_result,
            "old_soft_deleted": old_soft_deleted_result,
            "old_no_finish": old_no_finish_result,
            "old_deleted_baseline": old_deleted_baseline_result,
        },
    }


def test_candidate_count_respects_policy(session):
    dataset = _build_policy_dataset(session)

    current, cutoff, count = count_cleanup_candidates(session, now=NOW)
    assert current == NOW
    assert cutoff == CUTOFF
    assert count == 3  # old_normal + old_soft_deleted + old_no_finish


def test_dry_run_reports_without_deleting(session):
    dataset = _build_policy_dataset(session)

    report = cleanup_old_results(
        session, now=NOW, batch_size=2, dry_run=True
    )
    assert report.deleted == 3
    assert report.dry_run is True
    assert report.cutoff == CUTOFF

    stored_count = session.scalar(select(func.count(EvalResult.id)))
    assert stored_count == 8


def test_cleanup_deletes_old_normal_results_and_keeps_baselines(session):
    dataset = _build_policy_dataset(session)
    runs = dataset["runs"]

    report = cleanup_old_results(session, now=NOW, batch_size=1)
    session.commit()

    assert report.deleted == 3
    assert report.dry_run is False

    remaining_run_ids = set(session.scalars(select(EvalResult.run_id)).all())
    assert remaining_run_ids == {
        runs["old_baseline"].id,
        runs["recent"].id,
        runs["boundary"].id,
        runs["stale_running"].id,
        runs["old_deleted_baseline"].id,
    }

    # Idempotent: a second pass finds nothing.
    second = cleanup_old_results(session, now=NOW, batch_size=1)
    session.commit()
    assert second.deleted == 0


def test_cleanup_never_touches_a_soft_deleted_baseline(session):
    """A baseline pin protects its run even after the pin row is soft-deleted."""

    suite = create_suite(session)
    case = create_case(session, suite)
    run, result = _add_run_with_result(
        session,
        suite,
        case,
        start_days_ago=500,
        finish_days_ago=499,
    )
    session.add(make_baseline(suite, run, deleted_at=NOW - timedelta(days=450)))
    session.commit()

    report = cleanup_old_results(session, now=NOW)
    session.commit()

    assert report.deleted == 0
    assert session.get(EvalResult, result.id) is not None


def test_cli_script_uses_frozen_time_and_deletes(session, database_url):
    """AC-3 exercise through the actual ``scripts/cleanup_results.py`` entrypoint."""

    suite = create_suite(session)
    case = create_case(session, suite)
    old_run, old_result = _add_run_with_result(
        session,
        suite,
        case,
        start_days_ago=220,
        finish_days_ago=219,
    )
    recent_run, recent_result = _add_run_with_result(
        session,
        suite,
        case,
        start_days_ago=5,
        finish_days_ago=4,
    )
    session.commit()

    env = {**os.environ, "DATABASE_URL": database_url}
    command = [
        sys.executable,
        str(BASE_DIR / "scripts" / "cleanup_results.py"),
        "--now",
        NOW.isoformat(),
        "--days",
        "180",
    ]

    dry = subprocess.run(
        command + ["--dry-run"],
        cwd=BASE_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    dry_report = json.loads(dry.stdout)
    assert dry_report["dry_run"] is True
    assert dry_report["deleted"] == 1

    real = subprocess.run(
        command,
        cwd=BASE_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    real_report = json.loads(real.stdout)
    assert real_report["dry_run"] is False
    assert real_report["deleted"] == 1

    session.expunge_all()
    remaining = set(session.scalars(select(EvalResult.run_id)).all())
    assert remaining == {recent_run.id}
    assert (
        session.scalar(select(EvalResult.id).where(EvalResult.id == old_result.id))
        is None
    )
    assert (
        session.scalar(
            select(EvalResult.id).where(EvalResult.id == recent_result.id)
        )
        is not None
    )



def test_delete_recheck_skips_run_pinned_after_candidate_select(session):
    """The original race: SELECT candidates, then insert a baseline, then DELETE."""

    suite = create_suite(session)
    case = create_case(session, suite)
    run, result = _add_run_with_result(
        session,
        suite,
        case,
        start_days_ago=220,
        finish_days_ago=219,
    )
    session.commit()

    candidate_ids = session.scalars(
        select(EvalResult.id)
        .join(EvalRun, EvalResult.run_id == EvalRun.id)
        .where(*_policy_filter(CUTOFF))
    ).all()
    assert candidate_ids == [result.id]

    # Simulate another writer pinning the run after the candidate SELECT.
    session.add(make_baseline(suite, run))
    session.commit()

    deleted = delete_candidates(session, list(candidate_ids), CUTOFF)
    session.commit()

    assert deleted == 0
    assert session.get(EvalResult, result.id) is not None


def test_baseline_lock_is_exclusive_across_transactions(engine):
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    first = session_factory()
    second = session_factory()
    try:
        acquire_baseline_lock(first)

        acquired = second.scalar(
            select(func.pg_try_advisory_xact_lock(BASELINE_LOCK_KEY))
        )
        assert acquired is False

        first.commit()

        acquired = second.scalar(
            select(func.pg_try_advisory_xact_lock(BASELINE_LOCK_KEY))
        )
        assert acquired is True
    finally:
        first.rollback()
        first.close()
        second.rollback()
        second.close()


def test_set_baseline_rejects_run_without_results(session):
    suite = create_suite(session)
    run = create_run(session, suite)

    with pytest.raises(BaselineError, match="no live results"):
        set_baseline(
            session,
            org_id=suite.org_id,
            site_id=suite.site_id,
            suite_id=suite.id,
            run_id=run.id,
        )
    session.rollback()


def test_set_baseline_rejects_cross_tenant_run(session):
    suite = create_suite(session)
    case = create_case(session, suite)
    run, _result = _add_run_with_result(
        session,
        suite,
        case,
        start_days_ago=220,
        finish_days_ago=219,
    )
    session.commit()

    with pytest.raises(BaselineError, match="tenant/suite"):
        set_baseline(
            session,
            org_id=OTHER_ORG_ID,
            site_id=SITE_ID,
            suite_id=suite.id,
            run_id=run.id,
        )
    session.rollback()


def test_set_baseline_protects_results_from_cleanup(session):
    suite = create_suite(session)
    case = create_case(session, suite)
    run, result = _add_run_with_result(
        session,
        suite,
        case,
        start_days_ago=400,
        finish_days_ago=399,
    )
    session.commit()

    set_baseline(
        session,
        org_id=ORG_ID,
        site_id=SITE_ID,
        suite_id=suite.id,
        run_id=run.id,
        note="虚构基线：并发协议测试",
    )
    session.commit()

    report = cleanup_old_results(session, now=NOW)
    session.commit()

    assert report.deleted == 0
    assert session.get(EvalResult, result.id) is not None
