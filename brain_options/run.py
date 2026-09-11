"""
Master execution runner for brain_options.
Supports single bounded batch (ideal for Render cron jobs) or continuous daemon loop.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time

from brain_options.config import OptionsConfig
from brain_options.core.client import BrainClient, SimMetrics, SimSettings
from brain_options.core.correlation import check_pool_correlation
from brain_options.core.filter import evaluate_alpha_metrics
from brain_options.core.notifier import send_telegram_alert
from brain_options.core.sweep import SweepEngine
from brain_options.llm.adapter import LLMAdapter
from brain_options.specialist.generator import OptionsGenerator
from brain_options.specialist.templates import OptionCandidate
from brain_options.store.store import OptionsStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("brain_options")


async def run_candidate(
    candidate: OptionCandidate,
    sweep_engine: SweepEngine,
    client: BrainClient,
    store: OptionsStore,
    config: OptionsConfig,
) -> bool:
    """Executes the screening, optimization, filtering, and alert pipeline for one candidate."""
    log.info("=" * 70)
    log.info("TESTING CANDIDATE [%s]: %s", candidate.archetype_name, candidate.expression)
    log.info("Hypothesis: %s", candidate.hypothesis)

    # 1. Stage 0: Fast Screen (1 simulation)
    s0_passed, s0_settings, s0_metrics = await sweep_engine.stage0_screen(candidate.expression)
    store.record_evaluated_candidate(
        candidate,
        stage="STAGE0",
        status="PASS" if s0_passed else "FAIL",
        metrics=s0_metrics,
    )

    if not s0_passed:
        log.info(
            "Candidate rejected at Stage 0 (Sharpe=%.2f, Fitness=%.2f)",
            s0_metrics.sharpe,
            s0_metrics.fitness,
        )
        return False

    log.info("⭐ STAGE 0 PASSED! Proceeding to Stage 1 Grid Optimization...")

    # 2. Stage 1: Neutralization x Decay Grid Sweep (25-30 simulations)
    best_settings, best_metrics = await sweep_engine.stage1_grid_sweep(candidate.expression, s0_settings)
    store.record_evaluated_candidate(
        candidate,
        stage="STAGE1",
        status="OPTIMIZED",
        metrics=best_metrics,
    )

    # 3. Local Acceptance Filter
    passed_filter, reason = evaluate_alpha_metrics(best_metrics, config)
    if not passed_filter:
        log.info("Candidate failed local filter: %s", reason)
        return False

    log.info("🌟 QUALIFIED FOR POOL! Checking correlation...")

    # 4. Correlation Gate
    pnl_series: dict[str, float] = {}
    max_corr = 0.0
    if best_metrics.alpha_id:
        pnl_series = await client.get_alpha_pnl(best_metrics.alpha_id)
        pool_pnl = store.load_pool_pnl_series()
        passed_corr, max_corr = check_pool_correlation(
            pnl_series, pool_pnl, max_threshold=config.max_pool_correlation
        )
        if not passed_corr:
            log.warning("Candidate rejected by correlation gate (MaxCorr=%.2f >= %.2f)", max_corr, config.max_pool_correlation)
            return False

    # 5. Success! Save to Store & Alert
    log.info(
        "🏆 ALPHA ACCEPTED! Sharpe=%.2f, Fitness=%.2f, Turnover=%.2f%%, MaxCorr=%.2f",
        best_metrics.sharpe,
        best_metrics.fitness,
        best_metrics.turnover * 100,
        max_corr,
    )
    store.save_passed_alpha(candidate, best_settings, best_metrics, max_corr, pnl_series)
    send_telegram_alert(candidate.expression, best_settings, best_metrics, max_corr, config)
    return True


async def run_batch(config: OptionsConfig, batch_size: int, dry_run: bool = False) -> int:
    store = OptionsStore(database_url=config.database_url)
    evaluated = store.load_evaluated_expressions()

    llm_adapter = LLMAdapter(config)
    generator = OptionsGenerator(llm_adapter)
    generator.evaluated_expressions.update(evaluated)

    log.info("Loaded %d previously evaluated candidates.", len(evaluated))
    log.info("Generating next batch of %d options candidates...", batch_size)

    candidates = generator.get_next_batch(target_count=batch_size, template_ratio=0.5)
    log.info("Generated %d fresh options candidates.", len(candidates))

    if dry_run:
        log.info("DRY RUN MODE: Listing generated candidates without running simulations:")
        for idx, c in enumerate(candidates, 1):
            log.info("  [%d] (%s) %s -> %s", idx, c.generation_source, c.archetype_name, c.expression)
        return 0

    client = BrainClient(
        username=config.brain_username,
        password=config.brain_password,
        max_concurrent_sims=config.brain_max_concurrent_sims,
    )
    client.authenticate()

    sweep_engine = SweepEngine(client, config)

    passed_count = 0
    start_time = time.time()

    for idx, cand in enumerate(candidates, 1):
        elapsed = time.time() - start_time
        if elapsed > config.run_time_budget_seconds:
            log.warning("Run time budget (%ds) reached. Stopping batch.", config.run_time_budget_seconds)
            break

        log.info("\n[%d/%d] Starting processing...", idx, len(candidates))
        passed = await run_candidate(cand, sweep_engine, client, store, config)
        if passed:
            passed_count += 1

    log.info("\nBatch completed: %d/%d passed all criteria.", passed_count, len(candidates))
    return passed_count


def main():
    parser = argparse.ArgumentParser(description="WorldQuant BRAIN Options Alpha Pipeline")
    parser.add_argument("--single-batch", action="store_true", help="Run a single bounded batch and exit (Render cron mode)")
    parser.add_argument("--daemon", action="store_true", help="Run continuously in a loop")
    parser.add_argument("--dry-run", action="store_true", help="Generate candidates and verify without simulating")
    parser.add_argument("--candidates", type=int, default=0, help="Override candidate count per batch")
    args = parser.parse_args()

    config = OptionsConfig.from_env()
    batch_size = args.candidates if args.candidates > 0 else config.max_candidates_per_run

    log.info("Starting brain_options pipeline (Universe=%s, Delay=%d, MaxSims=%d)...", config.universe, config.delay, config.brain_max_concurrent_sims)

    if args.daemon:
        log.info("Running in continuous daemon mode...")
        while True:
            try:
                asyncio.run(run_batch(config, batch_size=batch_size, dry_run=args.dry_run))
            except Exception as e:
                log.error("Batch encountered unhandled error: %s", e, exc_info=True)
            log.info("Sleeping 300 seconds before next batch...")
            time.sleep(300)
    else:
        asyncio.run(run_batch(config, batch_size=batch_size, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
