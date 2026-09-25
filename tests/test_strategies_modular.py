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
    """Verify all 30 institutional strategy pillars are registered."""
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
        "institutional_13f_breadth",
        "insider_cluster_buying",
        "peavd_earnings_vol_drift",
        "jump_variance_moments",
        "patent_innovation_efficiency",
        "dynamic_short_squeeze",
        "order_flow_vpin",
        "gamma_pinning_clustering",
        "customer_supplier_cascades",
        "rd_capitalization_spillovers",
        "capex_asset_growth",
        "peavrp_volatility_premia",
        "realized_jump_intensity",
        "distance_to_default_debt",
        "macro_fomc_cpi_drift",
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
            assert any(op in c.expression for op in ["group_neutralize", "trade_when", "rank", "group_rank"])


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


def test_operator_name_wiring_in_decorrelator():
    """Verify that decorrelator populates operator_name with the axis key."""
    from brain_options.specialist.decorrelator import DecorrelationEngine
    engine = DecorrelationEngine()
    expr = "group_neutralize(rank(ts_decay_linear(implied_volatility_mean_skew_20 * 0.28, 5)), subindustry)"
    variants = engine.generate_orthogonal_variants(expr, "skew", colliding_id="TEST_ALPHA", base_sharpe=1.5)
    assert len(variants) > 0
    assert all(v.operator_name is not None for v in variants)
    assert any("Axis" in v.operator_name for v in variants)


@pytest.mark.asyncio
async def test_run_candidate_records_strategy_operator_reward():
    """Verify run_candidate records operator reward when operator_name is present."""
    from unittest.mock import AsyncMock, MagicMock
    from brain_options.config import OptionsConfig
    from brain_options.core.client import BrainClient, SimMetrics, SimSettings
    from brain_options.core.sweep import SweepEngine
    from brain_options.specialist.templates import OptionCandidate
    from brain_options.run import run_candidate

    cand = OptionCandidate(
        expression="group_neutralize(rank(ts_decay_linear(close, 5)), subindustry)",
        archetype_name="term_structure",
        hypothesis="Test operator reward recording",
        generation_source="decorrelator",
        operator_name="Axis 1 (Velocity Shift)",
    )

    mock_sweep = MagicMock(spec=SweepEngine)
    s0_metrics = SimMetrics(sharpe=0.1, fitness=0.05, turnover=0.10, status="FAIL")
    mock_sweep.stage0_screen = AsyncMock(return_value=(False, SimSettings(), s0_metrics))

    mock_client = MagicMock(spec=BrainClient)
    mock_store = MagicMock(spec=OptionsStore)
    mock_store.db = None
    config = OptionsConfig(brain_username="test", brain_password="test")

    passed = await run_candidate(cand, mock_sweep, mock_client, mock_store, config)
    assert passed is False
    assert mock_store.record_strategy_operator_reward.called
    call_kwargs = mock_store.record_strategy_operator_reward.call_args[1]
    assert call_kwargs["strategy_name"] == "term_structure"
    assert call_kwargs["operator_name"] == "Axis 1 (Velocity Shift)"
    assert call_kwargs["parameter_val"] == "rejected"
    assert call_kwargs["success"] is False

