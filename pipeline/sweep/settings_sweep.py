"""
Staged settings sweep — implements the project's settings-sweep spec exactly:

  Stage 0: quick screen                (1 simulation)
  Stage 1: neutralization x decay grid (30 simulations)
  Stage 2: truncation refinement       (4 simulations)
  Stage 3: delay / pasteurization / nan sensitivity, one-at-a-time (6 sims)
  Stage 4: robustness check            (0 simulations — computed from
                                         the 41 stored above)

Deliberately NOT a cartesian product over every field (that's ~1,200 sims
per spec's own math) — this module enforces the staged, bounded search and
nothing else. `simulate` is injected so this is fully unit-testable without
touching the real BRAIN API.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable, Optional

from pipeline.filter.local_filter import FilterThresholds

# --- Settings field domains ---

NEUTRALIZATIONS = ["NONE", "MARKET", "SECTOR", "INDUSTRY", "SUBINDUSTRY", "COUNTRY"]
DECAYS = [0, 4, 8, 15, 20]
TRUNCATIONS = [0.01, 0.03, 0.05, 0.08, 0.10]
DELAYS = [0, 1]

DEFAULT_TRUNCATION = 0.05
DEFAULT_DELAY = 1
DEFAULT_UNIVERSE = "TOP3000"
DEFAULT_NEUTRALIZATION = "SUBINDUSTRY"
DEFAULT_DECAY = 8
DEFAULT_PASTEURIZATION = True
DEFAULT_NAN_HANDLING = False

EXPECTED_STAGE1_COUNT = len(NEUTRALIZATIONS) * len(DECAYS)  # 30
EXPECTED_STAGE2_COUNT = len(TRUNCATIONS) - 1  # 4 (0.05 already tested)
EXPECTED_STAGE3_COUNT = 6  # 2 alternatives each for delay, pasteurization, nan


@dataclass(frozen=True)
class Settings:
    delay: int
    universe: str
    neutralization: str
    decay: int
    truncation: float
    pasteurization: bool
    nan_handling: bool


STAGE0_SETTINGS = Settings(
    delay=DEFAULT_DELAY,
    universe=DEFAULT_UNIVERSE,
    neutralization=DEFAULT_NEUTRALIZATION,
    decay=DEFAULT_DECAY,
    truncation=DEFAULT_TRUNCATION,
    pasteurization=DEFAULT_PASTEURIZATION,
    nan_handling=DEFAULT_NAN_HANDLING,
)


@dataclass(frozen=True)
class SimResult:
    sharpe: float
    fitness: float
    turnover: float
    returns_ann: Optional[float] = None
    drawdown: Optional[float] = None
    # BRAIN alpha id this result came from, when available (real
    # BrainClient.simulate_one() populates it; synthetic/fake simulators in
    # tests leave it None). Lets the worker fetch the winning settings'
    # actual daily-return series for the correlation check without having
    # to re-simulate -- see pipeline/brain/client.py's get_alpha_pnl().
    alpha_id: Optional[str] = None


@dataclass(frozen=True)
class SweepRun:
    stage: str
    settings: Settings
    result: SimResult


@dataclass(frozen=True)
class SweepOutcome:
    rejected_at_stage0: bool
    runs: list
    winning_settings: Optional[Settings]
    winning_result: Optional[SimResult]
    robust_count: int
    sweep_total: int
    fragile: bool


# expression, settings -> SimResult
Simulator = Callable[[str, Settings], SimResult]


def _pick_best(runs: list) -> SweepRun:
    """Best Fitness; ties broken by lower Turnover, then higher Sharpe —
    per the settings-sweep spec."""
    return sorted(
        runs,
        key=lambda run: (-run.result.fitness, run.result.turnover, -run.result.sharpe),
    )[0]


def _is_improvement(candidate: SimResult, current: SimResult, thresholds: FilterThresholds) -> bool:
    """Stage 3 rule: 'keep any flip that improves Fitness without moving
    Sharpe/Turnover outside your local filter bounds.'"""
    if candidate.fitness <= current.fitness:
        return False
    return thresholds.passes(candidate)


def run_staged_sweep(
    expression: str,
    simulate: Simulator,
    thresholds: Optional[FilterThresholds] = None,
    stage0_min_fitness: float = 0.3,
    stage0_min_sharpe: float = 0.5,
) -> SweepOutcome:
    thresholds = thresholds or FilterThresholds.from_env()
    runs: list[SweepRun] = []

    # --- Stage 0: quick screen ---
    stage0_result = simulate(expression, STAGE0_SETTINGS)
    runs.append(SweepRun("stage0", STAGE0_SETTINGS, stage0_result))

    if stage0_result.fitness < stage0_min_fitness or stage0_result.sharpe < stage0_min_sharpe:
        return SweepOutcome(
            rejected_at_stage0=True,
            runs=runs,
            winning_settings=None,
            winning_result=None,
            robust_count=0,
            sweep_total=len(runs),
            fragile=True,
        )

    # --- Stage 1: neutralization x decay grid (30 sims, full grid, no early exit) ---
    stage1_runs: list[SweepRun] = []
    for neut in NEUTRALIZATIONS:
        for decay in DECAYS:
            s = Settings(
                delay=DEFAULT_DELAY,
                universe=DEFAULT_UNIVERSE,
                neutralization=neut,
                decay=decay,
                truncation=DEFAULT_TRUNCATION,
                pasteurization=DEFAULT_PASTEURIZATION,
                nan_handling=DEFAULT_NAN_HANDLING,
            )
            run = SweepRun("stage1", s, simulate(expression, s))
            runs.append(run)
            stage1_runs.append(run)

    if len(stage1_runs) != EXPECTED_STAGE1_COUNT:
        # A real exception, not `assert` -- `assert` statements are stripped
        # entirely under `python -O` / PYTHONOPTIMIZE=1, which would silently
        # turn this invariant check into a no-op in an optimized deployment.
        # This is exactly the invariant the audit checklist calls
        # out as important (a silent early-break bug), so it must raise
        # unconditionally.
        raise RuntimeError(
            f"Stage 1 must run exactly {EXPECTED_STAGE1_COUNT} sims, got {len(stage1_runs)} "
            "(silent early-break bug flagged in the audit checklist)"
        )

    best_stage1 = _pick_best(stage1_runs)

    # --- Stage 2: truncation refinement (4 remaining values; 0.05 already tested) ---
    remaining_truncations = [t for t in TRUNCATIONS if t != DEFAULT_TRUNCATION]
    if len(remaining_truncations) != EXPECTED_STAGE2_COUNT:
        raise RuntimeError(
            f"Stage 2 must sweep exactly {EXPECTED_STAGE2_COUNT} truncation values, "
            f"got {len(remaining_truncations)}"
        )

    stage2_runs: list[SweepRun] = []
    for trunc in remaining_truncations:
        s = replace(best_stage1.settings, truncation=trunc)
        run = SweepRun("stage2", s, simulate(expression, s))
        runs.append(run)
        stage2_runs.append(run)

    best_trunc_run = _pick_best([best_stage1] + stage2_runs)
    current_settings = best_trunc_run.settings
    current_result = best_trunc_run.result

    # --- Stage 3: delay / pasteurization / nan sensitivity (6 sims total) ---
    # Per the settings-sweep spec: "Test the 2 alternatives each
    # for Delay, Pasteurization, and Nan Handling one at a time (6 sims)."
    # Delay only has 2 possible values in the whole domain (0, 1), so "the 2
    # alternatives" means both values of each field are simulated (holding
    # everything else at the current best), not just the one value that
    # differs from whatever's currently held -- that's the only reading
    # that produces 6 sims (2 fields x 3... no: 2 values x 3 fields = 6)
    # rather than 3. Each field is tested independently against the current
    # best (not a further cartesian product across the three fields), and a
    # flip is kept only if it improves Fitness within the local filter
    # bounds -- so the three fields are evaluated one at a time in sequence,
    # each against whatever `current_settings` is at that point.
    stage3_runs: list[SweepRun] = []

    for delay_value in DELAYS:
        s = replace(current_settings, delay=delay_value)
        r = simulate(expression, s)
        run = SweepRun("stage3", s, r)
        runs.append(run)
        stage3_runs.append(run)
        if _is_improvement(r, current_result, thresholds):
            current_settings, current_result = s, r

    for past_value in (True, False):
        s = replace(current_settings, pasteurization=past_value)
        r = simulate(expression, s)
        run = SweepRun("stage3", s, r)
        runs.append(run)
        stage3_runs.append(run)
        if _is_improvement(r, current_result, thresholds):
            current_settings, current_result = s, r

    for nan_value in (True, False):
        s = replace(current_settings, nan_handling=nan_value)
        r = simulate(expression, s)
        run = SweepRun("stage3", s, r)
        runs.append(run)
        stage3_runs.append(run)
        if _is_improvement(r, current_result, thresholds):
            current_settings, current_result = s, r

    if len(stage3_runs) != EXPECTED_STAGE3_COUNT:
        raise RuntimeError(
            f"Stage 3 must run exactly {EXPECTED_STAGE3_COUNT} sims, got {len(stage3_runs)}"
        )

    # --- Stage 4: robustness check, computed from stored runs, no new sims ---
    # Per the settings-sweep spec: "Count how many distinct
    # settings combos also clear your local filter bar" -- distinct, not
    # raw passing rows. Stage 3's "test both values of each field" approach
    # (see the comment above) deliberately re-simulates the current-best
    # settings combo more than once (whichever of the two tested values
    # matches what's already held), which would otherwise inflate the count
    # with duplicates of the same single combo and defeat the whole point
    # of this check.
    distinct_passing_settings = {run.settings for run in runs if thresholds.passes(run.result)}
    robust_count = len(distinct_passing_settings)
    sweep_total = len(runs)
    # "If only the single best combo clears the bar ... flag fragile=True.
    # If a healthy cluster of nearby combos ... clear the bar, that's a much
    # stronger signal." No exact cluster-size cutoff is given in the spec;
    # treating "only the winner (or nobody) clears the bar" as the fragile
    # case is the literal reading of "only the single best combo clears" —
    # flagged here as the interpretation used, since the spec doesn't pin
    # down a number.
    fragile = robust_count <= 1

    return SweepOutcome(
        rejected_at_stage0=False,
        runs=runs,
        winning_settings=current_settings,
        winning_result=current_result,
        robust_count=robust_count,
        sweep_total=sweep_total,
        fragile=fragile,
    )
