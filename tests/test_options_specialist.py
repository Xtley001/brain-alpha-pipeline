"""
Unit tests for brain_options.specialist with Master Books 1-4 Knowledge Base.
"""
from __future__ import annotations

import pytest
from brain_options.specialist.catalog import OptionsCatalog
from brain_options.specialist.archetypes import ARCHETYPES
from brain_options.specialist.templates import OptionCandidate, generate_template_candidates
from brain_options.specialist.generator import OptionsGenerator
from brain_options.specialist.kb import OptionsKnowledgeBase
from brain_options.config import OptionsConfig
from brain_options.llm.adapter import LLMAdapter


def test_options_catalog():
    catalog = OptionsCatalog()
    assert len(catalog.fields) == 138
    assert len(catalog.pcr_vol_fields) > 0
    assert len(catalog.pcr_oi_fields) > 0
    assert len(catalog.skew_fields) > 0
    assert len(catalog.atm_iv_fields) > 0
    assert len(catalog.forward_price_fields) > 0
    assert len(catalog.call_breakeven_fields) > 0


def test_archetypes_and_templates():
    assert len(ARCHETYPES) >= 10
    high_conf = [a for a in ARCHETYPES if a.is_high_confidence]
    assert len(high_conf) >= 4

    templates = generate_template_candidates()
    assert len(templates) >= 25

    # Verify high-confidence formulas exist in templates
    assert any("sqrt" in cand.expression for cand in templates)
    assert any("16.53" in cand.expression for cand in templates)  # Jensen-debiased
    assert any("0.75" in cand.expression for cand in templates)   # Sinclair optimal entry

    for cand in templates:
        valid_tokens = ["close", "implied", "pcr", "est_eps", "short", "borrow", "target"]
        assert any(token in cand.expression for token in valid_tokens)


def test_generator_multi_tier(monkeypatch):
    config = OptionsConfig.from_env()
    adapter = LLMAdapter(config)
    kb = OptionsKnowledgeBase()
    catalog = OptionsCatalog()
    generator = OptionsGenerator(adapter, kb=kb, catalog=catalog)

    # 1. Template batch
    batch = generator.get_template_batch(5)
    assert len(batch) == 5
    for c in batch:
        assert c.generation_source == "template"

    # 2. Mock LLM adapter for reasoning and mutation tiers
    mock_reasoning_json = '[{"expression": "group_neutralize(rank(-ts_delta(implied_volatility_mean_skew_30 * 0.345, 5)), sector)", "archetype": "Skew", "hypothesis": "Sqrt-T normalized skew"}]'
    mock_mutation_json = '[{"expression": "group_neutralize(rank(-ts_decay_linear(implied_volatility_mean_skew_30 * 0.345, 5)), subindustry)", "archetype": "Mutation", "hypothesis": "Smoothed version"}]'

    monkeypatch.setattr(adapter, "generate", lambda prompt, system_prompt, temperature=0.7: mock_reasoning_json)

    reasoning_batch = generator.get_reasoning_batch(count=1, archetype="skew")
    assert len(reasoning_batch) == 1
    assert reasoning_batch[0].generation_source == "llm_reasoning"
    assert "implied_volatility_mean_skew_30" in reasoning_batch[0].expression

    # 3. Mutation batch
    monkeypatch.setattr(adapter, "generate", lambda prompt, system_prompt, temperature=0.6: mock_mutation_json)
    seed = reasoning_batch[0]
    mutation_batch = generator.get_mutation_batch([seed], count_per_base=1)
    assert len(mutation_batch) == 1
    assert mutation_batch[0].generation_source == "llm_mechanical"
    assert "subindustry" in mutation_batch[0].expression


def test_clean_json_array_resilience():
    from brain_options.llm.adapter import clean_json_array

    # 1. Preamble and markdown fences
    text1 = """Here are the requested candidates:
```json
[
  {"expression": "alpha_1", "archetype": "skew", "hypothesis": "hyp 1"},
  {"expression": "alpha_2", "archetype": "skew", "hypothesis": "hyp 2"}
]
```
Let me know if you need more."""
    res1 = clean_json_array(text1)
    assert len(res1) == 2
    assert res1[0]["expression"] == "alpha_1"
    assert res1[1]["expression"] == "alpha_2"

    # 2. Trailing commas before closing brackets
    text2 = '[{"expression": "alpha_trail", "archetype": "term", "hypothesis": "hyp",}, ]'
    res2 = clean_json_array(text2)
    assert len(res2) == 1
    assert res2[0]["expression"] == "alpha_trail"

    # 3. Truncated output (cut off mid-stream) - must recover all complete items!
    text3 = """[
  {"expression": "alpha_complete_1", "archetype": "skew", "hypothesis": "hyp 1"},
  {"expression": "alpha_complete_2", "archetype": "basis", "hypothesis": "hyp 2"},
  {"expression": "alpha_truncated", "archetype": "skew", "hypoth"""
    res3 = clean_json_array(text3)
    assert len(res3) == 2
    assert res3[0]["expression"] == "alpha_complete_1"
    assert res3[1]["expression"] == "alpha_complete_2"


def test_generator_procedural_fallback_when_templates_and_llm_exhausted(monkeypatch):
    """Verifies that when all seed templates and LLM calls return 0, the pipeline never starves."""
    config = OptionsConfig.from_env()
    adapter = LLMAdapter(config)
    generator = OptionsGenerator(adapter)

    # 1. Mark all existing templates as already evaluated
    all_templates = generate_template_candidates()
    for t in all_templates:
        generator.mark_evaluated(t.expression)

    # 2. Simulate LLM failure (returns None)
    monkeypatch.setattr(adapter, "generate", lambda *args, **kwargs: None)

    # 3. Request a batch of 15 candidates
    batch = generator.get_next_batch(target_count=15)
    assert len(batch) == 15

    # 4. Verify all generated candidates are fresh and procedural
    for c in batch:
        assert c.generation_source == "procedural"
        assert c.expression not in [t.expression for t in all_templates]
        assert "group_neutralize" in c.expression or "trade_when" in c.expression


def test_llm_adapter_gemini_fallback(monkeypatch):
    """Verifies that _call_gemini cleanly falls back to OpenAI-compatible endpoint without crashing."""
    config = OptionsConfig(brain_username="u", brain_password="p", gemini_keys=["test_gemini_key"])
    adapter = LLMAdapter(config)

    # Mock _call_openai_compatible to simulate Gemini's OpenAI-compatible response
    mock_called = []
    def mock_openai_call(base_url, api_key, model, prompt, system_prompt, temperature=0.7):
        mock_called.append((base_url, api_key, model))
        return '[{"expression": "alpha_gemini", "archetype": "skew", "hypothesis": "gemini test"}]'

    monkeypatch.setattr(adapter, "_call_openai_compatible", mock_openai_call)
    res = adapter._call_gemini("test_key", "gemini-2.0-flash", "test prompt", "system prompt")
    assert res is not None
    assert len(mock_called) == 1
    assert "generativelanguage.googleapis.com" in mock_called[0][0]
    assert mock_called[0][1] == "test_key"
    assert mock_called[0][2] == "gemini-2.0-flash"


