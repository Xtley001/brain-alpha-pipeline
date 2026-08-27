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
        self.telegram_sent_ids = []

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
        self.telegram_sent_ids.append(review_id)

    def get_meta(self, key):
        return self.meta.get(key)

    def set_meta(self, key, value):
        self.meta[key] = value

    def reclaim_orphaned_running(self, older_than_minutes=30):
        self.reclaim_calls += 1
        return 0

    def insert_candidate(self, expression, category, generation_tier, provider=None):
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
        worker.executor.process_candidates_bounded(max_candidates=15, deadline=deadline)
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
        worker.executor.process_candidates_bounded(max_candidates=4, deadline=deadline)
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
        worker.executor.process_candidates_bounded(max_candidates=15, deadline=already_past_deadline)
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

    status = asyncio.run(worker.executor.process_candidate({"id": 1, "expression": "expr"}))

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

    status = asyncio.run(worker.executor.process_candidate({"id": 1, "expression": "expr"}))

    assert status == "passed"
    assert repo.statuses[1] == "passed"
    assert repo.pool_upserts == [("alpha_123", {"2026-01-01": 0.01, "2026-01-02": 0.02})]
    assert len(worker.notifier.candidate_alerts) == 1
    assert repo.telegram_sent_ids == [1]  # mark_telegram_sent called on send success


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

    status = asyncio.run(worker.executor.process_candidate({"id": 7, "expression": "expr"}))

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
        last_status = asyncio.run(worker.executor.process_candidate({"id": 9, "expression": "expr"}))

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

    added = asyncio.run(worker.generation.top_up_queue(10))

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

    # Update 10 Item 1: _insert_candidate_deduped is now async (its two
    # repo calls are offloaded via asyncio.to_thread), so it must be
    # awaited here rather than called synchronously.
    inserted = asyncio.run(worker.generation.insert_candidate_deduped("rank(close)", "cat", "template"))
    assert inserted is False

    inserted_new = asyncio.run(worker.generation.insert_candidate_deduped("rank(open)", "cat", "template"))
    assert inserted_new is True


# --- Update 10 Item 1: repo calls inside _process_candidate must not ----
# --- block the event loop and serialize a concurrent batch --------------


class _SlowFakeRepo(_FakeRepo):
    """Fake Repo whose methods sleep a small, deterministic duration to
    simulate a real network round trip to Neon -- used to prove
    _process_candidate's DB calls are non-blocking (Item 1), not to test
    correctness of the calls themselves (already covered by _FakeRepo's
    other consumers)."""

    LATENCY = 0.05

    def _delay(self):
        import time as _time
        _time.sleep(self.LATENCY)

    def set_candidate_status(self, candidate_id, status, **kwargs):
        self._delay()
        super().set_candidate_status(candidate_id, status, **kwargs)

    def insert_review_store(self, row):
        self._delay()
        return super().insert_review_store(row)

    def mark_telegram_sent(self, review_id):
        self._delay()
        super().mark_telegram_sent(review_id)

    def get_pool_returns(self):
        self._delay()
        return super().get_pool_returns()

    def upsert_pool_returns(self, alpha_id, series):
        self._delay()
        super().upsert_pool_returns(alpha_id, series)

    def insert_sweep_run(self, *a, **k):
        self._delay()
        return super().insert_sweep_run(*a, **k)

    def insert_sweep_run_error(self, *a, **k):
        self._delay()
        return super().insert_sweep_run_error(*a, **k)


def test_process_candidate_repo_calls_do_not_serialize_a_concurrent_batch(monkeypatch):
    """Update 10 Item 1 regression test.

    Before this fix, every `self.repo.*` call inside `_process_candidate`
    (an `async def` run concurrently in batches via `asyncio.gather` in
    `_process_candidates_bounded`) executed synchronously, directly on the
    event loop -- including the incremental sweep_runs writes made via the
    `persist_run` callback. That serializes an entire concurrent batch on
    Postgres I/O that has nothing to do with BRAIN, defeating the whole
    point of dispatching candidates concurrently.

    This test drives several candidates through `_process_candidate`
    concurrently (via asyncio.gather, matching how
    `_process_candidates_bounded` dispatches a batch) against a `Repo`
    whose methods each sleep `_SlowFakeRepo.LATENCY` seconds, and asserts
    the wall-clock time for the whole batch stays close to a single
    candidate's own latency chain rather than growing linearly with the
    number of candidates -- i.e. closer to max(latencies) than
    sum(latencies). This must fail against the pre-fix code (where it
    would take roughly n * (repo calls per candidate) * LATENCY) and pass
    after the fix."""
    import time as time_module

    from pipeline.sweep.settings_sweep import Settings, SweepOutcome, SweepRun

    settings = Settings(
        delay=1, universe="TOP3000", neutralization="SUBINDUSTRY", decay=8,
        truncation=0.05, pasteurization=True, nan_handling=False,
    )

    def make_outcome(alpha_id):
        winning_result = SimResult(sharpe=2.0, fitness=1.5, turnover=0.3, alpha_id=alpha_id)
        run = SweepRun(stage="stage0", settings=settings, result=winning_result)
        return SweepOutcome(
            rejected_at_stage0=False, aborted_stage=None, runs=[run],
            winning_settings=settings, winning_result=winning_result,
            robust_count=5, sweep_total=41, error_count=0, fragile=False,
        )

    n = 4
    repo = _SlowFakeRepo([])
    brain = _FakeBrainForCorrelation({f"alpha_{i}": {"2026-01-01": 0.01} for i in range(n)})
    worker = _make_worker(repo, brain, max_concurrent=n)

    import pipeline.run_worker as run_worker_module

    async def fake_run_staged_sweep(expression, *args, **kwargs):
        # Also exercises the persist_run callback path (the sweep_runs
        # writes), which is the one repo call site that can't simply be
        # `await`ed since run_staged_sweep invokes it as a synchronous
        # callback -- see _persist_sweep_run's docstring.
        outcome = make_outcome(expression)
        persist_run = kwargs.get("persist_run")
        if persist_run:
            for run in outcome.runs:
                persist_run(run)
        return outcome

    monkeypatch.setattr(run_worker_module, "run_staged_sweep", fake_run_staged_sweep)

    candidates = [{"id": i, "expression": f"alpha_{i}"} for i in range(n)]

    start = time_module.monotonic()
    statuses = asyncio.run(_gather_process_candidate(worker, candidates))
    elapsed = time_module.monotonic() - start

    assert statuses == ["passed"] * n

    # Repo calls per candidate on this passing path: persist_run (1
    # sweep_runs write) + get_pool_returns + insert_review_store +
    # set_candidate_status + mark_telegram_sent + upsert_pool_returns = 6
    # sleeping calls total.
    #
    # Update 10 Item 4 note: get_pool_returns + upsert_pool_returns are, as
    # of that item, intentionally serialized across the whole batch by
    # `self._correlation_lock` (guarding exactly that read-compare-write
    # sequence, to close the reopened correlation-gate race) -- so those 2
    # of the 6 calls are *expected* to add up linearly with n, not overlap.
    # The other 4 calls have no such lock and must still overlap across
    # candidates. Expected-best-case wall time is therefore roughly
    # `n * locked_latency + unlocked_latency` (serialized lock portion plus
    # one overlapped unlocked portion), which is well under the
    # fully-serialized-on-every-call worst case this test exists to catch
    # (`n * 6 * LATENCY`).
    locked_calls = 2  # get_pool_returns, upsert_pool_returns
    unlocked_calls = 4  # persist_run, insert_review_store, set_candidate_status, mark_telegram_sent
    fully_serial_worst_case = n * (locked_calls + unlocked_calls) * _SlowFakeRepo.LATENCY
    expected_best_case = n * locked_calls * _SlowFakeRepo.LATENCY + unlocked_calls * _SlowFakeRepo.LATENCY
    # Generous margin above the expected best case, but still well below
    # the fully-serial worst case, so this only fails if calls outside the
    # correlation lock stop overlapping.
    threshold = expected_best_case * 1.8
    assert threshold < fully_serial_worst_case, "test thresholds not meaningfully distinguishing serial vs concurrent"
    assert elapsed < threshold, (
        f"elapsed={elapsed:.3f}s for {n} concurrently-dispatched candidates "
        f"exceeds the expected-with-overlap threshold ({threshold:.3f}s; "
        f"fully-serial worst case would be {fully_serial_worst_case:.3f}s) -- "
        f"repo calls outside the Item 4 correlation lock are still blocking "
        f"the event loop and serializing the batch"
    )


async def _gather_process_candidate(worker, candidates):
    return await asyncio.gather(*(worker.executor.process_candidate(c) for c in candidates))


# --- Update 10 Item 9.3: external healthcheck ping -----------------------


def test_healthcheck_ping_is_noop_when_unconfigured():
    """Config.healthcheck_ping_url defaults to None -- send_healthcheck_ping
    must not attempt any network call in that case (and must not raise)."""
    from pipeline.run_worker import RunReporter

    reporter = RunReporter(repo=_FakeRepo([]), notifier=_FakeNotifier(), healthcheck_ping_url=None)
    asyncio.run(reporter.send_healthcheck_ping())  # must not raise


def test_healthcheck_ping_calls_configured_url(monkeypatch):
    from pipeline.run_worker import RunReporter

    calls = []
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda url, timeout=None: calls.append((url, timeout)),
    )
    reporter = RunReporter(
        repo=_FakeRepo([]), notifier=_FakeNotifier(), healthcheck_ping_url="https://hc-ping.com/fake-uuid"
    )
    asyncio.run(reporter.send_healthcheck_ping())
    assert calls == [("https://hc-ping.com/fake-uuid", 10)]


def test_healthcheck_ping_failure_is_swallowed(monkeypatch):
    """A ping failure (network error, service down, etc.) must never
    propagate -- run_once() already completed successfully by the time
    this fires, and a monitoring side-channel failing must not turn a
    good run into a crashed one."""
    from pipeline.run_worker import RunReporter

    def _raise(url, timeout=None):
        raise OSError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", _raise)
    reporter = RunReporter(
        repo=_FakeRepo([]), notifier=_FakeNotifier(), healthcheck_ping_url="https://hc-ping.com/fake-uuid"
    )
    asyncio.run(reporter.send_healthcheck_ping())  # must not raise


# --- Update 10 Item 9.4: _best_effort_startup_alert .strip() consistency -


def test_best_effort_startup_alert_strips_whitespace_like_config_optional(monkeypatch):
    """Update 10 Item 9.4 regression test. _best_effort_startup_alert reads
    TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID directly from os.environ (bypassing
    Config._optional(), deliberately -- see its docstring), which used to
    mean a trailing-whitespace env var value (e.g. from a pasted secret
    with a stray newline) behaved differently here than via the normal
    Config.from_env() path, which does strip(). This confirms the two
    paths now agree."""
    from pipeline.run_worker import _best_effort_startup_alert

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "  token-with-whitespace  \n")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "\tchat-id-with-whitespace\t")

    captured = {}

    class _CapturingNotifier:
        def __init__(self, token, chat_id):
            captured["token"] = token
            captured["chat_id"] = chat_id

        def send_operational_alert(self, message):
            captured["message"] = message

    import pipeline.run_worker as run_worker_module
    monkeypatch.setattr(run_worker_module, "TelegramNotifier", _CapturingNotifier)

    _best_effort_startup_alert("test message")

    assert captured["token"] == "token-with-whitespace"
    assert captured["chat_id"] == "chat-id-with-whitespace"


# --- Update 10 Item 2: a Telegram delivery failure after a candidate -----
# --- has already passed must never flip its status back -----------------


class _RaisingNotifier(_FakeNotifier):
    """send_candidate_alert raises every time -- simulates Telegram's
    legacy Markdown parser rejecting the message with a 400 (see
    telegram_notify.py's escape_markdown / Item 2's root-cause fix)."""

    def send_candidate_alert(self, row):
        raise RuntimeError("Telegram API returned 400 Bad Request: can't parse entities")


def test_notifier_failure_after_pass_does_not_revert_candidate_status(monkeypatch):
    """Update 10 Item 2 regression test. Before this fix, an unguarded
    `self.notifier.send_candidate_alert(row)` call sat between
    `set_candidate_status(candidate_id, 'passed')` and
    `mark_telegram_sent(review_id)`, with no try/except -- a delivery
    failure propagated into _process_candidate's broad `except Exception`
    handler, which called `_record_candidate_error` and flipped an
    already-'passed' candidate (with an already-inserted review_store row)
    back toward 'pending'/'rejected_error'.

    This drives a full passing outcome through `_process_candidate` with a
    notifier whose `send_candidate_alert` always raises, and asserts:
    (a) the method still returns 'passed', not an error status,
    (b) `repo.statuses[candidate_id]` is 'passed' and was never
        overwritten with anything else afterward,
    (c) no candidate-error/attempt-cap path was ever triggered (no
        operational alert, no attempts recorded)."""
    from pipeline.sweep.settings_sweep import Settings, SweepOutcome

    repo = _FakeRepo([])
    brain = _FakeBrainForCorrelation({"alpha_123": {"2026-01-01": 0.01, "2026-01-02": 0.02}})
    worker = _make_worker(repo, brain)
    worker.notifier = _RaisingNotifier()
    worker.executor.notifier = worker.notifier  # CandidateExecutor holds its own notifier reference

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

    status = asyncio.run(worker.executor.process_candidate({"id": 1, "expression": "expr"}))

    assert status == "passed"
    assert repo.statuses[1] == "passed"
    # The pool upsert (which happens after the guarded notifier call) must
    # still have run -- a delivery failure must not short-circuit the rest
    # of the passing path.
    assert repo.pool_upserts == [("alpha_123", {"2026-01-01": 0.01, "2026-01-02": 0.02})]
    # The attempt-cap/error path must never have been triggered.
    assert repo.candidate_attempts == {}
    assert worker.notifier.operational_alerts == []
    # mark_telegram_sent must only be called on send *success* -- a failed
    # delivery must stay honestly discoverable (no telegram_sent_at set).
    assert repo.telegram_sent_ids == []


# --- Update 10 Item 4: correlation gate must not be defeated by batch ----
# --- concurrency -----------------------------------------------------------


def test_two_near_duplicate_candidates_in_same_batch_do_not_both_pass_correlation(monkeypatch):
    """Update 10 Item 4 regression test -- the exact bug this item fixes.

    Update 02 fed a passed candidate's returns back into pool_returns
    immediately so the *next* candidate's correlation check could see it.
    Update 04 then dispatched a whole batch of candidates concurrently via
    asyncio.gather, so two near-duplicate candidates claimed into the same
    batch each called get_pool_returns() independently near the start of
    their own run, before either had upserted -- both could see the same
    stale (empty) pool and both pass, undetected by each other.

    This drives two candidates with *identical* return streams through
    `_process_candidates_bounded` in the same batch (batch size >= 2) and
    asserts at most one of them ends 'passed'. Must fail against the
    pre-Item-4 code (both would pass) and pass after the fix (the second
    to acquire `self._correlation_lock` sees the first's freshly-upserted
    returns and gets rejected on correlation)."""
    from pipeline.sweep.settings_sweep import Settings, SweepOutcome

    settings = Settings(
        delay=1, universe="TOP3000", neutralization="SUBINDUSTRY", decay=8,
        truncation=0.05, pasteurization=True, nan_handling=False,
    )
    # Identical return series for both candidates -- an identical stream
    # correlates at 1.0 with itself, which must fail the |corr| <=
    # MAX_CORRELATION (0.7) gate once the pool actually contains it.
    identical_returns = {f"2026-01-{d:02d}": 0.01 * d for d in range(1, 25)}

    def make_outcome(alpha_id):
        winning_result = SimResult(sharpe=2.0, fitness=1.5, turnover=0.3, alpha_id=alpha_id)
        return SweepOutcome(
            rejected_at_stage0=False, aborted_stage=None, runs=[],
            winning_settings=settings, winning_result=winning_result,
            robust_count=5, sweep_total=41, error_count=0, fragile=False,
        )

    import pipeline.run_worker as run_worker_module

    async def fake_run_staged_sweep(expression, *args, **kwargs):
        # Both candidates' sweeps "finish" at effectively the same moment
        # -- asyncio.sleep(0) yields control so both coroutines reach the
        # correlation-check section before either has upserted, which is
        # exactly the race window Item 4 closes.
        await asyncio.sleep(0)
        return make_outcome(expression)

    monkeypatch.setattr(run_worker_module, "run_staged_sweep", fake_run_staged_sweep)

    repo = _FakeRepo([
        {"id": 1, "expression": "dup_a"},
        {"id": 2, "expression": "dup_b"},
    ])
    brain = _FakeBrainForCorrelation({"dup_a": identical_returns, "dup_b": identical_returns})
    worker = _make_worker(repo, brain, max_concurrent=2)

    import time as time_module
    deadline = time_module.monotonic() + 5
    batches_run, processed, stopped_reason, stage_counts = asyncio.run(
        worker.executor.process_candidates_bounded(max_candidates=2, deadline=deadline)
    )

    assert processed == 2
    passed_count = sum(1 for s in repo.statuses.values() if s == "passed")
    assert passed_count <= 1, (
        f"{passed_count} candidates passed the correlation gate out of an "
        f"identical-returns pair claimed into the same batch -- the "
        f"correlation self-consistency check is not seeing its own "
        f"sibling's result (Item 4 race reopened)"
    )
    rejected_count = sum(1 for s in repo.statuses.values() if s == "rejected_correlation")
    assert passed_count + rejected_count == 2
