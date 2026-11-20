"""Retention policy for ``eval_result`` rows.

Policy fixed by the work order:

* results of ordinary runs are kept for **180 days**;
* results of runs pinned in ``eval_baseline`` are kept **forever**;
* only terminal runs are eligible — a run still ``queued``/``running`` is never
  touched, even if its ``started_at`` is old;
* the age of a run is measured from ``finished_at``, falling back to
  ``started_at`` when the run never finished.

The cleanup is a hard delete (a retention job must reclaim space); rows that
were soft-deleted earlier are also removed once their run is out of policy.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.locks import acquire_baseline_lock
from app.models.eval_baseline import EvalBaseline
from app.models.eval_result import EvalResult
from app.models.eval_run import EvalRun

RETENTION_DAYS = 180
TERMINAL_RUN_STATUSES = ("succeeded", "failed", "cancelled")
MAX_BATCH_SIZE = 10_000


@dataclass(frozen=True)
class CleanupReport:
    """Outcome of one cleanup pass."""

    now: datetime
    cutoff: datetime
    retention_days: int
    deleted: int
    dry_run: bool


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _policy_filter(cutoff: datetime):
    """SQL predicate shared by the count and the delete statements."""

    baseline_exists = (
        select(EvalBaseline.id)
        .where(EvalBaseline.run_id == EvalRun.id)
        .exists()
    )
    return (
        func.coalesce(EvalRun.finished_at, EvalRun.started_at) < cutoff,
        EvalRun.status.in_(TERMINAL_RUN_STATUSES),
        ~baseline_exists,
    )


def _eligible_run_ids(cutoff: datetime):
    """Runs whose results may be deleted, evaluated at DELETE time."""

    return select(EvalRun.id).where(*_policy_filter(cutoff))


def _delete_candidates(
    session: Session, result_ids: list[uuid.UUID], cutoff: datetime
) -> int:
    """Delete only candidates that still satisfy the policy.

    Internal helper: it takes the same advisory lock itself, so even a direct
    call cannot bypass the baseline/retention protocol.  The policy is
    re-evaluated inside the same DELETE statement; a baseline inserted after
    the candidate SELECT excludes its run instead of being silently ignored.
    """

    if not result_ids:
        return 0

    acquire_baseline_lock(session)

    result = session.execute(
        delete(EvalResult).where(
            EvalResult.id.in_(result_ids),
            EvalResult.run_id.in_(_eligible_run_ids(cutoff)),
        )
    )
    session.flush()
    return int(result.rowcount or 0)


def count_cleanup_candidates(
    session: Session,
    *,
    now: datetime | None = None,
    retention_days: int = RETENTION_DAYS,
) -> tuple[datetime, datetime, int]:
    """Return ``(now, cutoff, candidate_count)`` without deleting anything."""

    if retention_days < 1:
        raise ValueError("retention_days must be >= 1")

    current = _as_utc(now) if now is not None else datetime.now(timezone.utc)
    cutoff = current - timedelta(days=retention_days)

    count = session.scalar(
        select(func.count(EvalResult.id))
        .select_from(EvalResult)
        .join(EvalRun, EvalResult.run_id == EvalRun.id)
        .where(*_policy_filter(cutoff))
    )
    return current, cutoff, int(count or 0)


def cleanup_old_results(
    session: Session,
    *,
    now: datetime | None = None,
    retention_days: int = RETENTION_DAYS,
    batch_size: int = 500,
    dry_run: bool = False,
) -> CleanupReport:
    """Delete out-of-policy results in batches.

    ``now`` is injectable so tests can freeze time.  The caller owns the
    transaction: commit afterwards for a real run, roll back for a rehearsal.
    The transaction-scoped baseline lock is held until that commit/rollback.
    """

    if batch_size < 1 or batch_size > MAX_BATCH_SIZE:
        raise ValueError(f"batch_size must be between 1 and {MAX_BATCH_SIZE}")

    # Serialize with baseline writers.  Without this, a baseline inserted
    # between the candidate SELECT and the DELETE could pin a run whose rows
    # are already on the delete path.
    acquire_baseline_lock(session)

    current, cutoff, candidate_count = count_cleanup_candidates(
        session, now=now, retention_days=retention_days
    )

    if dry_run:
        return CleanupReport(
            now=current,
            cutoff=cutoff,
            retention_days=retention_days,
            deleted=candidate_count,
            dry_run=True,
        )

    deleted = 0
    while True:
        ids = session.scalars(
            select(EvalResult.id)
            .join(EvalRun, EvalResult.run_id == EvalRun.id)
            .where(*_policy_filter(cutoff))
            .order_by(EvalResult.id)
            .limit(batch_size)
        ).all()
        if not ids:
            break

        result = _delete_candidates(session, list(ids), cutoff)
        deleted += result
        # The next SELECT re-applies the policy, so rows protected by a new
        # baseline are naturally left behind.

    return CleanupReport(
        now=current,
        cutoff=cutoff,
        retention_days=retention_days,
        deleted=deleted,
        dry_run=False,
    )
