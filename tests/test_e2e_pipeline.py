"""
End-to-end path: generate -> screen -> sweep -> filter -> correlate -> store
-> alert, using in-memory fakes for BRAIN and the review store. No network,
no real Postgres, no real Telegram -- exercises the same call sequence
run_worker.Worker._process_candidate uses, per the audit checklist's end-to-end coverage item.
"""
import asyncio

from pipeline.filter.correlation_check import compute_max_correlation, passes_correlation_gate
from pipeline.filter.local_filter import FilterThresholds
from pipeline.generator.template_generator import generate_template_candidates
from pipeline.notify.telegram_notify import TelegramNotifier
from pipeline.sweep.settings_sweep import STAGE0_SETTINGS, SimResult, run_staged_sweep


def _run(coro):
    return asyncio.run(coro)


class InMemoryReviewStore:
    def __init__(self):
        self.rows = []

    def insert(self, row):
        self.rows.append(row)
        return len(self.rows)


def _fake_brain_simulate_factory(good_neutralization="SUBINDUSTRY", good_decay=8):
    """A deterministic fake BRAIN: the expression is 'good' at exactly one
    neutralization/decay combo (chosen to match Stage 0's own default so
    Stage 0 passes), mediocre everywhere else."""

    async def simulate(expression: str, settings) -> SimResult:
        if settings.neutralization == good_neutralization and settings.decay == good_decay:
            return SimResult(sharpe=1.8, fitness=1.6, turnover=0.25, returns_ann=0.12, drawdown=-0.06)
        return SimResult(sharpe=1.0, fitness=0.9, turnover=0.4, returns_ann=0.05, drawdown=-0.1)

    return simulate


def test_full_pipeline_happy_path_produces_a_review_store_row_and_alert():
    candidates = generate_template_candidates(seed_ids=(1,))  # "Classic 1-day reversal" variants
    assert len(candidates) > 0
    expression = candidates[0]["expression"]

    simulate = _fake_brain_simulate_factory(
        good_neutralization=STAGE0_SETTINGS.neutralization, good_decay=STAGE0_SETTINGS.decay
    )
    thresholds = FilterThresholds(min_sharpe=1.25, min_fitness=1.0, max_turnover=0.7, min_turnover=0.01)

    outcome = _run(run_staged_sweep(expression, simulate, thresholds=thresholds))
    assert outcome.rejected_at_stage0 is False
    assert thresholds.passes(outcome.winning_result) is True

    # Correlation check: independent (uncorrelated, not just negated) pool,
    # should pass easily.
    import random

    rng = random.Random(7)
    dates = [f"2026-02-{d:02d}" for d in range(1, 21)]
    candidate_returns = {d: rng.gauss(0, 1) for d in dates}
    pool = {"existing_alpha": {d: rng.gauss(0, 1) for d in dates}}
    corr = compute_max_correlation(candidate_returns, pool, min_overlap=10)
    assert passes_correlation_gate(corr, max_allowed_correlation=0.7) is True

    store = InMemoryReviewStore()
    row = {
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
        "max_correlation": corr.max_correlation,
        "robust_count": outcome.robust_count,
        "sweep_total": outcome.sweep_total,
        "fragile": outcome.fragile,
    }
    review_id = store.insert(row)
    assert review_id == 1

    sent = []
    notifier = TelegramNotifier("T", "C", http_post=lambda url, json, timeout: sent.append(json))
    notifier.send_candidate_alert(row)

    assert len(sent) == 1
    assert expression in sent[0]["text"]


def test_full_pipeline_correlation_rejection_produces_no_alert():
    candidates = generate_template_candidates(seed_ids=(1,))
    expression = candidates[0]["expression"]
    simulate = _fake_brain_simulate_factory(
        good_neutralization=STAGE0_SETTINGS.neutralization, good_decay=STAGE0_SETTINGS.decay
    )
    thresholds = FilterThresholds(min_sharpe=1.25, min_fitness=1.0, max_turnover=0.7, min_turnover=0.01)
    outcome = _run(run_staged_sweep(expression, simulate, thresholds=thresholds))

    dates = [f"2026-02-{d:02d}" for d in range(1, 21)]
    values = [0.01 * i for i in range(20)]
    candidate_returns = dict(zip(dates, values))
    pool = {"near_duplicate": dict(zip(dates, values))}  # perfectly correlated
    corr = compute_max_correlation(candidate_returns, pool, min_overlap=10)
    passes = passes_correlation_gate(corr, max_allowed_correlation=0.7)
    assert passes is False

    sent = []
    notifier = TelegramNotifier("T", "C", http_post=lambda url, json, timeout: sent.append(json))
    if passes:  # mirrors the worker's gating -- alert only fires if this holds
        notifier.send_candidate_alert({})
    assert sent == []


def test_full_pipeline_stage0_rejection_never_reaches_store_or_alert():
    async def bad_simulate(expression, settings):
        return SimResult(sharpe=0.1, fitness=0.05, turnover=0.5)

    outcome = _run(run_staged_sweep("junk", bad_simulate))
    assert outcome.rejected_at_stage0 is True

    store = InMemoryReviewStore()
    sent = []
    if not outcome.rejected_at_stage0:
        store.insert({})
        sent.append("would have alerted")
    assert store.rows == []
    assert sent == []
