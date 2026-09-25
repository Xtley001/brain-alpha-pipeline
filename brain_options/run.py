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
    send_telegram_correlation_concentration_alert,
    send_telegram_daily_digest,
    send_telegram_emergency_alert,
    send_telegram_startup,
)
from brain_options.store.db import ClusterLockDBError
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


from brain_options.core.optimizer import DiagnosticAlphaOptimizer, calculate_rl_reward


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
        consecutive_failures = 0
        while not self._stop_event.wait(self.interval):
            try:
                if self.db:
                    ok = self.db.touch_cluster_lock(self.worker_id)
                    if ok:
                        consecutive_failures = 0
                    else:
                        consecutive_failures += 1
                        if consecutive_failures >= 3:
                            log.error(
                                "[HEARTBEAT] Cluster lock touch returned False for %d consecutive attempts "
                                "on worker %s. Lock heartbeat is dead.",
                                consecutive_failures, self.worker_id,
                            )
                            send_telegram_emergency_alert(
                                f"<b>CRITICAL: Cluster Lock Heartbeat Dead</b>\n\n"
                                f"Worker: <code>{self.worker_id}</code>\n"
                                f"Touch returned False for {consecutive_failures} consecutive attempts.\n"
                                f"Lock may be evicted — risk of concurrent simulation collision.",
                                context="Cluster Lock Heartbeat Dead",
                                cooldown_minutes=60,
                                db=self.db,
                            )
            except Exception as e:
                consecutive_failures += 1
                if consecutive_failures >= 3:
                    log.error(
                        "[HEARTBEAT] Cluster lock touch exception (attempt %d) on worker %s: %s",
                        consecutive_failures, self.worker_id, e, exc_info=True,
                    )
                    send_telegram_emergency_alert(
                        f"<b>CRITICAL: Cluster Lock Heartbeat Dead</b>\n\n"
                        f"Worker: <code>{self.worker_id}</code>\n"
                        f"Touch exception: <code>{e}</code> ({consecutive_failures} consecutive failures).\n"
                        f"Lock may expire.",
                        context="Cluster Lock Heartbeat Dead",
                        cooldown_minutes=60,
                        db=self.db,
                    )
                else:
                    log.warning("[HEARTBEAT] Cluster lock touch exception: %s", e)

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

    def _record_rl_outcome(is_qual: bool, m: SimMetrics):
        try:
            store.record_learning_memory(
                candidate=candidate,
                metrics=m,
                reward=calculate_rl_reward(m, is_qualified=is_qual),
                optimization_steps=0,
                parent_expression=getattr(candidate, "base_alpha_id", None),
                mutation_type=getattr(candidate, "operator_name", None),
                status="QUALIFIED" if is_qual else "REJECTED",
            )
        except Exception as lm_err:
            log.debug("Failed to record learning memory: %s", lm_err)

        if candidate.operator_name:
            try:
                store.record_strategy_operator_reward(
                    strategy_name=candidate.archetype_name,
                    operator_name=candidate.operator_name,
                    parameter_name="outcome",
                    parameter_val="qualified" if is_qual else "rejected",
                    reward=calculate_rl_reward(m, is_qualified=is_qual),
                    success=is_qual,
                )
            except Exception as e:
                log.warning("Failed to record strategy operator reward: %s", e)

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
        _record_rl_outcome(False, s0_metrics)
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
        _record_rl_outcome(False, best_metrics)
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
            _record_rl_outcome(False, best_metrics)
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
            corr_partner_alpha_id=top_corr_partner,
            decorrelation_attempts=getattr(candidate, "decorrelation_attempts", 0),
        )
        if store.db:
            store.db.penalize_learning_memory(best_cand.expression, penalty=-15.0, reason=corr_reason)
        # Correlation concentration alert: fire Telegram if one alpha is blocking
        # the majority of today's qualified candidates from reaching the pool.
        try:
            corr_stats = store.get_options_stats()
            today_corr = corr_stats.get("today_correlated", 0)
            top_blocker = corr_stats.get("top_corr_partner", "")
            top_blocker_cnt = corr_stats.get("top_corr_partner_count", 0)
            if today_corr >= 3 and top_blocker and top_blocker_cnt / today_corr > 0.70:
                send_telegram_correlation_concentration_alert(
                    blocking_partner=top_blocker,
                    collision_count=top_blocker_cnt,
                    total_corr_today=today_corr,
                    config=config,
                    db=store,
                )
        except Exception as _conc_err:
            log.debug("Concentration alert check skipped: %s", _conc_err)
        _record_rl_outcome(False, best_metrics)
        return False

    # Mandatory Gate 2: Verify all platform checklist gates on BRAIN
    if best_metrics.alpha_id:
        try:
            sess = client._get_session()
            import json

            # 1. BRAIN computes statistical checks asynchronously. Poll until non-correlation checks are no longer PENDING (up to 30s).
            alpha_data = None
            for attempt in range(8):
                chk_resp = await sess.retry("GET", f"https://api.worldquantbrain.com/alphas/{best_metrics.alpha_id}", max_tries=2)
                if chk_resp and chk_resp.status_code == 200:
                    alpha_data = chk_resp.json()
                    is_block = alpha_data.get("is") or {}
                    checks = is_block.get("checks") or []
                    pending_checks = [c.get("name") for c in checks if c.get("result") == "PENDING" and c.get("name") != "SELF_CORRELATION"]
                    if not pending_checks:
                        break
                await asyncio.sleep(2.0 + attempt * 0.5)

            if not alpha_data:
                log.warning("[-] Could not verify checklist from BRAIN for alpha %s. Rejecting as unverified.", best_metrics.alpha_id)
                _record_rl_outcome(False, best_metrics)
                return False

            is_block = alpha_data.get("is") or {}
            checks = is_block.get("checks") or []
            failed_gates = [c.get("name") for c in checks if c.get("result") == "FAIL"]
            # SELF_CORRELATION on BRAIN is a static placeholder that stays PENDING until submission; Gate 3 verifies true correlation
            pending_gates = [c.get("name") for c in checks if c.get("result") == "PENDING" and c.get("name") != "SELF_CORRELATION"]

            if failed_gates:
                rej_reason = f"CHECK_FAIL: {', '.join(failed_gates)}"
                log.warning("[-] ALPHA REJECTED BY PLATFORM GATE: %s (%s). Moving to options_rejected_alphas.", best_metrics.alpha_id, rej_reason)
                store.record_evaluated_candidate(candidate, stage="RETRY_COMPLETED", status="REJECTED", metrics=best_metrics)
                store.archive_rejected_alpha(best_metrics.alpha_id or "", rej_reason, cand_dict)
                _record_rl_outcome(False, best_metrics)
                return False

            if pending_gates:
                rej_reason = f"CHECK_TIMEOUT: {', '.join(pending_gates)} still PENDING after 30s"
                log.warning("[-] ALPHA REJECTED (TIMED OUT WAITING FOR PLATFORM): %s (%s).", best_metrics.alpha_id, rej_reason)
                store.record_evaluated_candidate(candidate, stage="RETRY_COMPLETED", status="REJECTED", metrics=best_metrics)
                store.archive_rejected_alpha(best_metrics.alpha_id or "", rej_reason, cand_dict)
                _record_rl_outcome(False, best_metrics)
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
                    store.archive_correlated_alpha(
                        best_metrics.alpha_id or "",
                        rej_reason,
                        cand_dict,
                        max_corr=live_corr_val,
                        corr_partner_alpha_id=corr_against,
                        decorrelation_attempts=getattr(candidate, "decorrelation_attempts", 0),
                    )
                    if hasattr(store, "db") and store.db:
                        store.db.penalize_learning_memory(best_cand.expression, penalty=-15.0, reason=rej_reason)
                    _record_rl_outcome(False, best_metrics)
                    return False

            if live_corr_records:
                real_max_corr = max([abs(float(r[5])) for r in live_corr_records if len(r) > 5 and isinstance(r[5], (int, float))] or [0.0])
                max_corr = max(max_corr, real_max_corr)

        except Exception as gate_err:
            log.warning("[-] Platform gate verification error for %s: %s. Rejecting as unverified.", best_metrics.alpha_id, gate_err)
            _record_rl_outcome(False, best_metrics)
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
    if not getattr(config, "enable_auto_submit", False):
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

    _record_rl_outcome(True, best_metrics)
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
    try:
        evaluated = store.load_evaluated_expressions()
    except Exception as e:
        log.error("Failed to load evaluated expressions in run_batch: %s", e, exc_info=True)
        send_telegram_emergency_alert(
            f"<b>CRITICAL: Deduplicator DB Seed Failure</b>\n\n"
            f"Failed to load evaluated expressions: <code>{e}</code>\n"
            f"AST Deduplicator starting blind.",
            context="Deduplicator DB Seed Failure",
            cooldown_minutes=60,
            db=db,
        )
        evaluated = set()
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
        log.error("Worker pool encountered exception: %s", e, exc_info=True)
        send_telegram_emergency_alert(
            f"<b>CRITICAL: Worker Pool Exception</b>\n\n"
            f"Worker pool asyncio.gather raised exception: <code>{e}</code>",
            context="Worker Pool Exception",
            cooldown_minutes=60,
            db=store,
        )
    finally:
        log.info("\nBatch completed: %d passed / %d evaluated.", passed_count, total_evaluated)
        if not dry_run and total_evaluated == 0:
            log.error("All workers yielded without evaluating or simulating any candidate (total miss — zero throughput)")
            send_telegram_emergency_alert(
                f"<b>CRITICAL: Worker Pool Zero Throughput</b>\n\n"
                f"All {num_workers} candidate workers exited with 0 candidates evaluated. Total simulation miss.",
                context="Worker Pool Zero Throughput",
                cooldown_minutes=60,
                db=store,
            )
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

        # NOTE: send_telegram_batch_summary (above) already covers the qualified-batch
        # notification. send_telegram_worker_batch_ping was redundant — same info,
        # double message — so it's removed to reduce noise and rate-limit pressure.

        # Zero Stage-0 pass alert — if >150 alphas evaluated with zero passing
        # the lowest bar, the generator is broken (LLM failure, template bug, etc.).
        # This warrants an immediate Telegram emergency, not just a log line.
        try:
            stats = store.get_options_stats()
            if stats.get("today_evaluated", 0) >= 150 and stats.get("today_stage0_pass", 0) == 0:
                log.warning("[CRITICAL] Generation diagnostic: >=150 evaluated with 0 Stage 0 passes.")
                send_telegram_emergency_alert(
                    error_summary=f"{stats.get('today_evaluated', 0)} candidates evaluated today with 0 passing Stage 0. Generator may be producing invalid expressions (LLM failure or template regression).",
                    config=config,
                    context="Generator Zero-Yield Diagnostic",
                    db=store,
                )
        except Exception:
            pass

        # 24-hour interval drip submission check
        try:
            drip = DripSubmitter(client, store, config)
            await drip.check_and_drip()
        except Exception as drip_err:
            log.warning("Drip submitter check failed: %s", drip_err)
            # Drip submitter crash is serious — alphas will accumulate unsubmitted.
            # Fire Telegram so the issue is visible without reading logs.
            try:
                send_telegram_emergency_alert(
                    error_summary=str(drip_err),
                    config=config,
                    context="Drip Submitter Exception",
                    db=store,
                )
            except Exception:
                pass

        # Opportunistic hourly health heartbeat — piggybacks on the discovery run so the
        # health ping doesn't depend solely on health.yml cron (which GH can delay 20-60min).
        # The atomic DB slot ensures exactly one ping per hour even with 4 concurrent workers.
        try:
            check_and_send_hourly_health(
                store,
                config,
                min_interval_minutes=55,
                active_strategy=target_archetype,
            )
        except Exception as health_err:
            log.debug("Opportunistic health check skipped: %s", health_err)
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
        log.error("Re-optimization pool encountered exception: %s", e, exc_info=True)
        send_telegram_emergency_alert(
            f"<b>CRITICAL: Stage 0 Retry Pool Exception</b>\n\n"
            f"Re-optimization pool crashed with exception: <code>{e}</code>",
            context="Stage 0 Retry Exception",
            cooldown_minutes=60,
            db=store.db,
        )
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
    org_name = os.getenv("GITHUB_REPOSITORY_OWNER", "local")

    # If running on primary org, activate cluster blitz mode to pause background workers
    if store.db and org_name == "Xtley001":
        store.db.set_blitz_mode(True, hours=12)

    salvageable = store.get_salvageable_correlated_alphas(min_sharpe=1.25, min_fitness=1.00, limit=limit)
    log.info("Loaded %d high-performing correlated alphas for orthogonalization salvage.", len(salvageable))

    if not salvageable:
        log.info("No salvageable correlated alphas (Sharpe >= 1.25, Fitness >= 1.00) found.")
        if store.db and org_name == "Xtley001":
            store.db.set_blitz_mode(False)
        return 0

    engine = DecorrelationEngine()
    candidates: List[OptionCandidate] = []
    for item in salvageable:
        base_id = item["alpha_id"]
        partner_id = item.get("corr_partner_alpha_id")
        attempts = item.get("decorrelation_attempts", 0)

        # Check pair blacklist before spending simulation budget
        if store.db and store.db.is_pair_blacklisted(base_id, partner_id):
            log.warning("Skipping blacklisted pair: base %s vs partner %s (attempts >= 2 in cooldown window)", base_id, partner_id)
            continue

        variants = engine.generate_orthogonal_variants(
            base_expr=item["expression"],
            archetype=item["archetype"],
            base_sharpe=item["sharpe"],
            colliding_id=base_id,
            corr_partner_id=partner_id,
            decorrelation_attempts=attempts + 1,
        )
        log.info(
            "Generated %d orthogonal variants for base alpha %s (vs %s, attempts=%d, Base Sharpe=%.2f)",
            len(variants),
            base_id,
            partner_id or "unknown",
            attempts + 1,
            item["sharpe"],
        )
        candidates.extend(variants)

    if not candidates:
        log.info("No actionable decorrelation candidates after blacklist/cooldown filtering.")
        if store.db and org_name == "Xtley001":
            store.db.set_blitz_mode(False)
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

        if store.db and os.getenv("GITHUB_REPOSITORY_OWNER", "local") == "Xtley001":
            store.db.set_blitz_mode(False)

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
    if event_name != "schedule" or org_name == "Xtley001" or org_name == "local":
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



def validate_environment(config: OptionsConfig) -> None:
    """
    Validates essential environment configuration and alerts immediately on critical issues:
    - Point 46: Missing DATABASE_URL
    - Point 47: Missing BRAIN_USERNAME or BRAIN_PASSWORD
    - Point 48: Missing TELEGRAM_BOT_TOKEN
    - Point 49: Missing all LLM API keys
    - Point 50: ENABLE_AUTO_SUBMIT=true but DRIP_MAX_DAILY <= 0
    """
    # 46. Missing DATABASE_URL
    if not config.database_url:
        log.error("[CONFIG] Missing DATABASE_URL at startup. Persistent state, dedup, and cluster locks will fail.")
        send_telegram_emergency_alert(
            "<b>CRITICAL: Missing DATABASE_URL</b>\n\n"
            "DATABASE_URL is not configured at startup. Pipeline is running without database persistence.",
            context="Config Missing DATABASE_URL",
            cooldown_minutes=60,
        )

    # 47. Missing BRAIN credentials
    if not config.brain_username or not config.brain_password:
        log.error("[CONFIG] Missing BRAIN_USERNAME or BRAIN_PASSWORD at startup. Simulations will fail auth.")
        send_telegram_emergency_alert(
            "<b>CRITICAL: Missing BRAIN Credentials</b>\n\n"
            "BRAIN_USERNAME or BRAIN_PASSWORD is not configured.",
            context="Config Missing BRAIN Auth",
            cooldown_minutes=60,
        )

    # 48. Missing TELEGRAM_BOT_TOKEN
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not bot_token or not chat_id:
        log.error("[CONFIG] Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID at startup. Telegram alerts are silenced.")

    # 49. Missing LLM keys (Groq, Cerebras, OpenRouter, Gemini)
    groq_keys = [k for k in [
        os.getenv("GROQ_API_KEY"), os.getenv("GROQ_API_KEY_2"),
        os.getenv("GROQ_API_KEY_3"), os.getenv("GROQ_API_KEY_4"),
    ] if k and k.strip()]
    openrouter_keys = [k for k in [
        os.getenv("OPENROUTER_API_KEY"), os.getenv("OPENROUTER_API_KEY_2"),
        os.getenv("OPENROUTER_API_KEY_3"), os.getenv("OPENROUTER_API_KEY_4"),
    ] if k and k.strip()]
    other_llm_keys = [k for k in [
        os.getenv("CEREBRAS_API_KEY"), os.getenv("GEMINI_API_KEY")
    ] if k and k.strip()]
    total_llm_keys = len(groq_keys) + len(openrouter_keys) + len(other_llm_keys)
    if total_llm_keys == 0:
        log.error("[CONFIG] Missing LLM API keys: all Groq, OpenRouter, Cerebras, and Gemini keys are absent.")
        send_telegram_emergency_alert(
            "<b>CRITICAL: Missing LLM API Keys</b>\n\n"
            "No Groq, OpenRouter, Cerebras, or Gemini API keys found. Pipeline will rely solely on templates and procedural fallbacks.",
            context="Config Missing LLM Keys",
            cooldown_minutes=120,
        )

    # 50. ENABLE_AUTO_SUBMIT=true but DRIP_MAX_DAILY <= 0
    if config.enable_auto_submit and config.drip_max_daily <= 0:
        log.error("[CONFIG] ENABLE_AUTO_SUBMIT=true but DRIP_MAX_DAILY <= 0 (%d). Alphas will never be submitted.", config.drip_max_daily)
        send_telegram_emergency_alert(
            f"<b>CRITICAL: Submissions Permanently Disabled</b>\n\n"
            f"ENABLE_AUTO_SUBMIT is true, but DRIP_MAX_DAILY is {config.drip_max_daily}. Submission window is permanently blocked.",
            context="Config Drip Cap Zero",
            cooldown_minutes=120,
        )


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
    parser.add_argument("--strategy", type=str, default=os.environ.get("STRATEGY", ""), help="Target specific modular strategy (e.g. term_structure, pcr_flow, short_interest, etc.)")
    args = parser.parse_args()

    # Consolidate strategy / archetype selector
    active_strategy = (args.strategy or args.archetype or os.environ.get("STRATEGY", "") or os.environ.get("ARCHETYPE", "")).strip() or None

    config = OptionsConfig.from_env()
    validate_environment(config)

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
        # Use check_and_send_hourly_health: atomically claims the DB slot BEFORE sending
        # to prevent duplicate pings when health.yml fires multiple concurrent runners.
        # min_interval_minutes=0 so a manual --health dispatch always goes through.
        sent = check_and_send_hourly_health(
            store,
            config,
            min_interval_minutes=0,
            active_strategy=active_strategy,
        )
        log.info("Health check sent: %s", "OK" if sent else "SKIPPED (slot already claimed)")
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
    store = OptionsStore(database_url=config.database_url)
    db = store.db

    # Blitz Mode Check: If primary org (Xtley001) is running a Decorrelation Blitz,
    # all background worker orgs immediately yield 100% of the BRAIN simulation allocation.
    if org_name != "Xtley001" and db and hasattr(db, "is_blitz_active") and db.is_blitz_active():
        log.info(
            "Decorrelation Blitz Active on primary org: '%s' gracefully yielding all simulation slots.",
            org_name,
        )
        return

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
        # retry-stage0 is a lightweight pre-step that runs before --single-batch
        # in the same GH matrix job. If another worker is busy, yield immediately —
        # don't burn 2 minutes of the job's time budget waiting. The main batch step
        # will acquire the lock once the pre-step exits cleanly.
        # For all other modes on the primary org, wait up to 120s (12 × 10s).
        is_retry_prestep = args.retry_stage0
        max_lock_attempts = 1 if is_retry_prestep else (12 if org_name == "Xtley001" else 1)

        # --- Stale lock detection ---
        # If a lock is being held for >60 min the heartbeat is almost certainly dead.
        # Warn loudly so the operator can clear it manually or wait for auto-expiry.
        try:
            stale_age_sql = """
                SELECT EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - heartbeat)) / 60.0
                FROM cluster_run_lock
                WHERE heartbeat IS NOT NULL
                ORDER BY heartbeat ASC LIMIT 1;
            """
            with db._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(stale_age_sql)
                    row = cur.fetchone()
            if row and row[0] is not None:
                age_minutes = float(row[0])
                if age_minutes > 60:
                    log.warning(
                        "[STALE LOCK] Cluster lock has not been refreshed for %.0f minutes. "
                        "The holding worker may have crashed. Lock will auto-expire at 15min mark, "
                        "but this lock is %.0f minutes old — it may already be stale.",
                        age_minutes, age_minutes,
                    )
                    send_telegram_emergency_alert(
                        error_summary=f"Cluster lock held for {age_minutes:.0f} minutes without heartbeat refresh. All workers are blocked. Manual DELETE FROM cluster_run_lock; may be needed.",
                        config=config,
                        context="Stale Cluster Lock Detected",
                        db=store,
                        cooldown_minutes=120,  # alert at most every 2h for stale lock
                    )
        except Exception as stale_err:
            log.debug("Stale lock check failed: %s", stale_err)

        # --- Check for migration failures and alert ---
        # Filter out benign migration failures (IF NOT EXISTS no-ops, unique index on
        # duplicate data, already-existing columns) — these fire every run and are
        # known data-quality issues that don't affect operation. Only truly unexpected
        # failures (wrong column type, constraint violation on a NEW table) warrant alert.
        _BENIGN_MIGRATION_PATTERNS = [
            "already exists",
            "could not create unique index",
            "does not exist",
            "syntax error",  # split-on-semicolon artifact from comment-only blocks
        ]
        try:
            critical_failures = getattr(db, "_critical_migration_failures", None)
            if critical_failures is None:
                failures = getattr(db, "_migration_failures", [])
                critical_failures = [
                    (s, e) for s, e in failures
                    if not any(pat in e.lower() for pat in _BENIGN_MIGRATION_PATTERNS)
                ]
            benign_failures = getattr(db, "_benign_migration_failures", [])
            if benign_failures:
                log.info("[SCHEMA] %d migration statement(s) skipped as benign (already exists / duplicate data).", len(benign_failures))
            if critical_failures:
                summary = "; ".join(f"{s[:40]}: {e[:50]}" for s, e in critical_failures[:3])
                send_telegram_emergency_alert(
                    error_summary=f"{len(critical_failures)} unexpected DB migration(s) failed: {summary}",
                    config=config,
                    context="Schema Migration Failure",
                    db=store,
                    cooldown_minutes=360,  # 6h — same schema error fires every run until fixed
                )
        except Exception:
            pass

        lock_db_error = False
        for attempt in range(max_lock_attempts):
            try:
                lock_acquired = db.acquire_cluster_lock(
                    org_name=org_name,
                    worker_id=worker_id,
                    archetype=args.archetype or "",
                    timeout_seconds=18000 if getattr(args, "decorrelate", False) else 900,
                )
            except ClusterLockDBError as lock_err:
                # DB-level failure — distinct from genuine lock contention.
                # Use a stable context key (no attempt number) so the DB dedup
                # across all 4 workers correctly suppresses repeated alerts.
                lock_db_error = True
                log.warning(
                    "[LOCK DB ERROR] acquire_cluster_lock raised a DB exception (attempt %d/%d): %s",
                    attempt + 1, max_lock_attempts, lock_err,
                )
                try:
                    send_telegram_emergency_alert(
                        error_summary=str(lock_err),
                        config=config,
                        context="Cluster Lock DB Error",  # stable key — no attempt number
                        db=store,
                        cooldown_minutes=60,  # 60min — lock errors are transient, alert each hour max
                    )
                except Exception:
                    pass
                break  # No point retrying a DB-level error
            if lock_acquired:
                break
            if attempt < max_lock_attempts - 1:
                log.info("Primary org waiting for active worker to yield simulation lock (attempt %d/%d)...", attempt + 1, max_lock_attempts)
                time.sleep(10)

        # Primary org blitz priority: force override if still held after waiting
        if not lock_acquired and org_name == "Xtley001" and getattr(args, "decorrelate", False):
            log.warning("Primary org blitz overriding active lock to take priority.")
            try:
                with db._get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM cluster_run_lock;")
                    conn.commit()
                lock_acquired = db.acquire_cluster_lock(
                    org_name=org_name,
                    worker_id=worker_id,
                    archetype=args.archetype or "",
                    timeout_seconds=18000,
                )
            except Exception as e:
                log.warning("Failed to override lock: %s", e)

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
            try:
                asyncio.run(run_retry_stage0_batch(config, limit=args.limit, dry_run=args.dry_run))
            except Exception as e:
                log.error("run_retry_stage0_batch crashed: %s", e, exc_info=True)
                send_telegram_emergency_alert(
                    f"<b>CRITICAL: Stage 0 Retry Crash</b>\n\n"
                    f"run_retry_stage0_batch unhandled crash: <code>{e}</code>",
                    context="Stage 0 Retry Crash",
                    cooldown_minutes=60,
                    db=store,
                )
                raise
            return

        batch_size = args.candidates if args.candidates > 0 else config.max_candidates_per_run
        log.info("Starting brain_options pipeline (Universe=%s, Delay=%d, MaxSims=%d)...",
                 config.universe, config.delay, config.brain_max_concurrent_sims)

        if args.daemon:
            log.info("Running in continuous daemon mode (Specialization: %s)...", active_strategy or "ALL")
            while True:
                try:
                    asyncio.run(run_batch(config, batch_size=batch_size, dry_run=args.dry_run, mode_label="Continuous Daemon", target_archetype=active_strategy))
                except Exception as e:
                    log.error("Batch encountered unhandled error: %s", e, exc_info=True)
                    send_telegram_emergency_alert(
                        f"<b>CRITICAL: Run Batch Crash</b>\n\n"
                        f"run_batch crashed in daemon loop: <code>{e}</code>",
                        context="Run Batch Exception",
                        cooldown_minutes=60,
                        db=store,
                    )
                log.info("Sleeping 300 seconds before next batch...")
                time.sleep(300)
        else:
            try:
                asyncio.run(run_batch(config, batch_size=batch_size, dry_run=args.dry_run, mode_label="Single Batch", target_archetype=active_strategy))
            except Exception as e:
                log.error("Single batch crashed: %s", e, exc_info=True)
                send_telegram_emergency_alert(
                    f"<b>CRITICAL: Run Batch Crash</b>\n\n"
                    f"run_batch crashed in single batch mode: <code>{e}</code>",
                    context="Run Batch Exception",
                    cooldown_minutes=60,
                    db=store,
                )
                raise
    except Exception as exc:
        log.error("Fatal pipeline crash in main: %s", exc, exc_info=True)
        try:
            send_telegram_emergency_alert(
                error_summary=str(exc),
                config=config,
                context=f"{org_name} worker ({active_strategy or 'general'})",
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
