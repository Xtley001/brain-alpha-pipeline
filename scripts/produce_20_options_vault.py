#!/usr/bin/env python3
"""
Dedicated Production Pipeline: Qualify 20 Institutional Options Alphas for the Vault.
Target: Populate options_alphas table with 20 QUALIFIED alphas before 22:00 WAT.

Strictly enforces:
- Gate 1: Sharpe >= 1.25, Fitness >= 0.70, Turnover in [0.01, 0.70], Margin >= 8.0 bps, Drawdown <= 35%
- Gate 2: Correlation Firewall (|rho| < 0.70 vs all 21 submitted alphas AND all qualified vault alphas)
- Gate 3: Platform Checklist (Sub-Universe Sharpe PASS, Concentrated Weight PASS)
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
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("options_20_producer.log", mode="a", encoding="utf-8"),
    ],
)
log = logging.getLogger("options_20_producer")

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
            timeout=12,
        )
        if r.status_code == 200:
            log.info("Telegram alert delivered successfully.")
            return
        log.warning("Telegram HTML send returned %d: %s. Retrying in plain text...", r.status_code, r.text)
        plain_text = re.sub(r"<[^>]+>", "", html_text)
        r2 = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": plain_text},
            timeout=12,
        )
        if r2.status_code == 200:
            log.info("Telegram plain-text fallback delivered.")
        else:
            log.warning("Telegram plain-text send failed (%d): %s", r2.status_code, r2.text)
    except Exception as exc:
        log.warning("Telegram dispatch error: %s", exc)


def load_submitted_alphas_pnl(db_url: str) -> List[str]:
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
        log.warning("Could not fetch submitted alpha IDs from DB: %s", exc)

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


def load_qualified_vault_alphas(db_url: str) -> List[str]:
    alpha_ids = []
    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT alpha_id FROM options_alphas WHERE status = 'QUALIFIED' AND alpha_id IS NOT NULL"
                )
                for r in cur.fetchall():
                    if r[0] and r[0] not in alpha_ids:
                        alpha_ids.append(r[0])
    except Exception as exc:
        log.warning("Could not fetch qualified alpha IDs from DB: %s", exc)
    return alpha_ids


def verify_checklist_passes(session, alpha_id: str) -> Tuple[bool, str]:
    chk_url = f"https://api.worldquantbrain.com/alphas/{alpha_id}/check"
    try:
        for _ in range(10):
            resp = session.get(chk_url, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                checks = data.get("is", {}).get("checks", []) or data.get("checks", [])
                if checks:
                    failures = []
                    for c in checks:
                        name = c.get("name", "")
                        result = c.get("result", "")
                        if result != "PASS":
                            failures.append(f"{name}:{result}")
                    if failures:
                        return False, ", ".join(failures)
                    return True, "ALL_PASSED"
            time.sleep(2.5)
    except Exception as e:
        return False, f"Checklist request error: {e}"
    return False, "Checklist timed out"


def insert_qualified_alpha(
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
    strategy_name: str,
):
    sql = """
        INSERT INTO options_alphas (
            alpha_id, expression, archetype, hypothesis, source,
            sharpe, fitness, turnover, returns, drawdown, margin,
            max_correlation, universe, neutralization, delay, decay,
            truncation, pasteurization, nan_handling, status,
            created_at, strategy_name
        ) VALUES (
            %s, %s, %s, %s, 'options_20_producer',
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
    with psycopg.connect(db_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (
                alpha_id, expression, archetype, hypothesis,
                decimal.Decimal(str(round(metrics.sharpe, 4))),
                decimal.Decimal(str(round(metrics.fitness, 4))),
                decimal.Decimal(str(round(metrics.turnover, 4))),
                decimal.Decimal(str(round(metrics.annualized_return, 4))),
                decimal.Decimal(str(round(metrics.max_drawdown, 4))),
                decimal.Decimal(str(round(metrics.margin, 4))),
                decimal.Decimal(str(round(max_corr, 4))),
                universe, neutralization, decay,
                strategy_name,
            ))


def build_candidate_arsenal() -> List[Dict[str, Any]]:
    """Builds prioritized stream of orthogonal options alpha expressions."""
    candidates = []

    # =========================================================================
    # FAMILY 1: Put Open Interest Accumulation & Capitulation (The ZYAPYvqY Goldmine)
    # Base expression achieved Sharpe 1.17, Fitness 0.51, Turnover 11.6%
    # Orthogonal to price/reversal alphas (|rho| < 0.20)
    # =========================================================================
    for tenor in [30, 20, 60, 90]:
        for delta_win in [8, 10, 12, 15]:
            for smooth_win in [5, 6, 8]:
                for grp in ["SECTOR", "SUBINDUSTRY"]:
                    for decay in [12, 14, 15, 16, 18]:
                        # A. Core Rank Delta
                        expr_a = f"trade_when(volume > adv20 * 0.8, group_neutralize(rank(-ts_decay_linear(ts_delta(pcr_oi_{tenor}, {delta_win}), {smooth_win})), {grp.lower()}), -1)"
                        candidates.append({
                            "expression": expr_a,
                            "archetype": f"Put_OI_Buildup_{tenor}d_w{delta_win}_d{decay}_{grp}",
                            "hypothesis": f"Accumulation of put open interest over {delta_win}d at {tenor}d tenor captures structural options overhang.",
                            "universe": "TOP3000",
                            "neutralization": grp,
                            "decay": decay,
                            "strategy": "put_oi_accumulation",
                        })
                        # B. Signed Power Convexity
                        expr_b = f"group_neutralize(signed_power(rank(-ts_decay_linear(ts_delta(pcr_oi_{tenor}, {delta_win}), {smooth_win})) - 0.5, 1.5), {grp.lower()})"
                        candidates.append({
                            "expression": expr_b,
                            "archetype": f"Put_OI_Power_{tenor}d_w{delta_win}_d{decay}_{grp}",
                            "hypothesis": f"Convex signed power scaling on {delta_win}d put open interest delta.",
                            "universe": "TOP3000",
                            "neutralization": grp,
                            "decay": decay,
                            "strategy": "put_oi_power",
                        })

    # =========================================================================
    # FAMILY 2: PCR Velocity & Order Flow Imbalance (Tranche 4)
    # Proven virgin options order flow formula
    # =========================================================================
    tenors = [20, 30, 60, 90, 120]
    weights = [(0.65, 0.35), (0.60, 0.40), (0.50, 0.50)]
    for t in tenors:
        for w1, w2 in weights:
            for grp in ["SUBINDUSTRY", "SECTOR"]:
                for d in [10, 12, 14]:
                    sig1 = f"ts_decay_linear(ts_decay_linear(((pcr_vol_{t} / (pcr_oi_{t} + 0.001) - ts_mean(pcr_vol_{t} / (pcr_oi_{t} + 0.001), 20)) / (ts_std_dev(pcr_vol_{t} / (pcr_oi_{t} + 0.001), 20) + 0.001)), 10), 3)"
                    sig2 = f"ts_decay_linear(ts_decay_linear(((implied_volatility_put_{t} - implied_volatility_call_{t}) / (implied_volatility_mean_{t} + 0.001) * sqrt({t}/252.0)), 10), 3)"
                    combined = f"({w1} * rank({sig1}) + {w2} * rank({sig2}))"
                    expr = f"trade_when(abs(rank({combined}) - 0.5) > 0.25, group_neutralize(rank({combined}), {grp.lower()}), -1)"
                    candidates.append({
                        "expression": expr,
                        "archetype": f"PCR_Velocity_SkewDiv_{t}d_{int(w1*100)}_d{d}_{grp}",
                        "hypothesis": f"PCR volume velocity ({t}d) blended with skew divergence isolates institutional options flow.",
                        "universe": "TOP3000",
                        "neutralization": grp,
                        "decay": d,
                        "strategy": "pcr_velocity_flow",
                    })

    # =========================================================================
    # FAMILY 3: Multi-Factor Orthogonal Trios (Tranche 5)
    # Put floor + term structure slope + skew differential
    # =========================================================================
    trios = [
        (180, 60, 90), (270, 90, 60), (360, 120, 90), (120, 30, 60),
        (90, 30, 30), (150, 60, 60), (270, 60, 180)
    ]
    for t_put, t_term, t_skew in trios:
        for grp in ["SUBINDUSTRY", "SECTOR"]:
            for d in [10, 12, 14]:
                sig1 = f"ts_decay_linear(ts_decay_linear(((forward_price_{t_put} - put_breakeven_{t_put}) / close * (implied_volatility_mean_skew_{t_put} * sqrt({t_put}/252.0))), 10), 3)"
                sig2 = f"ts_decay_linear(ts_decay_linear(((implied_volatility_mean_{t_term} / (implied_volatility_mean_30 + 0.001)) * sqrt({t_term}/252.0)), 10), 3)"
                sig3 = f"ts_decay_linear(ts_decay_linear(((implied_volatility_call_{t_skew} - implied_volatility_put_{t_skew}) / (implied_volatility_mean_{t_skew} + 0.001)), 10), 3)"
                combined = f"(0.45 * rank({sig1}) + 0.35 * rank({sig2}) + 0.20 * rank({sig3}))"
                expr = f"trade_when(abs(rank({combined}) - 0.5) > 0.26, group_neutralize(rank({combined}), {grp.lower()}), -1)"
                candidates.append({
                    "expression": expr,
                    "archetype": f"Trio_{t_put}_{t_term}_{t_skew}_d{d}_{grp}",
                    "hypothesis": f"Tri-factor synthesis: {t_put}d put floor, {t_term}d term slope, and {t_skew}d skew asymmetry.",
                    "universe": "TOP3000",
                    "neutralization": grp,
                    "decay": d,
                    "strategy": "orthogonal_trios",
                })

    # =========================================================================
    # FAMILY 4: Volatility Risk Premium (VRP) & Term Structure Slope
    # Exploit variance risk premium (implied vol vs Parkinson / realized vol)
    # =========================================================================
    pairs = [(60, 20), (90, 30), (120, 30), (180, 60), (270, 90)]
    for t2, t1 in pairs:
        for grp in ["SUBINDUSTRY", "SECTOR"]:
            for d in [10, 12, 15]:
                expr = f"trade_when(volume > adv20 * 0.8, group_neutralize(rank(ts_decay_linear((implied_volatility_mean_{t2} - implied_volatility_mean_{t1}) / (implied_volatility_mean_{t1} + 0.001) * sqrt({t2}/252.0), {d})), {grp.lower()}), -1)"
                candidates.append({
                    "expression": expr,
                    "archetype": f"IV_Term_Slope_{t2}v{t1}_d{d}_{grp}",
                    "hypothesis": f"Implied volatility term structure slope ({t2}d vs {t1}d) captures macroeconomic variance risk premia.",
                    "universe": "TOP3000",
                    "neutralization": grp,
                    "decay": d,
                    "strategy": "iv_term_slope",
                })

    # =========================================================================
    # FAMILY 5: Put Breakeven Asymmetry & Skew Differential (Tranche 1B)
    # =========================================================================
    put_pairs = [
        (150, 30), (120, 20), (270, 120), (180, 20), (120, 30), (270, 90),
    ]
    for t1, t2 in put_pairs:
        for grp in ["SUBINDUSTRY", "SECTOR"]:
            for w1, w2 in [(0.65, 0.35), (0.60, 0.40)]:
                for d in [10, 12, 14]:
                    sig1 = f"ts_decay_linear(ts_decay_linear(((forward_price_{t1} - put_breakeven_{t1}) / close * (implied_volatility_mean_skew_{t1} * sqrt({t1}/252.0)) * (pcr_vol_{t1} / (pcr_oi_{t1} + 0.001))), 10), 3)"
                    sig2 = f"ts_decay_linear(ts_decay_linear(((implied_volatility_call_{t2} - implied_volatility_put_{t2}) / (implied_volatility_mean_{t2} + 0.001) * sqrt({t2}/252.0)), 10), 3)"
                    combined = f"({w1} * rank({sig1}) + {w2} * rank({sig2}))"
                    expr = f"trade_when(abs(rank({combined}) - 0.5) > 0.26, group_neutralize(rank({combined}), {grp.lower()}), -1)"
                    candidates.append({
                        "expression": expr,
                        "archetype": f"PutFloor_SkewDiff_{t1}_{t2}_{int(w1*100)}_d{d}_{grp}",
                        "hypothesis": f"Downside put floor ({t1}d) blended with skew differential ({t2}d) captures options mispricing.",
                        "universe": "TOP3000",
                        "neutralization": grp,
                        "decay": d,
                        "strategy": "put_floor_skew_diff",
                    })

    log.info("Built arsenal of %d prioritized orthogonal options candidate expressions.", len(candidates))
    return candidates


async def main():
    target_count = 20
    config = OptionsConfig.from_env()
    store = OptionsStore(data_dir=None, database_url=config.database_url)
    db = store.db

    log.info("=" * 80)
    log.info("STARTING DEDICATED 20-OPTIONS-ALPHA VAULT QUALIFIER")
    log.info("Target: %d QUALIFIED alphas committed to options_alphas", target_count)
    log.info("=" * 80)

    # 1. Authenticate with BRAIN
    client = BrainClient(
        username=config.brain_username,
        password=config.brain_password,
        max_concurrent_sims=1,
        db=db,
    )
    client.authenticate()

    # 2. Load submitted reference PnLs
    submitted_ids = load_submitted_alphas_pnl(config.database_url)
    submitted_pnls: Dict[str, Dict[str, float]] = {}
    log.info("Fetching PnL for %d submitted portfolio reference alphas...", len(submitted_ids))
    for aid in submitted_ids:
        pnl = await client.get_alpha_pnl(aid)
        if pnl:
            submitted_pnls[aid] = pnl
    log.info("Loaded %d clean submitted reference PnLs.", len(submitted_pnls))

    # 3. Load existing qualified vault alphas
    qualified_ids = load_qualified_vault_alphas(config.database_url)
    vault_pnls: Dict[str, Dict[str, float]] = {}
    for aid in qualified_ids:
        pnl = await client.get_alpha_pnl(aid)
        if pnl:
            vault_pnls[aid] = pnl
    current_qualified = len(vault_pnls)
    log.info("Initial Vault State: %d / %d QUALIFIED alphas already in DB.", current_qualified, target_count)

    # Send startup Telegram message
    send_tg_message(
        token=config.telegram_bot_token,
        chat_id=config.telegram_chat_id,
        html_text=(
            "🚀 <b>Dedicated 20-Options-Alpha Vault Qualifier Started</b>\n\n"
            f"🎯 <b>Goal:</b> 20 Qualified Options Alphas in Vault\n"
            f"📊 <b>Initial Count:</b> {current_qualified} / {target_count}\n"
            "🛡️ <b>Gates:</b> Sharpe &ge; 1.25, Fitness &ge; 0.70, |&rho;| &lt; 0.70, 100% Sub-Universe Check\n"
            "📡 <b>Mode:</b> Local High-Priority Dedicated Engine"
        ),
    )

    if current_qualified >= target_count:
        log.info("Vault already has %d qualified alphas (target %d reached)!", current_qualified, target_count)
        return

    # 4. Generate candidate expressions
    candidates = build_candidate_arsenal()
    sims_run = 0
    start_time = time.time()
    last_hourly_alert = time.time()

    # Near-miss priority queue for dynamic gradient sweeps
    priority_queue: List[Dict[str, Any]] = []

    while current_qualified < target_count:
        # Check candidate source
        if priority_queue:
            cand = priority_queue.pop(0)
            log.info("[⚡] Processing priority near-miss candidate: %s", cand["archetype"])
        elif candidates:
            cand = candidates.pop(0)
        else:
            log.warning("Exhausted all candidates in arsenal. Recycling with parameter perturbations...")
            candidates = build_candidate_arsenal()
            continue

        expr = cand["expression"]
        arch = cand["archetype"]
        hyp = cand["hypothesis"]
        u = cand["universe"]
        n = cand["neutralization"]
        d = cand["decay"]
        strat = cand["strategy"]

        # Hourly heartbeat
        now = time.time()
        if now - last_hourly_alert >= 3600:
            last_hourly_alert = now
            elapsed = (now - start_time) / 3600.0
            send_tg_message(
                token=config.telegram_bot_token,
                chat_id=config.telegram_chat_id,
                html_text=(
                    f"⏱️ <b>Hourly Vault Qualifier Heartbeat</b>\n\n"
                    f"📊 <b>Vault Progress:</b> {current_qualified} / {target_count} Qualified Alphas\n"
                    f"⏳ <b>Elapsed Time:</b> {elapsed:.1f} hours\n"
                    f"🔬 <b>Simulations Evaluated:</b> {sims_run}\n"
                    f"🟢 <b>Status:</b> Actively hunting options alpha"
                ),
            )

        sims_run += 1
        settings = SimSettings(
            region="USA",
            universe=u,
            delay=1,
            decay=d,
            neutralization=n,
            truncation=0.05,
            pasteurization=True,
        )

        log.info(
            "[Sim #%d] Simulating %s (decay=%d, u=%s, neut=%s)...",
            sims_run, arch, d, u, n
        )

        try:
            metrics = await client.simulate_one(expr, settings)
        except Exception as sim_err:
            log.warning("Simulation exception: %s", sim_err)
            await asyncio.sleep(2.0)
            continue

        if not metrics or not metrics.is_valid:
            await asyncio.sleep(1.0)
            continue

        log.info(
            "[Sim #%d] AlphaID=%s | Sharpe=%.2f | Fitness=%.2f | TO=%.1f%% | Margin=%.1fbps | DD=%.1f%% | %s",
            sims_run, metrics.alpha_id, metrics.sharpe, metrics.fitness,
            metrics.turnover * 100, metrics.margin * 10000, metrics.max_drawdown * 100, arch
        )

        # Gate 1: Performance Thresholds
        if (
            metrics.sharpe < 1.25
            or metrics.fitness < 0.70
            or metrics.turnover < 0.01
            or metrics.turnover > 0.70
            or metrics.margin < 0.0008
            or metrics.max_drawdown > 0.35
        ):
            # Dynamic Convex Near-Miss Sweep: if Sharpe in [1.05, 1.24] and Fitness >= 0.40
            if 1.05 <= metrics.sharpe < 1.25 and metrics.fitness >= 0.40 and len(priority_queue) < 20:
                log.info("[⚡ Near-Miss] Sharpe=%.2f, Fitness=%.2f for %s. Enqueuing gradient variations...", metrics.sharpe, metrics.fitness, metrics.alpha_id)
                for shift in [-3, -2, 2, 3]:
                    new_d = max(5, d + shift)
                    priority_queue.append({
                        "expression": expr,
                        "archetype": f"{arch}_d{new_d}",
                        "hypothesis": f"{hyp} [NearMiss d={new_d}]",
                        "universe": u,
                        "neutralization": n,
                        "decay": new_d,
                        "strategy": strat,
                    })
                alt_n = "SUBINDUSTRY" if n.upper() == "SECTOR" else "SECTOR"
                priority_queue.append({
                    "expression": expr,
                    "archetype": f"{arch}_{alt_n}",
                    "hypothesis": f"{hyp} [NearMiss neut={alt_n}]",
                    "universe": u,
                    "neutralization": alt_n,
                    "decay": d,
                    "strategy": strat,
                })
            await asyncio.sleep(1.0)
            continue

        # Gate 2: Correlation Firewall vs Submitted & Vault Alphas
        cand_pnl = await client.get_alpha_pnl(metrics.alpha_id)
        if not cand_pnl or len(cand_pnl) < 30:
            log.warning("Could not retrieve PnL for %s — skipping.", metrics.alpha_id)
            continue

        max_corr_sub = max([abs(compute_correlation(cand_pnl, p)) for p in submitted_pnls.values()] or [0.0])
        if max_corr_sub >= 0.70:
            log.info("[-] Correlation vs submitted portfolio failed: %.4f >= 0.70 for %s", max_corr_sub, metrics.alpha_id)
            continue

        max_corr_vault = max([abs(compute_correlation(cand_pnl, p)) for p in vault_pnls.values()] or [0.0])
        if max_corr_vault >= 0.70:
            log.info("[-] Correlation vs vault reserve failed: %.4f >= 0.70 for %s", max_corr_vault, metrics.alpha_id)
            continue

        overall_max_corr = max(max_corr_sub, max_corr_vault)

        # Gate 3: Platform Checklist Verification (SUB-UNIVERSE SHARPE)
        log.info("[*] Testing Gate 3 Platform Checklist on BRAIN for %s...", metrics.alpha_id)
        chk_passed, chk_msg = verify_checklist_passes(client._session, metrics.alpha_id)
        if not chk_passed:
            log.warning("[-] Checklist check FAILED for %s: %s", metrics.alpha_id, chk_msg)
            continue

        log.info("[✓] 100% CHECKLIST PASSED for %s: %s", metrics.alpha_id, chk_msg)

        # Passed all 3 gates! Commit to vault
        current_qualified += 1
        vault_pnls[metrics.alpha_id] = cand_pnl

        log.info("=" * 80)
        log.info(
            "🌟 [QUALIFIED #%d / %d] AlphaID=%s | Sharpe=%.2f | Fitness=%.2f | TO=%.1f%% | Margin=%.1fbps | Corr=%.4f",
            current_qualified, target_count, metrics.alpha_id, metrics.sharpe, metrics.fitness,
            metrics.turnover * 100, metrics.margin * 10000, overall_max_corr
        )
        log.info("=" * 80)

        insert_qualified_alpha(
            db_url=config.database_url,
            alpha_id=metrics.alpha_id,
            expression=expr,
            archetype=arch,
            hypothesis=hyp,
            metrics=metrics,
            max_corr=overall_max_corr,
            universe=u,
            neutralization=n,
            decay=d,
            strategy_name=strat,
        )

        safe_expr = html.escape(expr)
        safe_alpha = html.escape(metrics.alpha_id or "unknown")
        safe_strat = html.escape(strat)
        send_tg_message(
            token=config.telegram_bot_token,
            chat_id=config.telegram_chat_id,
            html_text=(
                f"🌟 <b>OPTIONS ALPHA QUALIFIED (#{current_qualified}/{target_count})!</b> 🌟\n\n"
                f"• <b>Alpha ID:</b> <code>{safe_alpha}</code>\n"
                f"• <b>Sharpe:</b> {metrics.sharpe:.2f} | <b>Fitness:</b> {metrics.fitness:.2f}\n"
                f"• <b>Margin:</b> {metrics.margin * 10000:.1f} bps | <b>Turnover:</b> {metrics.turnover * 100:.1f}%\n"
                f"• <b>Max Correlation:</b> {overall_max_corr:.4f} (&lt; 0.70)\n"
                f"• <b>Platform Checklist:</b> 100% PASS\n"
                f"• <b>Strategy:</b> {safe_strat}\n"
                f"• <b>Expression:</b>\n<code>{safe_expr}</code>"
            ),
        )

    log.info("=" * 80)
    log.info("🎯 TARGET REACHED: %d QUALIFIED OPTIONS ALPHAS COMMITTED TO VAULT!", current_qualified)
    log.info("=" * 80)
    send_tg_message(
        token=config.telegram_bot_token,
        chat_id=config.telegram_chat_id,
        html_text=(
            f"🏆 <b>GOAL FULFILLED: 20 QUALIFIED OPTIONS ALPHAS IN VAULT!</b> 🏆\n\n"
            f"All 20 alphas passed Sharpe &ge; 1.25, Fitness &ge; 0.70, |&rho;| &lt; 0.70, and 100% Sub-Universe checks.\n"
            "Ready for daily 3-alpha submissions!"
        ),
    )


if __name__ == "__main__":
    asyncio.run(main())
