import json

from pipeline.generator.llm_generator import mutate_candidate, propose_new_ideas


class _FakeAdapter:
    """Stands in for LLMAdapter -- reasoning_call/mechanical_call return
    (text, provider) tuples, matching the real adapter's Update 03 contract."""

    def __init__(self, reasoning_response=None, mechanical_response=None):
        self._reasoning_response = reasoning_response
        self._mechanical_response = mechanical_response

    def reasoning_call(self, prompt):
        return self._reasoning_response

    def mechanical_call(self, prompt):
        return self._mechanical_response


_SAMPLE_ITEMS = json.dumps([{"expression": "rank(close)", "category": "test"}])


def test_propose_new_ideas_records_provider_that_actually_answered_gemini():
    adapter = _FakeAdapter(reasoning_response=(_SAMPLE_ITEMS, "gemini"))
    ideas = propose_new_ideas(adapter, "pool summary", "failure log", n=1)
    assert len(ideas) == 1
    # Update 10 Item 3: generation_tier is now a single fixed 'llm' value
    # for every LLM-sourced candidate regardless of provider -- the actual
    # provider is recorded separately in 'provider'.
    assert ideas[0]["generation_tier"] == "llm"
    assert ideas[0]["provider"] == "gemini"


def test_propose_new_ideas_records_provider_that_actually_answered_groq():
    """Update 03's original bug: this used to be hardcoded to 'llm_gemini'
    regardless of which provider really answered. Update 10 Item 3 fixes
    the *tier* side of that same class of bug: whichever provider answers,
    generation_tier stays 'llm' and the real provider lands in `provider`
    -- there is no per-provider tier string left to drift out of sync."""
    adapter = _FakeAdapter(reasoning_response=(_SAMPLE_ITEMS, "groq"))
    ideas = propose_new_ideas(adapter, "pool summary", "failure log", n=1)
    assert len(ideas) == 1
    assert ideas[0]["generation_tier"] == "llm"
    assert ideas[0]["provider"] == "groq"


def test_mutate_candidate_records_provider_that_actually_answered_groq():
    adapter = _FakeAdapter(mechanical_response=(_SAMPLE_ITEMS, "groq"))
    mutations = mutate_candidate(adapter, "rank(close)", "test_category", n=1)
    assert len(mutations) == 1
    assert mutations[0]["generation_tier"] == "llm"
    assert mutations[0]["provider"] == "groq"


def test_mutate_candidate_records_provider_that_actually_answered_gemini():
    adapter = _FakeAdapter(mechanical_response=(_SAMPLE_ITEMS, "gemini"))
    mutations = mutate_candidate(adapter, "rank(close)", "test_category", n=1)
    assert len(mutations) == 1
    assert mutations[0]["generation_tier"] == "llm"
    assert mutations[0]["provider"] == "gemini"


def test_propose_new_ideas_from_cerebras_or_openrouter_is_not_dedup_blind():
    """Update 10 Item 3 regression test -- the exact bug this item fixes.

    Before the fix, a candidate whose winning provider was 'cerebras' or
    'openrouter' (anything other than the two hardcoded in the old
    _PROVIDER_TO_TIER map) got tagged 'llm_cerebras'/'llm_openrouter', and
    Repo.recent_llm_expressions()'s hardcoded
    `WHERE generation_tier IN ('llm_gemini','llm_groq')` never matched
    those tags -- the dedup/anti-duplication check silently never saw
    roughly two-thirds of real LLM-generated candidates while still
    running and returning rows for the other third.

    This test must fail against the pre-fix code (where
    ideas[0]["generation_tier"] would be 'llm_cerebras', which the old
    hardcoded IN-list does not match) and pass after the fix (a single
    'llm' tier value that recent_llm_expressions()'s
    `WHERE generation_tier = 'llm'` always matches, for any provider)."""
    for provider in ("cerebras", "openrouter"):
        adapter = _FakeAdapter(reasoning_response=(_SAMPLE_ITEMS, provider))
        ideas = propose_new_ideas(adapter, "pool summary", "failure log", n=1)
        assert len(ideas) == 1
        assert ideas[0]["generation_tier"] == "llm", (
            f"provider={provider!r} produced generation_tier="
            f"{ideas[0]['generation_tier']!r}, which recent_llm_expressions()'s "
            f"`WHERE generation_tier = 'llm'` would not match -- dedup blind spot reproduced"
        )
        assert ideas[0]["provider"] == provider


def test_mutate_candidate_uses_given_category_as_default():
    items_without_category = json.dumps([{"expression": "rank(close)"}])
    adapter = _FakeAdapter(mechanical_response=(items_without_category, "groq"))
    mutations = mutate_candidate(adapter, "rank(close)", "original_category", n=1)
    assert mutations[0]["category"] == "original_category"
