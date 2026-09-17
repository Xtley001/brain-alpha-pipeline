"""
Unit tests for Concurrency, Slot Saturation, and Multi-Arm Diagnostic Optimizer.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock
import pytest

from brain_options.config import OptionsConfig
from brain_options.core.client import BrainClient, SimMetrics, SimSettings
from brain_options.core.optimizer import DiagnosticAlphaOptimizer
from brain_options.specialist.templates import OptionCandidate
from brain_options.store.store import OptionsStore


@pytest.mark.asyncio
async def test_brain_client_semaphore_concurrency():
    """Verify that BrainClient semaphore strictly caps concurrent simulations at max_concurrent_sims."""
    max_sims = 3
    client = BrainClient("user", "pass", max_concurrent_sims=max_sims)

    in_flight_peaks = []
    current_in_flight = 0

    async def mock_simulate(payload):
        nonlocal current_in_flight
        current_in_flight += 1
        in_flight_peaks.append(current_in_flight)
        await asyncio.sleep(0.05)
        current_in_flight -= 1
        return {"status": "COMPLETE", "is": {"sharpe": 1.2, "fitness": 1.0, "turnover": 0.25}}

    mock_session = MagicMock()
    mock_session.simulate = AsyncMock(side_effect=mock_simulate)
    client._session = mock_session

    settings = SimSettings()
    # Launch 9 simulation requests concurrently
    tasks = [
        client.simulate_one(f"group_neutralize(rank(ts_decay_linear(x_{i}, 5)), subindustry)", settings)
        for i in range(9)
    ]
    results = await asyncio.gather(*tasks)

    assert len(results) == 9
    assert all(r.is_valid for r in results)
    assert max(in_flight_peaks) <= max_sims
    assert client.active_simulations == 0


@pytest.mark.asyncio
async def test_multi_arm_diagnostic_optimizer():
    """Verify that DiagnosticAlphaOptimizer fires multi-arm diagnostic trials concurrently."""
    config = OptionsConfig(
        brain_username="test",
        brain_password="test",
        stage0_min_sharpe=0.35,
        stage0_min_fitness=0.20,
        filter_min_sharpe=1.25,
        filter_min_fitness=1.00,
        filter_max_turnover=0.70,
        filter_min_turnover=0.01,
    )

    client = BrainClient("test", "test", max_concurrent_sims=3)
    mock_store = MagicMock(spec=OptionsStore)

    # Candidate with high turnover deficit
    candidate = OptionCandidate(
        expression="group_neutralize(rank(ts_delta(implied_volatility_mean_skew_20, 5)), sector)",
        archetype_name="Volatility Skew",
        hypothesis="High turnover skew test",
        generation_source="unit_test",
    )
    initial_metrics = SimMetrics(
        alpha_id="INIT1",
        sharpe=1.35,
        fitness=0.60,
        turnover=0.55,
        annualized_return=0.08,
        max_drawdown=0.05,
        margin=0.001,
        status="COMPLETE",
        raw_response={},
    )
    base_settings = SimSettings()

    sim_calls = []

    async def mock_simulate(expr, settings):
        sim_calls.append((expr, settings.decay, settings.neutralization))
        # Return passing metrics if smoothed with decay 14
        if "ts_decay_linear" in expr and settings.decay >= 14:
            return SimMetrics(
                alpha_id="QUALIFIED1",
                sharpe=1.45,
                fitness=1.20,
                turnover=0.22,
                annualized_return=0.10,
                max_drawdown=0.03,
                margin=0.002,
                status="COMPLETE",
                raw_response={},
            )
        return SimMetrics(
            alpha_id="TRIAL_FAIL",
            sharpe=0.90,
            fitness=0.50,
            turnover=0.45,
            annualized_return=0.04,
            max_drawdown=0.07,
            margin=0.001,
            status="COMPLETE",
            raw_response={},
        )

    client.simulate_one = AsyncMock(side_effect=mock_simulate)

    optimizer = DiagnosticAlphaOptimizer(client, mock_store, config)
    best_cand, best_settings, best_metrics, passed_filter, history = await optimizer.optimize(
        candidate=candidate,
        base_settings=base_settings,
        initial_metrics=initial_metrics,
        max_steps=2,
    )

    # Multi-arm optimization should fire 3 parallel arms in round 1 and immediately qualify
    assert len(sim_calls) == 3
    assert passed_filter is True
    assert best_metrics.sharpe >= 1.25
    assert best_metrics.fitness >= 1.00
    assert best_metrics.turnover <= 0.70
    assert "ts_decay_linear" in best_cand.expression


def test_stage0_telegram_notification():
    """Verify that send_telegram_stage0_alert correctly formats and attempts to send Stage 0 alerts."""
    from brain_options.core.notifier import send_telegram_stage0_alert
    from unittest.mock import patch

    config = OptionsConfig(
        brain_username="test",
        brain_password="test",
        telegram_bot_token="fake_token",
        telegram_chat_id="123456",
    )
    metrics = SimMetrics(
        alpha_id="S0_TEST",
        sharpe=1.04,
        fitness=0.45,
        turnover=0.33,
        annualized_return=0.06,
        max_drawdown=0.04,
        margin=0.001,
        status="COMPLETE",
        raw_response={},
    )

    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        result = send_telegram_stage0_alert("Call Breakeven", "group_neutralize(rank(x), subindustry)", metrics, config)
        assert result is True
        assert mock_post.called
        call_payload = mock_post.call_args[1]["json"]
        assert "Stage 0 Pass" in call_payload["text"]
        assert "1.04" in call_payload["text"]
        assert "Call Breakeven" in call_payload["text"]


def test_passed_alpha_telegram_notification():
    """Verify that send_telegram_alert formats short, clean alert with BRAIN link and margin."""
    from brain_options.core.notifier import send_telegram_alert
    from unittest.mock import patch, MagicMock

    config = OptionsConfig(
        brain_username="test",
        brain_password="test",
        telegram_bot_token="fake_token",
        telegram_chat_id="123456",
    )
    metrics = SimMetrics(
        alpha_id="gJbAP76e",
        sharpe=1.79,
        fitness=1.46,
        turnover=0.0411,
        annualized_return=0.0833,
        max_drawdown=0.0831,
        margin=0.004058,
        status="COMPLETE",
        raw_response={},
    )
    settings = SimSettings(
        universe="TOP3000",
        delay=1,
        decay=18,
        neutralization="SUBINDUSTRY",
        truncation=0.05,
        pasteurization=True,
    )

    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        res = send_telegram_alert("trade_when(x, y, -1)", settings, metrics, 0.0, config)
        assert res is True
        assert mock_post.called
        payload = mock_post.call_args[1]["json"]
        text = payload["text"]
        assert "PASSED ALPHA DISCOVERED" in text
        assert "https://platform.worldquantbrain.com/alpha/gJbAP76e" in text
        assert "40.6 bps" in text
        assert "1.79" in text
        assert "1.46" in text
        assert "SUBINDUSTRY" in text


def test_batch_summary_telegram_notification():
    """Verify that send_telegram_batch_summary formats clean short batch numbers."""
    from brain_options.core.notifier import send_telegram_batch_summary
    from unittest.mock import patch, MagicMock

    config = OptionsConfig(
        brain_username="test",
        brain_password="test",
        telegram_bot_token="fake_token",
        telegram_chat_id="123456",
    )
    stats = {
        "today_evaluated": 15,
        "today_stage0_pass": 6,
        "today_qualified": 2,
        "all_time_evaluated": 250,
        "all_time_stage0_pass": 95,
        "all_time_pool_alphas": 12,
    }

    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        result = send_telegram_batch_summary(2, 10, config, stats=stats)
        assert result is True
        assert mock_post.called
        call_payload = mock_post.call_args[1]["json"]
        text = call_payload["text"]
        assert "Batch Complete" in text
        assert "• *Evaluated:* `10` | *Passed:* `2`" in text
        assert "• *Pool Today:* `2` | *Total Pool:* `12`" in text


@pytest.mark.asyncio
async def test_run_candidate_qualifies_without_correlation_rejection():
    """Verify that run_candidate accepts an alpha without blocking on pool correlation."""
    from brain_options.run import run_candidate
    from brain_options.core.sweep import SweepEngine

    config = OptionsConfig(
        brain_username="test",
        brain_password="test",
        stage0_min_sharpe=0.35,
        stage0_min_fitness=0.20,
        filter_min_sharpe=1.25,
        filter_min_fitness=1.00,
        filter_max_turnover=0.70,
        filter_min_turnover=0.01,
        max_pool_correlation=0.70,
    )

    client = BrainClient("test", "test")
    mock_sweep = MagicMock(spec=SweepEngine)
    mock_store = MagicMock(spec=OptionsStore)

    cand = OptionCandidate("group_neutralize(rank(X), subindustry)", "TestArch", "Hyp", "unit_test")
    passing_metrics = SimMetrics(
        alpha_id="ALPHA_CORR_TEST",
        sharpe=1.60,
        fitness=1.20,
        turnover=0.15,
        annualized_return=0.10,
        max_drawdown=0.03,
        margin=0.002,
        status="COMPLETE",
        raw_response={},
    )
    s0_settings = SimSettings()
    mock_sweep.stage0_screen = AsyncMock(return_value=(True, s0_settings, passing_metrics))

    # Mock optimizer to return passing metrics
    with pytest.MonkeyPatch.context() as mp:
        mock_opt = MagicMock()
        mock_opt.optimize = AsyncMock(return_value=(cand, s0_settings, passing_metrics, True, []))
        mp.setattr("brain_options.run.DiagnosticAlphaOptimizer", lambda c, s, cfg: mock_opt)

        # Dates for identical return series -> correlation = 1.0
        dates = [f"2025-01-{i:02d}" for i in range(1, 35)]
        identical_series = {d: float(i % 5) for i, d in enumerate(dates)}

        client.get_alpha_pnl = AsyncMock(return_value=identical_series)
        mock_store.load_pool_pnl_series = MagicMock(return_value=[identical_series])

        # Candidate should be accepted even if correlation against existing pool is high
        passed = await run_candidate(cand, mock_sweep, client, mock_store, config)
        assert passed is True
        # Store should save passed alpha directly
        assert mock_store.save_passed_alpha.called



