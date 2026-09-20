"""
Telegram notifier for brain_options.

Design principles:
- Clean, minimalist, straight to the point.
- No inline links (they break on alpha IDs with underscores).
- No raw formula expressions in alerts.
- Proper MarkdownV2 escaping to prevent silent send failures.
- Three alert tiers:
    1. send_telegram_batch_summary  → fires only when a batch yields ≥1 qualified alpha.
    2. send_telegram_drip_alert     → fires immediately when an alpha is submitted.
    3. send_telegram_health_check   → hourly system heartbeat (called by health.yml).
    4. send_telegram_daily_digest   → end-of-day full summary (called by daily_digest.yml).
"""
from __future__ import annotations

import datetime
import logging
import os
import re
from typing import Any, Optional

import requests

from brain_options.config import OptionsConfig
from brain_options.core.client import SimMetrics, SimSettings

log = logging.getLogger("brain_options.notifier")

WAT_TZ = datetime.timezone(datetime.timedelta(hours=1))  # UTC+1 (WAT / Lagos time)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _escape(text: str) -> str:
    """Escapes a string for Telegram MarkdownV2 parse mode."""
    # Characters that must be escaped in MarkdownV2 outside code spans
    special = r"\_*[]()~`>#+-=|{}.!"
    return re.sub(f"([{re.escape(special)}])", r"\\\1", str(text))


def _now_wat() -> datetime.datetime:
    return datetime.datetime.now(WAT_TZ)


def _send(text: str, config: OptionsConfig) -> bool:
    """
    Sends a MarkdownV2 message to Telegram with plain-text fallback.
    Returns True on success.
    """
    if not config.telegram_bot_token or not config.telegram_chat_id:
        return False
    url = f"https://api.telegram.org/bot{config.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": config.telegram_chat_id,
        "text": text,
        "parse_mode": "MarkdownV2",
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            log.info("Telegram message sent.")
            return True
        # Fallback: strip parse_mode and retry with plain text
        payload.pop("parse_mode", None)
        resp2 = requests.post(url, json=payload, timeout=10)
        if resp2.status_code == 200:
            log.info("Telegram message sent (plain text fallback).")
            return True
        log.warning("Telegram send failed: %s %s", resp2.status_code, resp2.text[:200])
        return False
    except Exception as exc:
        log.warning("Telegram notification exception: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Public notification functions
# ---------------------------------------------------------------------------

def send_telegram_startup(config: OptionsConfig, mode: str = "Single Batch") -> bool:
    """Startup ping — only sent when NOTIFY_ON_STARTUP=true to prevent cron noise."""
    if os.environ.get("NOTIFY_ON_STARTUP", "false").lower() != "true":
        return True
    text = f"🚀 *Pipeline started* — {_escape(mode)}"
    return _send(text, config)


def send_telegram_batch_summary(
    passed_count: int,
    total_candidates: int,
    config: OptionsConfig,
    stats: Optional[dict[str, Any]] = None,
) -> bool:
    """
    Fires only when a batch yields at least one new qualified alpha.
    Clean, one-glance summary — no links, no expressions.
    """
    if not passed_count:
        return False  # Silent if nothing qualified — no noise.

    stats = stats or {}
    today_q = stats.get("today_qualified", 0)
    reserve = stats.get("reserve_count", 0)
    today_sub = stats.get("today_submitted", 0)
    ts = _now_wat().strftime("%H:%M")

    lines = [
        f"✅ *{_escape(str(passed_count))} alpha{'s' if passed_count > 1 else ''} qualified* · {_escape(ts)} UTC\\+1",
        "",
        f"Batch: {_escape(str(passed_count))}/{_escape(str(total_candidates))} passed",
        f"Today: {_escape(str(today_q))} qualified · {_escape(str(today_sub))} submitted · {_escape(str(reserve))} reserve",
    ]
    return _send("\n".join(lines), config)


def send_telegram_alert(
    expression: str,
    settings: SimSettings,
    metrics: SimMetrics,
    max_corr: float,
    config: OptionsConfig,
) -> bool:
    """
    Instant alert when a new alpha passes all gates and enters the qualified pool.
    No expression shown — just the numbers that matter.
    """
    if not config.telegram_bot_token or not config.telegram_chat_id:
        return False

    alpha_id = metrics.alpha_id or "unknown"
    margin_bps = (metrics.margin or 0.0) * 10_000.0
    ts = _now_wat().strftime("%H:%M")

    lines = [
        f"🎯 *Alpha qualified* · {_escape(ts)} UTC\\+1",
        "",
        f"`{_escape(alpha_id)}`",
        "",
        f"Sharpe `{_escape(f'{metrics.sharpe:.2f}')}` · "
        f"Fitness `{_escape(f'{metrics.fitness:.2f}')}` · "
        f"TO `{_escape(f'{metrics.turnover * 100:.1f}')}%`",
        f"Margin `{_escape(f'{margin_bps:.1f}')} bps` · "
        f"Corr `{_escape(f'{max_corr:.2f}')}` \\< 0\\.70 ✓",
        f"Universe `{_escape(settings.universe)}` · Delay `{_escape(str(settings.delay))}` · Decay `{_escape(str(settings.decay))}`",
    ]
    return _send("\n".join(lines), config)


def send_telegram_drip_alert(
    alpha_id: str,
    date_label: str,
    metrics: dict[str, Any],
    config: OptionsConfig,
    slot_num: int = 1,
    max_daily: int = 3,
    next_unlock_str: Optional[str] = None,
) -> bool:
    """
    Fires the moment an automated drip submission is confirmed live on BRAIN.
    Clean, slot-aware, no links, no formula noise.
    """
    if not config.telegram_bot_token or not config.telegram_chat_id:
        return False

    now_wat = _now_wat()
    ts = now_wat.strftime("%H:%M")
    sharpe = float(metrics.get("sharpe") or 0.0)
    fitness = float(metrics.get("fitness") or 0.0)
    turnover = float(metrics.get("turnover") or 0.0) * 100.0
    margin_bps = float(metrics.get("margin") or 0.0) * 10_000.0

    if next_unlock_str:
        next_msg = _escape(next_unlock_str)
    elif slot_num < max_daily:
        next_dt = now_wat + datetime.timedelta(hours=4)
        next_msg = f"Next slot opens at {_escape(next_dt.strftime('%H:%M'))} UTC\\+1"
    else:
        next_msg = f"Daily quota full \\({_escape(str(slot_num))}/{_escape(str(max_daily))}\\) · Next window tomorrow 05:00 UTC\\+1"

    lines = [
        f"📬 *Submitted* · Slot {_escape(str(slot_num))}/{_escape(str(max_daily))} · {_escape(ts)} UTC\\+1",
        "",
        f"`{_escape(alpha_id)}`",
        "",
        f"Sharpe `{_escape(f'{sharpe:.2f}')}` · Fitness `{_escape(f'{fitness:.2f}')}` · TO `{_escape(f'{turnover:.1f}')}%` · Margin `{_escape(f'{margin_bps:.1f}')} bps`",
        "",
        f"_{next_msg}_",
    ]
    return _send("\n".join(lines), config)


def send_telegram_health_check(
    config: OptionsConfig,
    stats: Optional[dict[str, Any]] = None,
    org_count: int = 5,
) -> bool:
    """
    Hourly system heartbeat. Shows today's discovery funnel progress at a glance.
    Called by the health.yml workflow every hour.
    """
    if not config.telegram_bot_token or not config.telegram_chat_id:
        return False

    stats = stats or {}
    ts = _now_wat().strftime("%H:%M")
    today_eval = stats.get("today_evaluated", 0)
    today_q = stats.get("today_qualified", 0)
    today_sub = stats.get("today_submitted", 0)
    reserve = stats.get("reserve_count", 0)
    today_corr = stats.get("today_correlated", 0)
    max_daily = 3

    # Submission slot indicator
    slot_bar = ""
    for i in range(1, max_daily + 1):
        slot_bar += "●" if i <= today_sub else "○"

    # Qualified progress toward daily target
    target = 5
    q_bar = ""
    for i in range(1, target + 1):
        q_bar += "●" if i <= today_q else "○"

    lines = [
        f"🟢 *Hourly Health* · {_escape(ts)} UTC\\+1",
        "",
        f"Simulated today: `{_escape(str(today_eval))}`",
        f"Qualified: `{_escape(str(today_q))}/{_escape(str(target))}` {_escape(q_bar)}",
        f"Submitted: `{_escape(str(today_sub))}/{_escape(str(max_daily))}` {_escape(slot_bar)}",
        f"Reserve \\(unsubmitted\\): `{_escape(str(reserve))}`",
        f"Corr\\-rejected today: `{_escape(str(today_corr))}`",
        "",
        f"Orgs: `{_escape(str(org_count))}/5` · 4 discovery \\+ drip active",
    ]
    return _send("\n".join(lines), config)


def send_telegram_daily_digest(
    config: OptionsConfig,
    stats: Optional[dict[str, Any]] = None,
) -> bool:
    """
    End-of-day full summary. Called once daily at 23:30 UTC by daily_digest.yml.
    Covers the full picture: funnel, submissions, reserve, and lifetime totals.
    """
    if not config.telegram_bot_token or not config.telegram_chat_id:
        return False

    stats = stats or {}
    now = _now_wat()
    date_label = _escape(now.strftime("%a %d %b"))
    max_daily = 3

    today_eval = stats.get("today_evaluated", 0)
    today_s0 = stats.get("today_stage0_pass", 0)
    today_q = stats.get("today_qualified", 0)
    today_sub = stats.get("today_submitted", 0)
    reserve = stats.get("reserve_count", 0)
    today_corr = stats.get("today_correlated", 0)
    all_pool = stats.get("all_time_pool_alphas", 0)
    all_corr = stats.get("all_time_correlated", 0)

    # Daily goal assessment
    if today_q >= 5:
        goal_icon = "✅"
        goal_note = "Daily target met"
    elif today_q >= 3:
        goal_icon = "🟡"
        goal_note = "Partial — below 5 target"
    else:
        goal_icon = "🔴"
        goal_note = "Below target"

    sub_status = f"{today_sub}/{max_daily} submitted"
    if today_sub >= max_daily:
        sub_status += " ✅"

    lines = [
        f"📊 *Daily Report* · {date_label}",
        "",
        f"*Discovery funnel*",
        f"Simulated: `{_escape(str(today_eval))}` → Stage 0: `{_escape(str(today_s0))}` → Qualified: `{_escape(str(today_q))}`",
        f"Corr\\-rejected: `{_escape(str(today_corr))}`",
        "",
        f"*Submissions*",
        f"{_escape(sub_status)}",
        f"Reserve \\(unsubmitted pool\\): `{_escape(str(reserve))}`",
        "",
        f"*Daily goal: 5 qualified* · {_escape(goal_icon)} {_escape(goal_note)}",
        "",
        f"*All\\-time*",
        f"Pool: `{_escape(str(all_pool))}` qualified · Correlated archive: `{_escape(str(all_corr))}`",
    ]
    return _send("\n".join(lines), config)
