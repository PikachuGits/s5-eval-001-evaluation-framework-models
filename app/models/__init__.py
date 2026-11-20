"""Import all models so ``Base.metadata`` is complete for Alembic."""

from app.models.eval_baseline import EvalBaseline
from app.models.eval_case import EvalCase
from app.models.eval_result import EvalResult
from app.models.eval_run import EvalRun
from app.models.eval_suite import EvalSuite

__all__ = [
    "EvalBaseline",
    "EvalCase",
    "EvalResult",
    "EvalRun",
    "EvalSuite",
]
