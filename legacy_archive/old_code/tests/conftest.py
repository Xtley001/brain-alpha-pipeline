import pytest

from pipeline.sweep.settings_sweep import SimResult


@pytest.fixture
def make_result():
    def _make(sharpe=1.5, fitness=1.2, turnover=0.3, returns_ann=0.1, drawdown=-0.05):
        return SimResult(sharpe=sharpe, fitness=fitness, turnover=turnover, returns_ann=returns_ann, drawdown=drawdown)
    return _make
