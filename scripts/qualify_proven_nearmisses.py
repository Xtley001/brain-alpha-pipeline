#!/usr/bin/env python3
"""
Proven Near-Miss Qualifier: Extracts top PASS-status alphas already simulated
by our cloud miners from options_evaluations, then runs them through:
  Gate 2: Correlation Firewall (|rho| < 0.70 vs all 21 production alphas)
  Gate 3: Platform Checklist (Sub-Universe Sharpe PASS)
  Then commits QUALIFIED to options_alphas vault.
"""
from __future__ import annotations

import asyncio
import decimal
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import html
import re

import psycopg
import requests
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("proven_qualifier")

from brain_options.config import OptionsConfig
from brain_options.core.client import BrainClient, SimSettings
from brain_options.core.correlation import compute_correlation
from brain_options.store.store import OptionsStore


def send_tg_message(token: str, chat_id: str, html_text: str):
    if not token or not chat_id:
        return
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": html_text, "parse_mode": "HTML"},
            timeout=10,
        )
        if r.status_code == 200:
            log.info("Telegram alert delivered successfully.")
            return
        log.warning("Telegram HTML send returned %d: %s. Retrying in plain text...", r.status_code, r.text)
        plain_text = re.sub(r"<[^>]+>", "", html_text)
        r2 = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": plain_text},
            timeout=10,
        )
        if r2.status_code == 200:
            log.info("Telegram plain-text fallback delivered.")
        else:
            log.warning("Telegram plain-text send failed (%d): %s", r2.status_code, r2.text)
    except Exception as exc:
        log.warning("Telegram dispatch failed: %s", exc)


def load_proven_candidates(db_url: str, limit: int = 15) -> List[Dict]:
    """
    Load top-performing PASS candidates from options_evaluations that
    haven't yet been committed to options_alphas.
    Diversity-picks across different archetypes to avoid correlated bundles.
    """
    candidates = []
    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                # Pull best unique candidate per archetype with high Sharpe
                cur.execute("""
                    SELECT DISTINCT ON (archetype)
                        id, alpha_id, archetype, sharpe, fitness, turnover,
                        returns, drawdown, expression
                    FROM options_evaluations
                    WHERE
                        sharpe >= 1.25
                        AND fitness >= 0.90
                        AND status IN ('PASS', 'OPTIMIZED', 'QUALIFIED')
                        AND alpha_id IS NOT NULL
                        AND expression IS NOT NULL
                        AND alpha_id NOT IN (
                            SELECT alpha_id FROM options_alphas
                            WHERE alpha_id IS NOT NULL
                        )
                    ORDER BY archetype, sharpe DESC
                    LIMIT %s
                """, (limit,))
                rows = cur.fetchall()
                for r in rows:
                    candidates.append({
                        "eval_id": r[0],
                        "alpha_id": r[1],
                        "archetype": r[2],
                        "sharpe": float(r[3]),
                        "fitness": float(r[4]),
                        "turnover": float(r[5]),
                        "returns": float(r[6]) if r[6] else 0.0,
                        "drawdown": float(r[7]) if r[7] else 0.0,
                        "expression": r[8],
                    })
    except Exception as exc:
        log.error("Could not fetch proven candidates: %s", exc)
    return candidates


def load_reference_pnls(db_url: str) -> List[str]:
    """Retrieve all submitted production alpha IDs."""
    alpha_ids = []
    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT alpha_id FROM options_alphas WHERE status = 'SUBMITTED' AND alpha_id IS NOT NULL"
                )
                for r in cur.fetchall():
                    if r[0] and r[0] not in alpha_ids:
                        alpha_ids.append(r[0])
    except Exception as exc:
        log.warning("Could not fetch reference alpha IDs: %s", exc)

    hardcoded = [
        "rKOa6qa9", "YPboG01w", "XgbOoJjx", "e7bWxz7E", "ZYbNORZx", "mLmQjlzE",
        "P02K7eYK", "Xgbv1A80", "levEYpmx", "YPb81N2v", "E5pNpQlm", "N176Geqp",
        "gJQWL7aK", "Grdg2Njo", "xA3872wq", "3qXLMqg0", "0mX0kG86", "RRbnn8xe",
        "blbZ9Wkp", "KPNd6Ovl", "gJbAP76e"
    ]
    for h in hardcoded:
        if h not in alpha_ids:
            alpha_ids.append(h)
    return alpha_ids


def verify_checklist_passes(session: requests.Session, alpha_id: str) -> Tuple[bool, str]:
    """Polls WorldQuant BRAIN check endpoint to confirm 100% PASS."""
    chk_url = f"https://api.worldquantbrain.com/alphas/{alpha_id}/check"
    try:
        for attempt in range(15):
            resp = session.get(chk_url, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                checks = data.get("checks", [])
                if checks:
                    failures = []
                    for c in checks:
                        res = c.get("result", "")
                        name = c.get("name", "Unknown")
                        val = c.get("value", "")
                        lim = c.get("limit", "")
                        if res in ("FAIL", "ERROR"):
                            failures.append(f"{name}({val} vs {lim})")
                    if failures:
                        return False, f"Checklist FAIL: {', '.join(failures)}"
                    return True, "Checklist 100% PASS"
            time.sleep(3)
        return False, "Checklist timed out"
    except Exception as exc:
        return False, f"Checklist error: {exc}"


def commit_qualified_alpha(
    db_url: str,
    alpha_id: str,
    expression: str,
    archetype: str,
    sharpe: float,
    fitness: float,
    turnover: float,
    returns: float,
    drawdown: float,
    max_corr: float,
    margin: float = 0.0,
):
    sql = """
        INSERT INTO options_alphas (
            alpha_id, expression, archetype, hypothesis, source,
            sharpe, fitness, turnover, returns, drawdown, margin,
            max_correlation, universe, neutralization, delay, decay,
            truncation, pasteurization, nan_handling, status,
            created_at, strategy_name
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, 1, 8,
            0.05, 'ON', 'OFF', 'QUALIFIED',
            NOW(), %s
        ) ON CONFLICT (alpha_id) DO UPDATE SET
            status = 'QUALIFIED',
            sharpe = EXCLUDED.sharpe,
            fitness = EXCLUDED.fitness,
            max_correlation = EXCLUDED.max_correlation;
    """
    try:
        with psycopg.connect(db_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (
                    alpha_id, expression, archetype,
                    f"Proven near-miss from cloud miner evaluation. Sharpe={sharpe:.2f}.",
                    "cloud_miner_proven",
                    decimal.Decimal(str(round(sharpe, 4))),
                    decimal.Decimal(str(round(fitness, 4))),
                    decimal.Decimal(str(round(turnover, 4))),
                    decimal.Decimal(str(round(returns, 4))),
                    decimal.Decimal(str(round(drawdown, 4))),
                    decimal.Decimal(str(round(margin, 6))),
                    decimal.Decimal(str(round(max_corr, 4))),
                    "TOP3000", "SUBINDUSTRY",
                    "vault_proven",
                ))
        log.info("[+] Committed %s (Sharpe=%.2f) to QUALIFIED vault.", alpha_id, sharpe)
    except Exception as e:
        log.error("Failed to commit %s: %s", alpha_id, e)


async def run_proven_qualification():
    config = OptionsConfig.from_env()
    store = OptionsStore()
    client = BrainClient(
        username=config.brain_username,
        password=config.brain_password,
        max_concurrent_sims=1,
        db=store.db,
    )

    log.info("=" * 70)
    log.info("PROVEN NEAR-MISS QUALIFICATION PIPELINE")
    log.info("Strategy: Use alphas already SIMulated & PASS'd by cloud miners")
    log.info("Skip Gate 1 (already passed). Run Gate 2 (Corr) + Gate 3 (Checklist)")
    log.info("=" * 70)

    # Authenticate
    try:
        await asyncio.to_thread(client.authenticate)
    except Exception as exc:
        log.error("Authentication failed: %s", exc)
        return

    # Load proven candidates from DB
    candidates = load_proven_candidates(config.database_url, limit=15)
    if not candidates:
        log.warning("No proven candidates found in evaluations DB! Check miners are running.")
        return
    log.info("Loaded %d proven PASS candidates from options_evaluations DB.", len(candidates))
    for c in candidates:
        log.info("  [%.2f Sh / %.2f Fit] %s | %s", c['sharpe'], c['fitness'], c['alpha_id'], c['archetype'])

    # Pre-fetch reference PnLs
    ref_alpha_ids = load_reference_pnls(config.database_url)
    ref_pnls: Dict[str, Dict[str, float]] = {}
    log.info("\nPre-fetching PnL for %d production reference alphas...", len(ref_alpha_ids))
    for aid in ref_alpha_ids:
        pnl = await client.get_alpha_pnl(aid)
        if pnl:
            ref_pnls[aid] = pnl
    log.info("Fetched %d reference PnL vectors.\n", len(ref_pnls))

    qualified_count = 0
    results_summary = []

    for idx, cand in enumerate(candidates, 1):
        alpha_id = cand["alpha_id"]
        archetype = cand["archetype"]
        log.info("-" * 65)
        log.info("[%d/%d] Checking proven candidate: %s", idx, len(candidates), archetype)
        log.info("  Alpha ID: %s | Sharpe: %.2f | Fitness: %.2f | Turnover: %.1f%%",
                 alpha_id, cand['sharpe'], cand['fitness'], cand['turnover'] * 100)

        try:
            # Gate 2: Correlation firewall
            cand_pnl = await client.get_alpha_pnl(alpha_id)
            if not cand_pnl or len(cand_pnl) < 30:
                log.warning("[-] Could not retrieve PnL for %s — skipping.", alpha_id)
                results_summary.append((archetype, alpha_id, "NO_PNL", cand['sharpe'], 0.0))
                continue

            max_corr = 0.0
            worst_corr_alpha = ""
            for ref_id, ref_p in ref_pnls.items():
                corr_val = abs(compute_correlation(cand_pnl, ref_p))
                if corr_val > max_corr:
                    max_corr = corr_val
                    worst_corr_alpha = ref_id

            if max_corr >= 0.70:
                log.info("[-] Gate 2 Corr FAIL: rho=%.4f (>= 0.70) vs %s", max_corr, worst_corr_alpha)
                results_summary.append((archetype, alpha_id, f"CORR_FAIL({worst_corr_alpha}:{max_corr:.3f})", cand['sharpe'], max_corr))
                continue

            log.info("[+] Gate 2 PASS: max_corr=%.4f (< 0.70)", max_corr)

            # Gate 3: Platform Checklist
            log.info("[*] Verifying platform checklist on BRAIN for %s...", alpha_id)
            chk_passed, chk_msg = verify_checklist_passes(client._session, alpha_id)
            if not chk_passed:
                log.warning("[-] Gate 3 Checklist FAIL: %s", chk_msg)
                results_summary.append((archetype, alpha_id, "CHECKLIST_FAIL", cand['sharpe'], max_corr))
                continue

            log.info("[+] Gate 3 PASS: %s", chk_msg)

            # ALL GATES PASSED — commit to vault!
            qualified_count += 1
            ref_pnls[alpha_id] = cand_pnl
            commit_qualified_alpha(
                db_url=config.database_url,
                alpha_id=alpha_id,
                expression=cand["expression"],
                archetype=archetype,
                sharpe=cand["sharpe"],
                fitness=cand["fitness"],
                turnover=cand["turnover"],
                returns=cand["returns"],
                drawdown=cand["drawdown"],
                max_corr=max_corr,
            )

            safe_aid = html.escape(alpha_id)
            safe_arch = html.escape(archetype)
            safe_expr = html.escape(cand["expression"][:300])
            send_tg_message(
                token=config.telegram_bot_token,
                chat_id=config.telegram_chat_id,
                html_text=(
                    f"🌟 <b>RESERVE ALPHA QUALIFIED (Proven Near-Miss)!</b> 🌟\n\n"
                    f"• <b>Alpha ID:</b> <code>{safe_aid}</code>\n"
                    f"• <b>Archetype:</b> {safe_arch}\n"
                    f"• <b>Sharpe:</b> <b>{cand['sharpe']:.2f}</b>  |  <b>Fitness:</b> <b>{cand['fitness']:.2f}</b>\n"
                    f"• <b>Turnover:</b> {cand['turnover'] * 100:.1f}%\n"
                    f"• <b>Max Corr:</b> <b>{max_corr:.4f}</b> (&lt; 0.70)\n"
                    f"• <b>Checklist:</b> 100% PASS\n"
                    f"• <b>Total Qualified:</b> {qualified_count}\n"
                    f"• <b>Expression:</b>\n<code>{safe_expr}</code>"
                ),
            )
            log.info("[🌟] VAULT QUALIFIED #%d: %s (Sharpe=%.2f, MaxCorr=%.4f)", qualified_count, alpha_id, cand['sharpe'], max_corr)
            results_summary.append((archetype, alpha_id, "QUALIFIED", cand['sharpe'], max_corr))

        except Exception as exc:
            log.error("Error checking %s: %s", alpha_id, exc)
            results_summary.append((archetype, alpha_id, f"ERROR", cand['sharpe'], 0.0))

    log.info("=" * 70)
    log.info("PROVEN QUALIFICATION COMPLETE: %d / %d QUALIFIED", qualified_count, len(candidates))
    log.info("SUMMARY:")
    for arch, aid, status, sh, corr in results_summary:
        status_icon = "✅" if status == "QUALIFIED" else "❌"
        log.info("  %s %-38s | %-8s | %-30s | Sh:%.2f | Corr:%.4f", status_icon, arch[:38], aid[:8], status[:30], sh, corr)
    log.info("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_proven_qualification())
