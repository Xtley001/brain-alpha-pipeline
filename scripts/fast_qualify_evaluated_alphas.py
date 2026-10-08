#!/usr/bin/env python3
"""
Fast Batch Verifier for Evaluated Alphas.
Scans already-evaluated high-Sharpe / high-Fitness candidates in options_evaluations,
checks correlation against the 21 reference production alphas, runs platform /check,
and commits them directly to options_alphas as QUALIFIED.
"""
from __future__ import annotations

import asyncio
import decimal
import html
import logging
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional, Set, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg
import requests
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("fast_qualifier")

from brain_options.config import OptionsConfig
from brain_options.core.client import BrainClient, SimMetrics, SimSettings
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
        plain_text = re.sub(r"<[^>]+>", "", html_text)
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": plain_text},
            timeout=10,
        )
    except Exception as exc:
        log.warning("Telegram dispatch failed: %s", exc)


def load_reference_pnls(db_url: str) -> List[str]:
    alpha_ids = []
    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT alpha_id FROM options_alphas WHERE status IN ('SUBMITTED', 'QUALIFIED') AND alpha_id IS NOT NULL"
                )
                for r in cur.fetchall():
                    if r[0] and r[0] not in alpha_ids:
                        alpha_ids.append(r[0])
    except Exception as exc:
        log.warning("Could not fetch reference alpha IDs from DB: %s", exc)

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
    chk_url = f"https://api.worldquantbrain.com/alphas/{alpha_id}/check"
    try:
        for _ in range(8):
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
                            failures.append(f"{name} ({val} vs {lim})")
                    if failures:
                        return False, f"Checklist FAIL: {', '.join(failures)}"
                    return True, "Checklist 100% PASS"
            time.sleep(2.0)
        return False, "Checklist timed out"
    except Exception as exc:
        return False, f"Checklist request error: {exc}"


def commit_qualified_alpha(
    db_url: str,
    alpha_id: str,
    expression: str,
    archetype: str,
    hypothesis: str,
    metrics: SimMetrics,
    max_corr: float,
    universe: str,
    neutralization: str,
    decay: int,
    category: str,
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
            %s, %s, %s, 1, %s,
            0.05, 'ON', 'OFF', 'QUALIFIED',
            NOW(), %s
        ) ON CONFLICT (alpha_id) DO UPDATE SET
            status = 'QUALIFIED',
            sharpe = EXCLUDED.sharpe,
            fitness = EXCLUDED.fitness,
            margin = EXCLUDED.margin,
            max_correlation = EXCLUDED.max_correlation;
    """
    try:
        ret_val = getattr(metrics, 'annualized_return', getattr(metrics, 'returns', 0.0))
        with psycopg.connect(db_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (
                    alpha_id, expression, archetype, hypothesis, f"fast_qualifier_{category}",
                    decimal.Decimal(str(round(metrics.sharpe, 4))),
                    decimal.Decimal(str(round(metrics.fitness, 4))),
                    decimal.Decimal(str(round(metrics.turnover, 4))),
                    decimal.Decimal(str(round(ret_val, 4))),
                    decimal.Decimal(str(round(metrics.max_drawdown, 4))),
                    decimal.Decimal(str(round(metrics.margin, 4))),
                    decimal.Decimal(str(round(max_corr, 4))),
                    universe, neutralization, decay,
                    f"vault_{category}",
                ))
        log.info("[+] Committed %s to options_alphas as QUALIFIED.", alpha_id)
    except Exception as e:
        log.error("Failed to commit qualified alpha %s: %s", alpha_id, e)


async def main():
    config = OptionsConfig.from_env()
    store = OptionsStore()
    client = BrainClient(
        username=config.brain_username,
        password=config.brain_password,
        max_concurrent_sims=1,
        db=store.db,
    )

    log.info("=" * 70)
    log.info("STARTING FAST QUALIFIER ACROSS EVALUATION HISTORY")
    log.info("=" * 70)

    # 1. Authenticate
    try:
        await asyncio.to_thread(client.authenticate)
    except Exception as exc:
        log.error("Authentication failed: %s", exc)
        return

    # 2. Pre-fetch reference PnLs
    ref_alpha_ids = load_reference_pnls(config.database_url)
    ref_pnls: Dict[str, Dict[str, float]] = {}
    log.info("Pre-fetching PnLs for %d reference production alphas...", len(ref_alpha_ids))
    for aid in ref_alpha_ids:
        pnl = await client.get_alpha_pnl(aid)
        if pnl:
            ref_pnls[aid] = pnl
    log.info("Fetched %d reference PnLs.", len(ref_pnls))

    # 3. Query all evaluated PASS alphas
    evaluated_candidates = []
    with psycopg.connect(config.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT ON (alpha_id)
                    alpha_id, expression, archetype, sharpe, fitness, turnover, returns, drawdown, source
                FROM options_evaluations
                WHERE alpha_id IS NOT NULL AND status = 'PASS' AND sharpe >= 1.25 AND turnover BETWEEN 0.01 AND 0.60
                ORDER BY alpha_id, sharpe DESC;
            """)
            for r in cur.fetchall():
                evaluated_candidates.append({
                    "alpha_id": r[0],
                    "expression": r[1],
                    "archetype": r[2] or "Historical_Evaluation",
                    "sharpe": float(r[3]),
                    "fitness": float(r[4]),
                    "turnover": float(r[5]),
                    "returns": float(r[6]),
                    "drawdown": float(r[7]),
                    "source": r[8] or "cloud_options",
                })

    log.info("Found %d evaluated candidates with Sharpe >= 1.25 to verify.", len(evaluated_candidates))

    qualified_count = 0
    with psycopg.connect(config.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM options_alphas WHERE status = 'QUALIFIED';")
            qualified_count = cur.fetchone()[0]

    log.info("Current Qualified Count: %d / 20", qualified_count)

    for idx, cand in enumerate(evaluated_candidates, 1):
        if qualified_count >= 20:
            log.info("🎉 TARGET 20 QUALIFIED ALPHAS REACHED!")
            break

        aid = cand["alpha_id"]
        if aid in ref_pnls:
            continue

        log.info("[%d/%d | Qualified: %d/20] Testing Alpha ID: %s (Sharpe=%.2f, Fit=%.2f, TO=%.1f%%)", idx, len(evaluated_candidates), qualified_count, aid, cand["sharpe"], cand["fitness"], cand["turnover"] * 100)

        # 1. Fetch PnL
        pnl = await client.get_alpha_pnl(aid)
        if not pnl or len(pnl) < 30:
            continue

        # 2. Check Correlation Gate
        max_corr = 0.0
        worst_ref = ""
        for r_id, r_pnl in ref_pnls.items():
            c_val = abs(compute_correlation(pnl, r_pnl))
            if c_val > max_corr:
                max_corr = c_val
                worst_ref = r_id

        if max_corr >= 0.70:
            log.info("[-] Correlation FAIL for %s: rho=%.4f vs %s (>= 0.70)", aid, max_corr, worst_ref)
            continue

        # 3. Check Platform Checklist
        chk_ok, chk_msg = verify_checklist_passes(client._session, aid)
        if not chk_ok:
            log.info("[-] Checklist FAIL for %s: %s", aid, chk_msg)
            continue

        # 4. Fetch full metadata from BRAIN
        sim_resp = client._session.get(f"https://api.worldquantbrain.com/alphas/{aid}", timeout=15)
        if sim_resp.status_code != 200:
            continue
        d = sim_resp.json()
        is_met = d.get("is", {})
        settings = d.get("settings", {})

        metrics = SimMetrics(
            alpha_id=aid,
            sharpe=float(is_met.get("sharpe", cand["sharpe"])),
            fitness=float(is_met.get("fitness", cand["fitness"])),
            turnover=float(is_met.get("turnover", cand["turnover"])),
            annualized_return=float(is_met.get("returns", cand["returns"])),
            max_drawdown=float(is_met.get("drawdown", cand["drawdown"])),
            margin=float(is_met.get("margin", 0.0015)),
            subuniverse_sharpe=float(is_met.get("subuniverseSharpe", 1.0)),
            is_valid=True,
        )

        category = "options" if "option" in cand["source"] else ("sentiment" if "sentiment" in cand["source"] else "risk_model")
        commit_qualified_alpha(
            db_url=config.database_url,
            alpha_id=aid,
            expression=cand["expression"],
            archetype=cand["archetype"],
            hypothesis=f"Fast verified historical candidate ({cand['archetype']})",
            metrics=metrics,
            max_corr=max_corr,
            universe=settings.get("universe", "TOP2000"),
            neutralization=settings.get("neutralization", "SUBINDUSTRY"),
            decay=int(settings.get("decay", 12)),
            category=category,
        )

        ref_pnls[aid] = pnl
        qualified_count += 1

        safe_expr = html.escape(cand["expression"])
        safe_alpha = html.escape(aid)
        safe_arch = html.escape(cand["archetype"])
        safe_cat = html.escape(category.upper())
        send_tg_message(
            token=config.telegram_bot_token,
            chat_id=config.telegram_chat_id,
            html_text=(
                f"🌟 <b>NEW RESERVE ALPHA QUALIFIED!</b> ({qualified_count}/20) 🌟\n\n"
                f"• <b>Alpha ID:</b> <code>{safe_alpha}</code>\n"
                f"• <b>Category:</b> {safe_cat}\n"
                f"• <b>Archetype:</b> {safe_arch}\n"
                f"• <b>Sharpe:</b> <b>{metrics.sharpe:.2f}</b>  |  <b>Fitness:</b> <b>{metrics.fitness:.2f}</b>\n"
                f"• <b>Margin:</b> {metrics.margin * 10000:.1f} bps  |  <b>Turnover:</b> {metrics.turnover * 100:.1f}%\n"
                f"• <b>Max Correlation:</b> <b>{max_corr:.4f}</b> (&lt; 0.70)\n"
                f"• <b>Checklist:</b> 100% PASS\n"
                f"• <b>Expression:</b>\n<code>{safe_expr}</code>"
            ),
        )
        log.info("[🌟] QUALIFIED & STORED IN VAULT: %s (%s, Sharpe=%.2f, MaxCorr=%.4f)", aid, cand["archetype"], metrics.sharpe, max_corr)

    log.info("=" * 70)
    log.info("FAST QUALIFIER COMPLETE: %d QUALIFIED ALPHAS IN VAULT", qualified_count)
    log.info("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
