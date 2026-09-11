from pipeline.filter.local_filter import FilterThresholds, compute_fitness
from pipeline.sweep.settings_sweep import SimResult


def test_passes_when_all_metrics_clear_the_bar():
    thresholds = FilterThresholds(min_sharpe=1.25, min_fitness=1.0, max_turnover=0.7, min_turnover=0.01)
    result = SimResult(sharpe=1.5, fitness=1.2, turnover=0.3)
    assert thresholds.passes(result) is True


def test_fails_when_sharpe_below_bar():
    thresholds = FilterThresholds(min_sharpe=1.25, min_fitness=1.0, max_turnover=0.7, min_turnover=0.01)
    result = SimResult(sharpe=1.0, fitness=1.2, turnover=0.3)
    assert thresholds.passes(result) is False


def test_fails_when_turnover_too_high():
    thresholds = FilterThresholds(min_sharpe=1.25, min_fitness=1.0, max_turnover=0.7, min_turnover=0.01)
    result = SimResult(sharpe=1.5, fitness=1.2, turnover=0.9)
    assert thresholds.passes(result) is False


def test_fails_when_turnover_degenerately_low():
    thresholds = FilterThresholds(min_sharpe=1.25, min_fitness=1.0, max_turnover=0.7, min_turnover=0.05)
    result = SimResult(sharpe=1.5, fitness=1.2, turnover=0.001)
    assert thresholds.passes(result) is False


def test_compute_fitness_matches_audit_checklist_formula():
    # Fitness = Sharpe * sqrt(|Returns| / max(Turnover, 0.125))
    sharpe, returns_ann, turnover = 2.0, 0.2, 0.5
    expected = 2.0 * ((0.2 / 0.5) ** 0.5)
    assert abs(compute_fitness(sharpe, returns_ann, turnover) - expected) < 1e-9


def test_compute_fitness_floors_turnover_at_point_125():
    sharpe, returns_ann, turnover = 1.0, 0.1, 0.01  # below the 0.125 floor
    expected = 1.0 * ((0.1 / 0.125) ** 0.5)
    assert abs(compute_fitness(sharpe, returns_ann, turnover) - expected) < 1e-9
