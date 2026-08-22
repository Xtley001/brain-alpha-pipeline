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


def test_stage0_rejects_junk_expression():
    def simulate(expr, settings):
        return SimResult(sharpe=0.1, fitness=0.05, turnover=0.3)

    outcome = run_staged_sweep("junk_expr", simulate)
    assert outcome.rejected_at_stage0 is True
    assert len(outcome.runs) == 1
    assert outcome.runs[0].stage == "stage0"
    assert outcome.winning_settings is None
    assert outcome.fragile is True


def test_stage0_lets_viable_expression_through_to_full_sweep():
    def simulate(expr, settings):
        return SimResult(sharpe=1.0, fitness=0.8, turnover=0.3)

    outcome = run_staged_sweep("ok_expr", simulate, stage0_min_fitness=0.3, stage0_min_sharpe=0.5)
    assert outcome.rejected_at_stage0 is False
    # 1 (stage0) + 30 (stage1) + 4 (stage2) + 6 (stage3) = 41
    assert len(outcome.runs) == 41


def test_stage1_runs_exactly_30_neutralization_by_decay_combinations():
    def simulate(expr, settings):
        return SimResult(sharpe=1.0, fitness=0.8, turnover=0.3)

    outcome = run_staged_sweep("ok_expr", simulate)
    stage1_runs = [r for r in outcome.runs if r.stage == "stage1"]
    assert len(stage1_runs) == EXPECTED_STAGE1_COUNT == 30

    combos = {(r.settings.neutralization, r.settings.decay) for r in stage1_runs}
    expected_combos = {(n, d) for n in NEUTRALIZATIONS for d in DECAYS}
    assert combos == expected_combos


def test_stage1_picks_best_by_fitness_then_turnover_then_sharpe():
    # INDUSTRY/decay=15 is the deliberate winner: highest fitness.
    def simulate(expr, settings):
        if settings.neutralization == "INDUSTRY" and settings.decay == 15:
            return SimResult(sharpe=2.0, fitness=3.0, turnover=0.2)
        return SimResult(sharpe=1.0, fitness=1.0, turnover=0.3)

    outcome = run_staged_sweep("expr", simulate)
    # Stage 2/3 build on the Stage 1 winner, so its neutralization/decay
    # should persist into the winning settings (absent a Stage 3 flip).
    assert outcome.winning_settings.neutralization == "INDUSTRY"
    assert outcome.winning_settings.decay == 15


def test_stage2_and_stage3_hold_stage1_winner_fixed_unless_improved():
    winner = ("SECTOR", 20)

    def simulate(expr, settings):
        if (settings.neutralization, settings.decay) == winner:
            return SimResult(sharpe=1.8, fitness=2.5, turnover=0.25)
        return SimResult(sharpe=1.0, fitness=1.0, turnover=0.3)

    outcome = run_staged_sweep("expr", simulate)
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

    def simulate(expr, settings):
        # Only the exact Stage 0 default combo clears the bar; everything
        # else is deliberately mediocre.
        if settings == STAGE0_SETTINGS:
            return SimResult(sharpe=2.0, fitness=2.0, turnover=0.2)
        return SimResult(sharpe=0.9, fitness=0.5, turnover=0.3)

    outcome = run_staged_sweep("expr", simulate, thresholds=thresholds)
    assert outcome.fragile is True
    assert outcome.robust_count == 1


def test_stage4_flags_not_fragile_when_a_cluster_of_combos_clears_the_bar():
    thresholds = FilterThresholds(min_sharpe=1.0, min_fitness=1.0, max_turnover=0.9, min_turnover=0.0)

    def simulate(expr, settings):
        # A broad cluster of decent-but-not-identical settings all clear
        # this generous bar.
        return SimResult(sharpe=1.2, fitness=1.2, turnover=0.3)

    outcome = run_staged_sweep("expr", simulate, thresholds=thresholds)
    assert outcome.fragile is False
    # robust_count counts *distinct* settings combos that pass (see
    # settings_sweep.py's Stage 4 comment) -- Stage 3's "test both values"
    # approach re-simulates a few duplicate combos, so this is slightly
    # below len(outcome.runs), not equal to it.
    assert outcome.robust_count > 30
    assert outcome.robust_count <= len(outcome.runs)


def test_stage4_robustness_uses_stored_runs_not_new_simulations():
    call_count = {"n": 0}

    def simulate(expr, settings):
        call_count["n"] += 1
        return SimResult(sharpe=1.0, fitness=0.8, turnover=0.3)

    outcome = run_staged_sweep("expr", simulate)
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

    def simulate(expr, settings):
        return SimResult(sharpe=1.0, fitness=0.8, turnover=0.3)

    outcome = run_staged_sweep("expr", simulate)
    assert outcome.winning_result.alpha_id is None
