"""
Telegram notifier for brain_options: sends instant alerts for passed options alphas
with copy-paste ready simulation settings blocks for BRAIN UI.
"""
from __future__ import annotations

import logging
import requests
from brain_options.config import OptionsConfig
from brain_options.core.client import SimMetrics, SimSettings

log = logging.getLogger("brain_options.notifier")


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

    url = f"https://api.telegram.org/bot{config.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": config.telegram_chat_id,
        "text": text,
        "parse_mode": "Markdown",
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            log.info("Telegram alert sent successfully.")
            return True
        else:
            log.warning("Telegram alert failed: %s %s", resp.status_code, resp.text)
            return False
    except Exception as e:
        log.warning("Telegram notification exception: %s", e)
        return False
