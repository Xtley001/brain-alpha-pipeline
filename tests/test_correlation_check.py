import random

from pipeline.filter.correlation_check import compute_max_correlation, passes_correlation_gate


def _dates(n):
    return [f"2026-01-{d:02d}" for d in range(1, n + 1)]


def test_identical_return_streams_correlate_near_one():
    dates = _dates(25)
    values = [0.01, -0.02, 0.015, 0.0, 0.03, -0.01] * 5
    values = values[:25]
    candidate = dict(zip(dates, values))
    pool = {"alpha_A": dict(zip(dates, values))}

    result = compute_max_correlation(candidate, pool, min_overlap=10)
    assert result.max_correlation > 0.999
    assert result.max_correlation_alpha_id == "alpha_A"


def test_independent_random_streams_correlate_near_zero():
    random.seed(42)
    dates = _dates(500)
    candidate = {d: random.gauss(0, 1) for d in dates}
    pool = {"alpha_B": {d: random.gauss(0, 1) for d in dates}}

    result = compute_max_correlation(candidate, pool, min_overlap=10)
    assert abs(result.max_correlation) < 0.15


def test_inverted_streams_correlate_near_negative_one():
    dates = _dates(25)
    values = [0.01, -0.02, 0.015, 0.0, 0.03, -0.01] * 5
    values = values[:25]
    candidate = dict(zip(dates, values))
    pool = {"alpha_C": dict(zip(dates, [-v for v in values]))}

    result = compute_max_correlation(candidate, pool, min_overlap=10)
    assert result.max_correlation < -0.999


def test_picks_max_absolute_correlation_across_pool():
    dates = _dates(25)
    values = [0.01, -0.02, 0.015, 0.0, 0.03, -0.01] * 5
    values = values[:25]
    candidate = dict(zip(dates, values))
    pool = {
        "low_corr": {d: 0.001 * i for i, d in enumerate(dates)},
        "high_corr": dict(zip(dates, values)),
    }

    result = compute_max_correlation(candidate, pool, min_overlap=10)
    assert result.max_correlation_alpha_id == "high_corr"


def test_insufficient_overlap_is_skipped_not_reported():
    dates = _dates(5)
    candidate = {d: 0.01 for d in dates}
    pool = {"too_short": {d: 0.01 for d in dates}}

    result = compute_max_correlation(candidate, pool, min_overlap=20)
    assert result.per_alpha == {}
    assert result.max_correlation == 0.0


def test_gate_rejects_above_threshold_and_accepts_below():
    dates = _dates(25)
    values = [0.01, -0.02, 0.015, 0.0, 0.03, -0.01] * 5
    values = values[:25]
    candidate = dict(zip(dates, values))
    pool_high = {"dup": dict(zip(dates, values))}
    pool_low = {"dup": {d: 0.001 * i for i, d in enumerate(dates)}}

    high = compute_max_correlation(candidate, pool_high, min_overlap=10)
    low = compute_max_correlation(candidate, pool_low, min_overlap=10)

    assert passes_correlation_gate(high, max_allowed_correlation=0.7) is False
    assert passes_correlation_gate(low, max_allowed_correlation=0.7) is True
