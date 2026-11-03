import pytest
from anthropic.types import CacheCreation, OutputTokensDetails, Usage

from engram.bench.cost import HAIKU_TIER_TOKENS, Tokens, cost_usd, estimate_usd, rate, tokens

M = 1_000_000


@pytest.mark.parametrize("model,inp,out,read,write", [
    ("claude-opus-5-5", 4.0, 20.0, 0.20, 5.0),
    ("claude-sonnet-5-5", 2.0, 10.0, 0.20, 2.5),
])
def test_list_prices(model, inp, out, read, write):
    assert cost_usd(model, {"input_tokens": M, "output_tokens": 0}) == pytest.approx(inp)
    assert cost_usd(model, {"input_tokens": 0, "output_tokens": M}) == pytest.approx(out)
    assert cost_usd(model, {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": M}) == pytest.approx(read)
    assert cost_usd(model, {"input_tokens": 0, "output_tokens": 0,
                            "cache_creation_input_tokens": M}) == pytest.approx(write)
    assert cost_usd(model, {"input_tokens": 0, "output_tokens": 0, "cache_creation_input_tokens": M},
                    ttl="1h") == pytest.approx(2 * inp)


def test_haiku_is_tiered_past_100k_prompt_tokens():
    short = {"input_tokens": HAIKU_TIER_TOKENS, "output_tokens": 1000}
    assert cost_usd("claude-haiku-5-5", short) == pytest.approx((HAIKU_TIER_TOKENS * 0.10 + 1000 * 0.50) / M)
    long = {"input_tokens": HAIKU_TIER_TOKENS + 1, "output_tokens": 1000}  # the long card prices output too
    assert cost_usd("claude-haiku-5-5", long) == pytest.approx(((HAIKU_TIER_TOKENS + 1) * 0.50 + 1000 * 2.50) / M)
    # cached tokens count toward the prompt's length
    cached = {"input_tokens": 10, "output_tokens": 0, "cache_read_input_tokens": HAIKU_TIER_TOKENS}
    assert rate("claude-haiku-5-5", tokens(cached).prompt).input == 0.50
    assert cost_usd("claude-haiku-5-5", cached) == pytest.approx((10 * 0.50 + HAIKU_TIER_TOKENS * 0.05) / M)


def test_sdk_usage_with_ttl_split_and_thinking():
    u = Usage(input_tokens=1000, output_tokens=500, cache_read_input_tokens=20_000, cache_creation_input_tokens=3000,
              cache_creation=CacheCreation(ephemeral_5m_input_tokens=1000, ephemeral_1h_input_tokens=2000),
              output_tokens_details=OutputTokensDetails(thinking_tokens=300))
    t = tokens(u)
    assert (t.input, t.output, t.cache_read, t.cache_write_5m, t.cache_write_1h, t.thinking) == (
        1000, 500, 20_000, 1000, 2000, 300)
    want = (1000 * 4 + 500 * 20 + 20_000 * 0.20 + 1000 * 5 + 2000 * 8) / M  # thinking is inside output, not added
    assert cost_usd("claude-opus-5-5", u) == pytest.approx(want)


def test_missing_cache_fields_are_zero():
    u = Usage(input_tokens=10, output_tokens=5)
    assert tokens(u) == Tokens(input=10, output=5)
    assert cost_usd("claude-sonnet-5-5", u) == pytest.approx((10 * 2 + 5 * 10) / M)


@pytest.mark.parametrize("model", ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"])
@pytest.mark.parametrize("prompt", [500, 99_000, 150_000, 900_000])
def test_estimate_is_never_below_the_bill(model, prompt):
    est = estimate_usd(model, prompt, 4000)
    third = prompt // 3
    for split in ((prompt, 0, 0), (0, prompt, 0), (0, 0, prompt), (third, third, prompt - 2 * third)):
        usage = {"input_tokens": split[0], "cache_creation_input_tokens": split[1], "cache_read_input_tokens": split[2],
                 "output_tokens": 4000}
        assert cost_usd(model, usage) <= est + 1e-12


def test_unknown_model_has_no_price():
    with pytest.raises(ValueError):
        cost_usd("claude-opus-4-8", {"input_tokens": 1, "output_tokens": 1})
