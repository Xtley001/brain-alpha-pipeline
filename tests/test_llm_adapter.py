import pytest

from pipeline.llm.adapter import (
    KeyedProvider,
    LLMAdapter,
    QuotaExhausted,
    RateLimitError,
)


def _usage_log():
    calls = []

    def logger(provider, key_label, tier, succeeded, error_text):
        calls.append((provider, key_label, tier, succeeded, error_text))

    return calls, logger


def test_falls_back_to_second_key_on_rate_limit():
    calls, logger = _usage_log()

    def call_fn(prompt, model, key_value):
        if key_value == "bad_key_1":
            raise RateLimitError("429 RESOURCE_EXHAUSTED")
        return f"ok from {key_value}"

    provider = KeyedProvider(name="gemini", keys=[("key_1", "bad_key_1"), ("key_2", "good_key_2")], call_fn=call_fn)
    result = provider.call("prompt", "model", "reasoning", logger, sleep_fn=lambda s: None)

    assert result == "ok from good_key_2"
    assert calls[0] == ("gemini", "key_1", "reasoning", False, "429 RESOURCE_EXHAUSTED")
    assert calls[1] == ("gemini", "key_2", "reasoning", True, None)


def test_falls_back_on_hard_failure_not_only_rate_limit():
    calls, logger = _usage_log()

    def call_fn(prompt, model, key_value):
        if key_value == "broken_key":
            raise ValueError("network unreachable")
        return "recovered"

    provider = KeyedProvider(name="groq", keys=[("key_1", "broken_key"), ("key_2", "fine_key")], call_fn=call_fn)
    result = provider.call("p", "m", "mechanical", logger, sleep_fn=lambda s: None)

    assert result == "recovered"
    assert calls[0][3] is False
    assert calls[1][3] is True


def test_all_keys_exhausted_raises_quota_exhausted_and_logs_each():
    calls, logger = _usage_log()

    def call_fn(prompt, model, key_value):
        raise RateLimitError("429")

    provider = KeyedProvider(name="gemini", keys=[("key_1", "k1"), ("key_2", "k2")], call_fn=call_fn)

    with pytest.raises(QuotaExhausted):
        provider.call("p", "m", "reasoning", logger, sleep_fn=lambda s: None)

    assert len(calls) == 2
    assert all(c[3] is False for c in calls)


def test_key_label_identifies_specific_key_not_generic_provider_name():
    calls, logger = _usage_log()

    def call_fn(prompt, model, key_value):
        return "ok"

    provider = KeyedProvider(name="gemini", keys=[("key_1", "k1"), ("key_2", "k2")], call_fn=call_fn)
    provider.call("p", "m", "reasoning", logger, sleep_fn=lambda s: None)

    assert calls[0][1] == "key_1"  # not just "gemini"


def test_reasoning_tier_falls_through_gemini_then_groq():
    calls, logger = _usage_log()

    def gemini_call_fn(prompt, model, key_value):
        raise RateLimitError("429")

    def groq_call_fn(prompt, model, key_value):
        return "groq answered"

    gemini = KeyedProvider(name="gemini", keys=[("key_1", "k1")], call_fn=gemini_call_fn)
    groq = KeyedProvider(name="groq", keys=[("key_1", "k1")], call_fn=groq_call_fn)

    adapter = LLMAdapter(gemini_provider=gemini, groq_provider=groq, usage_logger=logger)
    text, provider = adapter.reasoning_call("prompt")

    assert text == "groq answered"
    assert provider == "groq"  # Update 03: must report who actually answered


def test_reasoning_tier_reports_gemini_when_gemini_answers_directly():
    def gemini_call_fn(prompt, model, key_value):
        return "gemini answered"

    def groq_call_fn(prompt, model, key_value):
        raise AssertionError("groq should not be called if gemini succeeds")

    gemini = KeyedProvider(name="gemini", keys=[("key_1", "k1")], call_fn=gemini_call_fn)
    groq = KeyedProvider(name="groq", keys=[("key_1", "k1")], call_fn=groq_call_fn)

    adapter = LLMAdapter(gemini_provider=gemini, groq_provider=groq)
    text, provider = adapter.reasoning_call("prompt")

    assert text == "gemini answered"
    assert provider == "gemini"


def test_mechanical_tier_falls_through_groq_then_gemini():
    def groq_call_fn(prompt, model, key_value):
        raise RateLimitError("429")

    def gemini_call_fn(prompt, model, key_value):
        return "gemini answered"

    gemini = KeyedProvider(name="gemini", keys=[("key_1", "k1")], call_fn=gemini_call_fn)
    groq = KeyedProvider(name="groq", keys=[("key_1", "k1")], call_fn=groq_call_fn)

    adapter = LLMAdapter(gemini_provider=gemini, groq_provider=groq)
    text, provider = adapter.mechanical_call("prompt")

    assert text == "gemini answered"
    assert provider == "gemini"  # Update 03: must report who actually answered


def test_total_exhaustion_callback_fires_when_both_providers_exhausted():
    fired = []

    def gemini_call_fn(prompt, model, key_value):
        raise RateLimitError("429")

    def groq_call_fn(prompt, model, key_value):
        raise RateLimitError("429")

    gemini = KeyedProvider(name="gemini", keys=[("key_1", "k1")], call_fn=gemini_call_fn)
    groq = KeyedProvider(name="groq", keys=[("key_1", "k1")], call_fn=groq_call_fn)

    adapter = LLMAdapter(
        gemini_provider=gemini,
        groq_provider=groq,
        on_total_exhaustion=lambda tier: fired.append(tier),
    )

    with pytest.raises(QuotaExhausted):
        adapter.reasoning_call("prompt")

    assert fired == ["reasoning"]
