"""
Always-on entrypoint. Two internal loops in one process, per
the deployment architecture and throughput/scaling design:

  generation_loop(): keeps the `candidates` queue topped up (cheap,
      frequent, never blocks on BRAIN).
  simulation_loop(): a semaphore of size BRAIN_MAX_CONCURRENT_SIMS. Pulls
      the oldest pending candidate the instant a slot frees, and runs it
      through screen -> sweep -> filter -> correlation -> store -> alert.

Deploy target is a Render Background Worker (see render.yaml) — NOT a Cron
Job. This process is meant to run forever; it is not a batch script that
exits.

No BRAIN submit/create-alpha call exists anywhere in this file or anything
it imports. Submission is manual, always.
"""
from __future__ import annotations

import asyncio
import logging
import sys

from pipeline.brain.client import BrainClient
from pipeline.config import Config, MissingConfigError
from pipeline.db.repo import Repo
from pipeline.filter.correlation_check import compute_max_correlation, passes_correlation_gate
from pipeline.filter.local_filter import FilterThresholds
from pipeline.generator.llm_generator import mutate_candidate, propose_new_ideas
from pipeline.generator.template_generator import SEED_IDEAS, generate_template_candidates
from pipeline.llm.adapter import LLMAdapter, build_gemini_provider, build_groq_provider
from pipeline.notify.telegram_notify import TelegramNotifier
from pipeline.sweep.settings_sweep import run_staged_sweep

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("run_worker")

ORPHAN_RECLAIM_MINUTES = 30
GENERATION_INTERVAL_SECONDS = 180  # 3 min, within the 2-5 min band in 01_DEPLOYMENT_ARCHITECTURE.md
MAX_CORRELATION = 0.7


class Worker:
    def __init__(self, config: Config, repo: Repo, brain: BrainClient, notifier: TelegramNotifier, llm: LLMAdapter):
        self.config = config
        self.repo = repo
        self.brain = brain
        self.notifier = notifier
        self.llm = llm
        self.thresholds = FilterThresholds.from_env()
        self._sim_semaphore = asyncio.Semaphore(config.brain_max_concurrent_sims)
        # Round-robin pointer into SEED_IDEAS for the template tier. Persisted
        # via pipeline_meta (see _load_seed_cursor / _save_seed_cursor) rather
        # than left as a plain in-memory int, so a restart doesn't reset
        # candidate diversity back to category A every deploy (code review
        # §3.3). Restored lazily on first use of generation_loop, since Repo
        # needs a live DB connection that may not exist yet at __init__ time
        # in tests.
        self._seed_cursor = 0
        self._seed_cursor_loaded = False

    # --- generation loop ---

    async def generation_loop(self):
        if not self._seed_cursor_loaded:
            self._load_seed_cursor()
        while True:
            try:
                depth = self.repo.queue_depth()
                if depth < self.config.queue_target_depth:
                    await self._top_up_queue(self.config.queue_target_depth - depth)
            except Exception as e:  # noqa: BLE001
                log.exception("generation_loop error: %s", e)
                self._safe_operational_alert(f"generation_loop error: {e}")
            await asyncio.sleep(GENERATION_INTERVAL_SECONDS)

    def _load_seed_cursor(self) -> None:
        try:
            stored = self.repo.get_meta("seed_cursor")
            if stored is not None:
                self._seed_cursor = int(stored)
        except Exception:  # noqa: BLE001
            log.warning("could not load persisted seed_cursor, starting from 0", exc_info=True)
        self._seed_cursor_loaded = True

    async def _top_up_queue(self, needed: int) -> None:
        added = 0
        # Tier 1: template generator, cycling through seed ideas by category
        # order (build within a category before jumping around, per the
        # source doc's own build-order advice).
        template_candidates = generate_template_candidates()
        idx = 0
        while added < needed and template_candidates:
            c = template_candidates[self._seed_cursor % len(template_candidates)]
            self.repo.insert_candidate(c["expression"], c["category"], c["generation_tier"])
            self._seed_cursor += 1
            added += 1
            idx += 1
            if idx >= len(template_candidates):
                break  # exhausted this pass of the template pool; llm tier fills the rest

        # Persist the cursor after this pass so a restart resumes roughly
        # where it left off instead of re-biasing toward category A.
        try:
            self.repo.set_meta("seed_cursor", str(self._seed_cursor))
        except Exception:  # noqa: BLE001
            log.warning("could not persist seed_cursor", exc_info=True)

        # Tier 2: LLM-driven, only if template tier couldn't fill the gap
        # (keeps LLM calls to the volume actually needed, not spammed).
        #
        # propose_new_ideas() makes a real, blocking network call (and can
        # call a blocking time.sleep(...) internally on a 429 retry -- see
        # pipeline/llm/adapter.py). Run it in a worker thread rather than
        # awaiting it directly, so it can't freeze this coroutine's event
        # loop -- the same loop simulation_loop() shares via
        # asyncio.gather(...) in run_forever(). Without this, an LLM call
        # (or its retry sleep) stalls candidate claiming and simulation
        # dispatch for its entire duration (code review §1.2).
        remaining = needed - added
        if remaining > 0:
            try:
                proposals = await asyncio.to_thread(
                    propose_new_ideas,
                    self.llm,
                    self._pool_summary(),
                    self._recent_failure_log(),
                    min(remaining, 10),
                )
                for c in proposals:
                    self.repo.insert_candidate(c["expression"], c["category"], c["generation_tier"])
                    added += 1
            except Exception as e:  # noqa: BLE001
                log.warning("LLM proposal generation failed: %s", e)

    def _pool_summary(self) -> str:
        return f"{len(SEED_IDEAS)} seed idea families across A-H; ML combiner ideas (Section I) not yet built."

    def _recent_failure_log(self) -> str:
        return "See review_store/candidates status for recent rejections."

    # --- simulation loop ---

    async def simulation_loop(self):
        while True:
            # Don't claim a candidate into 'running' unless a sim slot is
            # actually free. `Semaphore.locked()` here is a plain gate on the
            # *claim*, separate from the semaphore acquired for the duration
            # of the real work in `_process_candidate_bounded` below -- it
            # exists so `claim_next_pending()` can't race ahead and pull a
            # large batch of candidates into 'running' while they just sit
            # queued in-process waiting for a slot (see the note in the code
            # review's §1.1 fix).
            if self._sim_semaphore.locked():
                await asyncio.sleep(0.5)
                continue
            candidate = self.repo.claim_next_pending()
            if candidate is None:
                await asyncio.sleep(2)
                continue
            asyncio.create_task(self._process_candidate_bounded(candidate))

    async def _process_candidate_bounded(self, candidate: dict) -> None:
        # The semaphore is acquired and held for the *entire* duration of
        # the real simulation work (not just around claiming + dispatching
        # the task), so it actually bounds how many `_process_candidate`
        # coroutines -- and therefore how many concurrent BRAIN simulate()
        # calls -- are in flight at once. Previously the `async with` block
        # wrapped `asyncio.create_task(...)`, which schedules and returns
        # immediately without waiting for the task to finish, so the
        # semaphore only ever gated the tiny window between claiming a
        # candidate and firing off its task -- it never limited real
        # concurrency (code review §1.1, the single most dangerous bug
        # found: unbounded concurrent BRAIN simulations risk rate-limiting
        # or account-level flagging).
        async with self._sim_semaphore:
            await self._process_candidate(candidate)

    async def _process_candidate(self, candidate: dict) -> None:
        candidate_id = candidate["id"]
        expression = candidate["expression"]
        try:
            # run_staged_sweep is sync and calls `simulate` repeatedly; each
            # call is run in its own thread with its own event loop so the
            # sweep module itself stays framework-agnostic and trivially
            # unit-testable with a plain synchronous fake.
            def simulate_sync(expr: str, settings):
                return asyncio.run(self.brain.simulate_one(expr, settings))

            outcome = await asyncio.to_thread(
                run_staged_sweep,
                expression,
                simulate_sync,
                self.thresholds,
                self.config.stage0_min_fitness,
                self.config.stage0_min_sharpe,
            )

            for run in outcome.runs:
                self.repo.insert_sweep_run(candidate_id, run.stage, run.settings, run.result)

            if outcome.rejected_at_stage0:
                self.repo.set_candidate_status(
                    candidate_id, "rejected_stage0",
                    stage0_fitness=outcome.runs[0].result.fitness,
                    stage0_sharpe=outcome.runs[0].result.sharpe,
                )
                return

            if not self.thresholds.passes(outcome.winning_result):
                self.repo.set_candidate_status(candidate_id, "rejected_filter")
                return

            # Correlation check vs. pool, on the *winning settings'* stream
            # (per the settings-sweep spec -- not the Stage 0
            # default settings' stream). `outcome.winning_result.alpha_id`
            # is the id BRAIN assigned to that specific simulation run (see
            # BrainClient.simulate_one -> _parse_sim_response), so this
            # fetches that exact run's daily-return series rather than
            # re-simulating. Previously this was hardcoded to an empty dict,
            # which made every candidate pass the correlation gate by
            # construction regardless of actual overlap with the pool (code
            # review §2.1).
            pool = self.repo.get_pool_returns()
            winning_alpha_id = outcome.winning_result.alpha_id
            if not winning_alpha_id:
                # Defensive only: a real BrainClient always populates
                # alpha_id from BRAIN's simulation response. Without one we
                # cannot compute a real correlation figure at all -- reject
                # explicitly here rather than falling through to
                # compute_max_correlation({}, pool), which would report
                # max_correlation=0.0 and pass by construction, silently
                # reproducing the exact no-op gate this fix replaces (code
                # review §2.1).
                log.warning(
                    "candidate %s: winning simulation result has no alpha_id, "
                    "cannot run the correlation check -- rejecting",
                    candidate_id,
                )
                self.repo.set_candidate_status(candidate_id, "rejected_correlation")
                return

            candidate_returns = await self.brain.get_alpha_pnl(winning_alpha_id)
            corr_result = compute_max_correlation(candidate_returns, pool)
            if not passes_correlation_gate(corr_result, MAX_CORRELATION):
                self.repo.set_candidate_status(candidate_id, "rejected_correlation")
                return

            row = {
                "candidate_id": candidate_id,
                "expression": expression,
                "delay": outcome.winning_settings.delay,
                "universe": outcome.winning_settings.universe,
                "neutralization": outcome.winning_settings.neutralization,
                "decay": outcome.winning_settings.decay,
                "truncation": outcome.winning_settings.truncation,
                "pasteurization": outcome.winning_settings.pasteurization,
                "nan_handling": outcome.winning_settings.nan_handling,
                "sharpe": outcome.winning_result.sharpe,
                "fitness": outcome.winning_result.fitness,
                "turnover": outcome.winning_result.turnover,
                "max_correlation": corr_result.max_correlation,
                "robust_count": outcome.robust_count,
                "sweep_total": outcome.sweep_total,
                "fragile": outcome.fragile,
            }
            review_id = self.repo.insert_review_store(row)
            self.repo.set_candidate_status(candidate_id, "passed")
            self.notifier.send_candidate_alert(row)
            self.repo.mark_telegram_sent(review_id)

        except Exception as e:  # noqa: BLE001
            log.exception("candidate %s failed: %s", candidate_id, e)
            self.repo.set_candidate_status(candidate_id, "pending")  # let it be retried
            self._safe_operational_alert(f"candidate {candidate_id} processing error: {e}")

    def _safe_operational_alert(self, message: str) -> None:
        try:
            self.notifier.send_operational_alert(message)
        except Exception:  # noqa: BLE001
            log.exception("failed to send operational alert")

    async def run_forever(self):
        reclaimed = self.repo.reclaim_orphaned_running(ORPHAN_RECLAIM_MINUTES)
        if reclaimed:
            log.info("reclaimed %d orphaned 'running' candidates back to 'pending'", reclaimed)
        await asyncio.gather(self.generation_loop(), self.simulation_loop())


def build_worker() -> Worker:
    config = Config.from_env()
    repo = Repo(config.database_url)
    repo.migrate()
    brain = BrainClient(config.brain_username, config.brain_password, config.brain_max_concurrent_sims)
    brain.authenticate()
    notifier = TelegramNotifier(config.telegram_bot_token, config.telegram_chat_id)
    llm = LLMAdapter(
        gemini_provider=build_gemini_provider(config.gemini_keys),
        groq_provider=build_groq_provider(config.groq_keys),
        usage_logger=repo.log_llm_usage,
        on_total_exhaustion=lambda tier: notifier.send_operational_alert(f"Both LLM providers exhausted on {tier} tier"),
    )
    return Worker(config, repo, brain, notifier, llm)


def main():
    try:
        worker = build_worker()
    except MissingConfigError as e:
        log.error("Startup aborted: %s", e)
        sys.exit(1)
    asyncio.run(worker.run_forever())


if __name__ == "__main__":
    main()
