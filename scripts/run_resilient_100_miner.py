#!/usr/bin/env python3
"""
Resilient Autonomous 100-Alpha Mining Supervisor & Watchdog.
Guarantees uninterrupted mining progress towards 100 fresh qualified alphas:
  - Runs master_quintuple_vault_miner_500.py with target 100
  - Survives Wi-Fi drops, transient network hiccups, and PC socket resets
  - Automatically tests connectivity, logs backoff, and resumes from current DB count
  - Sends real-time Telegram updates on pass + hourly heartbeats + emergency recovery pings
  - Strictly adheres to ZERO AUTO-SUBMISSIONS (Banked to PostgreSQL options_alphas)
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
from scripts.master_quintuple_vault_miner_500 import get_current_qualified_count, send_tg_message

os.makedirs("logs", exist_ok=True)

try:
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
except Exception:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [SUPERVISOR] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/resilient_supervisor.log", mode="a", encoding="utf-8"),
    ],
)
log = logging.getLogger("resilient_supervisor")


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

    log.warning("Internet connection appears down. Waiting for Wi-Fi recovery...")
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
                    html_text="🌐 <b>Wi-Fi / Internet Restored</b>: Pipeline supervisor resuming alpha mining...",
                )
            return True
        elif not ping_notified and (time.time() - start_wait) > 30:
            log.warning("Wi-Fi still offline after 30s. Sending notification when link returns.")
            ping_notified = True

    return False


def run_supervisor(target: int = 100, pillar: str = "all"):
    config = OptionsConfig.from_env()
    log.info("=" * 80)
    log.info("STARTING RESILIENT 100-ALPHA MINER SUPERVISOR")
    log.info("Target: %d Qualified Alphas | Pillar: %s | Zero Submissions | PC Fault-Tolerant", target, pillar.upper())
    log.info("=" * 80)

    consecutive_crashes = 0
    max_consecutive_crashes = 50

    while True:
        current_count = get_current_qualified_count(config.database_url)
        log.info("Supervisor Status: %d / %d Qualified Alphas Banked in DB.", current_count, target)

        if current_count >= target:
            log.info("🏆 Target reached! Current count (%d) >= Target (%d). Supervisor exiting cleanly.",
                     current_count, target)
            break

        if not check_internet_connection():
            log.warning("Wi-Fi / Internet is offline before process launch. Waiting for reconnection...")
            wait_for_connectivity(config)

        log.info("Spawning miner process: python scripts/master_quintuple_vault_miner_500.py --target %d --pillar %s", target, pillar)
        start_ts = time.time()

        proc = subprocess.Popen(
            [sys.executable, "scripts/master_quintuple_vault_miner_500.py", "--target", str(target), "--pillar", str(pillar)],
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
            log.info("Miner process exited with returncode 0. Progress: %d / %d.", post_count, target)
            if post_count >= target:
                break
            time.sleep(5)
            continue

        log.warning("Miner process exited unexpectedly with code %d after %.1fs (Current Bank: %d/%d).",
                    ret_code, runtime_sec, post_count, target)

        consecutive_crashes += 1
        if consecutive_crashes >= max_consecutive_crashes:
            err_msg = f"Supervisor abort: Miner process crashed {consecutive_crashes} times consecutively."
            log.error(err_msg)
            send_tg_message(
                token=config.telegram_bot_token,
                chat_id=config.telegram_chat_id,
                html_text=f"🚨 <b>SUPERVISOR EMERGENCY ALERT</b>\n\n{err_msg}\nCurrent qualified: {post_count}/{target}.",
            )
            break

        # Check connectivity
        if not check_internet_connection():
            send_tg_message(
                token=config.telegram_bot_token,
                chat_id=config.telegram_chat_id,
                html_text=(
                    f"⚠️ <b>Wi-Fi Disruption Detected</b>\n\n"
                    f"• <b>Status:</b> Process paused temporarily awaiting Wi-Fi reconnection.\n"
                    f"• <b>Current Bank:</b> <code>{post_count} / {target} Qualified Alphas</code>\n"
                    f"• <b>Auto-Resume:</b> Will resume immediately once internet reconnects."
                ),
            )
            wait_for_connectivity(config)

        backoff = min(60, 5 * consecutive_crashes)
        log.info("Backing off %ds before supervisor auto-restart...", backoff)
        time.sleep(backoff)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Resilient 100-Alpha Mining Supervisor")
    parser.add_argument("--target", type=int, default=100, help="Target count of qualified alphas (default: 100)")
    parser.add_argument("--pillar", type=str, default="all",
                        choices=["all", "options", "risk", "analyst", "short", "fundamental", "top3"],
                        help="Target pillar to focus on (default: all)")
    args = parser.parse_args()
    run_supervisor(target=args.target, pillar=args.pillar)
