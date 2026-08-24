"""
Worker-level tests using fakes for Repo/BrainClient/TelegramNotifier/LLM --
no real DB, network, or credentials. Covers:

  §1.1 (original)  batch processing must never let more than
        BRAIN_MAX_CONCURRENT_SIMS real simulate() calls run at once --
        now enforced by the *shared* self._sim_semaphore passed into every
        candidate's run_staged_sweep call (Update 04), not by a semaphore
        wrapped around each whole candidate.
  §2.1 (original)  the correlation gate must actually use the winning
        simulation's real return series (via alpha_id ->
        BrainClient.get_alpha_pnl), not silently pass everything.
  refactor  run_once() must actually bound work: it must stop once the
        queue is drained, once MAX_CANDIDATES_PER_RUN is hit, or once the
        time budget is exceeded -- and it must return (not loop forever).
  Update 04  a candidate whose sweep can't produce any usable result (or
        that raises elsewhere in _process_candidate) gets retried up to
        MAX_CANDIDATE_ATTEMPTS times before permanently flipping to
        'rejected_error', with exactly one alert on the terminal failure.
  Update 02 P0.2  a passed candidate's winning return series must be fed
        back into pool_returns so later candidates can see it.
  Update 01 P1.1 / Update 02 P1.2  every run_once() sends a heartbeat and
        writes a run_history row, unconditionally.
"""
import asyncio

from pipeline.config import Config
from pipeline.run_worker import MAX_CANDIDATE_ATTEMPTS, Worker
from pipeline.sweep.settings_sweep import SimResult


class _FakeRepo:
    def __init__(self, candidates, queue_depth=0):
        self._candidates = list(candidates)
        self.statuses = {}
        self.meta = {}
        self.sweep_runs = []
        self.sweep_run_errors = []
        self._queue_depth = queue_depth
        self.reclaim_calls = 0
        self.candidate_attempts = {}
        self.candidate_last_error = {}
        self.pool_returns = {}
        self.pool_upserts = []
        self.run_history_rows = []

    def queue_depth(self):
        return self._queue_depth

    def claim_next_pending(self):
        if self._candidates:
            return self._candidates.pop(0)
        return None

    def insert_sweep_run(self, *a, **k):
        self.sweep_runs.append((a, k))
        return len(self.sweep_runs)

    def insert_sweep_run_error(self, *a, **k):
        self.sweep_run_errors.append((a, k))
        return len(self.sweep_run_errors)

    def set_candidate_status(self, candidate_id, status, **kwargs):
        self.statuses[candidate_id] = status

    def record_candidate_error(self, candidate_id, error_text, max_attempts):
        attempts = self.candidate_attempts.get(candidate_id, 0) + 1
        self.candidate_attempts[candidate_id] = attempts
        self.candidate_last_error[candidate_id] = error_text
        if attempts >= max_attempts:
            status = "rejected_error"
        else:
            status = "pending"
        self.statuses[candidate_id] = status
        return status, attempts

    def get_pool_returns(self):
        return dict(self.pool_returns)

    def upsert_pool_returns(self, alpha_id, series):
        self.pool_upserts.append((alpha_id, series))
        self.pool_returns[alpha_id] = series

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

    def recent_llm_key_health(self):
        return []

    def insert_run_history(self, row):
        self.run_history_rows.append(row)
        return len(self.run_history_rows)

    def expression_exists(self, expression):
        return False

    def recent_llm_expressions(self):
        return []

    def category_performance(self):
        return []

    def recent_rejections(self, limit=10):
        return []


class _FakeNotifier:
    def __init__(self):
        self.candidate_alerts = []
        self.operational_alerts = []
        self.run_reports = []

    def send_candidate_alert(self, row):
        self.candidate_alerts.append(row)

    def send_operational_alert(self, message):
        self.operational_alerts.append(message)

    def send_run_report(self, summary, health):
        self.run_reports.append((summary, health))


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
    batches_run, processed, stopped_reason, stage_counts = asyncio.run(
        worker._process_candidates_bounded(max_candidates=15, deadline=deadline)
    )

    assert brain.exceeded is False, (
        f"peak in-flight simulate_one() calls ({brain.peak_in_flight}) exceeded "
        f"the configured limit (2) -- the shared-semaphore fix (Update 04) is not "
        f"bounding real concurrency"
    )
    assert brain.peak_in_flight >= 2, "test is not actually exercising concurrent dispatch"
    assert processed == 6
    assert batches_run == 3  # 6 candidates / batch size 2
    assert stopped_reason == "queue_drained"
    # Every candidate should have been rejected at stage0 (fast, deterministic fake).
    assert all(status == "rejected_stage0" for status in repo.statuses.values())
    assert stage_counts["rejected_stage0"] == 6


def test_process_candidates_bounded_stops_at_max_candidates_per_run():
    """run_once() must not drain an arbitrarily deep queue in one
    invocation -- it should stop at MAX_CANDIDATES_PER_RUN and leave the
    rest 'pending' for a future tick."""
    candidates = [
        {"id": i, "expression": f"expr_{i}", "category": "A", "generation_tier": "template"}
        for i in range(10)
    ]
    repo = _FakeRepo(candidates)
    brain = _FakeBrainConcurrencyTracker(max_concurrent=2)
    worker = _make_worker(repo, brain, max_concurrent=2)

    import time
    deadline = time.monotonic() + 5
    batches_run, processed, stopped_reason, stage_counts = asyncio.run(
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
    batches_run, processed, stopped_reason, stage_counts = asyncio.run(
        worker._process_candidates_bounded(max_candidates=15, deadline=already_past_deadline)
    )

    assert processed == 0
    assert batches_run == 0
    assert stopped_reason == "time_budget_exceeded"
    assert len(repo._candidates) == 5  # nothing claimed


def test_run_once_reclaims_generates_and_processes_then_returns():
    """End-to-end run_once(): reclaims orphans, tops up the queue (no-op
    here since queue_depth already meets target), processes the bounded
    batch, sends a heartbeat, writes run_history, and returns a RunSummary
    -- critically, it returns at all (doesn't hang/loop forever)."""
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
    assert summary.rejected_stage0 == 3
    assert summary.brain_auth_ok is True

    # Heartbeat: sent exactly once, and a matching run_history row was
    # written, unconditionally (Update 01 P1.1 / Update 02 P1.2).
    assert len(worker.notifier.run_reports) == 1
    sent_summary, sent_health = worker.notifier.run_reports[0]
    assert sent_summary is summary
    assert sent_health["stage_counts"]["rejected_stage0"] == 3
    assert len(repo.run_history_rows) == 1
    assert repo.run_history_rows[0]["rejected_stage0"] == 3


class _FakeBrainForCorrelation:
    def __init__(self, pnl_by_alpha_id):
        self._pnl = pnl_by_alpha_id

    def simulate_one(self, expression, settings):
        raise AssertionError("run_staged_sweep is patched in this test; simulate_one should never be called")

    async def get_alpha_pnl(self, alpha_id):
        return self._pnl[alpha_id]


def _patch_sweep(monkeypatch, outcome_or_factory):
    """Patches pipeline.run_worker.run_staged_sweep (the name imported into
    that module) with a fake async function returning a fixed SweepOutcome
    -- run_staged_sweep is awaited directly now (Update 04), so no more
    asyncio.to_thread monkeypatching is needed/possible here."""
    import pipeline.run_worker as run_worker_module

    async def fake_run_staged_sweep(*args, **kwargs):
        if callable(outcome_or_factory):
            return outcome_or_factory()
        return outcome_or_factory

    monkeypatch.setattr(run_worker_module, "run_staged_sweep", fake_run_staged_sweep)


def test_process_candidate_rejects_when_winning_result_has_no_alpha_id(monkeypatch):
    """A winning SimResult with no alpha_id must be rejected outright, not
    silently pass the correlation gate the way an old hardcoded {} did."""
    from pipeline.sweep.settings_sweep import Settings, SweepOutcome

    repo = _FakeRepo([])
    brain = _FakeBrainForCorrelation({})
    worker = _make_worker(repo, brain)

    settings = Settings(
        delay=1, universe="TOP3000", neutralization="SUBINDUSTRY", decay=8,
        truncation=0.05, pasteurization=True, nan_handling=False,
    )
    winning_result = SimResult(sharpe=2.0, fitness=1.5, turnover=0.3, alpha_id=None)

    outcome = SweepOutcome(
        rejected_at_stage0=False,
        aborted_stage=None,
        runs=[],
        winning_settings=settings,
        winning_result=winning_result,
        robust_count=5,
        sweep_total=41,
        error_count=0,
        fragile=False,
    )
    _patch_sweep(monkeypatch, outcome)

    status = asyncio.run(worker._process_candidate({"id": 1, "expression": "expr"}))

    assert status == "rejected_correlation"
    assert repo.statuses[1] == "rejected_correlation"


def test_process_candidate_upserts_pool_returns_on_pass(monkeypatch):
    """Update 02 P0.2 self-consistency fix: a passed candidate's winning
    return series must be fed back into pool_returns immediately."""
    from pipeline.sweep.settings_sweep import Settings, SweepOutcome

    repo = _FakeRepo([])
    brain = _FakeBrainForCorrelation({"alpha_123": {"2026-01-01": 0.01, "2026-01-02": 0.02}})
    worker = _make_worker(repo, brain)

    settings = Settings(
        delay=1, universe="TOP3000", neutralization="SUBINDUSTRY", decay=8,
        truncation=0.05, pasteurization=True, nan_handling=False,
    )
    winning_result = SimResult(sharpe=2.0, fitness=1.5, turnover=0.3, alpha_id="alpha_123")
    outcome = SweepOutcome(
        rejected_at_stage0=False, aborted_stage=None, runs=[],
        winning_settings=settings, winning_result=winning_result,
        robust_count=5, sweep_total=41, error_count=0, fragile=False,
    )
    _patch_sweep(monkeypatch, outcome)

    status = asyncio.run(worker._process_candidate({"id": 1, "expression": "expr"}))

    assert status == "passed"
    assert repo.statuses[1] == "passed"
    assert repo.pool_upserts == [("alpha_123", {"2026-01-01": 0.01, "2026-01-02": 0.02})]
    assert len(worker.notifier.candidate_alerts) == 1


def test_process_candidate_aborted_stage_goes_through_attempt_cap_not_a_quality_rejection(monkeypatch):
    """Update 04: aborted_stage means 'BRAIN never answered for this
    candidate', not 'this idea is bad' -- must go through the retry/attempt
    -cap path (record_candidate_error), never straight to rejected_stage0
    or rejected_filter."""
    from pipeline.sweep.settings_sweep import SweepOutcome

    repo = _FakeRepo([])
    brain = _FakeBrainForCorrelation({})
    worker = _make_worker(repo, brain)

    outcome = SweepOutcome(
        rejected_at_stage0=False, aborted_stage="stage1", runs=[],
        winning_settings=None, winning_result=None,
        robust_count=0, sweep_total=30, error_count=30, fragile=True,
    )
    _patch_sweep(monkeypatch, outcome)

    status = asyncio.run(worker._process_candidate({"id": 7, "expression": "expr"}))

    assert status == "pending"  # first attempt, retried
    assert repo.candidate_attempts[7] == 1
    assert repo.statuses[7] == "pending"
    assert worker.notifier.operational_alerts == []  # no alert until the final attempt


def test_candidate_permanently_fails_after_max_attempts_with_exactly_one_alert(monkeypatch):
    """A candidate that keeps hard-failing must get MAX_CANDIDATE_ATTEMPTS
    tries, then flip to rejected_error with exactly one operational alert
    -- not one alert per tick forever."""
    from pipeline.sweep.settings_sweep import SweepOutcome

    repo = _FakeRepo([])
    brain = _FakeBrainForCorrelation({})
    worker = _make_worker(repo, brain)

    outcome = SweepOutcome(
        rejected_at_stage0=False, aborted_stage="stage0", runs=[],
        winning_settings=None, winning_result=None,
        robust_count=0, sweep_total=1, error_count=1, fragile=True,
    )
    _patch_sweep(monkeypatch, outcome)

    last_status = None
    for _ in range(MAX_CANDIDATE_ATTEMPTS):
        last_status = asyncio.run(worker._process_candidate({"id": 9, "expression": "expr"}))

    assert last_status == "rejected_error"
    assert repo.candidate_attempts[9] == MAX_CANDIDATE_ATTEMPTS
    assert repo.statuses[9] == "rejected_error"
    assert len(worker.notifier.operational_alerts) == 1


# --- Update 05: template tier must not starve the LLM tiers -------------


class _FakeLLMAdapter:
    """Minimal stand-in for LLMAdapter -- just enough for
    propose_new_ideas()/mutate_candidate() to call through it."""

    def __init__(self, reasoning_items, mechanical_items=None):
        import json
        self._reasoning_raw = json.dumps(reasoning_items)
        self._mechanical_raw = json.dumps(mechanical_items or [])
        self.reasoning_calls = 0
        self.mechanical_calls = 0

    def reasoning_call(self, prompt):
        self.reasoning_calls += 1
        return self._reasoning_raw, "gemini"

    def mechanical_call(self, prompt):
        self.mechanical_calls += 1
        return self._mechanical_raw, "groq"


def test_template_tier_does_not_starve_llm_tiers_when_pool_covers_the_gap():
    """Update 05 regression test for the root cause of the false 'LLM key
    health' alarm: the template pool (53 expressions) covers most ticks'
    `needed` on its own, which used to mean propose_new_ideas() never got
    called and llm_usage never got fresh rows. template_tier_max_share
    must reserve real room for the LLM tiers even when the template pool
    alone could satisfy `needed`."""
    repo = _FakeRepo([])
    brain = _FakeBrainConcurrencyTracker(max_concurrent=2)
    config = Config(
        database_url="postgres://fake", brain_username="u", brain_password="p",
        brain_max_concurrent_sims=2, template_tier_max_share=0.5,
    )
    llm = _FakeLLMAdapter(
        reasoning_items=[{"expression": "rank(new_idea)", "category": "novel"}],
    )
    worker = Worker(config, repo, brain, _FakeNotifier(), llm=llm)

    added = asyncio.run(worker._top_up_queue(10))

    assert llm.reasoning_calls == 1, (
        "template tier consumed the whole gap again -- the LLM reasoning "
        "tier never got called, which is exactly the bug that made "
        "llm_usage (and therefore heartbeat key health) go stale forever"
    )
    assert added >= 5  # at least the template_tier_max_share portion landed


def test_top_up_queue_dedupes_against_existing_expressions():
    """Update 05: an expression already in the DB should not be inserted
    (and counted) again -- wasted BRAIN slot / wasted LLM tokens."""
    repo = _FakeRepo([])
    existing = {"rank(close)"}
    repo.expression_exists = lambda expr: expr in existing
    brain = _FakeBrainConcurrencyTracker(max_concurrent=2)
    config = Config(
        database_url="postgres://fake", brain_username="u", brain_password="p",
        brain_max_concurrent_sims=2, template_tier_max_share=1.0,
    )
    worker = Worker(config, repo, brain, _FakeNotifier(), llm=None)

    inserted = worker._insert_candidate_deduped("rank(close)", "cat", "template")
    assert inserted is False

    inserted_new = worker._insert_candidate_deduped("rank(open)", "cat", "template")
    assert inserted_new is True
