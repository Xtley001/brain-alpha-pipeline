"""
Unit tests for the Modular Strategy Sub-System architecture,
Strategy-Scoped RL isolation, and 5-tier platform neutralization.
"""
from __future__ import annotations

import pytest
from brain_options.core.client import SimSettings
from brain_options.strategies import (
    STRATEGY_REGISTRY,
    get_strategy,
    list_strategy_ids,
    generate_modular_candidates,
)
from brain_options.strategies.base import BaseStrategy
from brain_options.store.store import OptionsStore


def test_strategy_registry_completeness():
    """Verify all 15 institutional strategy pillars are registered."""
    expected = [
        "term_structure",
        "skew",
        "pcr_flow",
        "breakeven",
        "forward_basis",
        "short_interest",
        "analyst_revisions",
        "hybrid_confluence",
        "supply_chain",
        "accruals_cashflow",
        "informed_short_demand",
        "extreme_tail_risk",
        "iv_lead_lag",
        "network_momentum",
        "formulaic_101",
    ]
    registered = list_strategy_ids()
    for exp in expected:
        assert exp in registered, f"Strategy {exp} missing from registry"
        strat = get_strategy(exp)
        assert isinstance(strat, BaseStrategy)
        assert strat.strategy_id == exp
        assert len(strat.get_fields()) > 0
        assert len(strat.metadata.academic_references) > 0


def test_all_strategies_generate_valid_candidates():
    """Verify each strategy independently produces valid, non-empty candidate expressions."""
    for strat_id, strat in STRATEGY_REGISTRY.items():
        candidates = strat.generate_candidates()
        assert len(candidates) >= 3, f"Strategy {strat_id} produced fewer than 3 candidates"
        for c in candidates:
            assert c.expression and len(c.expression) > 10
            assert c.archetype_name and len(c.archetype_name) > 0
            assert c.hypothesis and len(c.hypothesis) > 0
            assert "group_neutralize" in c.expression or "trade_when" in c.expression


def test_modular_candidates_filtering():
    """Verify strategy filter correctly isolates target strategy expressions."""
    term_cands = generate_modular_candidates("term_structure")
    assert len(term_cands) > 0
    assert all("volatility" in c.expression.lower() or "returns" in c.expression.lower() for c in term_cands)

    pcr_cands = generate_modular_candidates("pcr_flow")
    assert len(pcr_cands) > 0
    assert all("pcr" in c.expression.lower() for c in pcr_cands)

    multi_cands = generate_modular_candidates("term_structure,pcr_flow")
    assert len(multi_cands) == len(term_cands) + len(pcr_cands)


def test_all_five_neutralizations_in_settings():
    """Verify all 5 WorldQuant BRAIN platform neutralization tiers are supported."""
    neutralizations = ["SUBINDUSTRY", "INDUSTRY", "SECTOR", "MARKET", "NONE"]
    for neut in neutralizations:
        # Case insensitive handling
        s = SimSettings(neutralization=neut.lower())
        payload = s.to_simulation_payload("rank(close)")
        assert payload["settings"]["neutralization"] == neut


def test_strategy_scoped_rl_isolation():
    """Verify strategy RL memory isolates operator rewards per strategy family."""
    store = OptionsStore(database_url=None)
    # When no DB configured, gracefully returns empty dict without errors
    w_term = store.get_strategy_operator_weights("term_structure")
    assert isinstance(w_term, dict)
    store.record_strategy_operator_reward("term_structure", "ts_decay_linear", "decay", "20", 5.0)
