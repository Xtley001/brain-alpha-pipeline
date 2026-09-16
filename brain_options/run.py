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
from brain_options.core.notifier import (
    send_telegram_alert,
    send_telegram_batch_summary,
    send_telegram_startup,
)
from brain_options.core.sweep import SweepEngine
from brain_options.llm.adapter import LLMAdapter
from brain_options.specialist.generator import OptionsGenerator
from brain_options.specialist.templates import OptionCandidate
from brain_options.store.store import OptionsStore

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("brain_options")


from brain_options.core.optimizer import DiagnosticAlphaOptimizer


async def run_candidate(
    candidate: OptionCandidate,
    sweep_engine: SweepEngine,
    client: BrainClient,
    store: OptionsStore,
    config: OptionsConfig,
) -> bool:
    """Executes the screening, diagnostic optimization, filtering, and alert pipeline for one candidate."""
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

    log.info("[*] STAGE 0 PASSED! Proceeding to Closed-Loop Diagnostic Optimization...")

    # 2. Closed-Loop Diagnostic Optimization Loop
    optimizer = DiagnosticAlphaOptimizer(client, store, config)
    best_cand, best_settings, best_metrics, passed_filter, opt_history = await optimizer.optimize(
        candidate=candidate,
        base_settings=s0_settings,
        initial_metrics=s0_metrics,
        max_steps=6,
    )

    if not passed_filter:
        log.info(
            "Candidate failed local filter after %d diagnostic steps: Sharpe=%.2f, Fitness=%.2f, TO=%.2f%%",
            len(opt_history) - 1,
            best_metrics.sharpe,
            best_metrics.fitness,
            best_metrics.turnover * 100,
        )
        return False

    log.info("[+] QUALIFIED FOR POOL! Checking correlation...")

    # 3. Correlation Gate
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

    # 4. Success! Save to Store & Alert
    log.info(
        "[SUCCESS] ALPHA ACCEPTED! Sharpe=%.2f, Fitness=%.2f, Turnover=%.2f%%, MaxCorr=%.2f",
        best_metrics.sharpe,
        best_metrics.fitness,
        best_metrics.turnover * 100,
        max_corr,
    )
    store.save_passed_alpha(best_cand, best_settings, best_metrics, max_corr, pnl_series)
    send_telegram_alert(best_cand.expression, best_settings, best_metrics, max_corr, config)

    # 5. Optional Auto-Submit to WorldQuant BRAIN platform
    import os
    if os.environ.get("ENABLE_AUTO_SUBMIT", "false").lower() == "true" and best_metrics.alpha_id:
        log.info("Auto-submitting alpha %s to WorldQuant BRAIN...", best_metrics.alpha_id)
        try:
            sub_res = await client.submit_alpha(best_metrics.alpha_id)
            log.info("WorldQuant BRAIN submission result: %s", sub_res)
        except Exception as e:
            log.warning("Auto-submit encountered error: %s", e)

    return True


async def run_batch(config: OptionsConfig, batch_size: int, dry_run: bool = False, mode_label: str = "Single Batch") -> int:
    store = OptionsStore(database_url=config.database_url)
    evaluated = store.load_evaluated_expressions()
    top_exemplars = store.load_top_performing_exemplars(limit=5, min_sharpe=0.85)
    archetype_summary = store.load_archetype_performance_summary()

    llm_adapter = LLMAdapter(config)
    generator = OptionsGenerator(llm_adapter)
    generator.evaluated_expressions.update(evaluated)

    log.info("Loaded %d previously evaluated candidates.", len(evaluated))
    log.info("Loaded %d top RL exemplars and archetype summary for MAB weighting.", len(top_exemplars))
    log.info("Generating next batch of %d options candidates...", batch_size)

    # Initial candidate batch generation
    initial_candidates = generator.get_next_batch(
        target_count=min(batch_size, 10),
        template_ratio=0.3,
        top_exemplars=top_exemplars,
        archetype_summary=archetype_summary,
    )
    log.info("Generated initial %d fresh options candidates (Batch Target: %d, Budget: %ds).",
             len(initial_candidates), batch_size, config.run_time_budget_seconds)

    if dry_run:
        log.info("DRY RUN MODE: Listing generated candidates without running simulations:")
        for idx, c in enumerate(initial_candidates, 1):
            log.info("  [%d] (%s) %s -> %s", idx, c.generation_source, c.archetype_name, c.expression)
        return 0

    client = BrainClient(
        username=config.brain_username,
        password=config.brain_password,
        max_concurrent_sims=config.brain_max_concurrent_sims,
    )
    client.authenticate()

    # Send startup notification
    send_telegram_startup(config, mode=mode_label)

    sweep_engine = SweepEngine(client, config)

    passed_count = 0
    total_evaluated = 0
    start_time = time.time()
    queue: asyncio.Queue[OptionCandidate] = asyncio.Queue()

    for cand in initial_candidates:
        queue.put_nowait(cand)

    async def worker(worker_id: int):
        nonlocal passed_count, total_evaluated
        while True:
            elapsed = time.time() - start_time
            if elapsed > config.run_time_budget_seconds:
                log.warning("Worker %d: Run time budget (%ds) reached. Stopping.", worker_id, config.run_time_budget_seconds)
                break

            if total_evaluated >= batch_size and queue.empty():
                log.info("Worker %d: Batch evaluation target (%d) reached.", worker_id, batch_size)
                break

            try:
                cand = queue.get_nowait()
            except asyncio.QueueEmpty:
                # If queue is empty, budget remains, and target not reached, generate next chunk
                if total_evaluated < batch_size and (config.run_time_budget_seconds - elapsed > 60):
                    fetch_n = min(6, batch_size - total_evaluated)
                    log.info("Worker %d: Queue empty. Generating %d more candidates...", worker_id, fetch_n)
                    try:
                        fresh_cands = generator.get_next_batch(
                            target_count=fetch_n,
                            template_ratio=0.3,
                            top_exemplars=top_exemplars,
                            archetype_summary=archetype_summary,
                        )
                        for fc in fresh_cands:
                            queue.put_nowait(fc)
                        cand = queue.get_nowait()
                    except Exception as gen_err:
                        log.warning("Worker %d: Candidate generation encountered error: %s", worker_id, gen_err)
                        break
                else:
                    break

            total_evaluated += 1
            log.info("\n[Worker %d | Cand %d/%d] Starting processing [%s]: %s",
                     worker_id, total_evaluated, batch_size, cand.archetype_name, cand.expression[:60])
            try:
                passed = await run_candidate(cand, sweep_engine, client, store, config)
                if passed:
                    passed_count += 1
            except Exception as e:
                log.error("Worker %d encountered error processing candidate %s: %s",
                          worker_id, cand.expression[:50], e, exc_info=True)
            finally:
                queue.task_done()

    num_workers = max(1, config.brain_max_concurrent_sims)
    log.info("Starting %d concurrent candidate workers to fully saturate BRAIN slots...", num_workers)
    workers = [asyncio.create_task(worker(i + 1)) for i in range(num_workers)]
    await asyncio.gather(*workers)

    log.info("\nBatch completed: %d passed / %d evaluated.", passed_count, total_evaluated)
    stats = store.get_options_stats()
    send_telegram_batch_summary(passed_count, total_evaluated, config, stats=stats)
    return passed_count


def main():
    parser = argparse.ArgumentParser(description="WorldQuant BRAIN Options Alpha Pipeline")
    parser.add_argument("--single-batch", action="store_true", help="Run a single bounded batch and exit (Render cron mode)")
    parser.add_argument("--daemon", action="store_true", help="Run continuously in a loop")
    parser.add_argument("--dry-run", action="store_true", help="Generate candidates and verify without simulating")
    parser.add_argument("--candidates", type=int, default=0, help="Override candidate count per batch")
    parser.add_argument("--test-telegram", action="store_true", help="Send a test notification to Telegram and exit")
    parser.add_argument("--stats", action="store_true", help="Display daily and all-time options alpha statistics")
    args = parser.parse_args()

    config = OptionsConfig.from_env()

    if args.stats:
        store = OptionsStore(database_url=config.database_url)
        stats = store.get_options_stats()
        print("\n" + "=" * 55)
        print(" WORLDQUANT BRAIN OPTIONS ALPHA PIPELINE STATS")
        print("=" * 55)
        print(f"  • Today's Evaluations:      {stats.get('today_evaluated', 0)}")
        print(f"  • Today's Stage 0 Passing:  {stats.get('today_stage0_pass', 0)}")
        print(f"  • Today's Qualified Alphas: {stats.get('today_qualified', 0)}")
        print("-" * 55)
        print(f"  • All-Time Evaluated:       {stats.get('all_time_evaluated', 0)}")
        print(f"  • All-Time Qualified Pool:  {stats.get('all_time_pool_alphas', 0)}")
        print("=" * 55 + "\n")
        return

    if args.test_telegram:
        log.info("Sending test notification to Telegram...")
        success = send_telegram_startup(config, mode="Test Notification")
        log.info("Telegram test result: %s", "SUCCESS" if success else "FAILED")
        return


    batch_size = args.candidates if args.candidates > 0 else config.max_candidates_per_run

    log.info("Starting brain_options pipeline (Universe=%s, Delay=%d, MaxSims=%d)...", config.universe, config.delay, config.brain_max_concurrent_sims)

    if args.daemon:
        log.info("Running in continuous daemon mode...")
        while True:
            try:
                asyncio.run(run_batch(config, batch_size=batch_size, dry_run=args.dry_run, mode_label="Continuous Daemon"))
            except Exception as e:
                log.error("Batch encountered unhandled error: %s", e, exc_info=True)
            log.info("Sleeping 300 seconds before next batch...")
            time.sleep(300)
    else:
        asyncio.run(run_batch(config, batch_size=batch_size, dry_run=args.dry_run, mode_label="Single Batch"))


if __name__ == "__main__":
    main()
