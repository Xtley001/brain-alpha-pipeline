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

Update 04 rewrite — two invariants changed, both load-bearing, see the audit
docs for the full "why":

1. **Stage 1 (30 sims) and Stage 2 (4 sims) now run concurrently within the
   stage**, bounded by the `max_concurrent_sims` semaphore, instead of one
   simulate() call at a time. Every combo within a stage is independent of
   every other combo in that same stage (Stage 2 depends on Stage 1's
   *winner*, not on Stage 1's individual combos being sequential), so
   serializing them was pure wasted wall-clock time — see Update 03's
   throughput analysis (a 7-14 minute sweep per candidate, largely serial
   waiting, was blowing past the whole tick's time budget). Stage 3 stays
   sequential on purpose: each field's test genuinely depends on whichever
   value the previous field's test settled on (`current_settings` is
   mutated between fields) — that dependency is real, not an oversight.
2. **Per-combo fault isolation.** A single settings combo failing to
   simulate (BRAIN error, timeout, whatever) no longer raises out of the
   sweep and loses every other combo's results with it. `_safe_simulate`
   catches per-call and returns a `SweepRun` with `.error` set instead of
   `.result` — callers must check `.ok` before touching `.result`. This is
   what makes `asyncio.gather` on a batch always safe (nothing in the batch
   can raise), and what lets the worker's attempt-cap logic (see
   run_worker.py) tell "this idea genuinely scored low" apart from "BRAIN
   never actually answered for this combo".
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from typing import Awaitable, Callable, Optional

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
    """One attempted settings combo. Exactly one of `result`/`error` is set
    (Update 04 fault isolation -- see module docstring). `ok` is what every
    downstream consumer (best-pick, robustness count, persistence) must
    check before touching `.result`."""

    stage: str
    settings: Settings
    result: Optional[SimResult] = None
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.result is not None


@dataclass(frozen=True)
class SweepOutcome:
    rejected_at_stage0: bool  # clean quality rejection -- Stage 0 ran, scored too low
    aborted_stage: Optional[str]
    # Set when a stage couldn't produce ANY usable result (every combo in it
    # errored) -- an operational failure, not a quality verdict. None on a
    # normal outcome. Distinguishing this from rejected_at_stage0 is exactly
    # what lets the worker's attempt-cap retry logic tell "genuinely weak
    # idea" apart from "BRAIN never actually answered" (Update 04).
    runs: list
    winning_settings: Optional[Settings]
    winning_result: Optional[SimResult]
    robust_count: int
    sweep_total: int
    error_count: int
    fragile: bool


# expression, settings -> SimResult (async: real BrainClient.simulate_one is
# already a coroutine; see run_worker.py, which no longer wraps it in
# asyncio.run()/asyncio.to_thread() to fake sync-ness -- Update 03/04.)
AsyncSimulator = Callable[[str, Settings], Awaitable[SimResult]]
PersistRun = Optional[Callable[["SweepRun"], None]]


async def _safe_simulate(
    expression: str,
    settings: Settings,
    simulate: AsyncSimulator,
    stage: str,
    semaphore: asyncio.Semaphore,
) -> SweepRun:
    """Run exactly one combo, bounded by `semaphore`. Never raises -- a
    failure becomes a SweepRun with `.error` set instead of propagating, so
    one bad combo can never take down the rest of a batch or the sweep
    (Update 04 fault isolation)."""
    async with semaphore:
        try:
            result = await simulate(expression, settings)
            return SweepRun(stage, settings, result=result)
        except Exception as e:  # noqa: BLE001 -- intentionally broad: any failure
            # (BRAIN error, timeout, malformed response) becomes a recorded,
            # isolated failure rather than an unhandled exception.
            return SweepRun(stage, settings, error=str(e))


async def _run_batch(
    expression: str,
    settings_list: list[Settings],
    simulate: AsyncSimulator,
    stage: str,
    semaphore: asyncio.Semaphore,
    persist_run: PersistRun,
) -> list[SweepRun]:
    """Run every combo in `settings_list` concurrently, bounded by
    `semaphore`. Every task already catches its own error via
    `_safe_simulate`, so `gather` here can never raise on a single bad combo
    -- no `return_exceptions=True` needed, because nothing in this batch
    ever raises in the first place. `persist_run`, if given, is called once
    per completed run so results land in the DB incrementally rather than
    only after the whole 41-sim sweep finishes clean."""
    tasks = [_safe_simulate(expression, s, simulate, stage, semaphore) for s in settings_list]
    runs = await asyncio.gather(*tasks)
    if persist_run:
        for run in runs:
            persist_run(run)
    return list(runs)


def _pick_best(runs: list[SweepRun]) -> Optional[SweepRun]:
    """Best Fitness; ties broken by lower Turnover, then higher Sharpe —
    per the settings-sweep spec. Only considers runs that actually
    succeeded (Update 04: a failed combo has no `.result` to rank)."""
    ok_runs = [r for r in runs if r.ok]
    if not ok_runs:
        return None
    return sorted(
        ok_runs,
        key=lambda run: (-run.result.fitness, run.result.turnover, -run.result.sharpe),
    )[0]


def _is_improvement(candidate: SimResult, current: SimResult, thresholds: FilterThresholds) -> bool:
    """Stage 3 rule: 'keep any flip that improves Fitness without moving
    Sharpe/Turnover outside your local filter bounds.'"""
    if candidate.fitness <= current.fitness:
        return False
    return thresholds.passes(candidate)


async def run_staged_sweep(
    expression: str,
    simulate: AsyncSimulator,
    thresholds: Optional[FilterThresholds] = None,
    stage0_min_fitness: float = 0.3,
    stage0_min_sharpe: float = 0.5,
    max_concurrent_sims: int = 3,
    semaphore: Optional[asyncio.Semaphore] = None,
    persist_run: PersistRun = None,
) -> SweepOutcome:
    """
    DEVIATION FLAGGED (Update 04): the implementation spec's prose says to
    "move the semaphore down to wrap each individual simulate() call, and
    share ONE instance across every in-flight candidate" (so
    BRAIN_MAX_CONCURRENT_SIMS is a real global ceiling regardless of how
    many candidates are being processed concurrently), but the spec's own
    literal code sample has this function create a *fresh*
    `asyncio.Semaphore(max_concurrent_sims)` from an int every call. Taken
    literally, that would mean N concurrently-processed candidates each get
    their own independent semaphore of size `max_concurrent_sims`, allowing
    up to N * max_concurrent_sims simulate() calls in flight at once --
    exactly the "share one instance" property the prose says this change is
    for. Resolved here by accepting an optional pre-built `semaphore`:
    `run_worker.Worker` constructs exactly one `asyncio.Semaphore` in
    `__init__` and passes that same object into every candidate's call to
    this function, so concurrency really is bounded globally as the prose
    describes. `max_concurrent_sims` (the int) is kept as a fallback for
    standalone/test callers that don't need cross-candidate sharing and
    just want "a sweep with its own bounded fan-out" -- every existing test
    in tests/test_settings_sweep.py calls this without `semaphore` and
    still gets that behavior unchanged.
    """
    thresholds = thresholds or FilterThresholds.from_env()
    semaphore = semaphore or asyncio.Semaphore(max_concurrent_sims)
    runs: list[SweepRun] = []

    # --- Stage 0: quick screen, 1 sim ---
    stage0_run = await _safe_simulate(expression, STAGE0_SETTINGS, simulate, "stage0", semaphore)
    runs.append(stage0_run)
    if persist_run:
        persist_run(stage0_run)

    if not stage0_run.ok:
        # BRAIN itself couldn't return a result -- operational failure, not
        # "this idea is weak". Let the worker retry (attempt cap applies) --
        # see aborted_stage's docstring on SweepOutcome.
        return SweepOutcome(
            rejected_at_stage0=False,
            aborted_stage="stage0",
            runs=runs,
            winning_settings=None,
            winning_result=None,
            robust_count=0,
            sweep_total=1,
            error_count=1,
            fragile=True,
        )

    if stage0_run.result.fitness < stage0_min_fitness or stage0_run.result.sharpe < stage0_min_sharpe:
        return SweepOutcome(
            rejected_at_stage0=True,
            aborted_stage=None,
            runs=runs,
            winning_settings=None,
            winning_result=None,
            robust_count=0,
            sweep_total=1,
            error_count=0,
            fragile=True,
        )

    # --- Stage 1: neutralization x decay grid, 30 independent combos,
    # run concurrently (Update 04 -- previously sequential; see module
    # docstring for why that was the single biggest throughput bug found) ---
    stage1_settings = [
        Settings(
            delay=DEFAULT_DELAY,
            universe=DEFAULT_UNIVERSE,
            neutralization=neut,
            decay=decay,
            truncation=DEFAULT_TRUNCATION,
            pasteurization=DEFAULT_PASTEURIZATION,
            nan_handling=DEFAULT_NAN_HANDLING,
        )
        for neut in NEUTRALIZATIONS
        for decay in DECAYS
    ]
    stage1_runs = await _run_batch(expression, stage1_settings, simulate, "stage1", semaphore, persist_run)
    runs.extend(stage1_runs)

    if len(stage1_runs) != EXPECTED_STAGE1_COUNT:
        # A real exception, not `assert` -- `assert` statements are stripped
        # entirely under `python -O` / PYTHONOPTIMIZE=1, which would silently
        # turn this invariant check into a no-op in an optimized deployment.
        # This is exactly the invariant the audit checklist calls
        # out as important (a silent early-break bug), so it must raise
        # unconditionally.
        raise RuntimeError(
            f"Stage 1 must attempt exactly {EXPECTED_STAGE1_COUNT} combos, got {len(stage1_runs)} "
            "(silent early-break bug flagged in the audit checklist)"
        )

    best_stage1 = _pick_best(stage1_runs)
    if best_stage1 is None:
        # Every single Stage 1 combo errored -- can't proceed at all. This
        # is categorically different from Stage 0's rejected_at_stage0: we
        # never got a real quality signal here, so this must not be
        # recorded as "the idea is bad" (Update 04's aborted_stage).
        return SweepOutcome(
            rejected_at_stage0=False,
            aborted_stage="stage1",
            runs=runs,
            winning_settings=None,
            winning_result=None,
            robust_count=0,
            sweep_total=len(runs),
            error_count=sum(1 for r in runs if not r.ok),
            fragile=True,
        )

    # --- Stage 2: truncation refinement (4 remaining values; 0.05 already
    # tested), run concurrently -- each combo only depends on Stage 1's
    # *winner*, not on the other Stage 2 combos, so this batch is safe to
    # parallelize the same way Stage 1 is. ---
    remaining_truncations = [t for t in TRUNCATIONS if t != DEFAULT_TRUNCATION]
    if len(remaining_truncations) != EXPECTED_STAGE2_COUNT:
        raise RuntimeError(
            f"Stage 2 must sweep exactly {EXPECTED_STAGE2_COUNT} truncation values, "
            f"got {len(remaining_truncations)}"
        )

    stage2_settings = [replace(best_stage1.settings, truncation=t) for t in remaining_truncations]
    stage2_runs = await _run_batch(expression, stage2_settings, simulate, "stage2", semaphore, persist_run)
    runs.extend(stage2_runs)

    best_trunc_run = _pick_best([best_stage1] + stage2_runs) or best_stage1
    current_settings = best_trunc_run.settings
    current_result = best_trunc_run.result

    # --- Stage 3: delay / pasteurization / nan sensitivity (6 sims total),
    # kept sequential on purpose -- see module docstring point 1. Still
    # fault-isolated per call via _safe_simulate.
    #
    # Per the settings-sweep spec: "Test the 2 alternatives each
    # for Delay, Pasteurization, and Nan Handling one at a time (6 sims)."
    # Delay only has 2 possible values in the whole domain (0, 1), so "the 2
    # alternatives" means both values of each field are simulated (holding
    # everything else at the current best), not just the one value that
    # differs from whatever's currently held -- that's the only reading
    # that produces 6 sims (2 values x 3 fields = 6) rather than 3. Each
    # field is tested independently against the current best (not a
    # further cartesian product across the three fields), and a flip is
    # kept only if it improves Fitness within the local filter bounds -- so
    # the three fields are evaluated one at a time in sequence, each
    # against whatever `current_settings` is at that point. This is a real
    # sequential dependency (the pasteurization sims must use whichever
    # delay value won, and the nan-handling sims must use whichever
    # pasteurization value won), which is exactly why this stage is not
    # parallelized like Stages 1/2 above -- see Update 03's throughput
    # analysis, which considered and rejected naively parallelizing this
    # stage for that reason.
    stage3_runs: list[SweepRun] = []

    for delay_value in DELAYS:
        s = replace(current_settings, delay=delay_value)
        run = await _safe_simulate(expression, s, simulate, "stage3", semaphore)
        runs.append(run)
        stage3_runs.append(run)
        if persist_run:
            persist_run(run)
        if run.ok and _is_improvement(run.result, current_result, thresholds):
            current_settings, current_result = s, run.result

    for past_value in (True, False):
        s = replace(current_settings, pasteurization=past_value)
        run = await _safe_simulate(expression, s, simulate, "stage3", semaphore)
        runs.append(run)
        stage3_runs.append(run)
        if persist_run:
            persist_run(run)
        if run.ok and _is_improvement(run.result, current_result, thresholds):
            current_settings, current_result = s, run.result

    for nan_value in (True, False):
        s = replace(current_settings, nan_handling=nan_value)
        run = await _safe_simulate(expression, s, simulate, "stage3", semaphore)
        runs.append(run)
        stage3_runs.append(run)
        if persist_run:
            persist_run(run)
        if run.ok and _is_improvement(run.result, current_result, thresholds):
            current_settings, current_result = s, run.result

    if len(stage3_runs) != EXPECTED_STAGE3_COUNT:
        raise RuntimeError(
            f"Stage 3 must attempt exactly {EXPECTED_STAGE3_COUNT} combos, got {len(stage3_runs)}"
        )

    # --- Stage 4: robustness check, computed from stored runs, no new sims ---
    # Per the settings-sweep spec: "Count how many distinct
    # settings combos also clear your local filter bar" -- distinct, not
    # raw passing rows, and only among combos that actually produced a
    # result (a failed combo can't "clear the bar" either way). Stage 3's
    # "test both values of each field" approach (see the comment above)
    # deliberately re-simulates the current-best settings combo more than
    # once (whichever of the two tested values matches what's already
    # held), which would otherwise inflate the count with duplicates of the
    # same single combo and defeat the whole point of this check.
    distinct_passing_settings = {r.settings for r in runs if r.ok and thresholds.passes(r.result)}
    robust_count = len(distinct_passing_settings)
    error_count = sum(1 for r in runs if not r.ok)
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
        aborted_stage=None,
        runs=runs,
        winning_settings=current_settings,
        winning_result=current_result,
        robust_count=robust_count,
        sweep_total=sweep_total,
        error_count=error_count,
        fragile=fragile,
    )
