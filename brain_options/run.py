"""
Master execution runner for brain_options.
Supports single bounded batch (GitHub Actions cron) or continuous daemon loop.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import logging
import math
import os
import sys
import threading
import time

from brain_options.config import OptionsConfig
from brain_options.core.client import BrainClient, SimMetrics, SimSettings
from brain_options.core.correlation import check_pool_correlation
from brain_options.core.drip import DripSubmitter
from brain_options.core.filter import evaluate_alpha_metrics
from brain_options.core.notifier import (
    check_and_send_hourly_health,
    send_telegram_alert,
    send_telegram_batch_summary,
    send_telegram_daily_digest,
    send_telegram_emergency_alert,
    send_telegram_health_check,
    send_telegram_startup,
    send_telegram_worker_batch_ping,
)
from brain_options.core.sweep import SweepEngine
from brain_options.llm.adapter import LLMAdapter
from brain_options.specialist.dedup import ASTDeduplicator
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


class ClusterLockHeartbeat:
    """
    Background daemon thread that touches the cluster lock every 60 seconds
    to guarantee in-flight workers (> 15 minutes) are never evicted as stale.
    """

    def __init__(self, db: Any, worker_id: str, interval_seconds: int = 60):
        self.db = db
        self.worker_id = worker_id
        self.interval = interval_seconds
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self):
        if not self.db or not getattr(self.db, "database_url", None):
            return
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name=f"heartbeat-{self.worker_id}",
        )
        self._thread.start()
        log.info("Started cluster lock heartbeat daemon for %s (interval: %ds).", self.worker_id, self.interval)

    def _run(self):
        while not self._stop_event.wait(self.interval):
            try:
                if self.db:
                    self.db.touch_cluster_lock(self.worker_id)
            except Exception as e:
                log.debug("Heartbeat touch exception: %s", e)

    def stop(self):
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
            log.info("Stopped cluster lock heartbeat daemon for %s.", self.worker_id)


async def run_candidate(
    candidate: OptionCandidate,
    sweep_engine: SweepEngine,
    client: BrainClient,
    store: OptionsStore,
    config: OptionsConfig,
    force_optimize: bool = False,
    deduplicator: Optional[ASTDeduplicator] = None,
) -> bool:
    """Executes the screening, diagnostic optimization, filtering, and alert pipeline for one candidate."""
    log.info("=" * 70)
    log.info("TESTING CANDIDATE [%s]: %s", candidate.archetype_name, candidate.expression)
    log.info("Hypothesis: %s", candidate.hypothesis)

    # 0. Pre-Simulation In-Memory Deduplication Gate (Pillar 2)
    if deduplicator and deduplicator.is_duplicate(candidate.expression):
        log.warning(
            "[-] PRE-SIMULATION DEDUP GATE: Expression has duplicate AST operator structure to an existing evaluated alpha. Skipping simulation."
        )
        store.record_evaluated_candidate(
            candidate,
            stage="PRE_SCREEN",
            status="DUPLICATE_AST",
            metrics=SimMetrics(sharpe=0.0, fitness=0.0, turnover=0.0),
        )
        return False
    if deduplicator:
        deduplicator.add(candidate.expression)

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
        max_steps=8,
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

    # 3. Mandatory Pre-Qualification Self-Correlation & Checklist Gates Verification
    max_corr = 0.0
    pnl_series: dict[str, float] = {}
    top_corr_partner = "existing_pool"

    if best_metrics.alpha_id:
        try:
            pnl_series = await client.get_alpha_pnl(best_metrics.alpha_id)
            pool_pnl = store.load_pool_pnl_series()
            if pool_pnl and pnl_series:
                _, max_corr = check_pool_correlation(pnl_series, pool_pnl, max_threshold=0.70)
        except Exception as pnl_err:
            log.debug("Could not complete pool correlation fetch for alpha %s: %s", best_metrics.alpha_id, pnl_err)

        # Check BRAIN platform live self-correlation endpoint
        try:
            sess = client._get_session()
            c_resp = await sess.retry("GET", f"https://api.worldquantbrain.com/alphas/{best_metrics.alpha_id}/correlations/self", max_tries=2)
            if c_resp and c_resp.status_code == 200 and c_resp.text.strip():
                c_data = json.loads(c_resp.text)
                platform_max = float(c_data.get("max", 0.0) or 0.0)
                if platform_max > max_corr:
                    max_corr = platform_max
                records = c_data.get("records") or []
                if records and len(records[0]) > 0:
                    top_corr_partner = records[0][0]
        except Exception as c_err:
            log.debug("Could not complete platform self-correlation check for alpha %s: %s", best_metrics.alpha_id, c_err)

    n_variants_tried = getattr(best_cand, "n_variants_tried", 1) or 1
    base_id = getattr(best_cand, "base_alpha_id", None) or ""

    cand_dict = {
        "expression": best_cand.expression,
        "archetype": best_cand.archetype_name,
        "hypothesis": best_cand.hypothesis,
        "source": best_cand.generation_source,
        "sharpe": best_metrics.sharpe,
        "fitness": best_metrics.fitness,
        "turnover": best_metrics.turnover,
        "returns": best_metrics.annualized_return,
        "drawdown": best_metrics.max_drawdown,
        "margin": best_metrics.margin,
        "max_correlation": max_corr,
        "n_variants_tried": n_variants_tried,
        "base_alpha_id": base_id,
    }

    # Mandatory Gate 0: Multiple-Hypothesis Testing Defense (Deflated Sharpe Hurdle)
    # When multiple variants are generated from a single base alpha (e.g. decorrelation salvage),
    # scale the minimum required Sharpe to guard against selection bias eating the scarce 3/day submission quota.
    if best_cand.generation_source == "decorrelator" and n_variants_tried > 1:
        min_required_sharpe = max(1.25, round(1.25 + 0.04 * math.log(n_variants_tried), 4))
        if float(best_metrics.sharpe) < min_required_sharpe:
            rej_reason = (
                f"DEFLATED_SHARPE_FAIL: Sharpe {best_metrics.sharpe:.2f} < hurdle {min_required_sharpe:.2f} "
                f"(n_variants_tried={n_variants_tried} for base {base_id or 'unknown'})"
            )
            log.warning(
                "[-] ALPHA REJECTED BY MULTIPLE-TESTING DEFENSE: %s (%s). Protecting daily 3/day submission quota.",
                best_metrics.alpha_id,
                rej_reason,
            )
            store.record_evaluated_candidate(
                candidate,
                stage="RETRY_COMPLETED",
                status="REJECTED",
                metrics=best_metrics,
            )
            store.archive_rejected_alpha(best_metrics.alpha_id or "", rej_reason, cand_dict)
            return False
        else:
            log.info(
                "[+] MULTIPLE-TESTING DEFENSE PASSED: %s cleared Deflated Sharpe hurdle %.2f (Achieved: %.2f with N=%d variants for base %s)",
                best_metrics.alpha_id,
                min_required_sharpe,
                best_metrics.sharpe,
                n_variants_tried,
                base_id,
            )

    # Mandatory Gate 1: If max_corr >= 0.70, REJECT as CORRELATED
    if max_corr >= 0.70:
        corr_reason = f"High self-correlation {max_corr:.4f} >= 0.70 vs {top_corr_partner}"
        log.warning(
            "[-] ALPHA REJECTED BY SELF-CORRELATION GATE: %s (Max Corr=%.4f >= 0.70 vs %s). Moving to options_correlated_alphas.",
            best_metrics.alpha_id, max_corr, top_corr_partner
        )
        store.record_evaluated_candidate(
            candidate,
            stage="RETRY_COMPLETED",
            status="CORRELATED",
            metrics=best_metrics,
        )
        store.archive_correlated_alpha(
            best_metrics.alpha_id or "",
            reason=corr_reason,
            cand_data=cand_dict,
            max_corr=max_corr,
        )
        if store.db:
            store.db.penalize_learning_memory(best_cand.expression, penalty=-15.0, reason=corr_reason)
        return False

    # Mandatory Gate 2: Verify all platform checklist gates on BRAIN
    if best_metrics.alpha_id:
        try:
            sess = client._get_session()
            import json

            # 1. BRAIN computes SELF_CORRELATION asynchronously. Poll until no longer PENDING (up to 30s).
            alpha_data = None
            for attempt in range(8):
                chk_resp = await sess.retry("GET", f"https://api.worldquantbrain.com/alphas/{best_metrics.alpha_id}", max_tries=2)
                if chk_resp and chk_resp.status_code == 200:
                    alpha_data = chk_resp.json()
                    is_block = alpha_data.get("is") or {}
                    checks = is_block.get("checks") or []
                    pending_checks = [c.get("name") for c in checks if c.get("result") == "PENDING"]
                    if not pending_checks:
                        break
                await asyncio.sleep(2.0 + attempt * 0.5)

            if not alpha_data:
                log.warning("[-] Could not verify checklist from BRAIN for alpha %s. Rejecting as unverified.", best_metrics.alpha_id)
                return False

            is_block = alpha_data.get("is") or {}
            checks = is_block.get("checks") or []
            failed_gates = [c.get("name") for c in checks if c.get("result") == "FAIL"]
            pending_gates = [c.get("name") for c in checks if c.get("result") == "PENDING"]

            if failed_gates:
                rej_reason = f"CHECK_FAIL: {', '.join(failed_gates)}"
                log.warning("[-] ALPHA REJECTED BY PLATFORM GATE: %s (%s). Moving to options_rejected_alphas.", best_metrics.alpha_id, rej_reason)
                store.record_evaluated_candidate(candidate, stage="RETRY_COMPLETED", status="REJECTED", metrics=best_metrics)
                store.archive_rejected_alpha(best_metrics.alpha_id or "", rej_reason, cand_dict)
                return False

            if pending_gates:
                rej_reason = f"CHECK_TIMEOUT: {', '.join(pending_gates)} still PENDING after 30s"
                log.warning("[-] ALPHA REJECTED (TIMED OUT WAITING FOR PLATFORM): %s (%s).", best_metrics.alpha_id, rej_reason)
                store.record_evaluated_candidate(candidate, stage="RETRY_COMPLETED", status="REJECTED", metrics=best_metrics)
                store.archive_rejected_alpha(best_metrics.alpha_id or "", rej_reason, cand_dict)
                return False

            # Mandatory Gate 3: Live BRAIN platform self-correlation check against active submitted portfolio
            corr_url = f"https://api.worldquantbrain.com/alphas/{best_metrics.alpha_id}/correlations/self"
            live_corr_records = []
            for _ in range(5):
                try:
                    c_resp = await sess.retry("GET", corr_url, max_tries=2)
                    if c_resp and c_resp.status_code == 200 and c_resp.text.strip():
                        c_data = json.loads(c_resp.text)
                        live_corr_records = c_data.get("records") or []
                        if live_corr_records:
                            break
                except Exception as corr_err:
                    log.debug("Live self-correlation fetch attempt error: %s", corr_err)
                await asyncio.sleep(2.0)

            for r in live_corr_records:
                if len(r) > 5 and isinstance(r[5], (int, float)) and abs(float(r[5])) >= 0.70:
                    live_corr_val = float(r[5])
                    corr_against = r[0]
                    rej_reason = f"HIGH_LIVE_CORRELATION: |{live_corr_val:.2f}| >= 0.70 vs {corr_against}"
                    log.warning("[-] ALPHA REJECTED BY LIVE BRAIN SELF-CORRELATION: %s (%s). Moving to options_correlated_alphas.", best_metrics.alpha_id, rej_reason)
                    store.record_evaluated_candidate(candidate, stage="RETRY_COMPLETED", status="CORRELATED", metrics=best_metrics)
                    store.archive_correlated_alpha(best_metrics.alpha_id or "", rej_reason, cand_dict, max_corr=live_corr_val)
                    if hasattr(store, "db") and store.db:
                        store.db.penalize_learning_memory(best_cand.expression, penalty=-15.0, reason=rej_reason)
                    return False

            if live_corr_records:
                real_max_corr = max([abs(float(r[5])) for r in live_corr_records if len(r) > 5 and isinstance(r[5], (int, float))] or [0.0])
                max_corr = max(max_corr, real_max_corr)

        except Exception as gate_err:
            log.warning("[-] Platform gate verification error for %s: %s. Rejecting as unverified.", best_metrics.alpha_id, gate_err)
            return False

    # 4. Verified Uncorrelated Alpha Accepted & Saved to Clean Qualified Table
    log.info(
        "[SUCCESS] UNCORRELATED ALPHA QUALIFIED! Sharpe=%.2f, Fitness=%.2f, Turnover=%.2f%%, MaxCorr=%.4f (<0.70)",
        best_metrics.sharpe,
        best_metrics.fitness,
        best_metrics.turnover * 100,
        max_corr,
    )
    store.record_evaluated_candidate(
        candidate,
        stage="RETRY_COMPLETED",
        status="QUALIFIED",
        metrics=best_metrics,
    )
    store.save_passed_alpha(best_cand, best_settings, best_metrics, max_corr, pnl_series)
    send_telegram_alert(best_cand.expression, best_settings, best_metrics, max_corr, config, db=store)

    # Immediately submit straight up if enabled and daily target quota is not yet full
    if getattr(config, "enable_auto_submit", False):
        log.info("[AUTO-SUBMIT] Immediate submission triggered for qualified alpha %s", best_metrics.alpha_id)
        try:
            from brain_options.core.drip import DripSubmitter
            drip = DripSubmitter(client, store, config)
            sub_ok, sub_id, sub_msg = await drip.check_and_drip(force_catchup=True)
            log.info("[AUTO-SUBMIT] Immediate drip result: %s (alpha: %s, msg: %s)", sub_ok, sub_id, sub_msg)
        except Exception as sub_err:
            log.warning("[AUTO-SUBMIT] Immediate submission encountered an error: %s", sub_err)

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
    recently_submitted = db.get_recently_submitted_archetypes(limit=5) if db else []
    today_saturated = db.get_today_saturated_archetypes(max_per_day=1) if db else []
    saturated_archetypes = list(set(recently_submitted + today_saturated))
    top_exemplars = store.load_top_performing_exemplars(limit=5, min_sharpe=0.85, exclude_archetypes=saturated_archetypes)
    archetype_summary = store.load_archetype_performance_summary()

    llm_adapter = LLMAdapter(config)
    generator = OptionsGenerator(llm_adapter)
    generator.evaluated_expressions.update(evaluated)
    generator.deduplicator.populate(evaluated)

    arch_label = f" [Specialization: {target_archetype}]" if target_archetype else ""
    log.info("Loaded %d previously evaluated candidates into AST Deduplicator (%d structural hashes).", len(evaluated), len(generator.deduplicator))
    log.info("Loaded %d top RL exemplars and archetype summary for MAB weighting.%s", len(top_exemplars), arch_label)
    if today_saturated:
        log.info("Daily Archetype Quota Hit Today (Cap=1/day): %s -> Probability dropped to 0.02 to steer workers into unfilled channels.", today_saturated)
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
    send_telegram_startup(config, mode=mode_label, db=store)

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
                passed = await run_candidate(
                    cand,
                    sweep_engine,
                    client,
                    store,
                    config,
                    deduplicator=generator.deduplicator,
                )
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
            if passed_count > 0:
                stats = store.get_options_stats()
                send_telegram_batch_summary(passed_count, total_evaluated, config, stats=stats, db=store)
        except Exception as summary_err:
            log.warning("Failed to send Telegram batch summary: %s", summary_err)

        # Record real org run results in org_runs audit table
        org_name = os.getenv("GITHUB_REPOSITORY_OWNER", "local")
        try:
            store.record_org_run(
                org_name=org_name,
                archetype=target_archetype or "options",
                evals_done=total_evaluated,
                qualified=passed_count,
            )
        except Exception as org_rec_err:
            log.warning("Failed to record org run telemetry: %s", org_rec_err)

        # Worker completion ping to Telegram (Option B):
        # Always delivers real-time visibility on batch size, qualified alphas, and daily totals
        try:
            stats = store.get_options_stats()
            send_telegram_worker_batch_ping(
                org_name=org_name,
                passed_count=passed_count,
                total_evaluated=total_evaluated,
                archetype=target_archetype or "options",
                config=config,
                stats=stats,
                db=store,
            )
        except Exception as ping_err:
            log.warning("Failed to send worker batch completion ping: %s", ping_err)

        # Multi-org guaranteed hourly health heartbeat:
        # Ensures operator receives a health report every hour across whichever org is currently running
        try:
            check_and_send_hourly_health(store, config)
        except Exception as health_err:
            log.warning("Hourly health auto-check encountered error: %s", health_err)

        # Zero-qualified check: only alert if high volume (>= 150) has ZERO Stage 0 passes (indicating broken generator)
        try:
            stats = store.get_options_stats()
            if stats.get("today_evaluated", 0) >= 150 and stats.get("today_stage0_pass", 0) == 0:
                log.warning("Generation diagnostic warning: >=150 evaluated with 0 Stage 0 passes.")
        except Exception:
            pass

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

    send_telegram_startup(config, mode=f"Stage 0 Re-Optimization ({len(candidates)} candidates)", db=store)

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
            if passed_count > 0:
                stats = store.get_options_stats()
                send_telegram_batch_summary(passed_count, total_evaluated, config, stats=stats, db=store)
        except Exception as summary_err:
            log.warning("Failed to send Telegram summary: %s", summary_err)

        # Record real reopt results in org_runs audit table
        try:
            org_name = os.getenv("GITHUB_REPOSITORY_OWNER", "local")
            if total_evaluated > 0:
                store.record_org_run(
                    org_name=org_name,
                    archetype="reopt",
                    evals_done=total_evaluated,
                    qualified=passed_count,
                )
        except Exception as org_rec_err:
            log.warning("Failed to record reopt telemetry: %s", org_rec_err)

        # Multi-org guaranteed hourly health heartbeat
        try:
            check_and_send_hourly_health(store, config)
        except Exception as health_err:
            log.warning("Hourly health auto-check encountered error: %s", health_err)

        # 24-hour interval drip submission check
        try:
            drip = DripSubmitter(client, store, config)
            await drip.check_and_drip()
        except Exception as drip_err:
            log.warning("Drip submitter check failed: %s", drip_err)

    return passed_count


async def run_decorrelate_batch(
    config: OptionsConfig,
    limit: int = 2,
    dry_run: bool = False,
) -> int:
    """
    Decorrelation Optimizer Tier: Salvages high-Sharpe (>= 1.25) and high-Fitness (>= 1.00)
    alphas from options_correlated_alphas by applying systematic orthogonalization transforms.
    """
    from brain_options.specialist.decorrelator import DecorrelationEngine

    store = OptionsStore(database_url=config.database_url)
    salvageable = store.get_salvageable_correlated_alphas(min_sharpe=1.25, min_fitness=1.00, limit=limit)
    log.info("Loaded %d high-performing correlated alphas for orthogonalization salvage.", len(salvageable))

    if not salvageable:
        log.info("No salvageable correlated alphas (Sharpe >= 1.25, Fitness >= 1.00) found.")
        return 0

    engine = DecorrelationEngine()
    candidates: List[OptionCandidate] = []
    for item in salvageable:
        variants = engine.generate_orthogonal_variants(
            base_expr=item["expression"],
            archetype=item["archetype"],
            base_sharpe=item["sharpe"],
            colliding_id=item["alpha_id"],
        )
        log.info(
            "Generated %d orthogonal variants for base alpha %s (Base Sharpe=%.2f, n_variants_tried=%d)",
            len(variants),
            item["alpha_id"],
            item["sharpe"],
            len(variants),
        )
        candidates.extend(variants)

    if not candidates:
        return 0

    if dry_run:
        log.info("DRY RUN: Generated %d decorrelated candidates across %d base alphas:", len(candidates), len(salvageable))
        for i, c in enumerate(candidates, 1):
            log.info("  [%d] [Base: %s | Variants Tried: %d] %s -> %s",
                     i, getattr(c, "base_alpha_id", "N/A"), getattr(c, "n_variants_tried", 1), c.archetype_name, c.expression[:100])
        return len(candidates)

    send_telegram_startup(config, mode=f"Decorrelation Salvage ({len(candidates)} variants from {len(salvageable)} bases)", db=store)

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
                log.warning("Decorrelator Worker %d: Run time budget (%ds) reached. Stopping.", worker_id, config.run_time_budget_seconds)
                break
            try:
                c = queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            total_evaluated += 1
            log.info(
                "\n[Decorrelator Worker %d | Cand %d/%d] Evaluating [%s] (Base: %s, Variant Tried %d): %s",
                worker_id,
                total_evaluated,
                len(candidates),
                c.archetype_name,
                getattr(c, "base_alpha_id", "N/A"),
                getattr(c, "n_variants_tried", 1),
                c.expression[:60],
            )
            try:
                qualified = await run_candidate(c, sweep_engine, client, store, config, force_optimize=True)
                if qualified:
                    passed_count += 1
                    log.info(
                        "[Decorrelator] Qualified decorrelated candidate (Base: %s, Total Variants Tested: %d) successfully cleared all gates!",
                        getattr(c, "base_alpha_id", "N/A"),
                        getattr(c, "n_variants_tried", 1),
                    )
            except Exception as exc:
                log.error("Error evaluating decorrelated candidate [%s]: %s", c.expression[:50], exc, exc_info=True)
            finally:
                queue.task_done()

    concurrency = min(config.brain_max_concurrent_sims, 3)
    log.info("Starting %d concurrent decorrelator workers with %ds time budget...", concurrency, config.run_time_budget_seconds)
    workers = [asyncio.create_task(worker(i + 1)) for i in range(concurrency)]

    try:
        await asyncio.gather(*workers)
    except Exception as e:
        log.error("Decorrelation pool encountered exception: %s", e)
    finally:
        log.info("\nDecorrelation salvage completed: %d passed / %d evaluated.", passed_count, total_evaluated)
        try:
            if passed_count > 0:
                stats = store.get_options_stats()
                send_telegram_batch_summary(passed_count, total_evaluated, config, stats=stats, db=store)
        except Exception as summary_err:
            log.warning("Failed to send Telegram summary: %s", summary_err)

        try:
            org_name = os.getenv("GITHUB_REPOSITORY_OWNER", "local")
            if total_evaluated > 0:
                store.record_org_run(
                    org_name=org_name,
                    archetype="decorrelate",
                    evals_done=total_evaluated,
                    qualified=passed_count,
                )
        except Exception as org_err:
            log.debug("Failed to record org run: %s", org_err)

        # 24-hour interval drip submission check
        try:
            drip = DripSubmitter(client, store, config)
            await drip.check_and_drip()
        except Exception as drip_err:
            log.warning("Drip submitter check failed: %s", drip_err)

    return passed_count


def check_worker_schedule_slot(org_name: str, now_utc: Optional[datetime.datetime] = None) -> tuple[bool, str]:
    """
    Enforces strict non-overlapping execution across the 4 worker orgs during scheduled cron runs.
    48 runs/day across 4 worker orgs (1 run every 30 minutes, 24/7):
      - Org 1 (xtley-alpha-research-01): even hours, 00-29 min (e.g. 00:07, 02:07, ...)
      - Org 2 (xtley-alpha-research-02): even hours, 30-59 min (e.g. 00:37, 02:37, ...)
      - Org 3 (xtley-alpha-research-03): odd hours, 00-29 min (e.g. 01:07, 03:07, ...)
      - Org 4 (xtley-alpha-research-04): odd hours, 30-59 min (e.g. 01:37, 03:37, ...)
    """
    event_name = os.getenv("GITHUB_EVENT_NAME", "").strip().lower()
    if event_name != "schedule":
        return True, "dispatch_or_local"

    if now_utc is None:
        now_utc = datetime.datetime.now(datetime.timezone.utc)
    is_even_hour = (now_utc.hour % 2 == 0)
    is_first_half = (now_utc.minute < 30)

    slot_map = {
        (True, True): "xtley-alpha-research-01",
        (True, False): "xtley-alpha-research-02",
        (False, True): "xtley-alpha-research-03",
        (False, False): "xtley-alpha-research-04",
    }
    designated_org = slot_map.get((is_even_hour, is_first_half), "unknown")
    is_our_slot = (org_name == designated_org)
    return is_our_slot, designated_org


def main():
    parser = argparse.ArgumentParser(description="WorldQuant BRAIN Options Alpha Pipeline")
    parser.add_argument("--single-batch", action="store_true", help="Run a single bounded batch and exit (GitHub Actions cron mode)")
    parser.add_argument("--daemon", action="store_true", help="Run continuously in a loop")
    parser.add_argument("--dry-run", action="store_true", help="Generate candidates and verify without simulating")
    parser.add_argument("--candidates", type=int, default=0, help="Override candidate count per batch")
    parser.add_argument("--retry-stage0", action="store_true", help="Retry historical Stage 0 passing candidates through upgraded optimizer")
    parser.add_argument("--decorrelate", action="store_true", help="Run Decorrelation Optimizer to salvage high-Sharpe correlated alphas")
    parser.add_argument("--limit", type=int, default=2, help="Max candidates to process in retry/decorrelate modes (default: 2)")
    parser.add_argument("--test-telegram", action="store_true", help="Send a test notification to Telegram and exit")
    parser.add_argument("--stats", action="store_true", help="Display daily and all-time options alpha statistics")
    parser.add_argument("--drip", action="store_true", help="Run 24-hour drip submitter check and exit")
    parser.add_argument("--force-catchup", action="store_true", help="Bypass pacing interval to catch up on missed daily submission quota")
    parser.add_argument("--health", action="store_true", help="Send hourly health check notification to Telegram and exit")
    parser.add_argument("--daily-digest", action="store_true", help="Send end-of-day daily digest notification to Telegram and exit")
    parser.add_argument("--archetype", type=str, default=os.environ.get("ARCHETYPE", ""), help="Target specific archetype family (e.g. breakeven, skew, term_structure, forward_basis,pcr_flow)")
    args = parser.parse_args()

    config = OptionsConfig.from_env()

    if args.drip:
        log.info("Checking 24-hour drip submission window (force_catchup=%s)...", args.force_catchup)
        store = OptionsStore(database_url=config.database_url)
        client = BrainClient(
            username=config.brain_username,
            password=config.brain_password,
            max_concurrent_sims=1,
            db=store.db,
        )
        client.authenticate()
        drip = DripSubmitter(client, store, config)
        drip_ok, aid, msg = asyncio.run(drip.check_and_drip(force_catchup=args.force_catchup))
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

    if args.health:
        store = OptionsStore(database_url=config.database_url)
        stats = store.get_options_stats()
        org_activity = store.db.get_org_activity(hours=26)
        success = send_telegram_health_check(config, stats=stats, org_activity=org_activity, db=store)
        if success and hasattr(store, "claim_hourly_health_slot"):
            store.claim_hourly_health_slot(min_interval_minutes=0)
        log.info("Health check sent: %s", "OK" if success else "FAILED")
        return

    if getattr(args, "daily_digest", False):
        store = OptionsStore(database_url=config.database_url)
        stats = store.get_options_stats()
        success = send_telegram_daily_digest(config, stats=stats, db=store)
        log.info("Daily digest sent: %s", "OK" if success else "FAILED")
        return

    if args.test_telegram:
        log.info("Sending test notification to Telegram...")
        store = OptionsStore(database_url=config.database_url)
        success = send_telegram_startup(config, mode="Test Notification", db=store)
        log.info("Telegram test result: %s", "SUCCESS" if success else "FAILED")
        return

    org_name = os.getenv("GITHUB_REPOSITORY_OWNER", "local")

    # Worker schedule slot gate (strictly prevents cron collisions):
    # During scheduled cron executions, only the assigned worker runs in each 30-min window.
    # Manual dispatches (workflow_dispatch) and local runs bypass this check.
    is_slot, designated_org = check_worker_schedule_slot(org_name)
    if not is_slot:
        log.info(
            "Worker Slot Gate: Scheduled trigger at %s UTC belongs to designated worker '%s'. "
            "'%s' gracefully yielding slot to prevent multi-org collision.",
            datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M"),
            designated_org,
            org_name,
        )
        return

    # Option D Cluster Concurrency Mutex:
    # Ensure no two worker orgs simulate simultaneously across the single BRAIN account
    worker_id = f"{org_name}-{os.getpid()}"
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

    heartbeat_runner = None
    if lock_acquired and db:
        heartbeat_runner = ClusterLockHeartbeat(db, worker_id, interval_seconds=60)
        heartbeat_runner.start()

    try:
        if getattr(args, "decorrelate", False):
            log.info("Starting Decorrelation Optimizer salvage pipeline (Limit: %d)...", args.limit)
            asyncio.run(run_decorrelate_batch(config, limit=args.limit, dry_run=args.dry_run))
            return

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
    except Exception as exc:
        log.error("Fatal pipeline crash in main: %s", exc, exc_info=True)
        try:
            send_telegram_emergency_alert(
                error_summary=str(exc),
                config=config,
                context=f"{org_name} worker ({args.archetype or 'general'})",
                db=store,
            )
        except Exception as alert_err:
            log.warning("Could not send emergency Telegram alert: %s", alert_err)
        raise
    finally:
        if heartbeat_runner:
            heartbeat_runner.stop()
        if lock_acquired and db:
            db.release_cluster_lock(worker_id)
        # Explicit DB pool close to prevent psycopg_pool finalizer errors
        try:
            if db:
                db.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
