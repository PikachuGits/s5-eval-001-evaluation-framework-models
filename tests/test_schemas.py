"""Pydantic schemas mirror the database rules where practical."""

from __future__ import annotations

from datetime import timedelta

import pytest
from pydantic import ValidationError

from app.schemas.eval import (
    EvalCaseCreate,
    EvalCaseRead,
    EvalResultCreate,
    EvalRunCreate,
    EvalSuiteCreate,
    EvalSuiteRead,
)
from tests.factories import (
    case_payload,
    create_case,
    create_suite,
    result_payload,
    run_payload,
    suite_payload,
    utcnow,
)


def test_valid_payloads_are_accepted():
    suite = EvalSuiteCreate.model_validate(suite_payload())
    assert suite.tool == "kqa"
    assert suite.version == 1

    case = EvalCaseCreate.model_validate(case_payload())
    assert case.tags == ["smoke"]

    run = EvalRunCreate.model_validate(run_payload())
    assert run.status == "queued"

    result = EvalResultCreate.model_validate(result_payload())
    assert result.passed is True


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("suite_key", "KQA.Retrieval"),
        ("tool", "search"),
        ("status", "archived"),
        ("version", 0),
        ("case_count", -1),
    ],
)
def test_suite_schema_rejects_invalid_values(field, value):
    with pytest.raises(ValidationError) as excinfo:
        EvalSuiteCreate.model_validate(suite_payload(**{field: value}))
    assert any(error["loc"] == (field,) for error in excinfo.value.errors())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("difficulty", "expert"),
        ("review_state", "draft"),
        ("weight", 0),
        ("input", []),
        ("expected_points", {"a": 1}),
        ("tags", ["smoke", " "]),
    ],
)
def test_case_schema_rejects_invalid_values(field, value):
    with pytest.raises(ValidationError) as excinfo:
        EvalCaseCreate.model_validate(case_payload(**{field: value}))
    assert any(error["loc"] == (field,) for error in excinfo.value.errors())


def test_run_schema_rejects_bad_ranges_and_time_order():
    with pytest.raises(ValidationError):
        EvalRunCreate.model_validate(run_payload(pass_rate="101.00"))

    with pytest.raises(ValidationError):
        EvalRunCreate.model_validate(run_payload(score_avg="-1.000"))

    started = utcnow()
    with pytest.raises(ValidationError):
        EvalRunCreate.model_validate(
            run_payload(
                started_at=started,
                finished_at=started - timedelta(minutes=1),
            )
        )


def test_result_schema_rejects_bad_score_and_latency():
    with pytest.raises(ValidationError):
        EvalResultCreate.model_validate(result_payload(score="101.000"))

    with pytest.raises(ValidationError):
        EvalResultCreate.model_validate(result_payload(latency_ms=-1))


def test_read_schemas_project_orm_rows(session):
    suite = create_suite(session)
    case = create_case(session, suite)
    session.commit()

    suite_read = EvalSuiteRead.model_validate(suite)
    assert suite_read.id == suite.id
    assert suite_read.suite_key == "kqa.retrieval"

    case_read = EvalCaseRead.model_validate(case)
    assert case_read.input["question"].startswith("虚构问题")
    assert case_read.weight == case.weight
