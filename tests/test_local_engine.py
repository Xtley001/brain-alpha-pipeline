"""
Unit tests for the 3 Local Engine Upgrades:
1. brain_options.core.validator: Strict AST & field whitelist validation.
2. brain_options.specialist.convex_mutator: 5-axis convex surface gradient optimizer.
3. brain_options.store.db: alpha_pnl_cache read/write paths and graceful handling.
"""
from __future__ import annotations

import pytest
from brain_options.core.validator import validate_expression
from brain_options.specialist.convex_mutator import ConvexNearMissMutator
from brain_options.store.db import OptionsDatabase


def test_validator_valid_expressions():
    # 1. Real analyst4 field expression
    expr1 = "group_neutralize(rank((anl4_af_eps_value - anl4_afv4_eps_mean) / (anl4_afv4_dts_spe + 0.001)), subindustry)"
    valid1, reason1 = validate_expression(expr1)
    assert valid1 is True, f"Failed: {reason1}"

    # 2. Real option8 field expression
    expr2 = "group_neutralize(rank(implied_volatility_call_30 - implied_volatility_put_30), subindustry)"
    valid2, reason2 = validate_expression(expr2)
    assert valid2 is True, f"Failed: {reason2}"

    # 3. Real model51 field expression — correct name without _spy suffix
    expr3 = "group_neutralize(-rank(unsystematic_risk_last_60_days), subindustry)"
    valid3, reason3 = validate_expression(expr3)
    assert valid3 is True, f"Failed: {reason3}"


def test_validator_syntax_rejections():
    # Unbalanced parentheses
    v, r = validate_expression("group_neutralize(rank(close), subindustry")
    assert v is False
    assert "Unclosed bracket/parenthesis" in r

    # Mismatched bracket
    v, r = validate_expression("group_neutralize(rank[close), subindustry]")
    assert v is False
    assert "Unbalanced" in r

    # Malformed comma
    v, r = validate_expression("group_neutralize(rank(close),, subindustry)")
    assert v is False
    assert "Malformed comma" in r

    # Direct division by zero
    v, r = validate_expression("group_neutralize(rank(close / 0), subindustry)")
    assert v is False
    assert "division by zero" in r

    # Redundant nested rank
    v, r = validate_expression("group_neutralize(rank(rank(close)), subindustry)")
    assert v is False
    assert "Redundant nested rank" in r

    # Missing group_neutralize or group_rank
    v, r = validate_expression("rank(close) - 0.5")
    assert v is False
    assert "group_neutralize" in r

    # Expression too short
    v, r = validate_expression("short")
    assert v is False
    assert "too short" in r


def test_validator_hallucinated_fields():
    # Reject earnings_surprise
    v, r = validate_expression("group_neutralize(rank(earnings_surprise), subindustry)")
    assert v is False
    assert "earnings_surprise" in r

    # Reject analyst_estimate_dispersion
    v, r = validate_expression("group_neutralize(rank(analyst_estimate_dispersion), subindustry)")
    assert v is False
    assert "analyst_estimate_dispersion" in r

    # Reject wrong field name with _spy suffix for model51 fields
    v, r = validate_expression("group_neutralize(-rank(unsystematic_risk_last_60_days_spy), subindustry)")
    assert v is False, f"Expected rejection of wrong field name but got: {r}"

    # Reject completely made-up unknown token — CRITICAL: strict mode must catch any unknown field
    v, r = validate_expression("group_neutralize(rank(made_up_field_xyz_123), subindustry)")
    assert v is False, f"LOOPHOLE: unknown token passed validation! reason={r}"
    assert "made_up_field_xyz_123" in r

    # Reject idiosyncratic_vol_last_60_days_spy
    v, r = validate_expression("group_neutralize(-rank(idiosyncratic_vol_last_60_days_spy), subindustry)")
    assert v is False


def test_convex_near_miss_mutator_generation():
    mutator = ConvexNearMissMutator()
    base_expr = "group_neutralize(rank(opt_implied_volatility_call_30), subindustry)"
    
    mutations = mutator.generate_convex_sweeps(
        expr=base_expr,
        archetype="IV_Skew_NearMiss",
        hypothesis="IV Skew hypothesis test",
        universe="TOP3000",
        neutralization="SUBINDUSTRY",
        decay=15,
        sharpe=1.12,
        fitness=0.85,
        region="USA",
    )

    assert len(mutations) >= 5
    axes = {m["mutation_axis"] for m in mutations}
    
    # Check that key axes are explored
    assert "decay" in axes
    assert "power" in axes
    assert "universe" in axes
    assert "neutralization" in axes
    assert "liquidity_gate" in axes

    # Verify decay shift ranges
    decay_muts = [m for m in mutations if m["mutation_axis"] == "decay"]
    assert any(m["decay"] != 15 for m in decay_muts)

    # Verify neutralization swap
    neut_muts = [m for m in mutations if m["mutation_axis"] == "neutralization"]
    assert len(neut_muts) == 1
    assert "sector" in neut_muts[0]["expression"]

    # Verify liquidity gate trade_when
    vol_muts = [m for m in mutations if m["mutation_axis"] == "liquidity_gate"]
    assert len(vol_muts) == 1
    assert "trade_when(volume > adv20 * 0.75" in vol_muts[0]["expression"]


def test_db_pnl_cache_offline_graceful():
    # When database_url is None, methods return gracefully without exception
    db = OptionsDatabase(database_url=None)
    
    res = db.save_alpha_pnl("test_alpha_1", {"2024-01-01": 0.01})
    assert res is False

    pnls = db.get_all_cached_alpha_pnls()
    assert pnls == {}
