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
    """When BRAIN reports daily quota (3 submissions) already made today in EDT, drip must skip without submitting."""
    today_ny = datetime.datetime.now(NY_TZ).date()
    today_iso1 = f"{today_ny.isoformat()}T02:00:00-04:00"
    today_iso2 = f"{today_ny.isoformat()}T08:00:00-04:00"
    today_iso3 = f"{today_ny.isoformat()}T14:00:00-04:00"

    mock_sess = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "results": [
            {"id": "ALREADY_SUB3", "dateSubmitted": today_iso3},
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
    fixed_utc = datetime.datetime(2026, 9, 21, 8, 0, tzinfo=datetime.timezone.utc)
    fixed_ny = fixed_utc.astimezone(NY_TZ)
    recent_dt = fixed_ny - datetime.timedelta(hours=1)
    recent_iso = recent_dt.isoformat()

    drip = DripSubmitter(mock_client, mock_store, config)
    drip.get_today_submissions_ny = AsyncMock(return_value=[{
        "id": "RECENT_SUB",
        "datetime_ny": recent_dt,
        "dateSubmitted": recent_iso,
    }])

    with patch("brain_options.core.drip.datetime.datetime") as mock_dt:
        mock_dt.now.side_effect = lambda tz=None: fixed_utc if tz == datetime.timezone.utc else fixed_ny
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

    is_submitted = False

    async def mock_submit(aid):
        nonlocal is_submitted
        is_submitted = True
        return {"ok": True, "status_code": 201}

    async def mock_retry(method, url, max_tries=3):
        if "users/self/alphas" in url:
            return resp_user_alphas
        r = MagicMock()
        r.status_code = 200
        if is_submitted:
            r.json.return_value = {
                "id": "SECOND_ALPHA",
                "status": "ACTIVE",
                "stage": "OS",
                "is": {"checks": [{"name": "LOW_SHARPE", "result": "PASS"}]}
            }
        else:
            r.json.return_value = {
                "id": "SECOND_ALPHA",
                "status": "UNSUBMITTED",
                "stage": "IS",
                "is": {"checks": [{"name": "LOW_SHARPE", "result": "PASS"}]}
            }
        return r

    mock_sess.retry = AsyncMock(side_effect=mock_retry)
    mock_client._get_session.return_value = mock_sess
    mock_client.submit_alpha = AsyncMock(side_effect=mock_submit)

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

    submitted_ids = set()

    async def mock_submit(aid):
        submitted_ids.add(aid)
        return {"ok": True, "status_code": 201}

    async def mock_retry(method, url, max_tries=3):
        if "users/self/alphas" in url:
            return resp_user_alphas
        elif "ALPHA_FAIL" in url:
            return resp_alpha1
        elif "ALPHA_PASS" in url:
            r = MagicMock()
            r.status_code = 200
            if "ALPHA_PASS" in submitted_ids:
                r.json.return_value = {
                    "id": "ALPHA_PASS",
                    "status": "ACTIVE",
                    "stage": "OS",
                    "is": resp_alpha2.json.return_value["is"],
                }
            else:
                r.json.return_value = resp_alpha2.json.return_value
            return r
        return None

    mock_sess.retry = AsyncMock(side_effect=mock_retry)
    mock_client._get_session.return_value = mock_sess
    mock_client.submit_alpha = AsyncMock(side_effect=mock_submit)

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

    submitted_ids = set()

    async def mock_submit(aid):
        submitted_ids.add(aid)
        return {"ok": True, "status_code": 201}

    async def mock_retry(method, url, max_tries=3):
        if "users/self/alphas" in url:
            return resp_user_alphas
        r = MagicMock()
        r.status_code = 200
        if any(aid in submitted_ids for aid in ["ALPHA_BREAKEVEN", "ALPHA_SKEW"]):
            r.json.return_value = {
                "id": "ALPHA_SKEW" if "ALPHA_SKEW" in submitted_ids else "ALPHA_BREAKEVEN",
                "status": "ACTIVE",
                "stage": "OS",
                "is": {"checks": [{"name": "LOW_SHARPE", "result": "PASS"}]}
            }
        else:
            r.json.return_value = {
                "status": "UNSUBMITTED",
                "stage": "IS",
                "is": {"checks": [{"name": "LOW_SHARPE", "result": "PASS"}]}
            }
        return r

    mock_sess.retry = AsyncMock(side_effect=mock_retry)
    mock_client._get_session.return_value = mock_sess
    mock_client.submit_alpha = AsyncMock(side_effect=mock_submit)

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


@pytest.mark.asyncio
async def test_drip_populates_name_and_description_on_submission(config, mock_client, mock_store):
    """When an alpha is submitted, DripSubmitter must generate name and description and call update_alpha_metadata."""
    yesterday_ny = datetime.datetime.now(NY_TZ).date() - datetime.timedelta(days=1)
    yesterday_iso = f"{yesterday_ny.isoformat()}T12:00:00-04:00"

    mock_sess = MagicMock()
    mock_resp_user = MagicMock()
    mock_resp_user.status_code = 200
    mock_resp_user.json.return_value = {
        "results": [{"id": "OLD_ALPHA", "dateSubmitted": yesterday_iso}]
    }

    is_submitted_meta = False

    async def mock_submit_meta(aid):
        nonlocal is_submitted_meta
        is_submitted_meta = True
        return {"ok": True, "status_code": 201}

    async def mock_retry(method, url, max_tries=3):
        if "users/self/alphas" in url:
            return mock_resp_user
        r = MagicMock()
        r.status_code = 200
        if is_submitted_meta:
            r.json.return_value = {
                "id": "ALPHA_NEW_99",
                "status": "ACTIVE",
                "stage": "OS",
                "is": {"checks": []},
            }
        else:
            r.json.return_value = {
                "id": "ALPHA_NEW_99",
                "status": "UNSUBMITTED",
                "stage": "IS",
                "is": {"checks": []},
            }
        return r

    mock_sess.retry = AsyncMock(side_effect=mock_retry)
    mock_client._get_session.return_value = mock_sess
    mock_client.submit_alpha = AsyncMock(side_effect=mock_submit_meta)
    mock_client.update_alpha_metadata = AsyncMock(return_value={"ok": True, "status_code": 200})

    mock_store.get_unsubmitted_pool_alphas.return_value = [
        {
            "alpha_id": "ALPHA_NEW_99",
            "archetype": "Mutation(breakeven)",
            "hypothesis": "Test breakeven hypothesis with volume liquidity surge.",
            "expression": "trade_when(volume > adv20, call_breakeven_30)",
            "sharpe": 1.60,
            "fitness": 1.25,
        }
    ]

    with patch("brain_options.core.drip.send_telegram_drip_alert"):
        drip = DripSubmitter(mock_client, mock_store, config)
        submitted, alpha_id, reason = await drip.check_and_drip()

        assert submitted is True
        assert alpha_id == "ALPHA_NEW_99"
        mock_client.update_alpha_metadata.assert_called_once()
        call_kwargs = mock_client.update_alpha_metadata.call_args.kwargs
        assert call_kwargs["name"].startswith("OPT_Breakeven_")
        assert "breakeven" in call_kwargs["description"].lower()
        assert "options" in call_kwargs["tags"]
        assert call_kwargs["category"] == "PRICE_VOLUME"
        mock_client.submit_alpha.assert_called_once_with("ALPHA_NEW_99")


@pytest.mark.asyncio
async def test_drip_rejects_negative_self_correlation(config, mock_client, mock_store):
    """Verify that verify_alpha_checks rejects negative self-correlation (-0.85 <= -0.70)."""
    import json
    mock_sess = MagicMock()

    async def mock_retry(method, url, **kwargs):
        r = MagicMock()
        r.status_code = 200
        if "/alphas/ALPHA_NEG_CORR" in url and "/correlations/self" not in url:
            r.json.return_value = {
                "id": "ALPHA_NEG_CORR",
                "status": "UNSUBMITTED",
                "stage": "IS",
                "is": {"checks": []},
            }
        elif "/correlations/self" in url:
            r.text = json.dumps({
                "records": [
                    ["EXISTING_ALPHA", "desc", 1.5, 1.0, 0.2, -0.85]
                ]
            })
        return r

    mock_sess.retry = AsyncMock(side_effect=mock_retry)
    mock_client._get_session.return_value = mock_sess

    drip = DripSubmitter(mock_client, mock_store, config)
    passed, failed_checks, data = await drip.verify_alpha_checks("ALPHA_NEG_CORR")

    assert passed is False
    assert any("HIGH_SELF_CORRELATION" in f for f in failed_checks)


@pytest.mark.asyncio
async def test_drip_catchup_missed_slots_preserves_remaining(config, mock_client, mock_store):
    """
    When earlier slots were missed (e.g. 15:00 UTC = 16:00 WAT -> 2 slots expected),
    drip submits straight up for the missed slots (2 alphas) and preserves the rest for tomorrow.
    """
    mock_sess = MagicMock()

    async def mock_retry(method, url, **kwargs):
        r = MagicMock()
        r.status_code = 200
        if "stage=OS" in url:
            # 0 submissions today
            r.json.return_value = {"results": []}
        elif "/correlations/self" in url:
            r.text = '{"records": []}'
        elif "/alphas/" in url:
            # Both alphas pass checks and verify ACTIVE on OS
            r.json.return_value = {
                "id": "ALPHA",
                "status": "ACTIVE",
                "stage": "OS",
                "is": {"checks": []},
            }
        return r

    mock_sess.retry = AsyncMock(side_effect=mock_retry)
    mock_client._get_session.return_value = mock_sess
    mock_client.submit_alpha = AsyncMock(return_value={"ok": True})
    mock_client.update_alpha_metadata = AsyncMock(return_value=True)

    # 4 qualified alphas in reserve pool
    mock_store.get_unsubmitted_pool_alphas.return_value = [
        {"alpha_id": f"ALPHA_{i}", "sharpe": 1.5 + i*0.1, "fitness": 1.1, "archetype": "volatility_skew"}
        for i in range(1, 5)
    ]
    mock_store.get_recently_submitted_archetypes.return_value = []

    # Mock time to 15:00 UTC (16:00 WAT) -> expected_slots_by_now = 2
    mock_utc_dt = datetime.datetime(2026, 9, 21, 15, 0, 0, tzinfo=datetime.timezone.utc)
    with patch("datetime.datetime") as mock_dt:
        mock_dt.now.side_effect = lambda tz=None: (
            mock_utc_dt if (tz == datetime.timezone.utc or tz == datetime.timezone.utc)
            else mock_utc_dt.astimezone(NY_TZ) if tz == NY_TZ
            else mock_utc_dt
        )
        mock_dt.fromisoformat = datetime.datetime.fromisoformat
        mock_dt.timezone = datetime.timezone

        with patch("brain_options.core.drip.send_telegram_drip_alert"):
            drip = DripSubmitter(mock_client, mock_store, config)
            # Patch verify_alpha_checks to return True
            drip.verify_alpha_checks = AsyncMock(return_value=(True, [], {"stage": "OS", "status": "ACTIVE", "is": {}}))

            submitted, last_id, reason = await drip.check_and_drip()

            assert submitted is True
            # Exactly 2 submitted (catching up for Slot 1 and Slot 2)
            assert mock_client.submit_alpha.call_count == 2
            assert "Submitted 2 alpha(s)" in reason
            # The other 2 alphas remain untouched in reserve for tomorrow!
            assert mock_store.mark_alpha_submitted.call_count == 2


