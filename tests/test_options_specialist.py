"""
Unit tests for brain_options.specialist.
"""
from __future__ import annotations

import pytest
from brain_options.specialist.catalog import OptionsCatalog
from brain_options.specialist.archetypes import ARCHETYPES
from brain_options.specialist.templates import generate_template_candidates
from brain_options.specialist.generator import OptionsGenerator
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
    assert len(ARCHETYPES) >= 5
    templates = generate_template_candidates()
    assert len(templates) >= 20
    for cand in templates:
        assert cand.expression
        assert cand.archetype_name
        assert "close" in cand.expression or "implied" in cand.expression or "pcr" in cand.expression


def test_generator_batch():
    config = OptionsConfig.from_env()
    adapter = LLMAdapter(config)
    generator = OptionsGenerator(adapter)

    batch = generator.get_template_batch(5)
    assert len(batch) == 5
    for c in batch:
        assert c.generation_source == "template"
