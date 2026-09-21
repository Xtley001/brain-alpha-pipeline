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
    """Verify that send_telegram_health_check formats a clean hourly status message."""
    from brain_options.core.notifier import send_telegram_health_check
    from unittest.mock import patch

    config = OptionsConfig(
        brain_username="test",
        brain_password="test",
        telegram_bot_token="fake_token",
        telegram_chat_id="123456",
    )
    stats = {
        "today_evaluated": 87,
        "today_stage0_pass": 12,
        "today_qualified": 3,
        "today_submitted": 1,
        "reserve_count": 2,
        "today_correlated": 4,
    }

    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        result = send_telegram_health_check(config, stats=stats)
        assert result is True
        assert mock_post.called
        call_payload = mock_post.call_args[1]["json"]
        text = call_payload["text"]
        assert "Hourly Health" in text
        assert "87" in text
        assert "3/5" in text


def test_passed_alpha_telegram_notification():
    """Verify that send_telegram_alert formats a clean, concise qualified-alpha alert."""
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
        # New format: clean metrics, no inline links, no formula
        # Numbers are MarkdownV2-escaped so dots become \\. in the raw string
        assert "Alpha qualified" in text
        assert "gJbAP76e" in text
        assert "40" in text  # margin bps ~40.6 (escaped as 40\\.6)
        assert "1" in text   # sharpe 1.79 present (escaped as 1\\.79)
        assert "TOP3000" in text
        assert "http" not in text  # no inline links


def test_batch_summary_telegram_notification():
    """Verify that send_telegram_batch_summary sends a clean message when alphas qualified."""
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
        "today_submitted": 0,
        "reserve_count": 2,
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
        # New format: clean counters, no old-style header
        assert "2 alphas qualified" in text
        assert "2/10" in text
        assert "2 qualified" in text

    # Verify behavior when passed_count == 0 (fires grey circle summary)
    with patch("requests.post") as mock_post2:
        mock_resp2 = MagicMock()
        mock_resp2.status_code = 200
        mock_post2.return_value = mock_resp2
        result_zero = send_telegram_batch_summary(0, 10, config, stats=stats)
        assert result_zero is True
        assert mock_post2.called
        text_zero = mock_post2.call_args[1]["json"]["text"]
        assert "0 qualified this batch" in text_zero


@pytest.mark.asyncio
async def test_run_candidate_rejects_high_correlation():
    """Verify that run_candidate rejects an alpha when self-correlation against existing pool is >= 0.70."""
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
    mock_session = MagicMock()
    mock_session.retry = AsyncMock(return_value=None)
    client._session = mock_session

    mock_sweep = MagicMock(spec=SweepEngine)
    mock_store = MagicMock(spec=OptionsStore)
    mock_store.db = None

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

        # Candidate should be rejected because correlation against existing pool is 1.0 >= 0.70
        passed = await run_candidate(cand, mock_sweep, client, mock_store, config)
        assert passed is False
        assert mock_store.archive_correlated_alpha.called
        assert not mock_store.save_passed_alpha.called


@pytest.mark.asyncio
async def test_run_candidate_qualifies_when_uncorrelated():
    """Verify that run_candidate accepts and saves an alpha when correlation is < 0.70."""
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
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "{}"
    mock_resp.json = MagicMock(return_value={"is": {"checks": [{"name": "CONCENTRATED_WEIGHT", "result": "PASS"}]}})
    mock_session.retry = AsyncMock(return_value=mock_resp)
    client._session = mock_session

    mock_sweep = MagicMock(spec=SweepEngine)
    mock_store = MagicMock(spec=OptionsStore)
    mock_store.db = None

    cand = OptionCandidate("group_neutralize(rank(X), subindustry)", "TestArch", "Hyp", "unit_test")
    passing_metrics = SimMetrics(
        alpha_id="ALPHA_UNCORR_TEST",
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

    with pytest.MonkeyPatch.context() as mp:
        mock_opt = MagicMock()
        mock_opt.optimize = AsyncMock(return_value=(cand, s0_settings, passing_metrics, True, []))
        mp.setattr("brain_options.run.DiagnosticAlphaOptimizer", lambda c, s, cfg: mock_opt)

        dates = [f"2025-01-{i:02d}" for i in range(1, 35)]
        series_a = {d: float(i % 2) for i, d in enumerate(dates)}
        series_b = {d: float((i // 2) % 2) for i, d in enumerate(dates)}

        client.get_alpha_pnl = AsyncMock(return_value=series_a)
        mock_store.load_pool_pnl_series = MagicMock(return_value=[series_b])

        passed = await run_candidate(cand, mock_sweep, client, mock_store, config)
        assert passed is True
        assert mock_store.save_passed_alpha.called


@pytest.mark.asyncio
async def test_run_candidate_rejects_unverified_checklist():
    """Verify that run_candidate fails closed (rejects) if BRAIN checklist verification fails."""
    from brain_options.run import run_candidate
    from brain_options.core.sweep import SweepEngine

    config = OptionsConfig(
        brain_username="test",
        brain_password="test",
        filter_min_sharpe=1.25,
        filter_min_fitness=1.00,
        filter_max_turnover=0.70,
        filter_min_turnover=0.01,
        max_pool_correlation=0.70,
    )

    client = BrainClient("test", "test")
    mock_session = MagicMock()
    # Simulate network error / unverified endpoint
    mock_session.retry = AsyncMock(return_value=None)
    client._session = mock_session

    mock_sweep = MagicMock(spec=SweepEngine)
    mock_store = MagicMock(spec=OptionsStore)
    mock_store.db = None

    cand = OptionCandidate("group_neutralize(rank(X), subindustry)", "TestArch", "Hyp", "unit_test")
    passing_metrics = SimMetrics(
        alpha_id="ALPHA_UNVERIFIED_TEST",
        sharpe=1.60,
        fitness=1.20,
        turnover=0.15,
        margin=0.002,
        status="COMPLETE",
        raw_response={},
    )
    s0_settings = SimSettings()
    mock_sweep.stage0_screen = AsyncMock(return_value=(True, s0_settings, passing_metrics))

    with pytest.MonkeyPatch.context() as mp:
        mock_opt = MagicMock()
        mock_opt.optimize = AsyncMock(return_value=(cand, s0_settings, passing_metrics, True, []))
        mp.setattr("brain_options.run.DiagnosticAlphaOptimizer", lambda c, s, cfg: mock_opt)

        dates = [f"2025-01-{i:02d}" for i in range(1, 35)]
        series_a = {d: float(i % 2) for i, d in enumerate(dates)}
        series_b = {d: float((i // 2) % 2) for i, d in enumerate(dates)}

        client.get_alpha_pnl = AsyncMock(return_value=series_a)
        mock_store.load_pool_pnl_series = MagicMock(return_value=[series_b])

        passed = await run_candidate(cand, mock_sweep, client, mock_store, config)
        assert passed is False
        assert not mock_store.save_passed_alpha.called


def test_cluster_lock_fails_closed_on_db_error():
    """Verify that acquire_cluster_lock fails closed (returns False) when database raises exception."""
    from brain_options.store.db import OptionsDatabase

    db = OptionsDatabase(None)
    db.database_url = "postgresql://mock_db"
    # Patch _get_connection to raise an exception simulating network outage
    with pytest.MonkeyPatch.context() as mp:
        def raise_err():
            raise RuntimeError("Neon connection timeout")
        mp.setattr(db, "_get_connection", raise_err)

        locked = db.acquire_cluster_lock("TestOrg", "worker-123")
        assert locked is False, "Cluster lock must fail closed on DB connection error"


def test_cluster_lock_heartbeat_lifecycle():
    """Verify that ClusterLockHeartbeat daemon starts, touches DB, and stops cleanly."""
    import time
    from brain_options.run import ClusterLockHeartbeat

    mock_db = MagicMock()
    mock_db.database_url = "postgresql://test"
    mock_db.touch_cluster_lock = MagicMock(return_value=True)

    heartbeat = ClusterLockHeartbeat(mock_db, "worker-test", interval_seconds=1)
    heartbeat.start()
    assert heartbeat._thread is not None and heartbeat._thread.is_alive()
    time.sleep(1.2)
    assert mock_db.touch_cluster_lock.called
    heartbeat.stop()
    assert not heartbeat._thread.is_alive()


def test_dedup_commutative_binops():
    """Verify that commutative operators like (a + b) and (b + a) produce identical fingerprints."""
    from brain_options.specialist.dedup import ASTDeduplicator

    dedup = ASTDeduplicator()
    expr1 = "close + open"
    expr2 = "open + close"
    fp1 = dedup.get_fingerprint(expr1)
    fp2 = dedup.get_fingerprint(expr2)
    assert fp1 == fp2, f"Commutative addition should produce identical fingerprint: {fp1} != {fp2}"

    dedup.add(expr1)
    assert dedup.is_duplicate(expr2)




