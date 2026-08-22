"""
Bounded-batch entrypoint. `run_once()` does a single fixed-size pass of
work and returns -- it does NOT loop forever. Deploy target is a Render
**Cron Job** (see render.yaml), invoked on a schedule (default: every 10
minutes); each scheduled tick is a fresh process that runs `main()` and
exits.

One invocation of `run_once()`:

  1. Reclaims any candidate orphaned in 'running' by a previous invocation
     that got cut off mid-simulation (crash, or Render's cron timeout).
     This recovery path matters *more* under cron than it did under the
     old always-on worker, since a cron tick can be killed mid-run.
  2. Runs ONE pass of the queue top-up logic (template tier, then LLM tier
     if needed) -- what the old generation_loop() did once per 3-minute
     sleep, now done once per cron tick instead.
  3. Processes candidates in successive batches of up to
     BRAIN_MAX_CONCURRENT_SIMS, concurrently, `await`ed to completion each
     round (claim batch -> gather -> claim next batch -> ...), until either
     the pending queue is drained, MAX_CANDIDATES_PER_RUN is reached, or
     RUN_TIME_BUDGET_SECONDS of wall-clock time has elapsed -- whichever
     comes first. This still never runs more than BRAIN_MAX_CONCURRENT_SIMS
     `_process_candidate` coroutines concurrently (see
     `_process_candidate_bounded` below); only the old infinite polling
     wrapper around that bound is gone, not the bound itself.

This was previously an always-on process (two internal `while True:` loops,
`generation_loop()` and `simulation_loop()`, run concurrently via
`run_forever()`) deployed as a Render Background Worker. See the refactor
handoff doc for the full rationale: a Background Worker has no Render free
tier (cheapest is $7/mo), so this was restructured into a bounded batch job
that a Cron Job invocation can run to completion and exit -- trading
continuous, low-latency throughput for a much cheaper, coarser-grained
schedule. See run_worker refactor summary for the honest speed tradeoffs;
this is not a like-for-like replacement of the always-on worker's
throughput.

No BRAIN submit/create-alpha call exists anywhere in this file or anything
it imports. Submission is manual, always.
"""
from __future__ import annotations

import asyncio
import logging
import sys
import time
from dataclasses import dataclass, field

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
MAX_CORRELATION = 0.7


@dataclass
class RunSummary:
    """What one `run_once()` invocation did -- returned so `main()` can log
    it, and so tests can assert on behavior without scraping log output."""

    reclaimed: int = 0
    queue_depth_before: int = 0
    candidates_generated: int = 0
    candidates_processed: int = 0
    batches_run: int = 0
    stopped_reason: str = "queue_drained"  # or "max_candidates_reached" / "time_budget_exceeded"
    errors: list[str] = field(default_factory=list)


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
        # §3.3). Restored lazily on first use of _generation_step, since
        # Repo needs a live DB connection that may not exist yet at
        # __init__ time in tests.
        self._seed_cursor = 0
        self._seed_cursor_loaded = False

    # --- generation step (single pass; called once per run_once()) ---

    async def _generation_step(self) -> int:
        """One iteration of what generation_loop()'s body used to do inside
        its `while True`, minus the sleep -- the cron schedule now provides
        the "interval" externally instead of an internal
        `asyncio.sleep(GENERATION_INTERVAL_SECONDS)`. Returns the number of
        candidates actually added (0 if the queue was already at target, or
        on error)."""
        if not self._seed_cursor_loaded:
            self._load_seed_cursor()
        try:
            depth = self.repo.queue_depth()
            if depth < self.config.queue_target_depth:
                return await self._top_up_queue(self.config.queue_target_depth - depth)
            return 0
        except Exception as e:  # noqa: BLE001
            log.exception("generation step error: %s", e)
            self._safe_operational_alert(f"generation step error: {e}")
            return 0

    def _load_seed_cursor(self) -> None:
        try:
            stored = self.repo.get_meta("seed_cursor")
            if stored is not None:
                self._seed_cursor = int(stored)
        except Exception:  # noqa: BLE001
            log.warning("could not load persisted seed_cursor, starting from 0", exc_info=True)
        self._seed_cursor_loaded = True

    async def _top_up_queue(self, needed: int) -> int:
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
        # loop. Under the old always-on design this mattered because
        # simulation_loop() shared the same loop concurrently; under
        # run_once() the generation step and simulation batches run
        # sequentially within one invocation, but to_thread is kept anyway
        # since a blocking multi-second (or retry-sleep) call with no
        # yield point is bad practice in an async function regardless, and
        # it costs nothing here (code review §1.2).
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

        return added

    def _pool_summary(self) -> str:
        return f"{len(SEED_IDEAS)} seed idea families across A-H; ML combiner ideas (Section I) not yet built."

    def _recent_failure_log(self) -> str:
        return "See review_store/candidates status for recent rejections."

    # --- bounded simulation batches (replaces the old simulation_loop) ---

    def _claim_batch(self, max_size: int) -> list[dict]:
        """Claim up to `max_size` pending candidates via repeated
        `claim_next_pending()` calls, stopping early if the queue runs dry.
        `claim_next_pending()` does an atomic `UPDATE ... FOR UPDATE SKIP
        LOCKED` claim per call (see Repo.claim_next_pending), so calling it
        N times in a row here is safe against a concurrent invocation
        double-claiming the same row -- and per Render's cron single-run
        guarantee, there won't be a concurrent invocation of *this* job
        anyway (Render queues/delays overlapping scheduled runs rather than
        running them in parallel)."""
        batch: list[dict] = []
        for _ in range(max_size):
            candidate = self.repo.claim_next_pending()
            if candidate is None:
                break
            batch.append(candidate)
        return batch

    async def _process_candidates_bounded(self, max_candidates: int, deadline: float) -> tuple[int, int, str]:
        """Process up to `max_candidates` pending candidates in successive
        batches of size `BRAIN_MAX_CONCURRENT_SIMS`, each batch launched
        concurrently and `await`ed to completion (`asyncio.gather`) before
        the next batch is claimed -- claim batch -> gather -> claim next
        batch -> ... -- until the queue is drained, the candidate cap is
        hit, or `deadline` (a `time.monotonic()` timestamp) passes.

        Returns (batches_run, candidates_processed, stopped_reason).

        This never runs more than `BRAIN_MAX_CONCURRENT_SIMS`
        `_process_candidate` coroutines concurrently -- each candidate in a
        batch still goes through `_process_candidate_bounded`, which
        acquires `self._sim_semaphore` for the full duration of its
        simulation work (see below). The batch size here is capped at the
        same number as the semaphore, so in the common case every batch
        member acquires its slot immediately; the semaphore remains the
        actual safety bound regardless (defense in depth, and it means this
        method staying correct doesn't depend on batch size always equalling
        semaphore size)."""
        batch_size = max(1, self.config.brain_max_concurrent_sims)
        processed = 0
        batches_run = 0
        while processed < max_candidates:
            if time.monotonic() >= deadline:
                return batches_run, processed, "time_budget_exceeded"
            want = min(batch_size, max_candidates - processed)
            batch = self._claim_batch(want)
            if not batch:
                return batches_run, processed, "queue_drained"
            await asyncio.gather(*(self._process_candidate_bounded(c) for c in batch))
            processed += len(batch)
            batches_run += 1
        return batches_run, processed, "max_candidates_reached"

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

    async def run_once(self) -> RunSummary:
        """One bounded pass: reclaim orphans, top up the queue once, process
        a bounded number of candidates, then return. Does not loop or sleep
        internally -- the caller (a Render Cron Job tick) provides the
        "loop" externally via its schedule."""
        summary = RunSummary()

        reclaimed = self.repo.reclaim_orphaned_running(ORPHAN_RECLAIM_MINUTES)
        summary.reclaimed = reclaimed
        if reclaimed:
            log.info("reclaimed %d orphaned 'running' candidates back to 'pending'", reclaimed)

        try:
            summary.queue_depth_before = self.repo.queue_depth()
        except Exception as e:  # noqa: BLE001
            log.exception("could not read queue_depth: %s", e)
            summary.errors.append(f"queue_depth: {e}")

        summary.candidates_generated = await self._generation_step()

        deadline = time.monotonic() + self.config.run_time_budget_seconds
        batches_run, processed, stopped_reason = await self._process_candidates_bounded(
            self.config.max_candidates_per_run, deadline
        )
        summary.batches_run = batches_run
        summary.candidates_processed = processed
        summary.stopped_reason = stopped_reason

        log.info(
            "run_once complete: reclaimed=%d generated=%d processed=%d batches=%d stopped_reason=%s",
            summary.reclaimed, summary.candidates_generated, summary.candidates_processed,
            summary.batches_run, summary.stopped_reason,
        )
        return summary


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
    asyncio.run(worker.run_once())
    # Process exits here (returns from main()) -- no forever-loop. Under
    # cron deployment, Render considers the invocation done once the
    # process exits, and bills only for the time it was running.


if __name__ == "__main__":
    main()
