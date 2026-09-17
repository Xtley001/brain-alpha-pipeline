"""
Unit tests for the 24-Hour Drip Submitter (brain_options.core.drip).
Verifies:
1. Correct New York calendar date interval calculation.
2. Strict checklist validation (rejecting alphas that fail any check, e.g. LOW_SUB_UNIVERSE_SHARPE).
3. Exact single-alpha daily submission and store update.
"""
from __future__ import annotations

import datetime
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import zoneinfo

from brain_options.config import OptionsConfig
from brain_options.core.client import BrainClient
from brain_options.core.drip import DripSubmitter, NY_TZ
from brain_options.store.store import OptionsStore


@pytest.fixture
def config():
    return OptionsConfig(
        brain_username="test@example.com",
        brain_password="test_password",
        telegram_bot_token="test_bot_token",
        telegram_chat_id="12345678",
    )


@pytest.fixture
def mock_client():
    client = MagicMock(spec=BrainClient)
    client._get_session = MagicMock()
    return client


@pytest.fixture
def mock_store():
    store = MagicMock(spec=OptionsStore)
    return store


@pytest.mark.asyncio
async def test_drip_skips_when_already_submitted_today(config, mock_client, mock_store):
    """When BRAIN reports a submission already made today in EDT, drip must skip without submitting."""
    today_ny = datetime.datetime.now(NY_TZ).date()
    today_iso = f"{today_ny.isoformat()}T05:00:00-04:00"

    mock_sess = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "results": [{"id": "ALREADY_SUB", "dateSubmitted": today_iso}]
    }
    mock_sess.retry = AsyncMock(return_value=mock_resp)
    mock_client._get_session.return_value = mock_sess

    drip = DripSubmitter(mock_client, mock_store, config)
    submitted, alpha_id, reason = await drip.check_and_drip()

    assert submitted is False
    assert alpha_id is None
    assert "already filled" in reason
    assert not mock_client.submit_alpha.called
    assert not mock_store.mark_alpha_submitted.called


@pytest.mark.asyncio
async def test_drip_skips_ineligible_alphas_and_submits_clean_alpha(config, mock_client, mock_store):
    """
    When submission slot is open:
    - Alpha 1 has failed checks (e.g. LOW_SUB_UNIVERSE_SHARPE) -> must be skipped.
    - Alpha 2 has all PASS checks -> must be submitted.
    - Exactly 1 alpha is submitted.
    """
    yesterday_ny = datetime.datetime.now(NY_TZ).date() - datetime.timedelta(days=1)
    yesterday_iso = f"{yesterday_ny.isoformat()}T14:00:00-04:00"

    mock_sess = MagicMock()

    # User alphas query response: last submission was yesterday
    resp_user_alphas = MagicMock()
    resp_user_alphas.status_code = 200
    resp_user_alphas.json.return_value = {
        "results": [{"id": "YESTERDAY_ALPHA", "dateSubmitted": yesterday_iso}]
    }

    # Alpha 1 (flawed, fails sub-universe)
    resp_alpha1 = MagicMock()
    resp_alpha1.status_code = 200
    resp_alpha1.json.return_value = {
        "id": "ALPHA_FAIL",
        "status": "UNSUBMITTED",
        "is": {
            "checks": [
                {"name": "LOW_SHARPE", "result": "PASS"},
                {"name": "LOW_SUB_UNIVERSE_SHARPE", "result": "FAIL"},
            ]
        }
    }

    # Alpha 2 (clean, all PASS)
    resp_alpha2 = MagicMock()
    resp_alpha2.status_code = 200
    resp_alpha2.json.return_value = {
        "id": "ALPHA_PASS",
        "status": "UNSUBMITTED",
        "is": {
            "sharpe": 1.55,
            "fitness": 1.25,
            "turnover": 0.05,
            "returns": 0.08,
            "margin": 0.003,
            "checks": [
                {"name": "LOW_SHARPE", "result": "PASS"},
                {"name": "LOW_FITNESS", "result": "PASS"},
                {"name": "LOW_SUB_UNIVERSE_SHARPE", "result": "PASS"},
                {"name": "CONCENTRATED_WEIGHT", "result": "PASS"},
            ]
        }
    }

    async def mock_retry(method, url, max_tries=3):
        if "users/self/alphas" in url:
            return resp_user_alphas
        elif "ALPHA_FAIL" in url:
            return resp_alpha1
        elif "ALPHA_PASS" in url:
            return resp_alpha2
        return None

    mock_sess.retry = AsyncMock(side_effect=mock_retry)
    mock_client._get_session.return_value = mock_sess
    mock_client.submit_alpha = AsyncMock(return_value={"ok": True, "status_code": 201})

    # Unsubmitted queue has both alphas
    mock_store.get_unsubmitted_pool_alphas.return_value = [
        {"alpha_id": "ALPHA_FAIL", "sharpe": 1.60, "fitness": 1.30},
        {"alpha_id": "ALPHA_PASS", "sharpe": 1.55, "fitness": 1.25},
    ]

    with patch("brain_options.core.drip.send_telegram_drip_alert") as mock_alert:
        drip = DripSubmitter(mock_client, mock_store, config)
        submitted, alpha_id, reason = await drip.check_and_drip()

        assert submitted is True
        assert alpha_id == "ALPHA_PASS"
        # Only ALPHA_PASS was submitted, ALPHA_FAIL was skipped!
        mock_client.submit_alpha.assert_called_once_with("ALPHA_PASS")
        mock_store.mark_alpha_submitted.assert_called_once_with("ALPHA_PASS")
        assert mock_alert.called
