"""
Local filter: Sharpe / Fitness / Turnover thresholds applied to a simulation
result, above BRAIN's own stated minimums (per the project's build prompt and
pipeline/filter/local_filter.py entry). Configurable via env vars so this
can be tightened without a code change.

Defaults below are set intentionally *above* WorldQuant BRAIN's commonly
published minimum bar (roughly Fitness >= 1.0, Sharpe >= 1.25) so that a
candidate that only just clears BRAIN's own floor doesn't slip through as
"good" here — the review store is meant to hold candidates worth a human's
attention, not the bare minimum submittable alpha.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class FilterThresholds:
    min_sharpe: float = 1.25
    min_fitness: float = 1.0
    max_turnover: float = 0.70
    min_turnover: float = 0.01  # near-zero turnover is often a degenerate/static signal

    @classmethod
    def from_env(cls) -> "FilterThresholds":
        return cls(
            min_sharpe=float(os.environ.get("FILTER_MIN_SHARPE", "1.25")),
            min_fitness=float(os.environ.get("FILTER_MIN_FITNESS", "1.0")),
            max_turnover=float(os.environ.get("FILTER_MAX_TURNOVER", "0.70")),
            min_turnover=float(os.environ.get("FILTER_MIN_TURNOVER", "0.01")),
        )

    def passes(self, result) -> bool:
        """`result` needs .sharpe, .fitness, .turnover attributes (duck-typed
        so both SimResult and a plain dict-like row work)."""
        sharpe = _get(result, "sharpe")
        fitness = _get(result, "fitness")
        turnover = _get(result, "turnover")
        if sharpe is None or fitness is None or turnover is None:
            return False
        return (
            sharpe >= self.min_sharpe
            and fitness >= self.min_fitness
            and self.min_turnover <= turnover <= self.max_turnover
        )


def _get(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def compute_fitness(sharpe: float, returns_ann: float, turnover: float) -> float:
    """Reference implementation of BRAIN's Fitness formula, per
    the audit checklist:

        Fitness = Sharpe * sqrt(|Returns| / max(Turnover, 0.125))

    Used to cross-check a stored row's fitness against a raw BRAIN response
    during the audit (catches a formula transcription bug) — not used to
    override whatever BRAIN itself reports, since BRAIN's reported fitness
    is the one that actually governs submission eligibility.
    """
    denom = max(turnover, 0.125)
    return sharpe * ((abs(returns_ann) / denom) ** 0.5)
