"""
Master execution runner for brain_options.
Supports single bounded batch (ideal for Render cron jobs) or continuous daemon loop.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time

from brain_options.config import OptionsConfig
from brain_options.core.client import BrainClient, SimMetrics, SimSettings
from brain_options.core.correlation import check_pool_correlation
from brain_options.core.drip import DripSubmitter
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
    force_optimize: bool = False,
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

    should_proceed = s0_passed or (force_optimize and s0_metrics.is_valid)

    if not should_proceed:
        log.info(
            "Candidate rejected at Stage 0 (Sharpe=%.2f, Fitness=%.2f)",
            s0_metrics.sharpe,
            s0_metrics.fitness,
        )
        return False

    log.info("[*] STAGE 0 PASSED (or force-optimized)! Proceeding to Closed-Loop Diagnostic Optimization...")

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
        store.record_evaluated_candidate(
            candidate,
            stage="RETRY_COMPLETED",
            status="EXHAUSTED",
            metrics=best_metrics,
        )
        return False

    # 3. PnL Series Extraction (Correlation filter removed per user request)
    max_corr = 0.0
    pnl_series: dict[str, float] = {}
    if best_metrics.alpha_id:
        try:
            pnl_series = await client.get_alpha_pnl(best_metrics.alpha_id)
            pool_pnl = store.load_pool_pnl_series()
            if pool_pnl:
                _, max_corr = check_pool_correlation(pnl_series, pool_pnl, 1.0)
        except Exception as pnl_err:
            log.debug("Could not complete pool correlation fetch for alpha %s: %s", best_metrics.alpha_id, pnl_err)

    log.info("[+] QUALIFIED! Sharpe=%.2f, Fitness=%.2f, TO=%.2f%%", best_metrics.sharpe, best_metrics.fitness, best_metrics.turnover * 100)
    store.record_evaluated_candidate(
        candidate,
        stage="RETRY_COMPLETED",
        status="QUALIFIED",
        metrics=best_metrics,
    )

    # 4. Save to Store & Alert
    log.info(
        "[SUCCESS] ALPHA ACCEPTED! Sharpe=%.2f, Fitness=%.2f, Turnover=%.2f%%",
        best_metrics.sharpe,
        best_metrics.fitness,
        best_metrics.turnover * 100,
    )
    store.save_passed_alpha(best_cand, best_settings, best_metrics, max_corr, pnl_series)
    send_telegram_alert(best_cand.expression, best_settings, best_metrics, max_corr, config)

    # 5. Auto-Submit disabled per user preference (manual submission only)
    return True


async def run_batch(
    config: OptionsConfig,
    batch_size: int,
    dry_run: bool = False,
    mode_label: str = "Single Batch",
    target_archetype: Optional[str] = None,
) -> int:
    store = OptionsStore(database_url=config.database_url)
    db = store.db
    evaluated = store.load_evaluated_expressions()
    saturated_archetypes = db.get_recently_submitted_archetypes(limit=5) if db else []
    top_exemplars = store.load_top_performing_exemplars(limit=5, min_sharpe=0.85, exclude_archetypes=saturated_archetypes)
    archetype_summary = store.load_archetype_performance_summary()

    llm_adapter = LLMAdapter(config)
    generator = OptionsGenerator(llm_adapter)
    generator.evaluated_expressions.update(evaluated)

    arch_label = f" [Specialization: {target_archetype}]" if target_archetype else ""
    log.info("Loaded %d previously evaluated candidates.", len(evaluated))
    log.info("Loaded %d top RL exemplars and archetype summary for MAB weighting.%s", len(top_exemplars), arch_label)
    if saturated_archetypes:
        log.info("Active Portfolio Saturated Archetypes: %s (Anti-correlation active)", saturated_archetypes)
    log.info("Generating next batch of %d options candidates...", batch_size)

    # Initial candidate batch generation (offloaded to thread to prevent blocking event loop)
    initial_candidates = await asyncio.to_thread(
        generator.get_next_batch,
        target_count=min(batch_size, 10),
        template_ratio=0.3,
        top_exemplars=top_exemplars,
        archetype_summary=archetype_summary,
        target_archetype=target_archetype,
        saturated_archetypes=saturated_archetypes,
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
        db=db,
    )
    client.authenticate()

    # Send startup notification
    send_telegram_startup(config, mode=mode_label)

    sweep_engine = SweepEngine(client, config)

    passed_count = 0
    total_evaluated = 0
    start_time = time.time()
    queue: asyncio.Queue[OptionCandidate] = asyncio.Queue()
    refill_lock = asyncio.Lock()

    for cand in initial_candidates:
        queue.put_nowait(cand)

    async def worker(worker_id: int):
        nonlocal passed_count, total_evaluated
        while True:
            elapsed = time.time() - start_time
            if elapsed > config.run_time_budget_seconds:
                log.warning("Worker %d: Run time budget (%ds) reached. Stopping.", worker_id, config.run_time_budget_seconds)
                break

            if total_evaluated >= batch_size:
                log.info("Worker %d: Batch evaluation target (%d) reached.", worker_id, batch_size)
                break

            try:
                cand = queue.get_nowait()
            except asyncio.QueueEmpty:
                # Guard refill with a lock so only one worker generates candidates
                async with refill_lock:
                    if queue.empty() and total_evaluated < batch_size and (config.run_time_budget_seconds - elapsed > 60):
                        fetch_n = min(6, batch_size - total_evaluated)
                        log.info("Worker %d: Queue empty. Generating %d more candidates in thread...", worker_id, fetch_n)
                        try:
                            fresh_cands = await asyncio.to_thread(
                                generator.get_next_batch,
                                target_count=fetch_n,
                                template_ratio=0.3,
                                top_exemplars=top_exemplars,
                                archetype_summary=archetype_summary,
                                target_archetype=target_archetype,
                                saturated_archetypes=saturated_archetypes,
                            )
                            for fc in fresh_cands:
                                queue.put_nowait(fc)
                        except Exception as gen_err:
                            log.warning("Worker %d: Candidate generation encountered error: %s", worker_id, gen_err)

                    try:
                        cand = queue.get_nowait()
                    except asyncio.QueueEmpty:
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
    try:
        await asyncio.gather(*workers)
    except Exception as e:
        log.error("Worker pool encountered exception: %s", e)
    finally:
        log.info("\nBatch completed: %d passed / %d evaluated.", passed_count, total_evaluated)
        try:
            if passed_count > 0 or os.environ.get("NOTIFY_EVERY_BATCH", "false").lower() == "true":
                stats = store.get_options_stats()
                send_telegram_batch_summary(passed_count, total_evaluated, config, stats=stats)
        except Exception as summary_err:
            log.warning("Failed to send Telegram batch summary: %s", summary_err)

        # 24-hour interval drip submission check
        try:
            drip = DripSubmitter(client, store, config)
            await drip.check_and_drip()
        except Exception as drip_err:
            log.warning("Drip submitter check failed: %s", drip_err)
    return passed_count


async def run_retry_stage0_batch(
    config: OptionsConfig,
    limit: int = 100,
    dry_run: bool = False,
) -> int:
    """Retries previously passed Stage 0 candidates through the upgraded DiagnosticAlphaOptimizer."""
    store = OptionsStore(database_url=config.database_url)
    candidates = store.get_stage0_passed_candidates(limit=limit)
    log.info("Loaded %d historical Stage 0 passed candidates for re-optimization.", len(candidates))

    if not candidates:
        log.warning("No Stage 0 passed candidates found in database.")
        return 0

    if dry_run:
        log.info("DRY RUN MODE: Listing Stage 0 candidates to be re-optimized:")
        for i, c in enumerate(candidates, 1):
            log.info("  [%d] (%s) %s -> %s", i, c.generation_source, c.archetype_name, c.expression[:100])
        return len(candidates)

    send_telegram_startup(config, mode=f"Stage 0 Re-Optimization ({len(candidates)} candidates)")

    store = OptionsStore(database_url=config.database_url)
    client = BrainClient(
        username=config.brain_username,
        password=config.brain_password,
        max_concurrent_sims=config.brain_max_concurrent_sims,
        db=store.db,
    )
    client.authenticate()
    sweep_engine = SweepEngine(client, config)

    passed_count = 0
    total_evaluated = 0
    start_time = time.time()
    queue: asyncio.Queue[OptionCandidate] = asyncio.Queue()
    for c in candidates:
        queue.put_nowait(c)

    async def worker(worker_id: int):
        nonlocal passed_count, total_evaluated
        while not queue.empty():
            elapsed = time.time() - start_time
            if elapsed > config.run_time_budget_seconds:
                log.warning("Retry Worker %d: Run time budget (%ds) reached. Stopping.", worker_id, config.run_time_budget_seconds)
                break
            try:
                c = queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            total_evaluated += 1
            log.info("\n[Retry Worker %d | Cand %d/%d] Re-optimizing [%s]: %s",
                     worker_id, total_evaluated, len(candidates), c.archetype_name, c.expression[:60])
            try:
                qualified = await run_candidate(c, sweep_engine, client, store, config, force_optimize=True)
                if qualified:
                    passed_count += 1
            except Exception as exc:
                log.error("Error optimizing Stage 0 passer [%s]: %s", c.expression[:50], exc, exc_info=True)
            finally:
                queue.task_done()

    concurrency = min(config.brain_max_concurrent_sims, 3)
    log.info("Starting %d concurrent retry workers with %ds time budget...", concurrency, config.run_time_budget_seconds)
    workers = [asyncio.create_task(worker(i + 1)) for i in range(concurrency)]

    try:
        await asyncio.gather(*workers)
    except Exception as e:
        log.error("Re-optimization pool encountered exception: %s", e)
    finally:
        log.info("\nRe-optimization completed: %d passed / %d evaluated.", passed_count, total_evaluated)
        try:
            if passed_count > 0 or os.environ.get("NOTIFY_EVERY_BATCH", "false").lower() == "true":
                stats = store.get_options_stats()
                send_telegram_batch_summary(passed_count, total_evaluated, config, stats=stats)
        except Exception as summary_err:
            log.warning("Failed to send Telegram summary: %s", summary_err)

        # 24-hour interval drip submission check
        try:
            drip = DripSubmitter(client, store, config)
            await drip.check_and_drip()
        except Exception as drip_err:
            log.warning("Drip submitter check failed: %s", drip_err)

    return passed_count


def main():
    parser = argparse.ArgumentParser(description="WorldQuant BRAIN Options Alpha Pipeline")
    parser.add_argument("--single-batch", action="store_true", help="Run a single bounded batch and exit (Render cron mode)")
    parser.add_argument("--daemon", action="store_true", help="Run continuously in a loop")
    parser.add_argument("--dry-run", action="store_true", help="Generate candidates and verify without simulating")
    parser.add_argument("--candidates", type=int, default=0, help="Override candidate count per batch")
    parser.add_argument("--retry-stage0", action="store_true", help="Retry historical Stage 0 passing candidates through upgraded optimizer")
    parser.add_argument("--limit", type=int, default=2, help="Max Stage 0 candidates to retry (default: 2)")
    parser.add_argument("--test-telegram", action="store_true", help="Send a test notification to Telegram and exit")
    parser.add_argument("--stats", action="store_true", help="Display daily and all-time options alpha statistics")
    parser.add_argument("--drip", action="store_true", help="Run 24-hour drip submitter check and exit")
    parser.add_argument("--archetype", type=str, default=os.environ.get("ARCHETYPE", ""), help="Target specific archetype family (e.g. breakeven, skew, term_structure, forward_basis,pcr_flow)")
    args = parser.parse_args()

    config = OptionsConfig.from_env()

    if args.drip:
        log.info("Checking 24-hour drip submission window...")
        store = OptionsStore(database_url=config.database_url)
        client = BrainClient(
            username=config.brain_username,
            password=config.brain_password,
            max_concurrent_sims=1,
            db=store.db,
        )
        client.authenticate()
        drip = DripSubmitter(client, store, config)
        drip_ok, aid, msg = asyncio.run(drip.check_and_drip())
        log.info("Drip check finished: %s (alpha: %s, msg: %s)", drip_ok, aid, msg)
        return

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
        print(f"  • All-Time Stage 0 Passing: {stats.get('all_time_stage0_pass', 0)}")
        print(f"  • All-Time Qualified Pool:  {stats.get('all_time_pool_alphas', 0)}")
        print("=" * 55 + "\n")
        return

    if args.test_telegram:
        log.info("Sending test notification to Telegram...")
        success = send_telegram_startup(config, mode="Test Notification")
        log.info("Telegram test result: %s", "SUCCESS" if success else "FAILED")
        return

    # Option D Cluster Concurrency Mutex:
    # Ensure no two worker orgs simulate simultaneously across the single BRAIN account
    worker_id = f"{os.getenv('GITHUB_REPOSITORY_OWNER', 'local')}-{os.getpid()}"
    org_name = os.getenv("GITHUB_REPOSITORY_OWNER", "local")
    store = OptionsStore(database_url=config.database_url)
    db = store.db
    lock_acquired = False

    if not args.dry_run and db:
        lock_acquired = db.acquire_cluster_lock(
            org_name=org_name,
            worker_id=worker_id,
            archetype=args.archetype or "",
            timeout_seconds=900,
        )
        if not lock_acquired:
            log.warning(
                "Cluster Mutex Busy: Another worker is currently simulating on BRAIN. "
                "Gracefully yielding slot to strictly enforce the 3 max concurrent simulations limit."
            )
            return

    try:
        if args.retry_stage0:
            log.info("Starting Stage 0 re-optimization pipeline (Limit: %d)...", args.limit)
            asyncio.run(run_retry_stage0_batch(config, limit=args.limit, dry_run=args.dry_run))
            return

        batch_size = args.candidates if args.candidates > 0 else config.max_candidates_per_run
        log.info("Starting brain_options pipeline (Universe=%s, Delay=%d, MaxSims=%d)...",
                 config.universe, config.delay, config.brain_max_concurrent_sims)

        if args.daemon:
            log.info("Running in continuous daemon mode (Specialization: %s)...", args.archetype or "ALL")
            while True:
                try:
                    asyncio.run(run_batch(config, batch_size=batch_size, dry_run=args.dry_run, mode_label="Continuous Daemon", target_archetype=args.archetype or None))
                except Exception as e:
                    log.error("Batch encountered unhandled error: %s", e, exc_info=True)
                log.info("Sleeping 300 seconds before next batch...")
                time.sleep(300)
        else:
            asyncio.run(run_batch(config, batch_size=batch_size, dry_run=args.dry_run, mode_label="Single Batch", target_archetype=args.archetype or None))
    finally:
        if lock_acquired and db:
            db.release_cluster_lock(worker_id)


if __name__ == "__main__":
    main()
