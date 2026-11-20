"""Small factories and fixed IDs used by the test suite.

All strings are fictional: no real person, company or customer data appears in
this repository.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.models.eval_baseline import EvalBaseline
from app.models.eval_case import EvalCase
from app.models.eval_result import EvalResult
from app.models.eval_run import EvalRun
from app.models.eval_suite import EvalSuite

ORG_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a1")
OTHER_ORG_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a2")
SITE_ID = uuid.UUID("00000000-0000-0000-0000-0000000000b1")
OTHER_SITE_ID = uuid.UUID("00000000-0000-0000-0000-0000000000b2")
ACTOR_ID = uuid.UUID("00000000-0000-0000-0000-0000000000c1")
REVIEWER_ID = uuid.UUID("00000000-0000-0000-0000-0000000000c2")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def make_suite(**overrides) -> EvalSuite:
    values = {
        "org_id": ORG_ID,
        "site_id": SITE_ID,
        "suite_key": "kqa.retrieval",
        "tool": "kqa",
        "version": 1,
        "case_count": 2,
        "status": "active",
        "created_by": ACTOR_ID,
    }
    values.update(overrides)
    return EvalSuite(**values)


def create_suite(session, **overrides) -> EvalSuite:
    suite = make_suite(**overrides)
    session.add(suite)
    session.flush()
    return suite


def make_case(suite_id: uuid.UUID, **overrides) -> EvalCase:
    values = {
        "org_id": ORG_ID,
        "site_id": SITE_ID,
        "suite_id": suite_id,
        "case_key": "CASE-001",
        "input": {"question": "虚构问题：如何登记一次虚构活动？"},
        "context": {"locale": "zh-CN", "tenant_tier": "demo"},
        "expected_points": ["说明虚构活动的登记入口", "提示需要虚构审批人"],
        "forbidden_points": ["编造不存在的审批时限", "输出任何真实个人信息"],
        "reference_output": None,
        "tags": ["smoke", "retrieval"],
        "difficulty": "easy",
        "weight": Decimal("1.000"),
        "review_state": "approved",
        "created_by": ACTOR_ID,
    }
    values.update(overrides)
    return EvalCase(**values)


def create_case(session, suite: EvalSuite, **overrides) -> EvalCase:
    case = make_case(suite.id, **overrides)
    session.add(case)
    session.flush()
    return case


def make_run(suite: EvalSuite, **overrides) -> EvalRun:
    now = utcnow()
    values = {
        "org_id": suite.org_id,
        "site_id": suite.site_id,
        "suite_id": suite.id,
        "suite_version": suite.version,
        "target_tool": suite.tool,
        "target_prompt_version": "prompt-v1",
        "target_model": "mock-judge-v1",
        "trigger": "manual",
        "git_sha": "abcdef1234567",
        "status": "succeeded",
        "pass_rate": Decimal("100.00"),
        "score_avg": Decimal("95.000"),
        "token_usage": 1234,
        "started_at": now,
        "finished_at": now + timedelta(minutes=5),
        "created_by": ACTOR_ID,
    }
    values.update(overrides)
    return EvalRun(**values)


def create_run(session, suite: EvalSuite, **overrides) -> EvalRun:
    run = make_run(suite, **overrides)
    session.add(run)
    session.flush()
    return run


def make_result(run: EvalRun, case: EvalCase, **overrides) -> EvalResult:
    values = {
        "org_id": run.org_id,
        "site_id": run.site_id,
        "run_id": run.id,
        "case_id": case.id,
        "suite_id": run.suite_id,
        "output_text": "虚构答案：先登记，再提交虚构审批人复核。",
        "output_json": {"answer": "先登记，再提交虚构审批人复核。"},
        "score": Decimal("95.000"),
        "passed": True,
        "point_hits": ["说明虚构活动的登记入口"],
        "violations": [],
        "latency_ms": 120,
        "judge_trace": {"judge": "mock-judge-v1", "rubric": "v1"},
        "error": None,
        "created_by": ACTOR_ID,
    }
    values.update(overrides)
    return EvalResult(**values)


def make_baseline(suite: EvalSuite, run: EvalRun, **overrides) -> EvalBaseline:
    values = {
        "org_id": suite.org_id,
        "site_id": suite.site_id,
        "suite_id": suite.id,
        "run_id": run.id,
        "set_by": REVIEWER_ID,
        "set_at": utcnow(),
        "note": "虚构基线：用于回归对比",
        "created_by": REVIEWER_ID,
    }
    values.update(overrides)
    return EvalBaseline(**values)


def suite_payload(**overrides) -> dict:
    values = {
        "org_id": ORG_ID,
        "site_id": SITE_ID,
        "suite_key": "kqa.retrieval",
        "tool": "kqa",
        "version": 1,
        "case_count": 0,
        "status": "draft",
    }
    values.update(overrides)
    return values


def case_payload(**overrides) -> dict:
    values = {
        "org_id": ORG_ID,
        "site_id": SITE_ID,
        "suite_id": ORG_ID,
        "case_key": "CASE-001",
        "input": {"question": "虚构问题"},
        "context": {},
        "expected_points": ["虚构要点"],
        "forbidden_points": ["虚构禁用项"],
        "tags": ["smoke"],
        "difficulty": "medium",
        "weight": "1.000",
        "review_state": "pending",
    }
    values.update(overrides)
    return values


def run_payload(**overrides) -> dict:
    values = {
        "org_id": ORG_ID,
        "site_id": SITE_ID,
        "suite_id": ORG_ID,
        "suite_version": 1,
        "target_tool": "kqa",
        "trigger": "manual",
        "status": "queued",
        "token_usage": 0,
    }
    values.update(overrides)
    return values


def result_payload(**overrides) -> dict:
    values = {
        "org_id": ORG_ID,
        "site_id": SITE_ID,
        "run_id": ORG_ID,
        "case_id": SITE_ID,
        "score": "95.000",
        "passed": True,
        "point_hits": [],
        "violations": [],
        "judge_trace": {},
    }
    values.update(overrides)
    return values
