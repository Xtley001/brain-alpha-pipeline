"""
Unit tests for multi-category expansion:
- brain_sentiment
- brain_risk_model
- brain_synthesis
"""
from __future__ import annotations

import pytest
from brain_sentiment.specialist.generator import SentimentGenerator
from brain_sentiment.specialist.kb import SentimentKnowledgeBase
from brain_sentiment.strategies import SENTIMENT_STRATEGY_REGISTRY, generate_modular_candidates as gen_sent_candidates

from brain_risk_model.specialist.generator import RiskModelGenerator
from brain_risk_model.specialist.kb import RiskModelKnowledgeBase
from brain_risk_model.strategies import RISK_STRATEGY_REGISTRY, generate_modular_candidates as gen_risk_candidates

from brain_synthesis import generate_apex_candidates


def test_sentiment_knowledge_base():
    kb = SentimentKnowledgeBase()
    assert len(kb.cards) >= 6
    assert kb.get_card("pead_earnings_drift") is not None
    assert "Chan" in kb.get_card("pead_earnings_drift").papers[0]


def test_sentiment_generator_and_strategies():
    assert len(SENTIMENT_STRATEGY_REGISTRY) >= 6
    candidates = gen_sent_candidates()
    assert len(candidates) > 0

    sg = SentimentGenerator()
    c = sg.generate_candidate()
    assert c.category == "sentiment"
    assert "group_neutralize(" in c.expression
    assert "subindustry" in c.expression.lower() or "sector" in c.expression.lower()


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
    for ac in apex_candidates:
        assert ac.category == "hybrid_tri_factor"
        assert "group_neutralize(" in ac.expression
        assert "rank(" in ac.expression
