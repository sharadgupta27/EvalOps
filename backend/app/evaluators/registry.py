"""Evaluator registry. New evaluator types register themselves with @register."""

from collections.abc import Callable
from typing import Any, TypeVar

from pydantic import ValidationError

from app.errors import Invalid
from app.evaluators.base import EvalDeps, Evaluator
from app.models import EvaluatorType

# TypeVar instead of PEP 695 syntax: keeps the file parseable by Semgrep (SAST coverage).
E = TypeVar("E", bound=type[Evaluator])

_REGISTRY: dict[EvaluatorType, type[Evaluator]] = {}


def register(evaluator_type: EvaluatorType) -> Callable[[E], E]:
    def deco(cls: E) -> E:
        cls.kind = evaluator_type
        _REGISTRY[evaluator_type] = cls
        return cls

    return deco


def registered_types() -> list[EvaluatorType]:
    return sorted(_REGISTRY, key=lambda t: t.value)


def validate_config(evaluator_type: EvaluatorType, config: dict[str, Any]) -> dict[str, Any]:
    """Return the normalised config or raise Invalid with a readable message."""
    cls = _REGISTRY.get(evaluator_type)
    if cls is None:
        raise Invalid(f"unknown evaluator type: {evaluator_type}")
    try:
        return cls.config_model.model_validate(config).model_dump(exclude_none=True)
    except ValidationError as e:
        msgs = "; ".join(
            f"{'.'.join(map(str, err['loc'])) or 'config'}: {err['msg']}" for err in e.errors()
        )
        raise Invalid(f"invalid {evaluator_type.value} config: {msgs}") from e


def build_evaluator(
    evaluator_type: EvaluatorType, name: str, config: dict[str, Any], deps: EvalDeps
) -> Evaluator:
    cls = _REGISTRY[evaluator_type]
    return cls(name, cls.config_model.model_validate(config), deps)
