"""
Unit tests for multi-category expansion:
- brain_risk_model (Model - Value Score 7.0)
- brain_options (Option - Value Score 6.0)
- brain_synthesis (Top 3 Cross-Category Synthesis)
"""
from __future__ import annotations

import pytest
from brain_risk_model.specialist.generator import RiskModelGenerator
from brain_risk_model.specialist.kb import RiskModelKnowledgeBase
from brain_risk_model.strategies import RISK_STRATEGY_REGISTRY, generate_modular_candidates as gen_risk_candidates

from brain_options.specialist.kb import OptionsKnowledgeBase
from brain_options.specialist.templates import generate_template_candidates as gen_options_candidates

from brain_synthesis import generate_apex_candidates


def test_options_knowledge_base():
    kb = OptionsKnowledgeBase()
    assert len(kb.cards) > 20
    skew_cards = kb.get_cards_for_archetype("skew", max_cards=2)
    assert len(skew_cards) > 0


def test_options_generator_and_strategies():
    candidates = gen_options_candidates()
    assert len(candidates) > 0
    sample = candidates[0]
    assert sample.archetype_name is not None
    assert "group_neutralize(" in sample.expression or "trade_when(" in sample.expression


def test_risk_model_knowledge_base():
    kb = RiskModelKnowledgeBase()
    assert len(kb.cards) >= 6
    assert kb.get_card("betting_against_beta") is not None
    assert "Frazzini" in kb.get_card("betting_against_beta").papers[0]


def test_risk_model_generator_and_strategies():
    assert len(RISK_STRATEGY_REGISTRY) >= 6
    candidates = gen_risk_candidates()
    assert len(candidates) > 0

    rg = RiskModelGenerator()
    c = rg.generate_candidate()
    assert c.category == "model"
    assert "group_neutralize(" in c.expression


def test_apex_cross_category_synthesis():
    apex_candidates = generate_apex_candidates()
    assert len(apex_candidates) >= 30

    sample = apex_candidates[0]
    assert sample.category == "top3_tri_factor"
    assert sample.value_score >= 6.0
    assert "group_neutralize(" in sample.expression
    assert "subindustry" in sample.expression.lower() or "sector" in sample.expression.lower()


def test_analyst_revision_candidates():
    from brain_generators.analyst.analyst_revision_generator import generate_analyst_revision_candidates
    candidates = generate_analyst_revision_candidates()
    assert len(candidates) >= 150
    sample = candidates[0]
    assert sample["category"] == "analyst"
    assert "group_neutralize(" in sample["expression"]
    assert "anl4_" in sample["expression"]
    assert sample["decay"] in (8, 10, 12, 15, 20, 25)

