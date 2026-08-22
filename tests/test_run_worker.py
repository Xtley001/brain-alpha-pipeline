"""
Worker-level tests using fakes for Repo/BrainClient/TelegramNotifier/LLM --
no real DB, network, or credentials. Covers the fixes from the code review
plus the bounded-batch (cron) refactor:

  §1.1  batch processing must never let more than BRAIN_MAX_CONCURRENT_SIMS
        `_process_candidate` coroutines run at once (previously enforced by
        simulation_loop(); now by `_process_candidates_bounded()` /
        `run_once()`, same semaphore, no infinite polling wrapper).
  §2.1  the correlation gate must actually use the winning simulation's
        real return series (via alpha_id -> BrainClient.get_alpha_pnl),
        not silently pass everything.
  refactor  run_once() must actually bound work: it must stop once the
        queue is drained, once MAX_CANDIDATES_PER_RUN is hit, or once the
        time budget is exceeded -- and it must return (not loop forever).
"""
import asyncio

import pytest

from pipeline.config import Config
from pipeline.run_worker import Worker
from pipeline.sweep.settings_sweep import SimResult


class _FakeRepo:
    def __init__(self, candidates, queue_depth=0):
        self._candidates = list(candidates)
        self.statuses = {}
        self.meta = {}
        self.sweep_runs = []
        self._queue_depth = queue_depth
        self.reclaim_calls = 0

    def queue_depth(self):
        return self._queue_depth

    def claim_next_pending(self):
        if self._candidates:
            return self._candidates.pop(0)
        return None

    def insert_sweep_run(self, *a, **k):
        self.sweep_runs.append((a, k))
        return len(self.sweep_runs)

    def set_candidate_status(self, candidate_id, status, **kwargs):
        self.statuses[candidate_id] = status

    def get_pool_returns(self):
        return {}

    def insert_review_store(self, row):
        return 1

    def mark_telegram_sent(self, review_id):
        pass

    def get_meta(self, key):
        return self.meta.get(key)

    def set_meta(self, key, value):
        self.meta[key] = value

    def reclaim_orphaned_running(self, older_than_minutes=30):
        self.reclaim_calls += 1
        return 0

    def insert_candidate(self, expression, category, generation_tier):
        return -1  # not exercised by these tests (queue_target_depth stays satisfied)


class _FakeNotifier:
    def send_candidate_alert(self, row):
        pass

    def send_operational_alert(self, message):
        pass


class _FakeBrainConcurrencyTracker:
    """Simulates BRAIN with a real bottleneck: raises if more than
    `max_concurrent` simulate_one() calls are in flight at once."""

    def __init__(self, max_concurrent: int):
        self.max_concurrent = max_concurrent
        self.in_flight = 0
        self.peak_in_flight = 0
        self.exceeded = False

    async def simulate_one(self, expression, settings):
        self.in_flight += 1
        self.peak_in_flight = max(self.peak_in_flight, self.in_flight)
        if self.in_flight > self.max_concurrent:
            self.exceeded = True
        await asyncio.sleep(0.02)  # hold the "slot" long enough for overlap to show up
        self.in_flight -= 1
        return SimResult(sharpe=0.1, fitness=0.05, turnover=0.3)  # rejected at stage0, fast path


def _make_worker(repo, brain, max_concurrent=2, max_candidates_per_run=15, run_time_budget_seconds=480):
    config = Config(
        database_url="postgres://fake",
        brain_username="u",
        brain_password="p",
        brain_max_concurrent_sims=max_concurrent,
        max_candidates_per_run=max_candidates_per_run,
        run_time_budget_seconds=run_time_budget_seconds,
    )
    return Worker(config, repo, brain, _FakeNotifier(), llm=None)


def test_batch_processing_never_exceeds_configured_concurrency():
    candidates = [
        {"id": i, "expression": f"expr_{i}", "category": "A", "generation_tier": "template"}
        for i in range(6)
    ]
    repo = _FakeRepo(candidates)
    brain = _FakeBrainConcurrencyTracker(max_concurrent=2)
    worker = _make_worker(repo, brain, max_concurrent=2)

    import time
    deadline = time.monotonic() + 5
    batches_run, processed, stopped_reason = asyncio.run(
        worker._process_candidates_bounded(max_candidates=15, deadline=deadline)
    )

    assert brain.exceeded is False, (
        f"peak in-flight simulate_one() calls ({brain.peak_in_flight}) exceeded "
        f"the configured limit (2) -- the semaphore fix (§1.1) is not bounding "
        f"real concurrency in the bounded-batch refactor"
    )
    assert brain.peak_in_flight >= 2, "test is not actually exercising concurrent dispatch"
    assert processed == 6
    assert batches_run == 3  # 6 candidates / batch size 2
    assert stopped_reason == "queue_drained"
    # Every candidate should have been rejected at stage0 (fast, deterministic fake).
    assert all(status == "rejected_stage0" for status in repo.statuses.values())


def test_process_candidates_bounded_stops_at_max_candidates_per_run():
    """run_once() must not drain an arbitrarily deep queue in one
    invocation -- it should stop at MAX_CANDIDATES_PER_RUN and leave the
    rest 'pending' for a future cron tick."""
    candidates = [
        {"id": i, "expression": f"expr_{i}", "category": "A", "generation_tier": "template"}
        for i in range(10)
    ]
    repo = _FakeRepo(candidates)
    brain = _FakeBrainConcurrencyTracker(max_concurrent=2)
    worker = _make_worker(repo, brain, max_concurrent=2)

    import time
    deadline = time.monotonic() + 5
    batches_run, processed, stopped_reason = asyncio.run(
        worker._process_candidates_bounded(max_candidates=4, deadline=deadline)
    )

    assert processed == 4
    assert stopped_reason == "max_candidates_reached"
    # 6 candidates should still be sitting unclaimed in the fake queue.
    assert len(repo._candidates) == 6


def test_process_candidates_bounded_stops_at_time_budget():
    """A near-past deadline should stop the loop before claiming anything,
    leaving candidates untouched for reclaim/retry on the next tick."""
    candidates = [
        {"id": i, "expression": f"expr_{i}", "category": "A", "generation_tier": "template"}
        for i in range(5)
    ]
    repo = _FakeRepo(candidates)
    brain = _FakeBrainConcurrencyTracker(max_concurrent=2)
    worker = _make_worker(repo, brain, max_concurrent=2)

    import time
    already_past_deadline = time.monotonic() - 1
    batches_run, processed, stopped_reason = asyncio.run(
        worker._process_candidates_bounded(max_candidates=15, deadline=already_past_deadline)
    )

    assert processed == 0
    assert batches_run == 0
    assert stopped_reason == "time_budget_exceeded"
    assert len(repo._candidates) == 5  # nothing claimed


def test_run_once_reclaims_generates_and_processes_then_returns():
    """End-to-end run_once(): reclaims orphans, tops up the queue (no-op
    here since queue_depth already meets target), processes the bounded
    batch, and returns a RunSummary -- critically, it returns at all
    (doesn't hang/loop forever)."""
    candidates = [
        {"id": i, "expression": f"expr_{i}", "category": "A", "generation_tier": "template"}
        for i in range(3)
    ]
    repo = _FakeRepo(candidates, queue_depth=999)  # already at/above target -> no generation
    brain = _FakeBrainConcurrencyTracker(max_concurrent=2)
    worker = _make_worker(repo, brain, max_concurrent=2)

    summary = asyncio.run(worker.run_once())

    assert repo.reclaim_calls == 1
    assert summary.candidates_generated == 0
    assert summary.candidates_processed == 3
    assert summary.stopped_reason == "queue_drained"
    assert all(status == "rejected_stage0" for status in repo.statuses.values())


class _FakeBrainForCorrelation:
    def __init__(self, pnl_by_alpha_id):
        self._pnl = pnl_by_alpha_id

    async def get_alpha_pnl(self, alpha_id):
        return self._pnl[alpha_id]


def test_process_candidate_rejects_when_winning_result_has_no_alpha_id():
    """A winning SimResult with no alpha_id must be rejected outright, not
    silently pass the correlation gate the way the old hardcoded {} did."""
    from pipeline.sweep.settings_sweep import Settings, SweepOutcome

    repo = _FakeRepo([])
    brain = _FakeBrainForCorrelation({})
    worker = _make_worker(repo, brain)

    settings = Settings(
        delay=1, universe="TOP3000", neutralization="SUBINDUSTRY", decay=8,
        truncation=0.05, pasteurization=True, nan_handling=False,
    )
    winning_result = SimResult(sharpe=2.0, fitness=1.5, turnover=0.3, alpha_id=None)

    async def fake_to_thread(fn, *args):
        return SweepOutcome(
            rejected_at_stage0=False,
            runs=[],
            winning_settings=settings,
            winning_result=winning_result,
            robust_count=5,
            sweep_total=41,
            fragile=False,
        )

    async def run():
        orig_to_thread = asyncio.to_thread
        asyncio.to_thread = fake_to_thread
        try:
            await worker._process_candidate({"id": 1, "expression": "expr"})
        finally:
            asyncio.to_thread = orig_to_thread

    asyncio.run(run())

    assert repo.statuses[1] == "rejected_correlation"
