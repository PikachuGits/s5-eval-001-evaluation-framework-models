"""Shared PostgreSQL advisory lock for baseline pinning and retention.

Both writers must take this transaction-scoped lock before touching rows that
participate in the "baseline is kept forever" rule:

* :func:`app.baseline.set_baseline` takes it before inserting a baseline;
* :func:`app.retention.cleanup_old_results` takes it before selecting and
  deleting results.

Because PostgreSQL releases the lock only on commit/rollback, a cleanup pass
and a baseline insert cannot interleave their check-then-act windows.

The protocol requires ``READ COMMITTED``; :func:`acquire_baseline_lock` checks
``SHOW transaction_isolation`` and refuses ``REPEATABLE READ``/``SERIALIZABLE``
rather than silently operating on a snapshot taken before the lock wait.
"""

from __future__ import annotations

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

# Stable 64-bit key.  Never change it without migrating every writer.
BASELINE_LOCK_KEY = 830_183_000_001


class LockProtocolError(RuntimeError):
    """The caller's transaction isolation level cannot use this lock safely."""


def _require_read_committed(session: Session) -> None:
    """Fail fast instead of silently using a stale REPEATABLE READ snapshot.

    Under REPEATABLE READ the transaction snapshot is taken before the advisory
    lock wait.  A baseline committed while the cleanup waits would therefore
    stay invisible to the subsequent SELECT/DELETE.  READ COMMITTED takes a
    fresh snapshot per statement, which is what the protocol relies on.
    """

    isolation = session.execute(text("SHOW transaction_isolation")).scalar()
    if isolation != "read committed":
        raise LockProtocolError(
            "baseline/retention lock requires READ COMMITTED, "
            f"got {isolation!r}; REPEATABLE READ/SERIALIZABLE can keep a stale "
            "snapshot while waiting for the lock"
        )


def acquire_baseline_lock(session: Session) -> None:
    """Block until the current transaction owns the baseline/retention lock."""

    _require_read_committed(session)
    session.execute(select(func.pg_advisory_xact_lock(BASELINE_LOCK_KEY)))
