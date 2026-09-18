"""
Telegram notifier for brain_options: sends instant alerts for passed options alphas
with copy-paste ready simulation settings blocks for BRAIN UI, as well as pipeline
startup and batch completion summaries.
"""
from __future__ import annotations

import logging
from typing import Any, Optional
import requests
from brain_options.config import OptionsConfig
from brain_options.core.client import SimMetrics, SimSettings

log = logging.getLogger("brain_options.notifier")


import os


def send_telegram_startup(config: OptionsConfig, mode: str = "Single Batch") -> bool:
    """Sends a startup notification only when NOTIFY_ON_STARTUP=true to prevent cron noise."""
    if not config.telegram_bot_token or not config.telegram_chat_id:
        return False
    if os.environ.get("NOTIFY_ON_STARTUP", "false").lower() != "true":
        return True

    text = f"🚀 *Pipeline Started* (`{mode}`)"
    return _send_telegram_raw(text, config)


def send_telegram_batch_summary(
    passed_count: int,
    total_candidates: int,
    config: OptionsConfig,
    stats: Optional[dict[str, Any]] = None,
) -> bool:
    """Sends a clean, short summary when a batch completes."""
    if not config.telegram_bot_token or not config.telegram_chat_id:
        return False

    today_pool = stats.get("today_qualified", 0) if stats else 0
    all_time_pool = stats.get("all_time_pool_alphas", 0) if stats else 0

    text = (
        f"🏁 *Batch Complete*\n\n"
        f"• *Evaluated:* `{total_candidates}` | *Passed:* `{passed_count}`\n"
        f"• *Pool Today:* `{today_pool}` | *Total Pool:* `{all_time_pool}`"
    )
    return _send_telegram_raw(text, config)


def send_telegram_stage0_alert(
    archetype_name: str,
    expression: str,
    metrics: SimMetrics,
    config: OptionsConfig,
) -> bool:
    """Sends a real-time notification when a candidate passes Stage 0 and enters diagnostic optimization."""
    if not config.telegram_bot_token or not config.telegram_chat_id:
        return False

    text = (
        f"⭐ *Stage 0 Pass: {archetype_name}*\n"
        f"• Sharpe: `{metrics.sharpe:.2f}` | Fitness: `{metrics.fitness:.2f}` | TO: `{metrics.turnover * 100:.1f}%`\n"
        f"```\n{expression[:140]}\n```"
    )
    return _send_telegram_raw(text, config)


def send_telegram_alert(
    expression: str,
    settings: SimSettings,
    metrics: SimMetrics,
    max_corr: float,
    config: OptionsConfig,
) -> bool:
    """Sends a clean, concise, easy-to-understand alert for passed alphas with direct BRAIN link."""
    if not config.telegram_bot_token or not config.telegram_chat_id:
        log.info("Telegram notification skipped (bot token or chat ID not set).")
        return False

    alpha_id = metrics.alpha_id or "N/A"
    alpha_link = f"https://platform.worldquantbrain.com/alpha/{alpha_id}" if metrics.alpha_id else ""
    id_display = f"[{alpha_id}]({alpha_link})" if alpha_link else f"`{alpha_id}`"
    margin_bps = (metrics.margin or 0.0) * 10000.0

    text = (
        f"🎯 *PASSED ALPHA DISCOVERED*\n\n"
        f"• *ID:* {id_display}\n"
        f"• *Sharpe:* `{metrics.sharpe:.2f}` | *Fitness:* `{metrics.fitness:.2f}`\n"
        f"• *Turnover:* `{metrics.turnover * 100:.1f}%` | *Margin:* `{margin_bps:.1f} bps`\n"
        f"• *Return:* `{metrics.annualized_return * 100:.1f}%` | *Drawdown:* `{metrics.max_drawdown * 100:.1f}%`\n\n"
        f"📐 *Expression:*\n"
        f"```\n{expression}\n```\n\n"
        f"⚙️ *Settings:* `{settings.universe}` | Delay `{settings.delay}` | Decay `{settings.decay}` | `{settings.neutralization}` | Trunc `{settings.truncation}` | Past `{'ON' if settings.pasteurization else 'OFF'}`"
    )
    return _send_telegram_raw(text, config)


def send_telegram_drip_alert(
    alpha_id: str,
    date_label: str,
    metrics: dict[str, Any],
    config: OptionsConfig,
    slot_num: int = 1,
    max_daily: int = 3,
    next_unlock_str: Optional[str] = None,
) -> bool:
    """Sends an instant Telegram alert when an automated drip submission succeeds (UTC+1 localized)."""
    if not config.telegram_bot_token or not config.telegram_chat_id:
        return False

    import datetime
    wat_tz = datetime.timezone(datetime.timedelta(hours=1))
    now_wat = datetime.datetime.now(wat_tz)
    submitted_time_wat = now_wat.strftime("%Y-%m-%d %H:%M WAT (UTC+1)")

    alpha_link = f"https://platform.worldquantbrain.com/alpha/{alpha_id}"
    sharpe = float(metrics.get("sharpe") or 0.0)
    fitness = float(metrics.get("fitness") or 0.0)
    turnover = float(metrics.get("turnover") or 0.0) * 100.0
    margin_bps = float(metrics.get("margin") or 0.0) * 10000.0

    if next_unlock_str:
        unlock_msg = next_unlock_str
    elif slot_num < max_daily:
        next_dt = now_wat + datetime.timedelta(hours=4)
        unlock_msg = f"unlocks today at {next_dt.strftime('%H:%M')} UTC+1 (in 4h 00m)"
    else:
        unlock_msg = f"daily quota complete ({slot_num}/{max_daily}). Next window unlocks tomorrow at 05:00 UTC+1 (00:00 EDT)"

    text = (
        f"🚀 *DAILY ALPHA DRIP SUBMITTED!*\n\n"
        f"• *Alpha ID:* [{alpha_id}]({alpha_link})\n"
        f"• *Submitted:* `{submitted_time_wat}`\n"
        f"• *Slot:* `{slot_num} of {max_daily} (Silver Tier)`\n"
        f"• *Date Credit:* `{date_label} EDT`\n"
        f"• *Sharpe:* `{sharpe:.2f}` | *Fitness:* `{fitness:.2f}`\n"
        f"• *Turnover:* `{turnover:.1f}%` | *Margin:* `{margin_bps:.1f} bps`\n"
        f"• *All Checklist Gates:* ✅ `PASSED`\n\n"
        f"⏳ _Next submission window {unlock_msg}._"
    )
    return _send_telegram_raw(text, config)


def _send_telegram_raw(text: str, config: OptionsConfig) -> bool:
    url = f"https://api.telegram.org/bot{config.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": config.telegram_chat_id,
        "text": text,
        "parse_mode": "Markdown",
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            log.info("Telegram message sent successfully.")
            return True
        elif resp.status_code == 400 and "parse" in resp.text.lower():
            # Retry without parse_mode if unescaped symbols broke Markdown parsing
            payload.pop("parse_mode", None)
            resp2 = requests.post(url, json=payload, timeout=10)
            if resp2.status_code == 200:
                log.info("Telegram message sent successfully (plain text fallback).")
                return True
            log.warning("Telegram send failed on plain text fallback: %s %s", resp2.status_code, resp2.text)
            return False
        else:
            log.warning("Telegram send failed: %s %s", resp.status_code, resp.text)
            return False
    except Exception as e:
        log.warning("Telegram notification exception: %s", e)
        return False
