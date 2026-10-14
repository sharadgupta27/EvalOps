from dataclasses import dataclass
from typing import Any, Protocol


class LLMError(Exception):
    """A model call failed after retries, was refused, or returned unusable output."""


@dataclass(frozen=True)
class Completion:
    text: str
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: float


class LLMProvider(Protocol):
    name: str

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
        """Send one user message and return the text answer.

        `json_schema` asks the provider to constrain output to JSON matching the schema.
        """
        ...
