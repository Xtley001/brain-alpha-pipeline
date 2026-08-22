"""
Worker-level tests using fakes for Repo/BrainClient/TelegramNotifier/LLM --
no real DB, network, or credentials. Covers two of the fixes from the code
review:

  §1.1  simulation_loop() must never let more than BRAIN_MAX_CONCURRENT_SIMS
        `_process_candidate` coroutines run at once.
  §2.1  the correlation gate must actually use the winning simulation's
        real return series (via alpha_id -> BrainClient.get_alpha_pnl),
        not silently pass everything.
"""
import asyncio

import pytest

from pipeline.config import Config
from pipeline.run_worker import Worker
from pipeline.sweep.settings_sweep import SimResult


class _FakeRepo:
    def __init__(self, candidates):
        self._candidates = list(candidates)
        self.statuses = {}
        self.meta = {}
        self.sweep_runs = []

    def queue_depth(self):
        return 0

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


def _make_worker(repo, brain, candidates_n=6, max_concurrent=2):
    config = Config(
        database_url="postgres://fake",
        brain_username="u",
        brain_password="p",
        brain_max_concurrent_sims=max_concurrent,
    )
    return Worker(config, repo, brain, _FakeNotifier(), llm=None)


def test_simulation_loop_never_exceeds_configured_concurrency():
    candidates = [
        {"id": i, "expression": f"expr_{i}", "category": "A", "generation_tier": "template"}
        for i in range(6)
    ]
    repo = _FakeRepo(candidates)
    brain = _FakeBrainConcurrencyTracker(max_concurrent=2)
    worker = _make_worker(repo, brain, max_concurrent=2)

    async def run_until_drained():
        task = asyncio.create_task(worker.simulation_loop())
        # Give the loop enough cycles to claim and process every candidate.
        for _ in range(50):
            await asyncio.sleep(0.02)
            if len(repo.statuses) >= len(candidates):
                break
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run_until_drained())

    assert brain.exceeded is False, (
        f"peak in-flight simulate_one() calls ({brain.peak_in_flight}) exceeded "
        f"the configured limit (2) -- the semaphore fix (§1.1) is not bounding "
        f"real concurrency"
    )
    assert brain.peak_in_flight >= 2, "test is not actually exercising concurrent dispatch"
    # Every candidate should have been rejected at stage0 (fast, deterministic fake).
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
