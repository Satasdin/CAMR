"""What a Claude call costs at list price, from the usage the API reports.

Prices are US dollars per million tokens, as in BUILD_PLAN.md. A cache write costs 1.25x the input price for the
5-minute cache and 2x for the 1-hour cache. Haiku has two price cards: one for prompts of 100K tokens or fewer, and
one for longer prompts, which then applies to every token of that call. BUILD_PLAN.md gives no cache prices for
Haiku, so its cache uses Anthropic's published rule for it: reads at 0.1x the input price, writes as above.

Thinking is billed as output: ``output_tokens`` already holds it, so it is never added twice.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

HAIKU_TIER_TOKENS = 100_000  # a prompt longer than this is priced on Haiku's long-prompt card


@dataclass(frozen=True)
class Rate:
    """One price card, in dollars per million tokens."""

    input: float
    output: float
    cache_read: float

    @property
    def cache_write_5m(self) -> float:
        return self.input * 1.25

    @property
    def cache_write_1h(self) -> float:
        return self.input * 2.0


OPUS = Rate(input=4.0, output=20.0, cache_read=0.20)
SONNET = Rate(input=2.0, output=10.0, cache_read=0.20)
HAIKU = Rate(input=0.10, output=0.50, cache_read=0.01)
HAIKU_LONG = Rate(input=0.50, output=2.50, cache_read=0.05)

PRICES: dict[str, tuple[Rate, Rate | None]] = {  # model -> (card, card past HAIKU_TIER_TOKENS or None)
    "claude-opus-5-5": (OPUS, None),
    "claude-sonnet-5-5": (SONNET, None),
    "claude-haiku-5-5": (HAIKU, HAIKU_LONG),
}


@dataclass(frozen=True)
class Tokens:
    """The token counts of one call, as the API bills them."""

    input: int = 0  # uncached prompt tokens (after the last cache breakpoint)
    output: int = 0  # everything written, thinking included
    cache_write_5m: int = 0
    cache_write_1h: int = 0
    cache_read: int = 0
    thinking: int = 0  # the part of ``output`` spent thinking; for the record only

    @property
    def cache_write(self) -> int:
        return self.cache_write_5m + self.cache_write_1h

    @property
    def prompt(self) -> int:
        """Every prompt token, cached or not: what Haiku's price card is chosen by."""
        return self.input + self.cache_write + self.cache_read

    def as_dict(self) -> dict:
        return {"input_tokens": self.input, "cache_creation_input_tokens": self.cache_write,
                "cache_write_5m_tokens": self.cache_write_5m, "cache_write_1h_tokens": self.cache_write_1h,
                "cache_read_input_tokens": self.cache_read, "output_tokens": self.output,
                "thinking_tokens": self.thinking, "prompt_tokens": self.prompt}


def _get(obj: Any, name: str) -> Any:
    return obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)


def tokens(usage: Any, ttl: str = "5m") -> Tokens:
    """The counts in a ``response.usage`` (an SDK object or a dict).

    A cache write the API does not split by lifetime is taken to be ``ttl`` long.
    """
    written = _get(usage, "cache_creation_input_tokens") or 0
    split = _get(usage, "cache_creation")
    w5 = _get(split, "ephemeral_5m_input_tokens") if split is not None else None
    w1 = _get(split, "ephemeral_1h_input_tokens") if split is not None else None
    if w5 is None and w1 is None:
        w5, w1 = (0, written) if ttl == "1h" else (written, 0)
    details = _get(usage, "output_tokens_details")
    thinking = (_get(details, "thinking_tokens") if details is not None else None) or 0
    return Tokens(input=_get(usage, "input_tokens") or 0, output=_get(usage, "output_tokens") or 0,
                  cache_write_5m=w5 or 0, cache_write_1h=w1 or 0,
                  cache_read=_get(usage, "cache_read_input_tokens") or 0, thinking=thinking)


def rate(model: str, prompt_tokens: int) -> Rate:
    """The price card for a call to ``model`` whose prompt is ``prompt_tokens`` long."""
    if model not in PRICES:
        raise ValueError(f"no list price for {model!r}; known: {', '.join(PRICES)}")
    card, long_card = PRICES[model]
    return long_card if long_card is not None and prompt_tokens > HAIKU_TIER_TOKENS else card


def cost_usd(model: str, usage: Any, ttl: str = "5m") -> float:
    """The list-price cost of one call, from its usage (an SDK ``Usage``, a dict or a ``Tokens``)."""
    t = usage if isinstance(usage, Tokens) else tokens(usage, ttl)
    r = rate(model, t.prompt)
    return (t.input * r.input + t.output * r.output + t.cache_read * r.cache_read
            + t.cache_write_5m * r.cache_write_5m + t.cache_write_1h * r.cache_write_1h) / 1e6


def estimate_usd(model: str, prompt_tokens: int, max_tokens: int, cache: str | None = "5m") -> float:
    """The most a call can cost before it is sent: every prompt token at the price of a cache write (or of plain
    input when ``cache`` is None), and every allowed output token."""
    r = rate(model, prompt_tokens)
    per_prompt = {None: r.input, "5m": r.cache_write_5m, "1h": r.cache_write_1h}[cache]
    return (prompt_tokens * max(per_prompt, r.input) + max_tokens * r.output) / 1e6
