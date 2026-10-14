from app.config import Settings
from app.llm.base import LLMProvider
from app.llm.fake import FakeProvider
from app.llm.instrumented import InstrumentedProvider


def build_provider(settings: Settings) -> LLMProvider:
    inner: LLMProvider
    if settings.llm_provider == "anthropic":
        from app.llm.anthropic_provider import AnthropicProvider

        key = settings.anthropic_api_key.get_secret_value() if settings.anthropic_api_key else None
        inner = AnthropicProvider(key, settings.llm_timeout_seconds, settings.llm_max_retries)
    else:
        inner = FakeProvider()
    return InstrumentedProvider(inner)
