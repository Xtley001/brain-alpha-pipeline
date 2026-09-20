"""
Correlation gate: ensures candidate alphas do not duplicate existing accepted alphas
in the options pool (Max Pool Correlation < 0.70).
"""
from __future__ import annotations

import logging
import math
from typing import Dict, List, Tuple

try:
    import numpy as np
except ImportError:
    np = None

log = logging.getLogger("brain_options.correlation")


def compute_correlation(series_a: Dict[str, float], series_b: Dict[str, float]) -> float:
    """Computes Pearson correlation coefficient between two daily return series."""
    valid_dates = []
    for d in sorted(set(series_a.keys()) & set(series_b.keys())):
        va = series_a.get(d)
        vb = series_b.get(d)
        if (
            va is not None
            and vb is not None
            and isinstance(va, (int, float))
            and isinstance(vb, (int, float))
            and math.isfinite(va)
            and math.isfinite(vb)
        ):
            valid_dates.append(d)

    if len(valid_dates) < 30:
        return 0.0

    if np is not None:
        vec_a = np.array([float(series_a[d]) for d in valid_dates], dtype=np.float64)
        vec_b = np.array([float(series_b[d]) for d in valid_dates], dtype=np.float64)

        std_a, std_b = float(np.std(vec_a)), float(np.std(vec_b))
        if std_a < 1e-9 or std_b < 1e-9:
            return 0.0

        corr_matrix = np.corrcoef(vec_a, vec_b)
        val = float(corr_matrix[0, 1])
        return val if math.isfinite(val) else 0.0

    # Pure Python fallback
    n = len(valid_dates)
    vals_a = [float(series_a[d]) for d in valid_dates]
    vals_b = [float(series_b[d]) for d in valid_dates]
    mean_a = sum(vals_a) / n
    mean_b = sum(vals_b) / n
    cov = sum((a - mean_a) * (b - mean_b) for a, b in zip(vals_a, vals_b))
    var_a = sum((a - mean_a) ** 2 for a in vals_a)
    var_b = sum((b - mean_b) ** 2 for b in vals_b)
    denom = var_a * var_b
    if denom < 1e-18:
        return 0.0
    val = float(cov / math.sqrt(denom))
    return val if math.isfinite(val) else 0.0


def check_pool_correlation(
    candidate_returns: Dict[str, float],
    pool_returns: List[Dict[str, float]],
    max_threshold: float = 0.70,
) -> Tuple[bool, float]:
    """Checks whether candidate correlation exceeds max_threshold against any pool alpha."""
    if not candidate_returns or not pool_returns:
        return True, 0.0

    max_seen = 0.0
    for prev_returns in pool_returns:
        corr = abs(compute_correlation(candidate_returns, prev_returns))
        if corr > max_seen:
            max_seen = corr
        if corr >= max_threshold:
            log.warning("Candidate rejected by correlation gate: %.2f >= %.2f", corr, max_threshold)
            return False, max_seen

    return True, max_seen
