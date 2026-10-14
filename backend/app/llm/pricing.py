"""USD per million tokens (input, output). Used for cost reporting and spend caps only.

Prices are Anthropic first-party list prices; update them when they change. Unknown models
fall back to the most expensive known price so spend caps fail safe.
"""

PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-fable-5-1": (10.0, 50.0),
    "claude-opus-5-5": (4.0, 20.0),
    "claude-opus-5": (5.0, 25.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-sonnet-5": (2.0, 10.0),
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-haiku-4-5": (1.0, 5.0),
    "fake": (1.0, 2.0),
}
_FALLBACK = max(PRICES_PER_MTOK.values())


def cost_usd(model: str, tokens_in: int, tokens_out: int) -> float:
    price_in, price_out = PRICES_PER_MTOK.get(model, _FALLBACK)
    return round((tokens_in * price_in + tokens_out * price_out) / 1_000_000, 8)
