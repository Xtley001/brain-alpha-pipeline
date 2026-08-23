"""
Bounded-batch entrypoint. `run_once()` does a single fixed-size pass of
work and returns -- it does NOT loop forever. Deploy target is a scheduled
GitHub Actions job (see `.github/workflows/run.yml`; previously Render Cron,
see `UPDATE.md`), invoked on a schedule (default: every 10 minutes); each
scheduled tick is a fresh process that runs `main()` and exits.

One invocation of `run_once()`:

  1. Reclaims any candidate orphaned in 'running' by a previous invocation
     that got cut off mid-simulation (crash, or a killed Actions run). This
     recovery path matters *more* under a scheduled-job deployment than it
     did under an always-on worker, since a tick can be killed mid-run.
  2. Runs ONE pass of the queue top-up logic (template tier, then LLM
     reasoning tier if needed, then LLM mechanical-mutation tier if there's
     still room -- see `_top_up_queue`).
  3. Processes candidates in successive batches of up to
     BRAIN_MAX_CONCURRENT_SIMS, concurrently, `await`ed to completion each
     round (claim batch -> gather -> claim next batch -> ...), until either
     the pending queue is drained, MAX_CANDIDATES_PER_RUN is reached, or
     RUN_TIME_BUDGET_SECONDS of wall-clock time has elapsed -- whichever
     comes first.
  4. Sends a heartbeat report to Telegram and writes one `run_history` row,
     unconditionally -- pass, fail, or "nothing happened this tick" (Update
     01 P1.1 / Update 02 P1.2). Silence is no longer a valid healthy state.

## Concurrency model (Update 04)

Real BRAIN-call concurrency is now bounded by ONE shared
`asyncio.Semaphore(BRAIN_MAX_CONCURRENT_SIMS)` (`self._sim_semaphore`),
acquired once per individual `simulate()` call *inside* the staged sweep
(`run_staged_sweep`'s `_safe_simulate`), not once per candidate. Previously
the semaphore wrapped an entire candidate's 41-sim sweep, which meant each
candidate's own sweep still ran its 41 simulations one at a time -- the
single biggest throughput bug found in the pipeline (a 7-14 minute sweep
per candidate could alone blow the whole tick's time budget; see the audit
docs' throughput analysis). `_process_candidate_bounded` no longer wraps a
candidate in the semaphore at all; concurrency is enforced entirely inside
`run_staged_sweep` now, shared across however many candidates happen to be
in flight at once, so `BRAIN_MAX_CONCURRENT_SIMS` means what it says: the
real ceiling on concurrent BRAIN calls, system-wide, regardless of which
candidate or sweep stage they come from.

## Fault isolation and attempt cap (Update 04)

A single settings combo failing to simulate no longer takes the whole
sweep down with it (`SweepRun.error` / `SweepOutcome.aborted_stage` -- see
`pipeline/sweep/settings_sweep.py`). A candidate whose sweep can't produce
*any* usable result, or that raises anywhere else in `_process_candidate`,
gets `MAX_CANDIDATE_ATTEMPTS` retries (tracked via `candidates.attempts` /
`last_error`) before permanently flipping to `rejected_error` with one
alert -- not one alert per tick, forever, and not silently retried forever
either.

No BRAIN submit/create-alpha call exists anywhere in this file or anything
it imports. Submission is manual, always.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from dataclasses import dataclass, field

from pipeline.brain.client import BrainAuthError, BrainClient
from pipeline.config import Config, MissingConfigError
from pipeline.db.repo import Repo
from pipeline.filter.correlation_check import compute_max_correlation, passes_correlation_gate
from pipeline.filter.local_filter import FilterThresholds
from pipeline.generator.llm_generator import mutate_candidate, propose_new_ideas
from pipeline.generator.template_generator import SEED_IDEAS, generate_template_candidates
from pipeline.llm.adapter import LLMAdapter, build_gemini_provider, build_groq_provider
from pipeline.notify.telegram_notify import TelegramNotifier
from pipeline.sweep.settings_sweep import SweepRun, run_staged_sweep

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("run_worker")

ORPHAN_RECLAIM_MINUTES = 30
MAX_CORRELATION = 0.7
# How many times a candidate that keeps hard-failing (BRAIN errors, not low
# scores) gets retried before permanently flipping to 'rejected_error'
# (Update 04). Not exposed as an env var -- 3 is a reasonable fixed default
# and this isn't the kind of knob that needs tuning per-deployment; raise it
# here directly if that changes.
MAX_CANDIDATE_ATTEMPTS = 3

# Terminal candidate outcomes the heartbeat/run_history break processing
# down by (Update 01 P1.1 / Update 02 P1.2). A retried-but-not-yet-terminal
# candidate (status flipped back to 'pending') intentionally has no bucket
# here -- it isn't an "exit status" yet, it'll show up in a future tick's
# breakdown once it resolves one way or another.
_TERMINAL_STATUSES = ("passed", "rejected_stage0", "rejected_filter", "rejected_correlation", "rejected_error")


@dataclass
class RunSummary:
    """What one `run_once()` invocation did -- returned so `main()` can log
    it, so the heartbeat/run_history can report it, and so tests can assert
    on behavior without scraping log output."""

    reclaimed: int = 0
    queue_depth_before: int = 0
    candidates_generated: int = 0
    candidates_processed: int = 0
    batches_run: int = 0
    stopped_reason: str = "queue_drained"  # or "max_candidates_reached" / "time_budget_exceeded"
    brain_auth_ok: bool = True
    # Per-exit-status breakdown of candidates_processed this tick (Update 01
    # P1.1) -- previously only a total count existed, which couldn't answer
    # "where are candidates dying".
    passed: int = 0
    rejected_stage0: int = 0
    rejected_filter: int = 0
    rejected_correlation: int = 0
    rejected_error: int = 0
    errors: list[str] = field(default_factory=list)


class Worker:
    def __init__(self, config: Config, repo: Repo, brain: BrainClient, notifier: TelegramNotifier, llm: LLMAdapter):
        self.config = config
        self.repo = repo
        self.brain = brain
        self.notifier = notifier
        self.llm = llm
        self.thresholds = FilterThresholds.from_env()
        # Update 04: this is now the single, global ceiling on concurrent
        # BRAIN simulate() calls, shared by every in-flight candidate's
        # sweep -- see run_staged_sweep's `semaphore` parameter and this
        # module's docstring. No longer acquired around a whole candidate
        # in _process_candidate_bounded.
        self._sim_semaphore = asyncio.Semaphore(config.brain_max_concurrent_sims)
        # A Worker instance is only ever constructed (via build_worker())
        # after BrainClient.authenticate() has already succeeded -- a
        # BrainAuthError raised there propagates out of build_worker()
        # before any Worker exists (see main()'s handling of it). So a live
        # Worker's BRAIN auth is always known-good at construction time;
        # this is just what the heartbeat surfaces every tick (Update 01
        # P1.1's "BRAIN auth status (already known at build_worker() time
        # -- surface it)").
        self._brain_auth_ok = True
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
                break  # exhausted this pass of the template pool; llm tiers fill the rest

        # Persist the cursor after this pass so a restart resumes roughly
        # where it left off instead of re-biasing toward category A.
        try:
            self.repo.set_meta("seed_cursor", str(self._seed_cursor))
        except Exception:  # noqa: BLE001
            log.warning("could not persist seed_cursor", exc_info=True)

        # Tier 2: LLM reasoning tier, only if the template tier couldn't
        # fill the gap (keeps LLM calls to the volume actually needed, not
        # spammed).
        #
        # propose_new_ideas() makes a real, blocking network call (and can
        # call a blocking time.sleep(...) internally on a 429 retry -- see
        # pipeline/llm/adapter.py). Run it in a worker thread rather than
        # awaiting it directly, so it can't freeze this coroutine's event
        # loop.
        proposals: list[dict] = []
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

        # Tier 3: mechanical mutation (Update 03) -- cheap, high-volume,
        # Groq-first variations on a direction the reasoning tier just
        # picked, per mutate_candidate()'s own docstring. Confirmed by grep
        # before this fix: mutate_candidate was fully written, imported, and
        # (per its docstring and tests) presumably working, but had zero
        # call sites anywhere in the codebase -- an entire generation tier
        # was dead code. Only fires if Tier 1 + Tier 2 still didn't fill the
        # queue AND the reasoning tier actually proposed something this
        # round to mutate a direction from -- if it proposed nothing (e.g.
        # exhausted quota), there's no "direction already picked" to work
        # from, and this tier intentionally sits out rather than mutating a
        # template-tier idea instead (that would blur the tier boundary the
        # two-tier design is built around: reasoning picks genuinely new
        # directions, mechanical cheaply varies one of them).
        remaining = needed - added
        if remaining > 0 and proposals:
            base = proposals[0]
            try:
                mutations = await asyncio.to_thread(
                    mutate_candidate,
                    self.llm,
                    base["expression"],
                    base["category"],
                    min(remaining, 10),
                )
                for c in mutations:
                    self.repo.insert_candidate(c["expression"], c["category"], c["generation_tier"])
                    added += 1
            except Exception as e:  # noqa: BLE001
                log.warning("LLM mechanical mutation failed: %s", e)

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
        double-claiming the same row."""
        batch: list[dict] = []
        for _ in range(max_size):
            candidate = self.repo.claim_next_pending()
            if candidate is None:
                break
            batch.append(candidate)
        return batch

    async def _process_candidates_bounded(self, max_candidates: int, deadline: float) -> tuple[int, int, str, dict]:
        """Process up to `max_candidates` pending candidates in successive
        batches of size `BRAIN_MAX_CONCURRENT_SIMS`, each batch launched
        concurrently and `await`ed to completion (`asyncio.gather`) before
        the next batch is claimed -- claim batch -> gather -> claim next
        batch -> ... -- until the queue is drained, the candidate cap is
        hit, or `deadline` (a `time.monotonic()` timestamp) passes.

        Returns (batches_run, candidates_processed, stopped_reason,
        stage_counts) -- `stage_counts` is a dict of terminal-status ->
        count for this call, used to build the heartbeat's per-stage
        breakdown (Update 01 P1.1).

        Note (Update 04): batching here is now a claiming/iteration
        granularity, not the concurrency bound -- real BRAIN-call
        concurrency is enforced by the shared `self._sim_semaphore` inside
        each candidate's `run_staged_sweep`, regardless of how many
        candidates this method dispatches concurrently. Batch size is kept
        at `BRAIN_MAX_CONCURRENT_SIMS` anyway since it's a reasonable
        default claiming chunk, not because it's load-bearing for the
        concurrency guarantee anymore.
        """
        batch_size = max(1, self.config.brain_max_concurrent_sims)
        processed = 0
        batches_run = 0
        stage_counts = {status: 0 for status in _TERMINAL_STATUSES}
        while processed < max_candidates:
            if time.monotonic() >= deadline:
                return batches_run, processed, "time_budget_exceeded", stage_counts
            want = min(batch_size, max_candidates - processed)
            batch = self._claim_batch(want)
            if not batch:
                return batches_run, processed, "queue_drained", stage_counts
            statuses = await asyncio.gather(*(self._process_candidate_bounded(c) for c in batch))
            for status in statuses:
                if status in stage_counts:
                    stage_counts[status] += 1
            processed += len(batch)
            batches_run += 1
        return batches_run, processed, "max_candidates_reached", stage_counts

    async def _process_candidate_bounded(self, candidate: dict) -> str:
        # Update 04: no semaphore acquired here anymore. Real BRAIN-call
        # concurrency is enforced entirely inside run_staged_sweep now, via
        # the shared self._sim_semaphore -- see this module's docstring.
        # Previously this wrapped the whole candidate, which meant each
        # candidate's own 41-sim sweep still ran serially inside it (the
        # actual bottleneck; see the throughput analysis in the audit docs).
        return await self._process_candidate(candidate)

    # --- per-candidate processing ---

    def _persist_sweep_run(self, candidate_id: int, run: SweepRun) -> None:
        """Called once per completed simulate() call, from inside
        run_staged_sweep, via the `persist_run` callback -- results land in
        the DB incrementally rather than only after the whole 41-sim sweep
        finishes clean (Update 04). `run.ok` decides which table shape this
        maps to: a real result (`insert_sweep_run`) or a recorded failure
        with every metric column NULL (`insert_sweep_run_error`)."""
        if run.ok:
            self.repo.insert_sweep_run(candidate_id, run.stage, run.settings, run.result)
        else:
            self.repo.insert_sweep_run_error(candidate_id, run.stage, run.settings, run.error)

    def _record_candidate_error(self, candidate_id: int, error_text: str) -> str:
        """Increments the candidate's attempt counter and returns the
        resulting status ('pending' if it'll be retried, 'rejected_error'
        if this was the final permitted attempt). Alerts exactly once, on
        the terminal failure -- not once per tick for however many ticks
        it keeps failing (Update 04)."""
        status, attempts = self.repo.record_candidate_error(candidate_id, error_text, MAX_CANDIDATE_ATTEMPTS)
        if status == "rejected_error":
            self._safe_operational_alert(
                f"candidate {candidate_id} permanently failed after {attempts} attempts: {error_text}"
            )
        return status

    async def _process_candidate(self, candidate: dict) -> str:
        """Runs one candidate through the full pipeline and returns its
        resulting status string -- used both to update the DB (as before)
        and, new in this pass, to let the caller aggregate a per-tick
        stage-count breakdown for the heartbeat without needing its own DB
        query (Update 01 P1.1)."""
        candidate_id = candidate["id"]
        expression = candidate["expression"]
        try:
            # run_staged_sweep is async now and awaited directly -- no more
            # asyncio.run()/asyncio.to_thread() wrapper spinning up a fresh
            # event loop per candidate (Update 03/04: that per-candidate
            # event-loop churn was real overhead on top of the sequential-
            # not-concurrent problem it was also hiding).
            outcome = await run_staged_sweep(
                expression,
                self.brain.simulate_one,
                self.thresholds,
                self.config.stage0_min_fitness,
                self.config.stage0_min_sharpe,
                semaphore=self._sim_semaphore,
                persist_run=lambda run: self._persist_sweep_run(candidate_id, run),
            )

            if outcome.aborted_stage is not None:
                # Every combo in some stage failed to simulate at all --
                # this is an operational failure, not a quality verdict
                # (see SweepOutcome.aborted_stage's docstring). Goes through
                # the same attempt-cap path as any other hard failure below,
                # rather than being recorded as rejected_stage0/filter.
                return self._record_candidate_error(
                    candidate_id, f"sweep aborted at {outcome.aborted_stage}: all combos in that stage failed"
                )

            if outcome.rejected_at_stage0:
                self.repo.set_candidate_status(
                    candidate_id, "rejected_stage0",
                    stage0_fitness=outcome.runs[0].result.fitness,
                    stage0_sharpe=outcome.runs[0].result.sharpe,
                )
                return "rejected_stage0"

            if not self.thresholds.passes(outcome.winning_result):
                self.repo.set_candidate_status(candidate_id, "rejected_filter")
                return "rejected_filter"

            # Correlation check vs. pool, on the *winning settings'* stream
            # (per the settings-sweep spec -- not the Stage 0 default
            # settings' stream). `outcome.winning_result.alpha_id` is the id
            # BRAIN assigned to that specific simulation run (see
            # BrainClient.simulate_one -> _parse_sim_response), so this
            # fetches that exact run's daily-return series rather than
            # re-simulating.
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
                return "rejected_correlation"

            try:
                candidate_returns = await self.brain.get_alpha_pnl(winning_alpha_id)
            except Exception as e:  # noqa: BLE001
                # A PnL-fetch failure is operational (BRAIN/network), not a
                # quality verdict -- goes through the same attempt-cap
                # retry/permanent-fail path as a sweep failure, not a silent
                # "pending forever" or a mis-bucketed rejection.
                return self._record_candidate_error(candidate_id, f"pnl fetch failed: {e}")

            corr_result = compute_max_correlation(candidate_returns, pool)
            if not passes_correlation_gate(corr_result, MAX_CORRELATION):
                self.repo.set_candidate_status(candidate_id, "rejected_correlation")
                return "rejected_correlation"

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
            # Update 02 P0.2 self-consistency fix: feed this pipeline's own
            # passed alpha back into pool_returns immediately, so the *next*
            # candidate's correlation check can actually see it. Previously
            # nothing ever called upsert_pool_returns, so get_pool_returns()
            # always returned {}, the correlation gate always passed by
            # construction, and two near-duplicate candidates from this same
            # pipeline could both sail through without ever seeing each
            # other.
            self.repo.upsert_pool_returns(winning_alpha_id, candidate_returns)
            return "passed"

        except Exception as e:  # noqa: BLE001 -- anything unexpected, not already handled above
            log.exception("candidate %s failed: %s", candidate_id, e)
            return self._record_candidate_error(candidate_id, str(e))

    def _safe_operational_alert(self, message: str) -> None:
        try:
            self.notifier.send_operational_alert(message)
        except Exception:  # noqa: BLE001
            log.exception("failed to send operational alert")

    # --- heartbeat / run_history (Update 01 P1.1, Update 02 P1.2) ---

    def _health_snapshot(self, summary: RunSummary) -> dict:
        """Assembles the health dict format_run_report()/insert_run_history()
        expect, from data already gathered this tick plus one extra query
        for LLM key health (llm_usage is otherwise never surfaced anywhere)."""
        db_ok = not any(e.startswith("queue_depth") for e in summary.errors)
        try:
            llm_keys = self.repo.recent_llm_key_health()
        except Exception:  # noqa: BLE001
            log.warning("could not fetch llm key health for heartbeat", exc_info=True)
            llm_keys = []
        return {
            "brain_auth_ok": summary.brain_auth_ok,
            "db_ok": db_ok,
            "llm_keys": llm_keys,
            "stage_counts": {
                "passed": summary.passed,
                "rejected_stage0": summary.rejected_stage0,
                "rejected_filter": summary.rejected_filter,
                "rejected_correlation": summary.rejected_correlation,
                "rejected_error": summary.rejected_error,
            },
        }

    def _safe_send_run_report(self, summary: RunSummary, health: dict) -> None:
        try:
            self.notifier.send_run_report(summary, health)
        except Exception:  # noqa: BLE001
            # A heartbeat-delivery failure must never crash run_once() or
            # mask the real results already computed above -- it's just
            # logged, same defensive posture as _safe_operational_alert.
            log.exception("failed to send heartbeat run report")

    def _safe_insert_run_history(self, summary: RunSummary, health: dict) -> None:
        try:
            self.repo.insert_run_history({
                "reclaimed": summary.reclaimed,
                "queue_depth_before": summary.queue_depth_before,
                "candidates_generated": summary.candidates_generated,
                "candidates_processed": summary.candidates_processed,
                "rejected_stage0": summary.rejected_stage0,
                "rejected_filter": summary.rejected_filter,
                "rejected_correlation": summary.rejected_correlation,
                "rejected_error": summary.rejected_error,
                "passed": summary.passed,
                "stopped_reason": summary.stopped_reason,
                "brain_auth_ok": health.get("brain_auth_ok"),
                "errors": "; ".join(summary.errors) if summary.errors else None,
            })
        except Exception:  # noqa: BLE001
            log.exception("failed to write run_history row")

    async def run_once(self) -> RunSummary:
        """One bounded pass: reclaim orphans, top up the queue once, process
        a bounded number of candidates, send the heartbeat, then return.
        Does not loop or sleep internally -- the caller (a scheduled job
        tick) provides the "loop" externally via its schedule."""
        summary = RunSummary()
        summary.brain_auth_ok = self._brain_auth_ok

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
        batches_run, processed, stopped_reason, stage_counts = await self._process_candidates_bounded(
            self.config.max_candidates_per_run, deadline
        )
        summary.batches_run = batches_run
        summary.candidates_processed = processed
        summary.stopped_reason = stopped_reason
        summary.passed = stage_counts["passed"]
        summary.rejected_stage0 = stage_counts["rejected_stage0"]
        summary.rejected_filter = stage_counts["rejected_filter"]
        summary.rejected_correlation = stage_counts["rejected_correlation"]
        summary.rejected_error = stage_counts["rejected_error"]

        log.info(
            "run_once complete: reclaimed=%d generated=%d processed=%d batches=%d stopped_reason=%s "
            "passed=%d rejected_stage0=%d rejected_filter=%d rejected_correlation=%d rejected_error=%d",
            summary.reclaimed, summary.candidates_generated, summary.candidates_processed,
            summary.batches_run, summary.stopped_reason,
            summary.passed, summary.rejected_stage0, summary.rejected_filter,
            summary.rejected_correlation, summary.rejected_error,
        )

        # Heartbeat: send + persist unconditionally, every tick, regardless
        # of whether anything above found a passing candidate -- silence is
        # no longer a valid healthy state (Update 01/03's "black box"
        # framing). Both calls are individually defensive so a delivery
        # failure here can't crash run_once() or discard the summary.
        health = self._health_snapshot(summary)
        self._safe_send_run_report(summary, health)
        self._safe_insert_run_history(summary, health)

        return summary


def _best_effort_startup_alert(message: str) -> None:
    """Update 03: a BRAIN-auth failure at startup previously produced total
    Telegram silence -- the crash happens inside build_worker(), before any
    Worker (and therefore any already-wired TelegramNotifier) exists to send
    an alert about it. This builds a throwaway notifier directly from env
    vars, deliberately NOT via Config.from_env()'s require_telegram=True
    path (which could itself raise MissingConfigError and mask the real
    BRAIN failure being reported), and sends one best-effort alert before
    main() exits non-zero. If Telegram itself is misconfigured, this can
    only log a warning -- see SETUP.md's note on enabling GitHub's native
    Actions-failure email notifications as the independent backup channel
    for exactly this scenario."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        log.warning("cannot send startup alert -- TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID not set")
        return
    try:
        TelegramNotifier(token, chat_id).send_operational_alert(message)
    except Exception:  # noqa: BLE001
        log.exception("failed to send best-effort startup alert")


def build_worker() -> Worker:
    config = Config.from_env()
    repo = Repo(config.database_url)
    repo.migrate()
    brain = BrainClient(config.brain_username, config.brain_password, config.brain_max_concurrent_sims)
    # BrainAuthError raised here propagates straight out of build_worker(),
    # before any Worker/TelegramNotifier exists -- main() catches it
    # specifically (as opposed to just MissingConfigError, which it already
    # handled) and attempts a best-effort alert before exiting non-zero.
    # See Update 03: this used to be a silent gap -- a failed GitHub Actions
    # run and nothing else.
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
    except BrainAuthError as e:
        log.error("Startup aborted: BRAIN authentication failed: %s", e)
        _best_effort_startup_alert(f"BRAIN authentication failed at startup: {e}")
        sys.exit(1)
    asyncio.run(worker.run_once())
    # Process exits here (returns from main()) -- no forever-loop. Under a
    # scheduled-job deployment, the platform considers the invocation done
    # once the process exits.


if __name__ == "__main__":
    main()
