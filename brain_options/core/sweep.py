"""
Two-stage simulation sweep for brain_options:
- Stage 0: Fast Screen (1 sim). Checks if raw signal passes minimal viable threshold.
- Stage 1: Neutralization x Decay Grid Sweep (up to 25-30 sims). Finds optimal settings.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional, Tuple

from brain_options.config import OptionsConfig
from brain_options.core.client import BrainClient, SimMetrics, SimSettings

log = logging.getLogger("brain_options.sweep")

NEUTRALIZATIONS = ["SUBINDUSTRY", "INDUSTRY", "SECTOR", "MARKET", "NONE"]
DECAYS = [0, 4, 8, 15, 20, 26, 30]


class SweepEngine:
    def __init__(self, client: BrainClient, config: OptionsConfig):
        self.client = client
        self.config = config

    async def stage0_screen(self, expression: str) -> Tuple[bool, SimSettings, SimMetrics]:
        """Runs a single simulation on default settings to weed out noise early."""
        default_settings = SimSettings(
            universe=self.config.universe,
            delay=self.config.delay,
            decay=8,
            neutralization="SUBINDUSTRY",
            truncation=0.05,
            pasteurization=True,
            nan_handling=False,
        )

        metrics = await self.client.simulate_one(expression, default_settings)

        passed = (
            metrics.is_valid
            and metrics.sharpe >= self.config.stage0_min_sharpe
            and metrics.fitness >= self.config.stage0_min_fitness
        )

        log.info(
            "Stage 0 Screen for %s: passed=%s (Sharpe=%.2f, Fitness=%.2f)",
            expression[:50],
            passed,
            metrics.sharpe,
            metrics.fitness,
        )
        return passed, default_settings, metrics

    async def stage1_grid_sweep(
        self,
        expression: str,
        base_settings: SimSettings,
        decays: Optional[list[int]] = None,
        neutralizations: Optional[list[str]] = None,
    ) -> Tuple[SimSettings, SimMetrics]:
        """Sweeps Neutralization x Decay grid to find the optimal combination."""
        log.info("Starting Stage 1 Grid Sweep for: %s", expression[:60])

        decay_grid = decays if decays and len(decays) > 0 else DECAYS
        neut_grid = neutralizations if neutralizations and len(neutralizations) > 0 else NEUTRALIZATIONS

        candidates_settings = [
            SimSettings(
                universe=base_settings.universe,
                delay=base_settings.delay,
                decay=d,
                neutralization=n,
                truncation=base_settings.truncation,
                pasteurization=base_settings.pasteurization,
                nan_handling=base_settings.nan_handling,
            )
            for n in neut_grid
            for d in decay_grid
        ]

        best_settings = base_settings
        best_metrics: Optional[SimMetrics] = None

        # Run simulations respecting max_concurrent_sims
        semaphore = asyncio.Semaphore(self.client.max_concurrent_sims)

        async def run_one(s: SimSettings) -> Tuple[SimSettings, SimMetrics]:
            async with semaphore:
                m = await self.client.simulate_one(expression, s)
                return s, m

        tasks = [run_one(s) for s in candidates_settings]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for res in results:
            if isinstance(res, Exception):
                log.warning("Stage 1 simulation failed with exception: %s", res)
                continue
            settings, metrics = res
            if not metrics.is_valid:
                continue

            if best_metrics is None or metrics.fitness > best_metrics.fitness:
                best_metrics = metrics
                best_settings = settings

        if best_metrics is None:
            best_metrics = SimMetrics(None, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "SWEEP_FAILED", {})

        log.info(
            "Stage 1 Best Combo: Neut=%s, Decay=%d -> Sharpe=%.2f, Fitness=%.2f, Turnover=%.2f%%",
            best_settings.neutralization,
            best_settings.decay,
            best_metrics.sharpe,
            best_metrics.fitness,
            best_metrics.turnover * 100,
        )
        return best_settings, best_metrics
