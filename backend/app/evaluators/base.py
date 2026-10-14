from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict

from app.llm.base import LLMProvider
from app.models import EvaluatorType


@dataclass(frozen=True)
class CaseData:
    """What an evaluator may see about a test case."""

    inputs: dict[str, Any]
    expected_output: str | None


@dataclass(frozen=True)
class EvalDeps:
    """Collaborators an evaluator may need. Only the judge uses them today."""

    provider: LLMProvider
    judge_model: str
    judge_effort: str | None = None


@dataclass
class EvalScore:
    evaluator: str
    type: EvaluatorType
    score: float  # normalised 0..1
    passed: bool
    reason: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)

    def public(self) -> dict[str, Any]:
        return {
            "evaluator": self.evaluator,
            "type": self.type.value,
            "score": round(self.score, 4),
            "passed": self.passed,
            "reason": self.reason,
        }


class EvaluatorConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Evaluator(ABC):
    kind: ClassVar[EvaluatorType]
    config_model: ClassVar[type[EvaluatorConfig]]

    def __init__(self, name: str, config: EvaluatorConfig, deps: EvalDeps) -> None:
        self.name = name
        self.config = config
        self.deps = deps

    @abstractmethod
    async def evaluate(self, case: CaseData, output: str) -> EvalScore: ...

    def _score(self, passed: bool, reason: str, score: float | None = None) -> EvalScore:
        return EvalScore(
            evaluator=self.name,
            type=self.kind,
            score=(1.0 if passed else 0.0) if score is None else score,
            passed=passed,
            reason=reason,
        )
