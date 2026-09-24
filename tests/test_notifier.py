"""
Unit tests for Telegram Notifier resilience:
- Connection / timeout error retry with backoff
- HTTP 429 rate limit parsing retry_after and retrying
- Plain text fallback on MarkdownV2 parse errors
- _send_bool wrapper behavior and logging
- Cross-org Telegram send lease pacing
"""
import time
from unittest.mock import MagicMock, call, patch

import pytest
import requests

from brain_options.config import OptionsConfig
from brain_options.core.notifier import (
    _post_with_retry,
    _send,
    _send_bool,
    send_telegram_startup,
    send_telegram_batch_summary,
    send_telegram_alert,
    send_telegram_drip_alert,
    send_telegram_health_check,
    send_telegram_daily_digest,
    send_telegram_emergency_alert,
    send_telegram_drip_failure_alert,
    send_telegram_worker_batch_ping,
)
from brain_options.core.client import SimMetrics, SimSettings


@pytest.fixture
def test_config():
    return OptionsConfig(
        brain_username="test",
        brain_password="test",
        telegram_bot_token="test_token_123",
        telegram_chat_id="test_chat_456",
    )


def test_post_with_retry_succeeds_first_attempt():
    with patch("requests.post") as mock_post:
        resp = MagicMock()
        resp.status_code = 200
        mock_post.return_value = resp

        r = _post_with_retry("http://example.com", {"k": "v"}, max_attempts=2, backoff_seconds=0.01)
        assert r is resp
        assert mock_post.call_count == 1


def test_post_with_retry_retries_on_connection_error():
    with patch("requests.post") as mock_post:
        resp_success = MagicMock()
        resp_success.status_code = 200
        mock_post.side_effect = [requests.exceptions.ConnectionError("Connection blip"), resp_success]

        r = _post_with_retry("http://example.com", {"k": "v"}, max_attempts=2, backoff_seconds=0.01)
        assert r is resp_success
        assert mock_post.call_count == 2


def test_post_with_retry_returns_none_when_all_attempts_fail():
    with patch("requests.post") as mock_post:
        mock_post.side_effect = requests.exceptions.Timeout("Timeout")

        r = _post_with_retry("http://example.com", {"k": "v"}, max_attempts=2, backoff_seconds=0.01)
        assert r is None
        assert mock_post.call_count == 2


def test_send_handles_429_with_retry_after(test_config):
    with patch("requests.post") as mock_post, patch("time.sleep") as mock_sleep:
        resp_429 = MagicMock()
        resp_429.status_code = 429
        resp_429.json.return_value = {"parameters": {"retry_after": 2.5}}

        resp_200 = MagicMock()
        resp_200.status_code = 200

        mock_post.side_effect = [resp_429, resp_200]

        success, reason = _send("Hello world", test_config)
        assert success is True
        assert reason == ""
        mock_sleep.assert_called_with(2.5)
        assert mock_post.call_count == 2


def test_send_handles_persistent_429(test_config):
    with patch("requests.post") as mock_post, patch("time.sleep") as mock_sleep:
        resp_429 = MagicMock()
        resp_429.status_code = 429
        resp_429.json.return_value = {"parameters": {"retry_after": 1.0}}

        mock_post.return_value = resp_429

        success, reason = _send("Hello world", test_config)
        assert success is False
        assert reason == "rate_limited"
        mock_sleep.assert_called_with(1.0)


def test_send_markdown_fallback_on_400(test_config):
    with patch("requests.post") as mock_post:
        resp_400 = MagicMock()
        resp_400.status_code = 400
        resp_400.text = "Bad Request: can't parse entities"

        resp_200 = MagicMock()
        resp_200.status_code = 200

        mock_post.side_effect = [resp_400, resp_200]

        success, reason = _send("Unescaped _text", test_config)
        assert success is True
        assert reason == ""
        assert mock_post.call_count == 2
        # Second attempt should NOT have parse_mode in payload
        fallback_payload = mock_post.call_args_list[1][1]["json"]
        assert "parse_mode" not in fallback_payload


def test_send_bool_returns_true_on_success(test_config):
    with patch("brain_options.core.notifier._send") as mock_send:
        mock_send.return_value = (True, "")
        result = _send_bool("test", test_config, label="unit test")
        assert result is True


def test_send_bool_returns_false_and_logs_on_failure(test_config):
    with patch("brain_options.core.notifier._send") as mock_send, patch("brain_options.core.notifier.log.warning") as mock_warn:
        mock_send.return_value = (False, "rate_limited")
        result = _send_bool("test", test_config, label="test alert")
        assert result is False
        assert any("test alert not delivered (reason=rate_limited)" in call[0][0] % call[0][1:] for call in mock_warn.call_args_list if call[0])


def test_send_acquires_lease_when_db_provided(test_config):
    mock_db = MagicMock()
    with patch("requests.post") as mock_post:
        resp = MagicMock()
        resp.status_code = 200
        mock_post.return_value = resp

        success, reason = _send("test", test_config, db=mock_db)
        assert success is True
        assert mock_db.acquire_telegram_send_lease.called


def test_all_public_functions_accept_db_parameter(test_config, monkeypatch):
    monkeypatch.setenv("NOTIFY_ON_STARTUP", "true")
    mock_db = MagicMock()
    with patch("brain_options.core.notifier._send_bool") as mock_send_bool:
        mock_send_bool.return_value = True

        # Test each of the 8 public notification functions with db=mock_db
        send_telegram_startup(test_config, mode="Test", db=mock_db)
        send_telegram_batch_summary(1, 5, test_config, stats={}, db=mock_db)

        metrics = SimMetrics(
            alpha_id="alpha1",
            sharpe=1.5,
            fitness=1.2,
            turnover=0.1,
            annualized_return=0.1,
            max_drawdown=0.05,
            margin=0.002,
            status="COMPLETE",
            raw_response={},
        )
        settings = SimSettings(
            universe="TOP3000",
            delay=1,
            decay=10,
            neutralization="SUBINDUSTRY",
            truncation=0.05,
            pasteurization=True,
        )
        send_telegram_alert("trade_when(x, y, -1)", settings, metrics, 0.1, test_config, db=mock_db)
        send_telegram_drip_alert("alpha1", "2026-09-21", {}, test_config, db=mock_db)
        send_telegram_health_check(test_config, stats={}, active_strategy=None, db=mock_db)
        send_telegram_daily_digest(test_config, stats={}, db=mock_db)
        send_telegram_emergency_alert("crash error", test_config, db=mock_db)
        send_telegram_drip_failure_alert("alpha1", "rejected", test_config, db=mock_db)
        send_telegram_worker_batch_ping("breakeven_skew", 1, 10, "skew", test_config, db=mock_db)

        assert mock_send_bool.call_count == 9
        for call_args in mock_send_bool.call_args_list:
            assert call_args[1].get("db") is mock_db


def test_send_telegram_worker_batch_ping_formats_message(test_config):
    with patch("brain_options.core.notifier._send_bool") as mock_send_bool:
        mock_send_bool.return_value = True

        # Test zero-pass ping (silent to prevent spam)
        result_zero = send_telegram_worker_batch_ping(
            strategy="breakeven_skew",
            passed_count=0,
            total_evaluated=40,
            archetype="breakeven,skew",
            config=test_config,
            stats={"today_evaluated": 120, "today_qualified": 2},
        )
        assert result_zero is True
        assert not mock_send_bool.called

        # Test positive-pass ping (emits clean alert)
        send_telegram_worker_batch_ping(
            strategy="analyst_revisions",
            passed_count=1,
            total_evaluated=40,
            archetype="analyst_revisions",
            config=test_config,
            stats={"today_evaluated": 120, "today_qualified": 2},
        )
        assert mock_send_bool.called
        msg = mock_send_bool.call_args[0][0]
        assert "analyst" in msg
        assert "Batch Yield" in msg
        assert "1/40 qualified" in msg
        assert "120 sims" in msg
