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


def send_telegram_startup(config: OptionsConfig, mode: str = "Single Batch") -> bool:
    """Sends a startup notification when the pipeline initializes."""
    if not config.telegram_bot_token or not config.telegram_chat_id:
        return False

    text = (
        f"🚀 *Brain Options Pipeline Started*\n\n"
        f"• *Mode:* `{mode}`\n"
        f"• *Universe:* `{config.universe}` (Delay: `{config.delay}`)\n"
        f"• *Knowledge Base:* `Master Books 1–4 (Sinclair, Derman, Natenberg, Handbook)`\n"
        f"• *Max Concurrent Sims:* `{config.brain_max_concurrent_sims}`\n"
        f"• *Max Correlation:* `{config.max_pool_correlation:.2f}`\n\n"
        f"_Scanning options space for institutional pricing anomalies..._"
    )
    return _send_telegram_raw(text, config)


def send_telegram_batch_summary(
    passed_count: int,
    total_candidates: int,
    config: OptionsConfig,
    stats: Optional[dict[str, Any]] = None,
) -> bool:
    """Sends a completion summary after a batch of candidates finishes."""
    if not config.telegram_bot_token or not config.telegram_chat_id:
        return False

    text_lines = [
        "🏁 *Options Alpha Batch Complete*\n",
        f"• *This Batch:* `{total_candidates}` evaluated | `{passed_count}` qualified",
    ]

    if stats:
        today_eval = stats.get("today_evaluated", 0)
        today_pass = stats.get("today_stage0_pass", 0)
        today_qual = stats.get("today_qualified", 0)
        all_time_eval = stats.get("all_time_evaluated", 0)
        all_time_pool = stats.get("all_time_pool_alphas", 0)

        text_lines.extend([
            f"\n📅 *Today's Options Activity:*",
            f"• Evaluated Today: `{today_eval}`",
            f"• Stage 0 Passing: `{today_pass}`",
            f"• Fully Qualified: `{today_qual}`",
            f"\n📊 *All-Time Options Totals:*",
            f"• Total Evaluated: `{all_time_eval}`",
            f"• Qualified in Pool: `{all_time_pool}`",
        ])

    text_lines.append("\n• *Status:* `Learning memory & pool synced`")
    return _send_telegram_raw("\n".join(text_lines), config)


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
        f"⭐ *Stage 0 Alpha Signal Detected!*\n\n"
        f"• *Archetype:* `{archetype_name}`\n"
        f"• *Stage 0 Sharpe:* `{metrics.sharpe:.2f}`\n"
        f"• *Stage 0 Fitness:* `{metrics.fitness:.2f}`\n"
        f"• *Turnover:* `{metrics.turnover * 100:.1f}%`\n\n"
        f"📐 *Signal:*\n"
        f"```\n{expression[:160]}\n```\n\n"
        f"🔄 _Entering multi-arm diagnostic optimization to push Sharpe \u2265 1.25 & Fitness \u2265 1.0..._"
    )
    return _send_telegram_raw(text, config)


def send_telegram_alert(
    expression: str,
    settings: SimSettings,
    metrics: SimMetrics,
    max_corr: float,
    config: OptionsConfig,
) -> bool:
    """Sends Telegram message with passed alpha stats and copy-paste ready settings."""
    if not config.telegram_bot_token or not config.telegram_chat_id:
        log.info("Telegram notification skipped (bot token or chat ID not set).")
        return False

    text = (
        f"🎯 *PASSED OPTIONS ALPHA DISCOVERED!*\n\n"
        f"📊 *Performance:*\n"
        f"• *Sharpe:* `{metrics.sharpe:.2f}`\n"
        f"• *Fitness:* `{metrics.fitness:.2f}`\n"
        f"• *Turnover:* `{metrics.turnover * 100:.1f}%`\n"
        f"• *Ann. Return:* `{metrics.annualized_return * 100:.1f}%`\n"
        f"• *Max Drawdown:* `{metrics.max_drawdown * 100:.1f}%`\n"
        f"• *Max Pool Correlation:* `{max_corr:.2f}`\n"
        f"• *Alpha ID:* `{metrics.alpha_id or 'N/A'}`\n\n"
        f"📐 *Fast Expression:*\n"
        f"```\n{expression}\n```\n\n"
        f"⚙️ *BRAIN Settings:*\n"
        f"• Universe: `{settings.universe}`\n"
        f"• Delay: `{settings.delay}`\n"
        f"• Decay: `{settings.decay}`\n"
        f"• Neutralization: `{settings.neutralization}`\n"
        f"• Truncation: `{settings.truncation}`\n"
        f"• Pasteurization: `{'ON' if settings.pasteurization else 'OFF'}`\n"
        f"• NaN Handling: `{'ON' if settings.nan_handling else 'OFF'}`\n"
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
        else:
            log.warning("Telegram send failed: %s %s", resp.status_code, resp.text)
            return False
    except Exception as e:
        log.warning("Telegram notification exception: %s", e)
        return False
