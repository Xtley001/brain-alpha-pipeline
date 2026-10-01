import asyncio
import logging
import sys
import argparse
from datetime import date

sys.path.insert(0, r"c:\Users\pc\Desktop\brain-alpha-pipeline")

import html
import re

import psycopg
import requests
from dotenv import load_dotenv

load_dotenv()

from brain_options.config import OptionsConfig
from brain_options.core.client import BrainClient
from brain_options.store.store import OptionsStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("daily_vault_submit")

DAILY_LIMIT = 3


def send_tg_alert(config, alpha_id, archetype, sharpe, fitness, margin, corr, rank_order, submitted_count, total_submitted):
    token = config.telegram_bot_token
    chat_id = config.telegram_chat_id
    if not token or not chat_id:
        return
    is_gain = int(sharpe * fitness * 300)
    score_gain = round(sharpe * fitness * 300 / 15000, 3)
    safe_alpha = html.escape(alpha_id or "unknown")
    safe_arch = html.escape(archetype or "general")
    text = (
        f"<b>RESERVE ALPHA SUBMITTED (Vault #{str(rank_order).zfill(2)})</b>\n\n"
        f"<b>Alpha ID:</b> <code>{safe_alpha}</code>\n"
        f"<b>Archetype:</b> <code>{safe_arch}</code>\n"
        f"<b>Sharpe:</b> <b>{sharpe:.2f}</b>  |  "
        f"<b>Fitness:</b> <b>{fitness:.2f}</b>\n"
        f"<b>Margin:</b> {margin:.1f} bps  |  "
        f"<b>Max Corr:</b> {corr:.4f}\n\n"
        f"<b>Submitted today:</b> {submitted_count}/{DAILY_LIMIT}\n"
        f"<b>Total on BRAIN:</b> {total_submitted}\n"
        f"IS Score gain: <b>+{is_gain:,} pts</b>\n"
        f"Total Score gain: <b>+{score_gain}</b>"
    )
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}, timeout=10)
        if r.status_code == 200:
            log.info("Telegram alert sent for %s.", alpha_id)
            return
        log.warning("Telegram HTML send failed (%d): %s. Retrying in plain text...", r.status_code, r.text)
        plain_text = re.sub(r"<[^>]+>", "", text)
        r2 = requests.post(url, json={"chat_id": chat_id, "text": plain_text}, timeout=10)
        if r2.status_code == 200:
            log.info("Telegram plain-text fallback delivered.")
        else:
            log.warning("Telegram plain-text failed (%d): %s", r2.status_code, r2.text)
    except Exception as e:
        log.warning("Telegram alert failed: %s", e)


def load_qualified_vault(database_url):
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT alpha_id, archetype, expression, sharpe, fitness, turnover, "
                "margin, max_correlation, returns, drawdown, universe, neutralization, "
                "delay, decay, strategy_name, (sharpe * fitness) AS score_proxy "
                "FROM options_alphas WHERE status = 'QUALIFIED' ORDER BY score_proxy DESC;"
            )
            rows = cur.fetchall()
    cols = [
        "alpha_id", "archetype", "expression", "sharpe", "fitness", "turnover",
        "margin", "max_correlation", "returns", "drawdown", "universe",
        "neutralization", "delay", "decay", "strategy_name", "score_proxy"
    ]
    return [dict(zip(cols, r)) for r in rows]


def mark_submitted(database_url, alpha_id):
    with psycopg.connect(database_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE options_alphas SET status = 'SUBMITTED' WHERE alpha_id = %s;", (alpha_id,))
    log.info("DB: %s  QUALIFIED -> SUBMITTED", alpha_id)


def total_submitted(database_url):
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM options_alphas WHERE status = 'SUBMITTED';")
            return cur.fetchone()[0]


def run_checklist(session, alpha_id, max_retries=5, delay=2.0):
    url = "https://api.worldquantbrain.com/alphas/" + alpha_id + "/check"
    import time
    for attempt in range(1, max_retries + 1):
        try:
            resp = session.get(url)
            if resp.status_code == 200 and resp.text.strip():
                try:
                    data = resp.json()
                except Exception:
                    data = {}
                checks = data.get("is", {}).get("checks", []) or data.get("checks", [])
                if checks:
                    failing = [c.get("name") for c in checks if c.get("result") == "FAIL"]
                    if failing:
                        log.warning("  Checklist FAIL for %s: %s -- SKIPPING.", alpha_id, failing)
                        return False
                    log.info("  Checklist PASS for %s (%d checks OK).", alpha_id, len(checks))
                    return True
            log.info("  Checklist for %s pending/warming (attempt %d/%d)... waiting %ss", alpha_id, attempt, max_retries, delay)
            time.sleep(delay)
        except Exception as e:
            log.warning("  Checklist request error for %s (attempt %d): %s", alpha_id, attempt, e)
            time.sleep(delay)
    log.warning("  Checklist timeout/empty for %s -- SKIPPING.", alpha_id)
    return False


async def main(dry_run=False):
    config = OptionsConfig.from_env()
    store = OptionsStore(database_url=config.database_url)
    client = BrainClient(
        username=config.brain_username,
        password=config.brain_password,
        max_concurrent_sims=1,
        db=store.db,
    )
    client.authenticate()
    session = client._get_session()

    today = date.today().isoformat()
    log.info("=" * 70)
    log.info("DAILY VAULT SUBMISSION ENGINE  --  %s  [limit %d/day  dry-run=%s]", today, DAILY_LIMIT, dry_run)
    log.info("=" * 70)

    vault = load_qualified_vault(config.database_url)
    log.info("Vault: %d QUALIFIED alphas loaded.", len(vault))

    if not vault:
        log.info("Vault is empty. Nothing to submit today.")
        return

    log.info("")
    log.info("  === SUBMISSION ORDER (highest IS Score proxy first) ===")
    for i, a in enumerate(vault, 1):
        log.info(
            "  #%02d: %s | %-45s | Sh:%.2f  Fit:%.2f  Proxy:%.3f",
            i, a["alpha_id"], a["archetype"][:45], a["sharpe"], a["fitness"], a["score_proxy"]
        )
    log.info("")

    submitted_today = 0

    for rank_order, alpha in enumerate(vault, 1):
        if submitted_today >= DAILY_LIMIT:
            log.info("Daily limit of %d reached. Stopping.", DAILY_LIMIT)
            break

        alpha_id = alpha["alpha_id"]
        archetype = alpha["archetype"]
        sharpe = alpha["sharpe"]
        fitness = alpha["fitness"]
        margin = (alpha["margin"] or 0.0) * 10000
        corr = alpha["max_correlation"] or 0.0

        log.info("-" * 70)
        log.info("[Vault #%02d]  %s  |  %s", rank_order, alpha_id, archetype)
        log.info("  Sh:%.2f  Fit:%.2f  Marg:%.1f bps  Corr:%.4f  Proxy:%.3f",
                 sharpe, fitness, margin, corr, alpha["score_proxy"])

        if not run_checklist(session, alpha_id):
            log.warning("  SKIP: %s  -- failed checklist.", alpha_id)
            continue

        if dry_run:
            log.info("  [DRY-RUN] Would submit %s  (no actual API call).", alpha_id)
            submitted_today += 1
            continue

        log.info("  Submitting %s ...", alpha_id)
        result = await client.submit_alpha(alpha_id)

        if result.get("ok"):
            log.info("  SUCCESS: %s  (HTTP %s)", alpha_id, result.get("status_code"))
            mark_submitted(config.database_url, alpha_id)
            submitted_today += 1
            tot = total_submitted(config.database_url)
            send_tg_alert(config, alpha_id, archetype, sharpe, fitness,
                          margin, corr, rank_order, submitted_today, tot)
        else:
            http = result.get("status_code")
            msg = result.get("message", "")[:200]
            log.error("  FAILED: %s  HTTP %s  -- %s", alpha_id, http, msg)
            if http == 403:
                log.error("  403 Forbidden: BRAIN daily submission limit hit. Stopping.")
                break

    log.info("=" * 70)
    tot = total_submitted(config.database_url)
    log.info("DONE:  %d submitted today  |  %d total on BRAIN  |  %d remaining in vault",
             submitted_today, tot, len(vault) - submitted_today)
    log.info("Est IS Score gain: ~+%s pts  |  Est Total Score gain: ~+%.3f",
             "{:,}".format(submitted_today * 370), submitted_today * 0.020)
    log.info("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Daily Vault Submission Engine -- 2 alphas/day, highest IS Score first")
    parser.add_argument("--dry-run", action="store_true", help="Preview plan only, no actual submissions.")
    args = parser.parse_args()
    asyncio.run(main(dry_run=args.dry_run))
