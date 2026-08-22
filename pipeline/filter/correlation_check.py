"""
Correlation check: a candidate's winning-settings return stream vs. every
alpha already in the pool (`pool_returns`). Per the settings-sweep spec
§8, correlation must be computed on the *winning* settings' return stream,
not the Stage 0 default settings' stream.

Pure math module — no DB or network calls here. The worker is responsible
for pulling `pool_returns` and the candidate's own return series and handing
plain series in; that keeps this testable with synthetic data per
the audit checklist (identical streams ~1.0, independent streams
~0.0).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True)
class CorrelationResult:
    max_correlation: float
    max_correlation_alpha_id: str | None
    per_alpha: dict


def _pearson(a: Sequence[float], b: Sequence[float]) -> float:
    n = len(a)
    if n == 0 or n != len(b):
        raise ValueError("Return series must be non-empty and equal length")
    mean_a = sum(a) / n
    mean_b = sum(b) / n
    cov = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b))
    var_a = sum((x - mean_a) ** 2 for x in a)
    var_b = sum((y - mean_b) ** 2 for y in b)
    denom = (var_a * var_b) ** 0.5
    if denom == 0:
        return 0.0
    return cov / denom


def align_series(
    candidate_returns: Mapping[str, float], pool_alpha_returns: Mapping[str, float]
) -> tuple[list, list]:
    """Align two {date: return} maps on their common dates, in date order."""
    common_dates = sorted(set(candidate_returns) & set(pool_alpha_returns))
    a = [candidate_returns[d] for d in common_dates]
    b = [pool_alpha_returns[d] for d in common_dates]
    return a, b


def compute_max_correlation(
    candidate_returns: Mapping[str, float],
    pool_returns_by_alpha: Mapping[str, Mapping[str, float]],
    min_overlap: int = 20,
) -> CorrelationResult:
    """
    candidate_returns: {date_str: daily_return} for the candidate's winning
        settings.
    pool_returns_by_alpha: {alpha_id: {date_str: daily_return}} for the
        existing pool.
    min_overlap: minimum number of overlapping dates required to trust a
        correlation figure; pairs with less overlap are skipped rather than
        reported as a possibly-meaningless correlation.
    """
    per_alpha = {}
    for alpha_id, series in pool_returns_by_alpha.items():
        a, b = align_series(candidate_returns, series)
        if len(a) < min_overlap:
            continue
        per_alpha[alpha_id] = _pearson(a, b)

    if not per_alpha:
        return CorrelationResult(max_correlation=0.0, max_correlation_alpha_id=None, per_alpha={})

    max_alpha_id = max(per_alpha, key=lambda k: abs(per_alpha[k]))
    return CorrelationResult(
        max_correlation=per_alpha[max_alpha_id],
        max_correlation_alpha_id=max_alpha_id,
        per_alpha=per_alpha,
    )


def passes_correlation_gate(result: CorrelationResult, max_allowed_correlation: float = 0.7) -> bool:
    return abs(result.max_correlation) <= max_allowed_correlation
