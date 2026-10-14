"""Claude via the official Anthropic SDK.

- Retries (408/409/429/5xx/connection) and timeouts are handled by the SDK client.
- No server-side model fallback: an eval must measure the configured model, so a refusal
  becomes an error on that case instead of being silently answered by another model.
- Sampling parameters are sent only when set, because current models reject them.
"""

import time
from typing import Any

import anthropic

from app.llm.base import Completion, LLMError
from app.llm.pricing import cost_usd


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str | None, timeout: float, max_retries: int) -> None:
        # api_key=None lets the SDK resolve credentials from its usual sources.
        self._client = anthropic.AsyncAnthropic(
            api_key=api_key, timeout=timeout, max_retries=max_retries
        )

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
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        if temperature is not None:
            kwargs["temperature"] = temperature
        output_config: dict[str, Any] = {}
        if json_schema is not None:
            output_config["format"] = {"type": "json_schema", "schema": json_schema}
        if effort:
            output_config["effort"] = effort
        if output_config:
            kwargs["output_config"] = output_config

        started = time.perf_counter()
        try:
            response = await self._client.messages.create(**kwargs)
        except anthropic.AuthenticationError as e:
            raise LLMError("authentication failed: check ANTHROPIC_API_KEY") from e
        except anthropic.BadRequestError as e:
            raise LLMError(f"bad request: {e.message}") from e
        except anthropic.RateLimitError as e:
            raise LLMError("rate limited after retries") from e
        except anthropic.APIStatusError as e:
            raise LLMError(f"API error {e.status_code}: {e.message}") from e
        except anthropic.APIConnectionError as e:
            raise LLMError("connection error after retries") from e
        latency_ms = (time.perf_counter() - started) * 1000

        if response.stop_reason == "refusal":
            raise LLMError("model refused the request")
        text = "".join(b.text for b in response.content if b.type == "text")
        tin, tout = response.usage.input_tokens, response.usage.output_tokens
        return Completion(
            text=text,
            model=response.model,
            tokens_in=tin,
            tokens_out=tout,
            cost_usd=cost_usd(model, tin, tout),
            latency_ms=latency_ms,
        )
