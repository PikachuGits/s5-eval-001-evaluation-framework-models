#!/usr/bin/env python3
"""Delete evaluation results that are older than the 180-day retention window.

Usage::

    export DATABASE_URL='postgresql+psycopg://USER:PASSWORD@127.0.0.1:5432/DB'
    python scripts/cleanup_results.py --dry-run
    python scripts/cleanup_results.py --days 180 --batch-size 500

Runs pinned in ``eval_baseline`` are never deleted, and non-terminal runs
(``queued``/``running``) are skipped regardless of age.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

from app.db import get_database_url  # noqa: E402
from app.retention import cleanup_old_results  # noqa: E402


def _parse_now(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:  # pragma: no cover - argparse error path
        raise argparse.ArgumentTypeError(
            f"--now must be an ISO-8601 timestamp, got {value!r}"
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Delete eval_result rows older than the retention window."
    )
    parser.add_argument(
        "--days",
        type=int,
        default=180,
        help="Retention window in days (default: 180)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Rows per DELETE statement (default: 500)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report the candidate count without deleting anything",
    )
    parser.add_argument(
        "--now",
        type=_parse_now,
        default=None,
        help="Freeze the reference time (ISO-8601, UTC assumed when naive)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.days < 1:
        print("--days must be >= 1", file=sys.stderr)
        return 2

    engine = create_engine(get_database_url(), poolclass=NullPool, future=True)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        with session_factory() as session:
            report = cleanup_old_results(
                session,
                now=args.now,
                retention_days=args.days,
                batch_size=args.batch_size,
                dry_run=args.dry_run,
            )
            if args.dry_run:
                session.rollback()
            else:
                session.commit()
    finally:
        engine.dispose()

    payload = asdict(report)
    payload["now"] = report.now.isoformat()
    payload["cutoff"] = report.cutoff.isoformat()
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
