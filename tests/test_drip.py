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
    """When BRAIN reports daily quota (2 submissions) already made today in EDT, drip must skip without submitting."""
    today_ny = datetime.datetime.now(NY_TZ).date()
    today_iso1 = f"{today_ny.isoformat()}T02:00:00-04:00"
    today_iso2 = f"{today_ny.isoformat()}T08:00:00-04:00"

    mock_sess = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "results": [
            {"id": "ALREADY_SUB2", "dateSubmitted": today_iso2},
            {"id": "ALREADY_SUB1", "dateSubmitted": today_iso1},
        ]
    }
    mock_sess.retry = AsyncMock(return_value=mock_resp)
    mock_client._get_session.return_value = mock_sess

    drip = DripSubmitter(mock_client, mock_store, config)
    submitted, alpha_id, reason = await drip.check_and_drip()

    assert submitted is False
    assert alpha_id is None
    assert "already reached" in reason
    assert not mock_client.submit_alpha.called
    assert not mock_store.mark_alpha_submitted.called


@pytest.mark.asyncio
async def test_drip_pacing_limit_when_one_recent_submission_today(config, mock_client, mock_store):
    """When 1 submission was made today within the pacing window (< 4 hours ago), drip must skip."""
    now_ny = datetime.datetime.now(NY_TZ)
    recent_dt = now_ny - datetime.timedelta(hours=1)
    recent_iso = recent_dt.isoformat()

    mock_sess = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "results": [{"id": "RECENT_SUB", "dateSubmitted": recent_iso}]
    }
    mock_sess.retry = AsyncMock(return_value=mock_resp)
    mock_client._get_session.return_value = mock_sess

    drip = DripSubmitter(mock_client, mock_store, config)
    submitted, alpha_id, reason = await drip.check_and_drip()

    assert submitted is False
    assert alpha_id is None
    assert "Pacing limit" in reason
    assert not mock_client.submit_alpha.called


@pytest.mark.asyncio
async def test_drip_submits_second_alpha_when_pacing_cleared(config, mock_client, mock_store):
    """When 1 submission was made today > 4 hours ago, drip should proceed to submit the second alpha."""
    now_ny = datetime.datetime.now(NY_TZ)
    earlier_dt = now_ny - datetime.timedelta(hours=5)
    earlier_iso = earlier_dt.isoformat()

    mock_sess = MagicMock()
    resp_user_alphas = MagicMock()
    resp_user_alphas.status_code = 200
    resp_user_alphas.json.return_value = {
        "results": [{"id": "EARLIER_SUB", "dateSubmitted": earlier_iso}]
    }

    resp_alpha_clean = MagicMock()
    resp_alpha_clean.status_code = 200
    resp_alpha_clean.json.return_value = {
        "status": "UNSUBMITTED",
        "is": {"checks": [{"name": "LOW_SHARPE", "result": "PASS"}]}
    }

    async def mock_retry(method, url, max_tries=3):
        if "users/self/alphas" in url:
            return resp_user_alphas
        return resp_alpha_clean

    mock_sess.retry = AsyncMock(side_effect=mock_retry)
    mock_client._get_session.return_value = mock_sess
    mock_client.submit_alpha = AsyncMock(return_value={"ok": True, "status_code": 201})

    mock_store.get_unsubmitted_pool_alphas.return_value = [
        {"alpha_id": "SECOND_ALPHA", "archetype": "skew", "sharpe": 1.65, "fitness": 1.35}
    ]

    with patch("brain_options.core.drip.send_telegram_drip_alert"):
        drip = DripSubmitter(mock_client, mock_store, config)
        submitted, alpha_id, reason = await drip.check_and_drip()

        assert submitted is True
        assert alpha_id == "SECOND_ALPHA"
        mock_client.submit_alpha.assert_called_once_with("SECOND_ALPHA")
        mock_store.mark_alpha_submitted.assert_called_once_with("SECOND_ALPHA")


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


@pytest.mark.asyncio
async def test_drip_diversity_ranking_prefers_non_recent_archetype(config, mock_client, mock_store):
    """Verifies that unsubmitted alphas are reordered to prioritize diverse archetypes over repeat archetypes."""
    yesterday_ny = (datetime.datetime.now(NY_TZ) - datetime.timedelta(days=1)).date()
    yesterday_iso = f"{yesterday_ny.isoformat()}T12:00:00-04:00"

    mock_sess = MagicMock()
    mock_sess.retry = AsyncMock()

    resp_user_alphas = MagicMock()
    resp_user_alphas.status_code = 200
    resp_user_alphas.json.return_value = {
        "results": [{"id": "OLD_SUB", "dateSubmitted": yesterday_iso}]
    }

    resp_alpha_clean = MagicMock()
    resp_alpha_clean.status_code = 200
    resp_alpha_clean.json.return_value = {
        "status": "UNSUBMITTED",
        "is": {"checks": [{"name": "LOW_SHARPE", "result": "PASS"}]}
    }

    async def mock_retry(method, url, max_tries=3):
        if "users/self/alphas" in url:
            return resp_user_alphas
        return resp_alpha_clean

    mock_sess.retry = AsyncMock(side_effect=mock_retry)
    mock_client._get_session.return_value = mock_sess
    mock_client.submit_alpha = AsyncMock(return_value={"ok": True, "status_code": 201})

    # Last submitted archetype was 'breakeven'
    mock_store.get_recently_submitted_archetypes.return_value = ["breakeven"]

    # Queue has a higher Sharpe 'breakeven' alpha and a slightly lower Sharpe 'skew' alpha
    mock_store.get_unsubmitted_pool_alphas.return_value = [
        {"alpha_id": "ALPHA_BREAKEVEN", "archetype": "breakeven", "sharpe": 1.70, "fitness": 1.40},
        {"alpha_id": "ALPHA_SKEW", "archetype": "skew", "sharpe": 1.60, "fitness": 1.30},
    ]

    with patch("brain_options.core.drip.send_telegram_drip_alert"):
        drip = DripSubmitter(mock_client, mock_store, config)
        submitted, alpha_id, reason = await drip.check_and_drip()

        assert submitted is True
        # ALPHA_SKEW should be submitted first because it provides diversity over repeat 'breakeven'!
        assert alpha_id == "ALPHA_SKEW"
        mock_client.submit_alpha.assert_called_once_with("ALPHA_SKEW")
