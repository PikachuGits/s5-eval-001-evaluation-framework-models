"""Baseline pinning with the shared retention lock protocol.

There is deliberately no "bare insert" helper.  Any writer that pins a run as
a baseline must call :func:`set_baseline` (or acquire
:func:`app.locks.acquire_baseline_lock` itself) so it cannot race the 180-day
cleanup job.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.locks import acquire_baseline_lock
from app.models.eval_baseline import EvalBaseline
from app.models.eval_result import EvalResult
from app.models.eval_run import EvalRun

TERMINAL_RUN_STATUSES = ("succeeded", "failed", "cancelled")


class BaselineError(ValueError):
    """A run cannot be pinned under the requested scope."""


def set_baseline(
    session: Session,
    *,
    org_id: uuid.UUID,
    site_id: uuid.UUID,
    suite_id: uuid.UUID,
    run_id: uuid.UUID,
    set_by: uuid.UUID | None = None,
    note: str | None = None,
    set_at: datetime | None = None,
) -> EvalBaseline:
    """Pin a terminal run as a baseline.

    The helper takes the same advisory lock as retention, verifies that the
    run belongs to the requested tenant/suite and is terminal, and refuses a
    run with no live results.  The caller still owns the transaction.
    """

    acquire_baseline_lock(session)

    run = session.scalar(
        select(EvalRun).where(
            EvalRun.id == run_id,
            EvalRun.org_id == org_id,
            EvalRun.site_id == site_id,
            EvalRun.suite_id == suite_id,
        )
    )
    if run is None:
        raise BaselineError("run does not belong to the requested tenant/suite")
    if run.status not in TERMINAL_RUN_STATUSES:
        raise BaselineError(f"run status {run.status!r} is not terminal")

    live_results = session.scalar(
        select(func.count(EvalResult.id)).where(
            EvalResult.run_id == run_id,
            EvalResult.deleted_at.is_(None),
        )
    )
    if not live_results:
        raise BaselineError("run has no live results to pin")

    existing = session.scalar(
        select(EvalBaseline).where(
            EvalBaseline.org_id == org_id,
            EvalBaseline.site_id == site_id,
            EvalBaseline.suite_id == suite_id,
            EvalBaseline.run_id == run_id,
        )
    )
    if existing is not None:
        return existing

    baseline = EvalBaseline(
        org_id=org_id,
        site_id=site_id,
        suite_id=suite_id,
        run_id=run_id,
        set_by=set_by,
        note=note,
    )
    if set_at is not None:
        baseline.set_at = set_at
    session.add(baseline)
    session.flush()
    return baseline
