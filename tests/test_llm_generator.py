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


def test_propose_new_ideas_labels_gemini_when_gemini_answered():
    adapter = _FakeAdapter(reasoning_response=(_SAMPLE_ITEMS, "gemini"))
    ideas = propose_new_ideas(adapter, "pool summary", "failure log", n=1)
    assert len(ideas) == 1
    assert ideas[0]["generation_tier"] == "llm_gemini"


def test_propose_new_ideas_labels_groq_when_gemini_was_exhausted_and_groq_answered():
    """Update 03's actual bug: this used to be hardcoded to 'llm_gemini'
    regardless of which provider really answered, silently corrupting the
    generated-by-tier breakdown the heartbeat reports."""
    adapter = _FakeAdapter(reasoning_response=(_SAMPLE_ITEMS, "groq"))
    ideas = propose_new_ideas(adapter, "pool summary", "failure log", n=1)
    assert len(ideas) == 1
    assert ideas[0]["generation_tier"] == "llm_groq"


def test_mutate_candidate_labels_groq_when_groq_answered():
    adapter = _FakeAdapter(mechanical_response=(_SAMPLE_ITEMS, "groq"))
    mutations = mutate_candidate(adapter, "rank(close)", "test_category", n=1)
    assert len(mutations) == 1
    assert mutations[0]["generation_tier"] == "llm_groq"


def test_mutate_candidate_labels_gemini_when_groq_was_exhausted_and_gemini_answered():
    adapter = _FakeAdapter(mechanical_response=(_SAMPLE_ITEMS, "gemini"))
    mutations = mutate_candidate(adapter, "rank(close)", "test_category", n=1)
    assert len(mutations) == 1
    assert mutations[0]["generation_tier"] == "llm_gemini"


def test_mutate_candidate_uses_given_category_as_default():
    items_without_category = json.dumps([{"expression": "rank(close)"}])
    adapter = _FakeAdapter(mechanical_response=(items_without_category, "groq"))
    mutations = mutate_candidate(adapter, "rank(close)", "original_category", n=1)
    assert mutations[0]["category"] == "original_category"
