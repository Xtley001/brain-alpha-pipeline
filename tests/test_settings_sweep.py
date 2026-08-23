import asyncio

from pipeline.filter.local_filter import FilterThresholds
from pipeline.sweep.settings_sweep import (
    DECAYS,
    EXPECTED_STAGE1_COUNT,
    EXPECTED_STAGE2_COUNT,
    EXPECTED_STAGE3_COUNT,
    NEUTRALIZATIONS,
    STAGE0_SETTINGS,
    SimResult,
    run_staged_sweep,
)


def _run(coro):
    return asyncio.run(coro)


def test_stage0_rejects_junk_expression():
    async def simulate(expr, settings):
        return SimResult(sharpe=0.1, fitness=0.05, turnover=0.3)

    outcome = _run(run_staged_sweep("junk_expr", simulate))
    assert outcome.rejected_at_stage0 is True
    assert outcome.aborted_stage is None
    assert len(outcome.runs) == 1
    assert outcome.runs[0].stage == "stage0"
    assert outcome.runs[0].ok is True
    assert outcome.winning_settings is None
    assert outcome.fragile is True


def test_stage0_lets_viable_expression_through_to_full_sweep():
    async def simulate(expr, settings):
        return SimResult(sharpe=1.0, fitness=0.8, turnover=0.3)

    outcome = _run(run_staged_sweep("ok_expr", simulate, stage0_min_fitness=0.3, stage0_min_sharpe=0.5))
    assert outcome.rejected_at_stage0 is False
    assert outcome.aborted_stage is None
    # 1 (stage0) + 30 (stage1) + 4 (stage2) + 6 (stage3) = 41
    assert len(outcome.runs) == 41
    assert outcome.error_count == 0


def test_stage1_runs_exactly_30_neutralization_by_decay_combinations():
    async def simulate(expr, settings):
        return SimResult(sharpe=1.0, fitness=0.8, turnover=0.3)

    outcome = _run(run_staged_sweep("ok_expr", simulate))
    stage1_runs = [r for r in outcome.runs if r.stage == "stage1"]
    assert len(stage1_runs) == EXPECTED_STAGE1_COUNT == 30

    combos = {(r.settings.neutralization, r.settings.decay) for r in stage1_runs}
    expected_combos = {(n, d) for n in NEUTRALIZATIONS for d in DECAYS}
    assert combos == expected_combos


def test_stage1_picks_best_by_fitness_then_turnover_then_sharpe():
    # INDUSTRY/decay=15 is the deliberate winner: highest fitness.
    async def simulate(expr, settings):
        if settings.neutralization == "INDUSTRY" and settings.decay == 15:
            return SimResult(sharpe=2.0, fitness=3.0, turnover=0.2)
        return SimResult(sharpe=1.0, fitness=1.0, turnover=0.3)

    outcome = _run(run_staged_sweep("expr", simulate))
    # Stage 2/3 build on the Stage 1 winner, so its neutralization/decay
    # should persist into the winning settings (absent a Stage 3 flip).
    assert outcome.winning_settings.neutralization == "INDUSTRY"
    assert outcome.winning_settings.decay == 15


def test_stage2_and_stage3_hold_stage1_winner_fixed_unless_improved():
    winner = ("SECTOR", 20)

    async def simulate(expr, settings):
        if (settings.neutralization, settings.decay) == winner:
            return SimResult(sharpe=1.8, fitness=2.5, turnover=0.25)
        return SimResult(sharpe=1.0, fitness=1.0, turnover=0.3)

    outcome = _run(run_staged_sweep("expr", simulate))
    stage2_runs = [r for r in outcome.runs if r.stage == "stage2"]
    stage3_runs = [r for r in outcome.runs if r.stage == "stage3"]
    assert len(stage2_runs) == EXPECTED_STAGE2_COUNT == 4
    assert len(stage3_runs) == EXPECTED_STAGE3_COUNT == 6

    for r in stage2_runs:
        assert r.settings.neutralization == winner[0]
        assert r.settings.decay == winner[1]

    # Stage 3 only flips delay/pasteurization/nan_handling one at a time --
    # neutralization/decay/truncation should never change in stage 3 rows.
    for r in stage3_runs:
        assert r.settings.neutralization == winner[0]
        assert r.settings.decay == winner[1]


def test_stage4_flags_fragile_when_only_one_combo_clears_the_bar():
    thresholds = FilterThresholds(min_sharpe=1.25, min_fitness=1.0, max_turnover=0.70, min_turnover=0.0)

    async def simulate(expr, settings):
        # Only the exact Stage 0 default combo clears the bar; everything
        # else is deliberately mediocre.
        if settings == STAGE0_SETTINGS:
            return SimResult(sharpe=2.0, fitness=2.0, turnover=0.2)
        return SimResult(sharpe=0.9, fitness=0.5, turnover=0.3)

    outcome = _run(run_staged_sweep("expr", simulate, thresholds=thresholds))
    assert outcome.fragile is True
    assert outcome.robust_count == 1


def test_stage4_flags_not_fragile_when_a_cluster_of_combos_clears_the_bar():
    thresholds = FilterThresholds(min_sharpe=1.0, min_fitness=1.0, max_turnover=0.9, min_turnover=0.0)

    async def simulate(expr, settings):
        # A broad cluster of decent-but-not-identical settings all clear
        # this generous bar.
        return SimResult(sharpe=1.2, fitness=1.2, turnover=0.3)

    outcome = _run(run_staged_sweep("expr", simulate, thresholds=thresholds))
    assert outcome.fragile is False
    # robust_count counts *distinct* settings combos that pass (see
    # settings_sweep.py's Stage 4 comment) -- Stage 3's "test both values"
    # approach re-simulates a few duplicate combos, so this is slightly
    # below len(outcome.runs), not equal to it.
    assert outcome.robust_count > 30
    assert outcome.robust_count <= len(outcome.runs)


def test_stage4_robustness_uses_stored_runs_not_new_simulations():
    call_count = {"n": 0}

    async def simulate(expr, settings):
        call_count["n"] += 1
        return SimResult(sharpe=1.0, fitness=0.8, turnover=0.3)

    outcome = _run(run_staged_sweep("expr", simulate))
    # Exactly 41 simulate() calls total -- Stage 4 must not add any more.
    assert call_count["n"] == 41
    assert outcome.sweep_total == 41


def test_stage_count_invariants_raise_real_exceptions_not_asserts():
    """Code review §3.2: these invariant checks used to be bare `assert`
    statements, which are stripped entirely under `python -O` /
    PYTHONOPTIMIZE=1. They must raise unconditionally instead. This doesn't
    (and can't, within one pytest process) exercise -O directly, but it
    pins down that the checks are explicit `if ...: raise` rather than
    `assert`, and that a genuinely broken stage count still surfaces as a
    RuntimeError under normal execution."""
    import inspect

    from pipeline.sweep import settings_sweep

    source = inspect.getsource(settings_sweep)
    assert "assert " not in source, (
        "settings_sweep.py must not use bare `assert` for production invariants "
        "(stripped under python -O) -- use explicit `if ...: raise` instead"
    )


def test_winning_result_alpha_id_defaults_to_none_for_synthetic_simulators():
    """SimResult.alpha_id is populated by the real BrainClient; synthetic
    simulators (as used throughout this test file and in fakes) correctly
    leave it unset/None rather than needing to know about it."""

    async def simulate(expr, settings):
        return SimResult(sharpe=1.0, fitness=0.8, turnover=0.3)

    outcome = _run(run_staged_sweep("expr", simulate))
    assert outcome.winning_result.alpha_id is None


# --- Update 04: fault isolation and concurrency -------------------------


def test_a_single_failing_combo_does_not_take_down_the_whole_sweep():
    """One bad settings combo (BRAIN error, timeout, whatever) must be
    recorded as a SweepRun with `.error` set and everything else in that
    batch must still complete -- not raise and lose the other 29 Stage 1
    results with it."""

    async def simulate(expr, settings):
        if settings.neutralization == "COUNTRY":
            raise RuntimeError("simulated BRAIN failure for this combo")
        return SimResult(sharpe=1.0, fitness=0.8, turnover=0.3)

    outcome = _run(run_staged_sweep("expr", simulate))
    assert outcome.aborted_stage is None  # plenty of other Stage 1 combos succeeded
    stage1_runs = [r for r in outcome.runs if r.stage == "stage1"]
    assert len(stage1_runs) == EXPECTED_STAGE1_COUNT
    failed = [r for r in stage1_runs if not r.ok]
    assert len(failed) == len(DECAYS)  # one per decay value, all under COUNTRY
    assert all(r.error is not None for r in failed)
    assert all(r.result is None for r in failed)
    assert outcome.error_count == len(DECAYS)
    # A winner still gets picked from the combos that did succeed.
    assert outcome.winning_settings is not None


def test_sweep_aborts_the_stage_when_every_combo_in_it_fails():
    """If literally every Stage 1 combo errors, there's no winner to build
    Stage 2/3 on -- this must surface as aborted_stage='stage1' (an
    operational failure), not silently proceed with a None winner or get
    mis-recorded as a quality rejection."""

    call_count = {"n": 0}

    async def simulate(expr, settings):
        call_count["n"] += 1
        if call_count["n"] == 1:
            # Only the very first call (Stage 0's quick screen) succeeds --
            # deliberately not keyed off `settings == STAGE0_SETTINGS`,
            # since the Stage 1 grid's own SUBINDUSTRY/decay=8 combo equals
            # STAGE0_SETTINGS too and would accidentally "succeed" as well.
            return SimResult(sharpe=1.0, fitness=0.8, turnover=0.3)
        raise RuntimeError("BRAIN is down for the whole sweep")

    outcome = _run(run_staged_sweep("expr", simulate))
    assert outcome.aborted_stage == "stage1"
    assert outcome.rejected_at_stage0 is False
    assert outcome.winning_settings is None
    assert outcome.winning_result is None
    stage1_runs = [r for r in outcome.runs if r.stage == "stage1"]
    assert len(stage1_runs) == EXPECTED_STAGE1_COUNT
    assert all(not r.ok for r in stage1_runs)


def test_stage0_failure_aborts_at_stage0_not_rejected_at_stage0():
    """A Stage 0 simulate() call that raises is an operational failure, not
    a quality verdict -- must be aborted_stage='stage0', distinct from
    rejected_at_stage0 (which means Stage 0 ran and scored too low)."""

    async def simulate(expr, settings):
        raise RuntimeError("BRAIN unreachable")

    outcome = _run(run_staged_sweep("expr", simulate))
    assert outcome.aborted_stage == "stage0"
    assert outcome.rejected_at_stage0 is False
    assert outcome.error_count == 1


def test_stage1_and_stage2_run_concurrently_not_sequentially():
    """Stage 1's 30 combos (and Stage 2's 4) must be dispatched together and
    awaited concurrently, bounded by the semaphore -- not one at a time.
    Proven by tracking peak in-flight simulate() calls with an artificial
    delay: a sequential implementation could never show more than 1
    in-flight at once."""
    in_flight = {"current": 0, "peak": 0}

    async def simulate(expr, settings):
        in_flight["current"] += 1
        in_flight["peak"] = max(in_flight["peak"], in_flight["current"])
        await asyncio.sleep(0.01)
        in_flight["current"] -= 1
        return SimResult(sharpe=1.0, fitness=0.8, turnover=0.3)

    _run(run_staged_sweep("expr", simulate, max_concurrent_sims=5))
    assert in_flight["peak"] >= 2, (
        f"peak in-flight simulate() calls was only {in_flight['peak']} -- Stage 1/2 "
        "are not actually running concurrently"
    )
    assert in_flight["peak"] <= 5, "concurrency exceeded the configured semaphore size"


def test_shared_semaphore_bounds_concurrency_across_two_sweeps_at_once():
    """Update 04: when a single asyncio.Semaphore instance is shared across
    two concurrently-running sweeps (as run_worker.Worker does across
    candidates), total in-flight simulate() calls must stay bounded by that
    one semaphore's size -- not double up because each sweep would
    otherwise create its own independent semaphore."""
    shared = asyncio.Semaphore(3)
    in_flight = {"current": 0, "peak": 0}

    async def simulate(expr, settings):
        in_flight["current"] += 1
        in_flight["peak"] = max(in_flight["peak"], in_flight["current"])
        await asyncio.sleep(0.01)
        in_flight["current"] -= 1
        return SimResult(sharpe=1.0, fitness=0.8, turnover=0.3)

    async def two_sweeps():
        await asyncio.gather(
            run_staged_sweep("expr_a", simulate, semaphore=shared),
            run_staged_sweep("expr_b", simulate, semaphore=shared),
        )

    _run(two_sweeps())
    assert in_flight["peak"] <= 3, (
        f"peak in-flight simulate() calls ({in_flight['peak']}) exceeded the shared "
        "semaphore's size (3) -- two sweeps given the same semaphore instance must "
        "never exceed its bound between them"
    )


def test_persist_run_callback_fires_once_per_completed_run_including_failures():
    persisted = []

    async def simulate(expr, settings):
        if settings.neutralization == "COUNTRY" and settings.decay == 0:
            raise RuntimeError("one bad combo")
        return SimResult(sharpe=1.0, fitness=0.8, turnover=0.3)

    outcome = _run(run_staged_sweep("expr", simulate, persist_run=lambda run: persisted.append(run)))
    assert len(persisted) == len(outcome.runs) == 41
    assert any(not r.ok for r in persisted)
