"""LLM-as-judge. The judge sees untrusted data only inside delimited blocks and has no tools."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field

from app.evaluators.base import CaseData, EvalScore, Evaluator, EvaluatorConfig
from app.evaluators.registry import register
from app.llm.base import LLMError
from app.models import EvaluatorType

PROMPT_PATH = Path(__file__).parent / "prompts" / "judge.md"
_DELIMS = ("rubric", "input", "expected", "output")

JUDGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "score": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
        "reasoning": {"type": "string"},
    },
    "required": ["score", "reasoning"],
    "additionalProperties": False,
}


@lru_cache
def load_judge_prompt() -> tuple[str, str]:
    system, user = PROMPT_PATH.read_text(encoding="utf-8").split("---USER---", 1)
    return system.strip(), user.strip()


def neutralise(text: str) -> str:
    """Stop untrusted text from closing or opening our delimiter tags."""
    for tag in _DELIMS:
        text = text.replace(f"<{tag}>", f"<{tag}_>").replace(f"</{tag}>", f"</{tag}_>")
    return text


def render_judge_prompt(rubric: str, case: CaseData, output: str) -> tuple[str, str]:
    system, user = load_judge_prompt()
    return system, user.format(
        rubric=neutralise(rubric),
        inputs=neutralise(json.dumps(case.inputs, ensure_ascii=False, indent=2)),
        expected=neutralise(case.expected_output or ""),
        output=neutralise(output),
    )


def parse_judgement(text: str) -> tuple[int, str]:
    try:
        data = json.loads(text.strip().removeprefix("```json").removesuffix("```"))
        score = int(data["score"])
        reasoning = str(data.get("reasoning", ""))
    except (ValueError, KeyError, TypeError) as e:
        raise LLMError(f"judge returned unparseable output: {text[:200]!r}") from e
    if not 1 <= score <= 5:
        raise LLMError(f"judge score out of range: {score}")
    return score, reasoning


class LLMJudgeConfig(EvaluatorConfig):
    rubric: str = Field(min_length=3, max_length=5000)
    threshold: int = Field(default=4, ge=1, le=5)


@register(EvaluatorType.llm_judge)
class LLMJudge(Evaluator):
    config_model = LLMJudgeConfig
    config: LLMJudgeConfig

    async def evaluate(self, case: CaseData, output: str) -> EvalScore:
        system, prompt = render_judge_prompt(self.config.rubric, case, output)
        completion = await self.deps.provider.complete(
            prompt,
            system=system,
            model=self.deps.judge_model,
            max_tokens=1024,
            json_schema=JUDGE_SCHEMA,
            effort=self.deps.judge_effort,
        )
        raw, reasoning = parse_judgement(completion.text)
        passed = raw >= self.config.threshold
        result = self._score(passed, f"{raw}/5: {reasoning}", score=(raw - 1) / 4)
        result.tokens_in = completion.tokens_in
        result.tokens_out = completion.tokens_out
        result.cost_usd = completion.cost_usd
        result.extra = {"raw_score": raw}
        return result
