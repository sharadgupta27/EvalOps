import json
from types import SimpleNamespace
from typing import Any

import pytest

from app.errors import Unauthorized
from app.llm.anthropic_provider import AnthropicProvider
from app.llm.base import LLMError
from app.llm.fake import FakeProvider
from app.llm.pricing import cost_usd
from app.services import security


async def test_fake_provider_is_deterministic_and_follows_instructions() -> None:
    fake = FakeProvider()
    kwargs: dict[str, Any] = {"model": "m", "max_tokens": 10}
    a = await fake.complete("Be polite. Reply in JSON.\nWhere is my order?", **kwargs)
    b = await fake.complete("Be polite. Reply in JSON.\nWhere is my order?", **kwargs)
    assert a == b
    body = json.loads(a.text)["answer"]
    assert body.startswith("Thanks") and "order" in body
    terse = await fake.complete("Be terse.\nWhere is my order?", **kwargs)
    assert terse.text == "order?"


async def test_fake_provider_scripted_error() -> None:
    fake = FakeProvider()
    fake.script("boom", error="simulated outage")
    with pytest.raises(LLMError, match="outage"):
        await fake.complete("boom", model="m", max_tokens=1)


def test_unknown_model_priced_at_most_expensive_rate() -> None:
    assert cost_usd("mystery-model", 1_000_000, 0) >= cost_usd("claude-opus-5-5", 1_000_000, 0)


class _FakeMessages:
    def __init__(self, response: Any) -> None:
        self.response = response
        self.kwargs: dict[str, Any] = {}

    async def create(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        return self.response


def _response(stop_reason: str = "end_turn") -> Any:
    return SimpleNamespace(
        stop_reason=stop_reason,
        model="claude-opus-5-5",
        content=[
            SimpleNamespace(type="thinking", thinking=""),
            SimpleNamespace(type="text", text="hi"),
        ],
        usage=SimpleNamespace(input_tokens=1000, output_tokens=500),
    )


async def test_anthropic_provider_maps_request_and_usage() -> None:
    provider = AnthropicProvider(api_key="test", timeout=1, max_retries=0)
    messages = _FakeMessages(_response())
    provider._client = SimpleNamespace(messages=messages)  # type: ignore[assignment]
    c = await provider.complete(
        "q",
        model="claude-opus-5-5",
        max_tokens=99,
        system="sys",
        json_schema={"type": "object"},
        effort="low",
    )
    assert c.text == "hi" and (c.tokens_in, c.tokens_out) == (1000, 500)
    assert c.cost_usd == pytest.approx(0.004 + 0.01)
    sent = messages.kwargs
    assert sent["system"] == "sys" and "temperature" not in sent
    assert sent["output_config"] == {
        "format": {"type": "json_schema", "schema": {"type": "object"}},
        "effort": "low",
    }


async def test_anthropic_provider_refusal_is_an_error() -> None:
    provider = AnthropicProvider(api_key="test", timeout=1, max_retries=0)
    provider._client = SimpleNamespace(messages=_FakeMessages(_response("refusal")))  # type: ignore[assignment]
    with pytest.raises(LLMError, match="refused"):
        await provider.complete("q", model="m", max_tokens=1)


def test_password_hashing() -> None:
    h = security.hash_password("s3cret-pass")
    assert h != "s3cret-pass"
    assert security.verify_password("s3cret-pass", h)
    assert not security.verify_password("wrong", h)
    assert not security.verify_password("x", "not-a-hash")


def test_jwt_round_trip_and_tamper() -> None:
    token = security.create_jwt(7, "k" * 32, 5)
    assert security.decode_jwt(token, "k" * 32) == 7
    with pytest.raises(Unauthorized):
        security.decode_jwt(token, "other-secret-" * 3)
    with pytest.raises(Unauthorized):
        security.decode_jwt(security.create_jwt(7, "k" * 32, -1), "k" * 32)


def test_api_keys_are_random_and_hashed() -> None:
    a, b = security.generate_api_key(), security.generate_api_key()
    assert a != b and a.startswith("eo_")
    assert len(security.hash_api_key(a)) == 64 and security.hash_api_key(a) != a


def test_prod_refuses_default_jwt_secret() -> None:
    from pydantic import ValidationError

    from app.config import Settings

    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(environment="prod")
    assert Settings(environment="prod", jwt_secret="x" * 40).environment == "prod"
