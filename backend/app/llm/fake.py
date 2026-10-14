"""Deterministic provider for tests, CI and the public demo. Never touches the network.

Default behaviour simulates a "reasonable" model so demos are meaningful:
- Generation: replies to the last non-empty line of the prompt. The reply is polite when
  the prompt asks for politeness, JSON when the prompt asks for JSON, and terse when it
  asks for brevity.
- Judging: the judge prompt (evaluators/prompts/judge.md) is recognised and scored by a
  transparent heuristic over the delimited <output>, <expected> and <rubric> blocks.

Tests can override any of this with `script()` rules or a custom `responder`.
"""

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.llm.base import Completion, LLMError
from app.llm.pricing import cost_usd

POLITE_WORDS = ("thank", "sorry", "happy to help", "please", "glad")
JUDGE_MARKER = "You are an impartial evaluator"


def _tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _block(prompt: str, tag: str) -> str:
    m = re.search(rf"<{tag}>\n?(.*?)\n?</{tag}>", prompt, re.S)
    return m.group(1).strip() if m else ""


@dataclass
class _Rule:
    contains: str
    reply: str | None
    error: str | None


class FakeProvider:
    name = "fake"

    def __init__(
        self,
        responder: Callable[[str], str] | None = None,
        latency_ms: float = 5.0,
    ) -> None:
        self._responder = responder
        self._rules: list[_Rule] = []
        self.latency_ms = latency_ms
        self.calls: list[str] = []

    def script(self, contains: str, reply: str | None = None, error: str | None = None) -> None:
        """When the prompt contains `contains`, return `reply` (or raise `error`)."""
        self._rules.append(_Rule(contains, reply, error))

    async def complete(
        self,
        prompt: str,
        *,
        model: str,
        max_tokens: int,
        system: str | None = None,
        temperature: float | None = None,
        json_schema: dict[str, Any] | None = None,
        effort: str | None = None,
    ) -> Completion:
        self.calls.append(prompt)
        text = self._reply(prompt, system or "")
        tin, tout = _tokens((system or "") + prompt), _tokens(text)
        return Completion(
            text=text,
            model=model,
            tokens_in=tin,
            tokens_out=tout,
            cost_usd=cost_usd("fake", tin, tout),
            latency_ms=self.latency_ms + len(prompt) % 17,
        )

    def _reply(self, prompt: str, system: str) -> str:
        for rule in self._rules:
            if rule.contains in prompt:
                if rule.error:
                    raise LLMError(rule.error)
                return rule.reply or ""
        if self._responder:
            return self._responder(prompt)
        if JUDGE_MARKER in system or JUDGE_MARKER in prompt:
            return self._judge(prompt)
        return self._generate(prompt, system)

    @staticmethod
    def _generate(prompt: str, system: str) -> str:
        instructions = (system + "\n" + prompt).lower()
        lines = [ln.strip() for ln in prompt.strip().splitlines() if ln.strip()]
        subject = lines[-1] if lines else ""
        body = f"Regarding: {subject} - here is the answer."
        words = subject.split()
        if "terse" in instructions or "one word" in instructions:
            body = words[-1] if words else ""
        elif "polite" in instructions or "friendly" in instructions:
            body = f"Thanks for reaching out! {body} Happy to help further."
        if "json" in instructions:
            return json.dumps({"answer": body})
        return body

    @staticmethod
    def _judge(prompt: str) -> str:
        output = _block(prompt, "output").lower()
        expected = _block(prompt, "expected").lower()
        rubric = _block(prompt, "rubric").lower()
        score = 2
        if expected and expected in output:
            score = 4
        elif not expected and len(output) > 20:
            score = 3
        if "polite" in rubric:
            score += 1 if any(w in output for w in POLITE_WORDS) else -1
        score = min(5, max(1, score))
        return json.dumps({"score": score, "reasoning": f"Heuristic fake judge: {score}/5."})
