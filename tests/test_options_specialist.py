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
        assert cand.expression
        assert cand.archetype_name
        assert "close" in cand.expression or "implied" in cand.expression or "pcr" in cand.expression


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
