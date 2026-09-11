"""
Qualification criteria for WorldQuant BRAIN accepted alphas.
"""
from __future__ import annotations

from typing import Tuple
from brain_options.config import OptionsConfig
from brain_options.core.client import SimMetrics


def evaluate_alpha_metrics(metrics: SimMetrics, config: OptionsConfig) -> Tuple[bool, str]:
    """Evaluates if an optimized alpha passes WorldQuant BRAIN qualification criteria."""
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

    return True, "PASSED_ALL_GATES"
