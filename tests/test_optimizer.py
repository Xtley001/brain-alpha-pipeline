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

    # 2. High turnover penalty
    m_high_to = SimMetrics("A1", sharpe=1.5, fitness=1.0, turnover=0.85, annualized_return=0.08, max_drawdown=0.05, margin=0.001, status="COMPLETE", raw_response={})
    reward_high_to = calculate_rl_reward(m_high_to, is_qualified=False)
    # Sharpe(1.5) + 1.5*Fitness(1.0) - 3.0*(0.85 - 0.70) = 3.0 - 0.45 = 2.55
    assert reward_high_to < 3.0

    # 3. Qualified alpha with completion bonus
    m_qual = SimMetrics("A2", sharpe=1.8, fitness=1.4, turnover=0.22, annualized_return=0.12, max_drawdown=0.04, margin=0.002, status="COMPLETE", raw_response={})
    reward_qual = calculate_rl_reward(m_qual, is_qualified=True)
    # Sharpe(1.8) + 1.5*Fitness(1.4) + 5.0 bonus = 1.8 + 2.1 + 5.0 = 8.9
    assert reward_qual >= 8.5


def test_expression_transformation_operators():
    # 1. Wrap decay linear
    expr1 = "group_neutralize(rank(ts_delta((call_breakeven_20 - close) / close, 5)), subindustry)"
    smoothed1 = DiagnosticAlphaOptimizer.wrap_decay_linear(expr1, window=5)
    assert "ts_decay_linear(ts_delta((call_breakeven_20 - close) / close, 5), 5)" in smoothed1

    # 2. Re-adjust existing decay linear
    expr2 = "group_neutralize(rank(ts_decay_linear(ts_delta((call_breakeven_20 - close) / close, 5), 5)), subindustry)"
    smoothed2 = DiagnosticAlphaOptimizer.wrap_decay_linear(expr2, window=10)
    assert "ts_decay_linear(ts_delta((call_breakeven_20 - close) / close, 5), 10)" in smoothed2

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

    # 7. Wrap exponential decay
    expr_exp = "group_neutralize(rank(ts_decay_linear(X, 8)), subindustry)"
    wrapped_exp = DiagnosticAlphaOptimizer.wrap_decay_exp(expr_exp, window=10, factor=0.25)
    assert "ts_decay_exp_window(X, 8, 0.25)" in wrapped_exp

    # 8. Wrap Z-score
    expr_zs = "group_neutralize(rank(ts_delta(X, 5)), subindustry)"
    wrapped_zs = DiagnosticAlphaOptimizer.wrap_zscore(expr_zs, window=20)
    assert "ts_zscore(X, 20)" in wrapped_zs

    # 9. Inject conviction gating
    expr_conv = "group_neutralize(rank(ts_decay_linear(X, 8)), subindustry)"
    gated_conv = DiagnosticAlphaOptimizer.inject_conviction_gate(expr_conv, threshold=0.15)
    assert "trade_when(abs(rank(ts_decay_linear(X, 8)) - 0.5) > 0.15," in gated_conv
    assert ", -1)" in gated_conv
