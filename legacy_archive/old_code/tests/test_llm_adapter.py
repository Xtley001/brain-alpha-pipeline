import pytest

from pipeline.llm.adapter import (
    KeyedProvider,
    LLMAdapter,
    ProviderStep,
    QuotaExhausted,
    RateLimitError,
    build_default_llm_adapter,
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

    provider = KeyedProvider(name="groq", keys=[("key_1", "bad_key_1"), ("key_2", "good_key_2")], call_fn=call_fn)
    result = provider.call("prompt", "model", "reasoning", logger, sleep_fn=lambda s: None)

    assert result == "ok from good_key_2"
    assert calls[0] == ("groq", "key_1", "reasoning", False, "429 RESOURCE_EXHAUSTED")
    assert calls[1] == ("groq", "key_2", "reasoning", True, None)


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

    provider = KeyedProvider(name="groq", keys=[("key_1", "k1"), ("key_2", "k2")], call_fn=call_fn)

    with pytest.raises(QuotaExhausted):
        provider.call("p", "m", "reasoning", logger, sleep_fn=lambda s: None)

    assert len(calls) == 2
    assert all(c[3] is False for c in calls)


def test_key_label_identifies_specific_key_not_generic_provider_name():
    calls, logger = _usage_log()

    def call_fn(prompt, model, key_value):
        return "ok"

    provider = KeyedProvider(name="groq", keys=[("key_1", "k1"), ("key_2", "k2")], call_fn=call_fn)
    provider.call("p", "m", "reasoning", logger, sleep_fn=lambda s: None)

    assert calls[0][1] == "key_1"  # not just "groq"


def test_reasoning_tier_falls_through_first_provider_to_second():
    calls, logger = _usage_log()

    def groq_call_fn(prompt, model, key_value):
        raise RateLimitError("429")

    def openrouter_call_fn(prompt, model, key_value):
        return "openrouter answered"

    groq = KeyedProvider(name="groq", keys=[("key_1", "k1")], call_fn=groq_call_fn)
    openrouter = KeyedProvider(name="openrouter", keys=[("key_1", "k1")], call_fn=openrouter_call_fn)

    adapter = LLMAdapter(
        reasoning_chain=[ProviderStep(groq, "model-a"), ProviderStep(openrouter, "model-b")],
        mechanical_chain=[ProviderStep(groq, "model-c"), ProviderStep(openrouter, "model-d")],
        usage_logger=logger,
    )
    text, provider = adapter.reasoning_call("prompt")

    assert text == "openrouter answered"
    assert provider == "openrouter"  # Update 03/07: must report who actually answered


def test_reasoning_tier_reports_first_provider_when_it_answers_directly():
    def groq_call_fn(prompt, model, key_value):
        return "groq answered"

    def openrouter_call_fn(prompt, model, key_value):
        raise AssertionError("openrouter should not be called if groq succeeds")

    groq = KeyedProvider(name="groq", keys=[("key_1", "k1")], call_fn=groq_call_fn)
    openrouter = KeyedProvider(name="openrouter", keys=[("key_1", "k1")], call_fn=openrouter_call_fn)

    adapter = LLMAdapter(
        reasoning_chain=[ProviderStep(groq, "model-a"), ProviderStep(openrouter, "model-b")],
        mechanical_chain=[ProviderStep(groq, "model-c"), ProviderStep(openrouter, "model-d")],
    )
    text, provider = adapter.reasoning_call("prompt")

    assert text == "groq answered"
    assert provider == "groq"


def test_mechanical_tier_falls_through_first_provider_to_second():
    def groq_call_fn(prompt, model, key_value):
        raise RateLimitError("429")

    def openrouter_call_fn(prompt, model, key_value):
        return "openrouter answered"

    groq = KeyedProvider(name="groq", keys=[("key_1", "k1")], call_fn=groq_call_fn)
    openrouter = KeyedProvider(name="openrouter", keys=[("key_1", "k1")], call_fn=openrouter_call_fn)

    adapter = LLMAdapter(
        reasoning_chain=[ProviderStep(groq, "model-a"), ProviderStep(openrouter, "model-b")],
        mechanical_chain=[ProviderStep(groq, "model-c"), ProviderStep(openrouter, "model-d")],
    )
    text, provider = adapter.mechanical_call("prompt")

    assert text == "openrouter answered"
    assert provider == "openrouter"  # Update 03/07: must report who actually answered


def test_total_exhaustion_callback_fires_when_every_provider_in_chain_exhausted():
    fired = []

    def groq_call_fn(prompt, model, key_value):
        raise RateLimitError("429")

    def openrouter_call_fn(prompt, model, key_value):
        raise RateLimitError("429")

    groq = KeyedProvider(name="groq", keys=[("key_1", "k1")], call_fn=groq_call_fn)
    openrouter = KeyedProvider(name="openrouter", keys=[("key_1", "k1")], call_fn=openrouter_call_fn)

    adapter = LLMAdapter(
        reasoning_chain=[ProviderStep(groq, "model-a"), ProviderStep(openrouter, "model-b")],
        mechanical_chain=[ProviderStep(groq, "model-c"), ProviderStep(openrouter, "model-d")],
        on_total_exhaustion=lambda tier: fired.append(tier),
    )

    with pytest.raises(QuotaExhausted):
        adapter.reasoning_call("prompt")

    assert fired == ["reasoning"]


def test_single_step_chain_still_raises_after_its_own_exhaustion():
    """A chain doesn't need OpenRouter/Gemini in it at all -- Groq-only
    (e.g. no OpenRouter keys configured) must still behave like a normal,
    single-provider adapter."""

    def groq_call_fn(prompt, model, key_value):
        raise RateLimitError("429")

    groq = KeyedProvider(name="groq", keys=[("key_1", "k1")], call_fn=groq_call_fn)
    adapter = LLMAdapter(
        reasoning_chain=[ProviderStep(groq, "model-a")],
        mechanical_chain=[ProviderStep(groq, "model-c")],
    )

    with pytest.raises(QuotaExhausted):
        adapter.reasoning_call("prompt")


def test_build_default_llm_adapter_is_groq_first_openrouter_fallback():
    adapter = build_default_llm_adapter(groq_keys=["g1"], cerebras_keys=["c1"], openrouter_keys=["o1"])

    assert [step.provider.name for step in adapter.reasoning_chain] == ["groq", "cerebras", "openrouter"]
    assert [step.provider.name for step in adapter.mechanical_chain] == ["groq", "cerebras", "openrouter"]


def test_build_default_llm_adapter_works_groq_only_with_no_other_keys():
    adapter = build_default_llm_adapter(groq_keys=["g1"], cerebras_keys=None, openrouter_keys=None)

    # cerebras/openrouter steps are still present in the chain (with 0
    # keys), so it's a harmless immediate QuotaExhausted rather than an
    # IndexError/crash.
    assert [step.provider.name for step in adapter.reasoning_chain] == ["groq", "cerebras", "openrouter"]
    assert adapter.reasoning_chain[1].provider.keys == []
    assert adapter.reasoning_chain[2].provider.keys == []


def test_three_provider_chain_falls_through_in_order():
    def groq_call_fn(prompt, model, key_value):
        raise RateLimitError("429")

    def cerebras_call_fn(prompt, model, key_value):
        raise RateLimitError("429")

    def openrouter_call_fn(prompt, model, key_value):
        return "openrouter answered"

    groq = KeyedProvider(name="groq", keys=[("key_1", "k1")], call_fn=groq_call_fn)
    cerebras = KeyedProvider(name="cerebras", keys=[("key_1", "k1")], call_fn=cerebras_call_fn)
    openrouter = KeyedProvider(name="openrouter", keys=[("key_1", "k1")], call_fn=openrouter_call_fn)

    adapter = LLMAdapter(
        reasoning_chain=[
            ProviderStep(groq, "model-a"),
            ProviderStep(cerebras, "model-b"),
            ProviderStep(openrouter, "model-c"),
        ],
        mechanical_chain=[ProviderStep(groq, "model-d")],
    )
    text, provider = adapter.reasoning_call("prompt")

    assert text == "openrouter answered"
    assert provider == "openrouter"
