"""Evaluator plugins. Importing this package registers every built-in evaluator."""

from app.evaluators import deterministic, llm_judge  # noqa: F401  (registration side effect)
from app.evaluators.base import CaseData, EvalDeps, EvalScore, Evaluator
from app.evaluators.registry import build_evaluator, registered_types, validate_config

__all__ = [
    "CaseData",
    "EvalDeps",
    "EvalScore",
    "Evaluator",
    "build_evaluator",
    "registered_types",
    "validate_config",
]
