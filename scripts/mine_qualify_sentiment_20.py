#!/usr/bin/env python3
"""
Dedicated Sentiment-Only 20 Alphas Qualification Miner.
Exclusively focuses on institutional Sentiment & PEAD factor interactions:
- Standardized Unexpected Earnings (SUE) Tail Shocks x Volatility Decoupling
- Post-Earnings Announcement Drift (PEAD) Net Revisions x Short-term Price Reversal
- Analyst Recommendation & Target Price Upgrades Confluence
- Analyst Forecast Dispersion Anomalies
- Dynamic Focus & Media Buzz Reversals

Applies:
- Sub-Universe Liquidity Armor: trade_when(volume > adv20 * 0.8, ...)
- Subindustry Neutralization: group_neutralize(..., subindustry)
- Decay Calibration: ts_decay_linear(ts_decay_linear(..., decay), 3)
- Real-time Correlation Gate: |rho| < 0.70 vs all 21 production alphas & mutually in reserve
- Platform Checklist Verification: 100% PASS on /alphas/{alpha_id}/check
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
log = logging.getLogger("sentiment_20_qualifier")

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
    """Retrieve all production & qualified alpha IDs from database."""
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


def get_current_qualified_count(db_url: str) -> int:
    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM options_alphas WHERE status = 'QUALIFIED';")
                return cur.fetchone()[0]
    except Exception as exc:
        log.warning("Error getting qualified count: %s", exc)
        return 0


def verify_checklist_passes(session: requests.Session, alpha_id: str) -> Tuple[bool, str]:
    chk_url = f"https://api.worldquantbrain.com/alphas/{alpha_id}/check"
    try:
        for _ in range(12):
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
            time.sleep(2.5)
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
            NOW(), 'vault_sentiment'
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
                    alpha_id, expression, archetype, hypothesis, "sentiment_vault_miner",
                    decimal.Decimal(str(round(metrics.sharpe, 4))),
                    decimal.Decimal(str(round(metrics.fitness, 4))),
                    decimal.Decimal(str(round(metrics.turnover, 4))),
                    decimal.Decimal(str(round(ret_val, 4))),
                    decimal.Decimal(str(round(metrics.max_drawdown, 4))),
                    decimal.Decimal(str(round(metrics.margin, 4))),
                    decimal.Decimal(str(round(max_corr, 4))),
                    universe, neutralization, decay,
                ))
        log.info("[+] Committed %s to options_alphas as QUALIFIED.", alpha_id)
    except Exception as e:
        log.error("Failed to commit qualified alpha %s: %s", alpha_id, e)


def build_sentiment_candidate_matrix() -> List[Dict[str, Any]]:
    """Builds an exhaustive matrix of institutional bivariate sentiment candidates with parameter sweeps."""
    candidates = []
    universes = ["TOP3000", "TOP2000", "TOP1000"]
    neutralizations = ["SUBINDUSTRY", "SECTOR"]

    # 1. SUE Shock x Volatility Decoupling Sweeps (Highest historical near-miss candidate)
    for u in universes:
        for neut in neutralizations:
            for d in [10, 12, 14, 16, 18, 20]:
                for p_window in [3, 5]:
                    for vol_window in [20, 40]:
                        candidates.append({
                            "expression": f"trade_when(volume > adv20 * 0.8, group_neutralize(rank(ts_decay_linear(ts_decay_linear(snt1_d1_earningssurprise, {d}), 3)) * rank(-ts_delta(close, {p_window}) / (ts_std_dev(close, {vol_window}) + 0.001)), {neut.lower()}), -1)",
                            "archetype": f"SUE_Vol_Bivariate_d{d}_{neut}",
                            "hypothesis": f"Earnings surprise shock interacted with {p_window}d price reversal / {vol_window}d volatility spread (decay={d}, {neut}).",
                            "universe": u,
                            "neutralization": neut,
                            "decay": d,
                        })

    # 2. PEAD Revision Sluggishness x Reversal Sweeps
    for u in universes:
        for neut in neutralizations:
            for d in [10, 12, 14, 16, 18, 22]:
                for rev_window in [3, 5, 8]:
                    candidates.append({
                        "expression": f"trade_when(volume > adv20 * 0.8, group_neutralize(rank(ts_decay_linear(ts_decay_linear(snt1_d1_netearningsrevision, {d}), 3)) * rank(-ts_delta(close, {rev_window})), {neut.lower()}), -1)",
                        "archetype": f"PEAD_Revision_Reversal_d{d}_r{rev_window}",
                        "hypothesis": f"Net earnings revision smoothed over {d}d interacting with {rev_window}d return reversal.",
                        "universe": u,
                        "neutralization": neut,
                        "decay": d,
                    })

    # 3. Target Price Revision Spread x Intraday High-Low
    for u in universes:
        for neut in neutralizations:
            for d in [10, 12, 14, 16, 18]:
                candidates.append({
                    "expression": f"trade_when(volume > adv20 * 0.8, group_neutralize(rank(ts_decay_linear(ts_decay_linear(snt1_d1_uptargetpercent - snt1_d1_downtargetpercent, {d}), 3)) * rank((high - low) / (vwap + 0.001)), {neut.lower()}), -1)",
                    "archetype": f"Target_Price_Spread_Intraday_d{d}",
                    "hypothesis": f"Target price revision momentum interacting with intraday volatility range (decay={d}).",
                    "universe": u,
                    "neutralization": neut,
                    "decay": d,
                })

    # 4. Analyst Recommendation Upgrades x PEAD Revision Confluence
    for u in universes:
        for neut in neutralizations:
            for d in [12, 14, 16, 20]:
                for w1 in [0.5, 0.6, 0.7]:
                    w2 = round(1.0 - w1, 2)
                    candidates.append({
                        "expression": f"trade_when(volume > adv20 * 0.8, group_neutralize(rank({w1} * rank(ts_decay_linear(ts_decay_linear(snt1_d1_netrecpercent, {d}), 3)) + {w2} * rank(ts_decay_linear(ts_decay_linear(snt1_d1_netearningsrevision, {d}), 3))), {neut.lower()}), -1)",
                        "archetype": f"Rec_Revision_Confluence_d{d}_w{int(w1*100)}",
                        "hypothesis": f"Confluence of analyst recommendation changes and earnings revisions (weights {w1}/{w2}, decay={d}).",
                        "universe": u,
                        "neutralization": neut,
                        "decay": d,
                    })

    # 5. Analyst Target Price to Close Ratio Momentum
    for u in universes:
        for neut in neutralizations:
            for d in [12, 15, 18]:
                candidates.append({
                    "expression": f"trade_when(volume > adv20 * 0.8, group_neutralize(rank(ts_decay_linear(ts_decay_linear(snt1_d1_targetprice / (close + 0.001), {d}), 3)) * rank(-ts_delta(close, 5)), {neut.lower()}), -1)",
                    "archetype": f"Target_to_Close_Reversal_d{d}",
                    "hypothesis": f"Target price valuation ratio smoothed over {d}d interacted with 5d price reversal.",
                    "universe": u,
                    "neutralization": neut,
                    "decay": d,
                })

    return candidates


async def run_sentiment_miner():
    config = OptionsConfig.from_env()
    store = OptionsStore()
    client = BrainClient(
        username=config.brain_username,
        password=config.brain_password,
        max_concurrent_sims=1,
        db=store.db,
    )

    log.info("=" * 70)
    log.info("STARTING DEDICATED SENTIMENT 20 QUALIFIED ALPHAS MINER")
    log.info("=" * 70)

    # 1. Authenticate with BRAIN
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
    log.info("Successfully loaded %d reference PnL vectors.", len(ref_pnls))

    # 3. Build Candidate Matrix
    candidates = build_sentiment_candidate_matrix()
    target_count = 20
    current_qualified = get_current_qualified_count(config.database_url)
    log.info("Loaded %d candidate sentiment configurations. Target: %d (Current: %d)", len(candidates), target_count, current_qualified)

    near_miss_queue: List[Dict[str, Any]] = []

    for idx, cand in enumerate(candidates, 1):
        current_qualified = get_current_qualified_count(config.database_url)
        if current_qualified >= target_count:
            log.info("🎉 TARGET REACHED: %d Sentiment Alphas Qualified in Vault!", current_qualified)
            break

        # Check near-miss queue first
        active_cand = near_miss_queue.pop(0) if near_miss_queue else cand
        expr = active_cand["expression"]
        arch = active_cand["archetype"]
        hyp = active_cand["hypothesis"]
        universe = active_cand["universe"]
        neut = active_cand["neutralization"]
        decay = active_cand["decay"]

        log.info("-" * 65)
        log.info("[%d/%d | Qualified: %d/%d] Simulating: %s (u=%s, neut=%s, d=%d)", idx, len(candidates), current_qualified, target_count, arch, universe, neut, decay)

        settings = SimSettings(
            region="USA",
            universe=universe,
            delay=1,
            decay=decay,
            neutralization=neut,
            truncation=0.05,
            pasteurization=True,
        )

        try:
            metrics = await client.simulate_one(expr, settings)
        except Exception as sim_err:
            log.warning("Simulation error on %s: %s", arch, sim_err)
            await asyncio.sleep(2.0)
            continue

        if not metrics or not metrics.is_valid:
            await asyncio.sleep(1.0)
            continue

        log.info(
            "Simulated %s | Sharpe=%.2f | Fit=%.2f | TO=%.1f%% | Margin=%.1fbps | DD=%.1f%%",
            metrics.alpha_id, metrics.sharpe, metrics.fitness, metrics.turnover * 100, metrics.margin * 10000, metrics.max_drawdown * 100
        )

        # Gate 1: Performance Criteria
        passed_gate1 = (
            metrics.sharpe >= 1.25
            and metrics.fitness >= 1.00
            and 0.01 <= metrics.turnover <= 0.60
            and (metrics.margin * 10000) >= 8.0
            and metrics.max_drawdown <= 0.35
        )

        if not passed_gate1:
            # Check near-miss: If Sharpe in [1.00, 1.24] and TO < 25%, enqueue parameter sweeps
            if 1.00 <= metrics.sharpe < 1.25 and metrics.turnover <= 0.25 and len(near_miss_queue) < 10:
                log.info("[⚡] Near-Miss on %s (Sharpe=%.2f, Fit=%.2f). Enqueuing micro-decay sweeps...", metrics.alpha_id, metrics.sharpe, metrics.fitness)
                for d_offset in [-2, 2]:
                    new_d = max(6, decay + d_offset)
                    near_miss_queue.append({
                        "expression": expr,
                        "archetype": f"{arch}_d{new_d}",
                        "hypothesis": f"{hyp} [Micro-Sweep d={new_d}]",
                        "universe": universe,
                        "neutralization": neut,
                        "decay": new_d,
                    })
            continue

        # Gate 2: Correlation Firewall
        cand_pnl = await client.get_alpha_pnl(metrics.alpha_id)
        if not cand_pnl or len(cand_pnl) < 30:
            log.warning("[-] Could not retrieve PnL for %s — skipping.", metrics.alpha_id)
            continue

        max_corr = 0.0
        worst_ref = ""
        for r_id, r_pnl in ref_pnls.items():
            c_val = abs(compute_correlation(cand_pnl, r_pnl))
            if c_val > max_corr:
                max_corr = c_val
                worst_ref = r_id

        if max_corr >= 0.70:
            log.info("[-] Gate 2 Correlation FAIL for %s: rho=%.4f vs %s (>= 0.70)", arch, max_corr, worst_ref)
            continue

        # Gate 3: Platform Checklist
        log.info("[*] Checking platform checklist on BRAIN for %s...", metrics.alpha_id)
        chk_ok, chk_msg = verify_checklist_passes(client._session, metrics.alpha_id)
        if not chk_ok:
            log.warning("[-] Gate 3 Checklist FAIL for %s: %s", metrics.alpha_id, chk_msg)
            continue

        # ALL 3 GATES PASSED! Commit to Vault
        current_qualified += 1
        ref_pnls[metrics.alpha_id] = cand_pnl
        commit_qualified_alpha(
            db_url=config.database_url,
            alpha_id=metrics.alpha_id,
            expression=expr,
            archetype=arch,
            hypothesis=hyp,
            metrics=metrics,
            max_corr=max_corr,
            universe=universe,
            neutralization=neut,
            decay=decay,
        )

        safe_expr = html.escape(expr)
        safe_alpha = html.escape(metrics.alpha_id)
        safe_arch = html.escape(arch)
        send_tg_message(
            token=config.telegram_bot_token,
            chat_id=config.telegram_chat_id,
            html_text=(
                f"🌟 <b>NEW SENTIMENT ALPHA QUALIFIED!</b> ({current_qualified}/20) 🌟\n\n"
                f"• <b>Alpha ID:</b> <code>{safe_alpha}</code>\n"
                f"• <b>Category:</b> SENTIMENT\n"
                f"• <b>Archetype:</b> {safe_arch}\n"
                f"• <b>Sharpe:</b> <b>{metrics.sharpe:.2f}</b>  |  <b>Fitness:</b> <b>{metrics.fitness:.2f}</b>\n"
                f"• <b>Margin:</b> {metrics.margin * 10000:.1f} bps  |  <b>Turnover:</b> {metrics.turnover * 100:.1f}%\n"
                f"• <b>Max Correlation:</b> <b>{max_corr:.4f}</b> (&lt; 0.70)\n"
                f"• <b>Checklist:</b> 100% PASS\n"
                f"• <b>Expression:</b>\n<code>{safe_expr}</code>"
            ),
        )
        log.info("[🌟] QUALIFIED & STORED IN VAULT: %s (%s, Sharpe=%.2f, MaxCorr=%.4f)", metrics.alpha_id, arch, metrics.sharpe, max_corr)

    final_count = get_current_qualified_count(config.database_url)
    log.info("=" * 70)
    log.info("SENTIMENT MINER COMPLETE: %d / 20 QUALIFIED IN VAULT", final_count)
    log.info("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_sentiment_miner())
