"""Wraps any provider with a trace span and Prometheus metrics (model, tokens, cost)."""

from typing import Any

from app.llm.base import Completion, LLMError, LLMProvider
from app.observability import LLM_COST, LLM_ERRORS, LLM_LATENCY, LLM_TOKENS, tracer


class InstrumentedProvider:
    def __init__(self, inner: LLMProvider) -> None:
        self.inner = inner
        self.name = inner.name

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
        with tracer.start_as_current_span("llm.complete") as span:
            span.set_attribute("gen_ai.system", self.name)
            span.set_attribute("gen_ai.request.model", model)
            span.set_attribute("gen_ai.request.max_tokens", max_tokens)
            try:
                c = await self.inner.complete(
                    prompt,
                    model=model,
                    max_tokens=max_tokens,
                    system=system,
                    temperature=temperature,
                    json_schema=json_schema,
                    effort=effort,
                )
            except LLMError as e:
                LLM_ERRORS.labels(self.name, model).inc()
                span.record_exception(e)
                raise
            span.set_attribute("gen_ai.usage.input_tokens", c.tokens_in)
            span.set_attribute("gen_ai.usage.output_tokens", c.tokens_out)
            span.set_attribute("evalops.cost_usd", c.cost_usd)
            LLM_LATENCY.labels(self.name, model).observe(c.latency_ms / 1000)
            LLM_TOKENS.labels(model, "input").inc(c.tokens_in)
            LLM_TOKENS.labels(model, "output").inc(c.tokens_out)
            LLM_COST.labels(model).inc(c.cost_usd)
            return c
