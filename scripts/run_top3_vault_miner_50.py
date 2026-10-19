#!/usr/bin/env python3
"""
Dedicated Resilient Supervisor for Operation First 50.
Guarantees uninterrupted mining progress towards 50 qualified alphas across Top 3 Categories:
  - Executes scripts/mine_top3_first_50.py --target 50
  - Survives Wi-Fi drops, socket resets, and transient network hiccups
  - Automatically reconnects, monitors database count, and auto-resumes
  - Sends real-time Telegram updates on qualified alpha discoveries
  - Strictly enforces ZERO AUTO-SUBMISSIONS (Banked to PostgreSQL & JSON vault only)
"""
from __future__ import annotations

import argparse
import datetime
import logging
import os
import subprocess
import sys
import time
from typing import Optional

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brain_options.config import OptionsConfig
from scripts.mine_top3_first_50 import get_current_qualified_count, send_tg_message

os.makedirs("logs", exist_ok=True)

try:
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
except Exception:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [SUPERVISOR-50] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/top3_first_50_supervisor.log", mode="a", encoding="utf-8"),
    ],
)
log = logging.getLogger("supervisor_50")


def check_internet_connection(timeout: float = 5.0) -> bool:
    """Checks if external internet is reachable (WorldQuant or Cloudflare)."""
    endpoints = [
        "https://api.worldquantbrain.com/users/self",
        "https://1.1.1.1",
        "https://www.google.com",
    ]
    for url in endpoints:
        try:
            r = requests.get(url, timeout=timeout)
            if r.status_code in (200, 401, 403):
                return True
        except Exception:
            pass
    return False


def wait_for_connectivity(config: OptionsConfig, max_wait_sec: int = 3600) -> bool:
    """Blocks until internet connectivity is restored."""
    if check_internet_connection():
        return True

    log.warning("Wi-Fi / Internet connection appears down. Waiting for recovery...")
    start_wait = time.time()
    ping_notified = False

    while time.time() - start_wait < max_wait_sec:
        time.sleep(10)
        if check_internet_connection():
            log.info("Internet connection restored!")
            if ping_notified:
                send_tg_message(
                    token=config.telegram_bot_token,
                    chat_id=config.telegram_chat_id,
                    html_text="🌐 <b>Wi-Fi Restored</b>: First-50 Pipeline Supervisor resuming mining...",
                )
            return True
        elif not ping_notified and (time.time() - start_wait) > 30:
            log.warning("Wi-Fi still offline after 30s. Will notify when link returns.")
            ping_notified = True

    return False


def run_supervisor(target: int = 50, concurrency: int = 3):
    config = OptionsConfig.from_env()
    log.info("=" * 80)
    log.info("STARTING OPERATION FIRST 50 SUPERVISOR")
    log.info("Target: %d Qualified Alphas | Concurrency: %d Slots | Top 3 Categories", target, concurrency)
    log.info("Policy: ZERO AUTO-SUBMISSIONS | 100%% Banked to Vault")
    log.info("=" * 80)

    consecutive_crashes = 0
    max_consecutive_crashes = 50

    while True:
        current_count = get_current_qualified_count(config.database_url)
        log.info("Supervisor Status: %d / %d Qualified Alphas Banked in DB.", current_count, target)

        if current_count >= target:
            log.info("🏆 Target reached! Current count (%d) >= Target (%d). Supervisor exiting cleanly.",
                     current_count, target)
            send_tg_message(
                token=config.telegram_bot_token,
                chat_id=config.telegram_chat_id,
                html_text=(
                    f"🏆 <b>OPERATION FIRST 50 COMPLETE!</b>\n\n"
                    f"• <b>Total Qualified Alphas Banked:</b> <code>{current_count} / {target}</code>\n"
                    f"• <b>Submissions Status:</b> ON HOLD (Awaiting User Command)\n"
                    f"• <b>Vault Status:</b> Fully Banked & Correlation-Checked."
                ),
            )
            break

        if not check_internet_connection():
            log.warning("Wi-Fi is offline before launch. Waiting for reconnection...")
            wait_for_connectivity(config)

        log.info("Spawning miner: python scripts/mine_top3_first_50.py --target %d --pillar top3", target)
        start_ts = time.time()

        proc = subprocess.Popen(
            [sys.executable, "scripts/mine_top3_first_50.py", "--target", str(target), "--pillar", "top3"],
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )

        try:
            ret_code = proc.wait()
        except KeyboardInterrupt:
            log.info("Supervisor interrupted by user. Terminating child process...")
            proc.terminate()
            proc.wait()
            break

        runtime_sec = time.time() - start_ts
        post_count = get_current_qualified_count(config.database_url)

        if post_count >= target:
            log.info("Target of %d qualified alphas achieved! Supervisor shutting down cleanly.", target)
            break

        if ret_code == 0:
            log.info("Miner cycle completed cleanly. Current Bank: %d / %d.", post_count, target)
            time.sleep(5)
            continue

        log.warning("Miner cycle exited with code %d after %.1fs (Bank: %d/%d).",
                    ret_code, runtime_sec, post_count, target)

        consecutive_crashes += 1
        if consecutive_crashes >= max_consecutive_crashes:
            err_msg = f"Supervisor abort: Miner process crashed {consecutive_crashes} times consecutively."
            log.error(err_msg)
            send_tg_message(
                token=config.telegram_bot_token,
                chat_id=config.telegram_chat_id,
                html_text=f"🚨 <b>SUPERVISOR ALERT</b>\n\n{err_msg}\nCurrent qualified: {post_count}/{target}.",
            )
            break

        if not check_internet_connection():
            send_tg_message(
                token=config.telegram_bot_token,
                chat_id=config.telegram_chat_id,
                html_text=(
                    f"⚠️ <b>Wi-Fi Disruption Detected</b>\n\n"
                    f"• <b>Status:</b> Mining paused temporarily awaiting Wi-Fi.\n"
                    f"• <b>Current Bank:</b> <code>{post_count} / {target} Qualified Alphas</code>\n"
                    f"• <b>Auto-Resume:</b> Resuming immediately once Wi-Fi returns."
                ),
            )
            wait_for_connectivity(config)

        backoff = min(60, 5 * consecutive_crashes)
        log.info("Backing off %ds before supervisor auto-restart...", backoff)
        time.sleep(backoff)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dedicated Operation First 50 Supervisor")
    parser.add_argument("--target", type=int, default=50, help="Target count of qualified alphas (default: 50)")
    parser.add_argument("--concurrency", type=int, default=3, help="Concurrent simulation slots (default: 3)")
    args = parser.parse_args()
    run_supervisor(target=args.target, concurrency=args.concurrency)
