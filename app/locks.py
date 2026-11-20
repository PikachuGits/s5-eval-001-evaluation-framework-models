"""Shared PostgreSQL advisory lock for baseline pinning and retention.

Both writers must take this transaction-scoped lock before touching rows that
participate in the "baseline is kept forever" rule:

* :func:`app.baseline.set_baseline` takes it before inserting a baseline;
* :func:`app.retention.cleanup_old_results` takes it before selecting and
  deleting results.

Because PostgreSQL releases the lock only on commit/rollback, a cleanup pass
and a baseline insert cannot interleave their check-then-act windows.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

# Stable 64-bit key.  Never change it without migrating every writer.
BASELINE_LOCK_KEY = 830_183_000_001


def acquire_baseline_lock(session: Session) -> None:
    """Block until the current transaction owns the baseline/retention lock."""

    session.execute(select(func.pg_advisory_xact_lock(BASELINE_LOCK_KEY)))
