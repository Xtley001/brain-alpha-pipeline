"""
Unit tests for brain_options.core filter and correlation logic.
"""
from __future__ import annotations

import pytest
from brain_options.config import OptionsConfig
from brain_options.core.client import SimMetrics
from brain_options.core.filter import compute_sharpe_sampling_error, evaluate_alpha_metrics
from brain_options.core.correlation import compute_correlation, check_pool_correlation


def test_filter_evaluation():
    config = OptionsConfig.from_env()

    # 1. Failing Sharpe
    m1 = SimMetrics(alpha_id="A1", sharpe=0.8, fitness=1.2, turnover=0.20, annualized_return=0.1, max_drawdown=0.05, margin=0.001, status="COMPLETE", raw_response={})
    passed, reason = evaluate_alpha_metrics(m1, config)
    assert not passed
    assert "Sharpe" in reason

    # 2. Failing Turnover (too high)
    m2 = SimMetrics(alpha_id="A2", sharpe=1.5, fitness=1.2, turnover=0.85, annualized_return=0.1, max_drawdown=0.05, margin=0.001, status="COMPLETE", raw_response={})
    passed, reason = evaluate_alpha_metrics(m2, config)
    assert not passed
    assert "Turnover" in reason

    # 3. Passing all gates
    m3 = SimMetrics(alpha_id="A3", sharpe=1.65, fitness=1.35, turnover=0.25, annualized_return=0.15, max_drawdown=0.04, margin=0.001, status="COMPLETE", raw_response={})
    passed, reason = evaluate_alpha_metrics(m3, config)
    assert passed
    assert reason == "PASSED_ALL_GATES"


def test_sharpe_sampling_error_gate():
    config = OptionsConfig.from_env()

    # Low sample years (e.g. 1 year) with Sharpe 1.3 -> SE = sqrt((1 + 1.3^2/2)/1) = sqrt(1.845) = 1.358
    # 1.3 < 1.96 * 1.358 -> rejected as noisy
    se = compute_sharpe_sampling_error(1.3, sample_years=1.0)
    assert se > 1.0

    m = SimMetrics(alpha_id="A_noisy", sharpe=1.3, fitness=1.1, turnover=0.3, annualized_return=0.1, max_drawdown=0.05, margin=0.001, status="COMPLETE", raw_response={})
    passed, reason = evaluate_alpha_metrics(m, config, sample_years=1.0, enforce_sampling_error=True)
    assert not passed
    assert "statistically noisy" in reason

    # For 5 years with robust Sharpe 2.0 -> SE = sqrt((1 + 4/2)/5) = sqrt(0.6) = 0.774
    # 2.0 > 1.96 * 0.774 = 1.517 -> passes!
    m_robust = SimMetrics(alpha_id="A_robust", sharpe=2.0, fitness=1.5, turnover=0.3, annualized_return=0.2, max_drawdown=0.05, margin=0.001, status="COMPLETE", raw_response={})
    passed, reason = evaluate_alpha_metrics(m_robust, config, sample_years=5.0, enforce_sampling_error=True)
    assert passed


def test_leland_drag_rejection():
    config = OptionsConfig.from_env()
    # High turnover (>50%) with thin margin (<0.0005) and low return (<0.03)
    m = SimMetrics(alpha_id="A_drag", sharpe=1.5, fitness=1.2, turnover=0.55, annualized_return=0.02, max_drawdown=0.05, margin=0.0002, status="COMPLETE", raw_response={})
    passed, reason = evaluate_alpha_metrics(m, config)
    assert not passed
    assert "Leland drag" in reason


def test_correlation_check():
    dates = [f"2025-01-{i:02d}" for i in range(1, 35)]
    series_a = {d: float(i % 5) for i, d in enumerate(dates)}
    series_b = {d: float(i % 5) for i, d in enumerate(dates)}  # perfectly correlated

    corr_ab = compute_correlation(series_a, series_b)
    assert abs(corr_ab - 1.0) < 1e-4

    passed, max_corr = check_pool_correlation(series_a, [series_b], max_threshold=0.70)
    assert not passed
    assert max_corr > 0.70
