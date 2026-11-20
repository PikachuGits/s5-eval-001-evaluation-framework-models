"""AC-2: one result per (run, case), enforced by the database.

A worker retry must not create a second judgment.  The unique constraint
``uq_eval_result_run_case`` is the single source of truth; application code is
expected to catch the IntegrityError and update the existing row instead.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models.eval_result import EvalResult
from tests.factories import (
    create_case,
    create_run,
    create_suite,
    make_case,
    make_result,
)


def _setup(session):
    suite = create_suite(session)
    case = create_case(session, suite)
    run = create_run(session, suite)
    return suite, case, run


def test_duplicate_result_for_same_run_and_case_is_rejected(session):
    suite, case, run = _setup(session)
    first = make_result(run, case)
    session.add(first)
    session.commit()

    duplicate = make_result(run, case, score=None, passed=None)
    session.add(duplicate)
    with pytest.raises(IntegrityError, match="uq_eval_result_run_case"):
        session.flush()
    session.rollback()

    count = session.scalar(select(func.count(EvalResult.id)))
    assert count == 1


def test_same_case_in_a_different_run_is_allowed(session):
    suite, case, run = _setup(session)
    second_run = create_run(session, suite, git_sha="1234567abcdef")

    session.add(make_result(run, case))
    session.add(make_result(run=second_run, case=case))
    session.commit()

    count = session.scalar(select(func.count(EvalResult.id)))
    assert count == 2


def test_different_case_in_the_same_run_is_allowed(session):
    suite, case, run = _setup(session)
    second_case = create_case(session, suite, case_key="CASE-002")

    session.add(make_result(run, case))
    session.add(make_result(run, second_case))
    session.commit()

    count = session.scalar(select(func.count(EvalResult.id)))
    assert count == 2


def test_existing_result_can_be_updated_in_place(session):
    suite, case, run = _setup(session)
    result = make_result(run, case, score=Decimal("60.000"), passed=False)
    session.add(result)
    session.commit()

    result.score = Decimal("95.000")
    result.passed = True
    session.commit()

    stored = session.get(EvalResult, result.id)
    assert stored is not None
    assert stored.score == Decimal("95.000")
    assert stored.passed is True


def test_database_index_supports_duplicate_detection(engine):
    """The unique constraint is backed by an index named in AC-2."""

    from sqlalchemy import text

    with engine.connect() as connection:
        index_rows = connection.execute(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE schemaname = 'public' AND tablename = 'eval_result'"
            )
        ).all()
    assert ("uq_eval_result_run_case",) in index_rows
