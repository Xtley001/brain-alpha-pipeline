"""
Unit tests for DiagnosticAlphaOptimizer and RL reward calculation.
"""
from __future__ import annotations

import pytest
from brain_options.core.client import SimMetrics, SimSettings
from brain_options.core.optimizer import DiagnosticAlphaOptimizer, calculate_rl_reward


def test_calculate_rl_reward():
    # 1. Invalid metrics
    m_invalid = SimMetrics(None, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "ERROR", {})
    assert calculate_rl_reward(m_invalid) == -5.0

    # 2. High turnover penalty vs low turnover efficiency
    m_high_to = SimMetrics("A1", sharpe=1.5, fitness=1.0, turnover=0.85, annualized_return=0.08, max_drawdown=0.05, margin=0.001, status="COMPLETE", raw_response={})
    reward_high_to = calculate_rl_reward(m_high_to, is_qualified=False)
    
    m_low_to = SimMetrics("A2", sharpe=1.5, fitness=1.0, turnover=0.12, annualized_return=0.08, max_drawdown=0.05, margin=0.001, status="COMPLETE", raw_response={})
    reward_low_to = calculate_rl_reward(m_low_to, is_qualified=False)
    assert reward_low_to > reward_high_to + 3.0

    # 3. Qualified alpha with completion bonus
    m_qual = SimMetrics("A3", sharpe=1.8, fitness=1.4, turnover=0.12, annualized_return=0.12, max_drawdown=0.04, margin=0.002, status="COMPLETE", raw_response={})
    reward_qual = calculate_rl_reward(m_qual, is_qualified=True)
    assert reward_qual >= 15.0


def test_expression_transformation_operators():
    # 1. Wrap decay linear
    expr1 = "group_neutralize(rank(ts_delta((call_breakeven_20 - close) / close, 5)), subindustry)"
    smoothed1 = DiagnosticAlphaOptimizer.wrap_decay_linear(expr1, window=5)
    assert "ts_decay_linear(ts_delta((call_breakeven_20 - close) / close, 5), 5)" in smoothed1

    # 2. Re-adjust existing decay linear
    expr2 = "group_neutralize(rank(ts_decay_linear(ts_delta((call_breakeven_20 - close) / close, 5), 5)), subindustry)"
    smoothed2 = DiagnosticAlphaOptimizer.wrap_decay_linear(expr2, window=10)
    assert "ts_decay_linear(ts_delta((call_breakeven_20 - close) / close, 5), 12)" in smoothed2

    # 3. Upgrade neutralization
    expr_sector = "group_neutralize(rank(X), sector)"
    upgraded = DiagnosticAlphaOptimizer.upgrade_neutralization(expr_sector, "subindustry")
    assert upgraded == "group_neutralize(rank(X), subindustry)"

    # 4. Inject volume gating
    expr_raw = "group_neutralize(rank(X), subindustry)"
    gated = DiagnosticAlphaOptimizer.inject_volume_gating(expr_raw)
    assert gated == "trade_when(volume > adv20, group_neutralize(rank(X), subindustry), -1)"
    # Idempotent
    assert DiagnosticAlphaOptimizer.inject_volume_gating(gated) == gated

    # 5. Shift tenor
    expr_10 = "group_neutralize(rank((call_breakeven_10 - close) / close), subindustry)"
    shifted = DiagnosticAlphaOptimizer.shift_tenor(expr_10)
    assert "call_breakeven_20" in shifted

    # 6. Adjust delta window
    expr_delta = "group_neutralize(rank(ts_delta(X, 3)), subindustry)"
    adjusted_delta = DiagnosticAlphaOptimizer.adjust_delta_window(expr_delta, target_window=20)
    assert "ts_delta(X, 20)" in adjusted_delta

    # 7. Wrap exponential decay (maps to deep linear decay in FastExpr)
    expr_exp = "group_neutralize(rank(ts_decay_linear(X, 8)), subindustry)"
    wrapped_exp = DiagnosticAlphaOptimizer.wrap_decay_exp(expr_exp, window=15, factor=0.25)
    assert "ts_decay_linear(X, 15)" in wrapped_exp

    # 8. Wrap Z-score
    expr_zs = "group_neutralize(rank(ts_delta(X, 5)), subindustry)"
    wrapped_zs = DiagnosticAlphaOptimizer.wrap_zscore(expr_zs, window=20)
    assert "ts_zscore(X, 20)" in wrapped_zs

    # 9. Inject conviction gating with default 0.38 threshold and update to 0.42
    expr_conv = "group_neutralize(rank(ts_decay_linear(X, 8)), subindustry)"
    gated_conv = DiagnosticAlphaOptimizer.inject_conviction_gate(expr_conv, threshold=0.38)
    assert "trade_when(abs(rank(ts_decay_linear(X, 8)) - 0.5) > 0.38," in gated_conv
    assert ", -1)" in gated_conv

    # Update existing threshold specifically without corrupting other inequalities
    expr_multi = "trade_when((opt_vol > 0.20) && (abs(rank(X) - 0.5) > 0.35), X, -1)"
    updated_multi = DiagnosticAlphaOptimizer.inject_conviction_gate(expr_multi, threshold=0.42)
    assert "opt_vol > 0.20" in updated_multi
    assert "abs(rank(X) - 0.5) > 0.42" in updated_multi

    # 10. Volume gating combined with existing trade_when condition
    gated_tw = DiagnosticAlphaOptimizer.inject_volume_gating(gated_conv)
    assert "trade_when((volume > adv20) && (abs(rank(ts_decay_linear(X, 8)) - 0.5) > 0.38)," in gated_tw

    # 11. Neutralization upgrade on un-neutralized and case-insensitive expressions
    expr_none = "ts_zscore(X, 10)"
    upgraded_none = DiagnosticAlphaOptimizer.upgrade_neutralization(expr_none, "subindustry")
    assert upgraded_none == "group_neutralize(rank(ts_zscore(X, 10)), subindustry)"

    expr_cap = "group_neutralize(rank(X), SECTOR)"
    upgraded_cap = DiagnosticAlphaOptimizer.upgrade_neutralization(expr_cap, "subindustry")
    assert upgraded_cap == "group_neutralize(rank(X), subindustry)"


def test_stage_reward_functions():
    from brain_options.core.optimizer import (
        _stage0_validity_reward,
        _stage1_hurdle_reward,
        _stage2_efficiency_reward,
        calculate_rl_reward,
    )
    m = SimMetrics(
        "A1",
        sharpe=1.6,
        fitness=1.2,
        turnover=0.10,
        annualized_return=0.10,
        max_drawdown=0.04,
        status="COMPLETE",
        raw_response={
            "is": {
                "checks": [
                    {"name": "LOW_SUB_UNIVERSE_SHARPE", "result": "FAIL"},
                ]
            }
        },
    )
    s0 = _stage0_validity_reward(m)
    s1 = _stage1_hurdle_reward(m)
    s2 = _stage2_efficiency_reward(m)

    assert s0 == -8.0
    # base: 1.6 + 2.5 * min(1.2, 3.0) = 1.6 + 3.0 = 4.6
    # fitness >= 1.0 (+2.0), sharpe >= 1.25 (+2.0) -> s1 = 8.6
    assert round(s1, 4) == 8.6
    # turnover=0.10 in [0.04, 0.18] and sharpe >= 1.0 -> +1.5 -> s2 = 1.5
    assert round(s2, 4) == 1.5

    assert calculate_rl_reward(m, is_qualified=False) == round(s0 + s1 + s2, 4)
    assert calculate_rl_reward(m, is_qualified=True) == round(s0 + s1 + s2 + 10.0, 4)


def test_record_learning_memory_with_reward_breakdown():
    from brain_options.specialist.templates import OptionCandidate
    from brain_options.store.store import OptionsStore
    from unittest.mock import MagicMock

    mock_db = MagicMock()
    store = OptionsStore(database_url=None)
    store.db = mock_db

    candidate = OptionCandidate(
        expression="group_neutralize(rank(implied_volatility_mean_skew_20), subindustry)",
        archetype_name="volatility_skew",
        hypothesis="test",
        generation_source="test",
    )
    metrics = SimMetrics("A1", sharpe=1.5, fitness=1.2, turnover=0.10, status="COMPLETE")
    breakdown = {"stage0": 0.0, "stage1": 8.5, "stage2": 1.5, "completion": 10.0}

    store.record_learning_memory(
        candidate=candidate,
        metrics=metrics,
        reward=20.0,
        reward_breakdown=breakdown,
    )
    mock_db.record_learning_memory.assert_called_once_with(
        candidate,
        metrics,
        20.0,
        0,
        None,
        None,
        "EVALUATED",
        reward_breakdown=breakdown,
    )

