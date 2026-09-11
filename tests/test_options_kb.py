"""
Tests for OptionsKnowledgeBase parser and retrieval.
"""
from __future__ import annotations

import pytest
from brain_options.specialist.kb import OptionsKnowledgeBase


def test_kb_loading_and_parsing():
    kb = OptionsKnowledgeBase()
    assert len(kb.cards) > 20, f"Expected at least 20 cards, found {len(kb.cards)}"
    assert len(kb.high_confidence_themes) >= 5, f"Expected >=5 high-confidence themes, found {len(kb.high_confidence_themes)}"


def test_kb_archetype_queries():
    kb = OptionsKnowledgeBase()
    skew_cards = kb.get_cards_for_archetype("skew", max_cards=3)
    assert len(skew_cards) > 0
    assert any("sqrt" in c.idea.lower() or "skew" in c.title.lower() for c in skew_cards)

    term_cards = kb.get_cards_for_archetype("term_structure", max_cards=3)
    assert len(term_cards) > 0

    basis_cards = kb.get_cards_for_archetype("forward_basis", max_cards=3)
    assert len(basis_cards) > 0


def test_kb_corroborated_cards():
    kb = OptionsKnowledgeBase()
    corroborated = kb.get_corroborated_cards()
    assert len(corroborated) >= 3
    for c in corroborated:
        assert c.is_corroborated


def test_kb_format_for_prompt():
    kb = OptionsKnowledgeBase()
    cards = kb.get_cards_for_archetype("skew", max_cards=2)
    prompt_text = kb.format_cards_for_prompt(cards)
    assert "Principle:" in prompt_text
    assert "Heuristic:" in prompt_text
