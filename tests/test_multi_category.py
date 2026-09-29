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


def test_generator_dynamic_rl_weights():
    class MockDB:
        def get_empirical_archetype_weights(self, archetypes, base_priors, temperature=8.0):
            # Dynamic weights mock favoring the first archetype
            w = {a: 0.1 for a in archetypes}
            w[archetypes[0]] = 0.5
            total = sum(w.values())
            return {k: v / total for k, v in w.items()}

    mock_db = MockDB()
    sg = SentimentGenerator(db=mock_db)
    s_weights = sg.get_current_weights()
    assert len(s_weights) == len(sg.archetype_priors)
    assert abs(sum(s_weights.values()) - 1.0) < 1e-4
    assert s_weights[list(sg.archetype_priors.keys())[0]] > 0.3

    rg = RiskModelGenerator(db=mock_db)
    r_weights = rg.get_current_weights()
    assert len(r_weights) == len(rg.archetype_priors)
    assert abs(sum(r_weights.values()) - 1.0) < 1e-4
    assert r_weights[list(rg.archetype_priors.keys())[0]] > 0.3


def test_options_db_offline_fallback():
    from brain_options.store.db import OptionsDatabase
    db = OptionsDatabase(database_url=None)
    res = db.distill_learning_memory()
    assert res["status"] == "no_db"
    assert res["pruned"] == 0

    priors = {"arch_a": 0.6, "arch_b": 0.4}
    weights = db.get_empirical_archetype_weights(list(priors.keys()), priors)
    assert weights == priors

