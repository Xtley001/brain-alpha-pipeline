"""
Qualification criteria for WorldQuant BRAIN accepted alphas.
Embeds statistical sampling error bounds (Sharpe t-stat gate) and institutional
risk checks from Options Master Knowledge Base (Books 1-4).
"""
from __future__ import annotations

import math
from typing import Tuple
from brain_options.config import OptionsConfig
from brain_options.core.client import SimMetrics


def compute_sharpe_sampling_error(sharpe: float, sample_years: float = 5.0) -> float:
    """
    Computes standard error of Sharpe ratio using the Sinclair (Book 1) & Derman (Book 3) formula:
    Var(Sharpe) = (1 / T) * (1 + Sharpe^2 / 2)
    SE(Sharpe) = sqrt(Var(Sharpe))
    """
    if sample_years <= 0:
        return 0.5
    var_sharpe = (1.0 + (sharpe ** 2) / 2.0) / sample_years
    return math.sqrt(var_sharpe)


def evaluate_alpha_metrics(
    metrics: SimMetrics,
    config: OptionsConfig,
    sample_years: float = 5.0,
    enforce_sampling_error: bool = False,
) -> Tuple[bool, str]:
    """
    Evaluates if an optimized alpha passes WorldQuant BRAIN qualification criteria,
    including sampling error sanity gates to reject 'passed by noise' candidates.
    """
    if not metrics.is_valid:
        return False, f"Invalid simulation response (status: {metrics.status})"

    if metrics.sharpe < config.filter_min_sharpe:
        return False, f"Sharpe {metrics.sharpe:.2f} < {config.filter_min_sharpe:.2f}"

    if metrics.fitness < config.filter_min_fitness:
        return False, f"Fitness {metrics.fitness:.2f} < {config.filter_min_fitness:.2f}"

    if metrics.turnover < config.filter_min_turnover:
        return False, f"Turnover {metrics.turnover * 100:.2f}% < {config.filter_min_turnover * 100:.2f}% (too passive)"

    if metrics.turnover > config.filter_max_turnover:
        return False, f"Turnover {metrics.turnover * 100:.2f}% > {config.filter_max_turnover * 100:.2f}% (too high)"

    # Institutional gate from Master Books 1 & 3: Sharpe sampling error gate
    if enforce_sampling_error:
        se = compute_sharpe_sampling_error(metrics.sharpe, sample_years=sample_years)
        # Check if Sharpe is distinguishable from zero at ~95% confidence level (1.96 SE)
        if metrics.sharpe < 1.96 * se:
            return False, f"Sharpe {metrics.sharpe:.2f} < 1.96 * SE({se:.2f}) - statistically noisy edge"

    # Leland transaction drag check: very high turnover with minimal margin
    if metrics.turnover > 0.50 and metrics.margin < 0.0005 and metrics.annualized_return < 0.03:
        return False, f"Leland drag: turnover {metrics.turnover*100:.1f}% erodes thin margin ({metrics.margin:.4f})"

    return True, "PASSED_ALL_GATES"
