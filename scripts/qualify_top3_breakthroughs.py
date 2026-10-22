#!/usr/bin/env python3
"""
Dedicated Top-3 Alpha Precision Strike.
Directly targets the 3 breakthrough alphas discovered over the last 24h:
1. Risk Model BAB (Sharpe 1.74 base, YPxl6kPv) -> Solves turnover & fitness with decay 18-22 and smoothed zscore.
2. Options Vol Skew (Sharpe 1.28 base, npA6KXod) -> Pushes fitness >= 1.00 via conviction thresholding (0.32 - 0.40) & power 2.0.
3. Apex Tri-Factor (Fitness 1.01 base, VkdxMokw) -> Replaces raw volume gate with rank conviction gating to clear concentrated weight and push Sharpe >= 1.25.
"""
from __future__ import annotations

import asyncio
import decimal
import html
import logging
import os
import sys
import time
from typing import Any, Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("top3_strike")

from brain_options.config import OptionsConfig
from brain_options.core.client import BrainClient, SimMetrics, SimSettings
from brain_options.core.correlation import compute_correlation
from brain_options.core.validator import validate_expression
from brain_options.store.store import OptionsStore
from scripts.cloud_multi_miner import (
    commit_qualified_alpha,
    log_candidate_evaluation,
    send_tg_message,
    verify_checklist_passes,
    load_reference_pnls,
)


def build_strike_candidates() -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []

    # ── PILLAR 1: Risk Model BAB (Base Sharpe 1.74, AID=YPxl6kPv) ──
    # Turnover was 61.4% -> decay 18-22 and smoothed return windows cut turnover to ~25-30%, pushing Fitness >= 1.20
    candidates.append({
        "name": "BAB_Smoothed_d18_w10_d5",
        "expr": "group_neutralize(rank(-ts_decay_linear(beta_last_60_days_spy, 18) * ts_decay_linear(ts_zscore(returns, 10), 5)), subindustry)",
        "decay": 18,
        "truncation": 0.05,
        "universe": "TOPSP500",
        "neut": "SUBINDUSTRY",
        "category": "risk_model",
        "hypothesis": "BAB with 18d decay and 10d smoothed returns to cut turnover below 30% and push Fitness >= 1.20",
    })
    candidates.append({
        "name": "BAB_Smoothed_d22_w10_d5",
        "expr": "group_neutralize(rank(-ts_decay_linear(beta_last_60_days_spy, 22) * ts_decay_linear(ts_zscore(returns, 10), 5)), subindustry)",
        "decay": 22,
        "truncation": 0.05,
        "universe": "TOPSP500",
        "neut": "SUBINDUSTRY",
        "category": "risk_model",
        "hypothesis": "BAB with 22d decay and 10d smoothed returns for minimum turnover and maximum fitness",
    })
    candidates.append({
        "name": "BAB_Smoothed_d22_w15_d5",
        "expr": "group_neutralize(rank(-ts_decay_linear(beta_last_60_days_spy, 22) * ts_decay_linear(ts_zscore(returns, 15), 5)), subindustry)",
        "decay": 22,
        "truncation": 0.05,
        "universe": "TOPSP500",
        "neut": "SUBINDUSTRY",
        "category": "risk_model",
        "hypothesis": "BAB with 15d return window and 22d decay for low turnover",
    })
    candidates.append({
        "name": "BAB_Gated_d18_w10_d5",
        "expr": "trade_when(abs(rank(-ts_decay_linear(beta_last_60_days_spy, 18) * ts_decay_linear(ts_zscore(returns, 10), 5)) - 0.5) > 0.20, group_neutralize(rank(-ts_decay_linear(beta_last_60_days_spy, 18) * ts_decay_linear(ts_zscore(returns, 10), 5)), subindustry), -1)",
        "decay": 18,
        "truncation": 0.05,
        "universe": "TOPSP500",
        "neut": "SUBINDUSTRY",
        "category": "risk_model",
        "hypothesis": "Conviction-gated BAB with 18d decay to eliminate noise and boost fitness",
    })
    candidates.append({
        "name": "BAB_Gated_d22_w10_d5",
        "expr": "trade_when(abs(rank(-ts_decay_linear(beta_last_60_days_spy, 22) * ts_decay_linear(ts_zscore(returns, 10), 5)) - 0.5) > 0.20, group_neutralize(rank(-ts_decay_linear(beta_last_60_days_spy, 22) * ts_decay_linear(ts_zscore(returns, 10), 5)), subindustry), -1)",
        "decay": 22,
        "truncation": 0.05,
        "universe": "TOPSP500",
        "neut": "SUBINDUSTRY",
        "category": "risk_model",
        "hypothesis": "Conviction-gated BAB with 22d decay for maximum Sharpe & Fitness",
    })

    # ── PILLAR 2: Options Vol Skew Steepness (Base Sharpe 1.28, AID=npA6KXod) ──
    # Base had threshold > 0.26 and fitness 0.70 -> wider threshold (0.32 - 0.40) drops turnover and lifts returns to push Fitness >= 1.00
    for thresh in ["0.32", "0.36", "0.40"]:
        for p in [1.5, 2.0]:
            expr = f"trade_when(abs(rank(ts_decay_linear(-ts_delta(implied_volatility_mean_skew_30, 10), 8)) - 0.5) > {thresh}, group_neutralize(signed_power(rank(ts_decay_linear(-ts_delta(implied_volatility_mean_skew_30, 10), 8)) - 0.5, {p}), subindustry), -1)"
            candidates.append({
                "name": f"VolSkew_t{thresh}_p{p}_d8",
                "expr": expr,
                "decay": 8,
                "truncation": 0.05,
                "universe": "TOPSP500",
                "neut": "SUBINDUSTRY",
                "category": "options",
                "hypothesis": f"Vol Skew conviction threshold={thresh} with signed_power={p} and decay=8 to push Fitness >= 1.00",
            })

    # ── PILLAR 3: Apex Tri-Factor Accumulation (Base Fitness 1.01, AID=VkdxMokw) ──
    # Replaces raw volume hurdle with rank conviction gating to clear CONCENTRATED_WEIGHT and lift Sharpe >= 1.25
    inner_rank = (
        "rank(0.45 * rank(ts_decay_linear(((call_breakeven_60 - forward_price_60) / (close + 0.001)), 8)) + "
        "0.35 * rank(ts_decay_linear(((anl4_af_eps_value - anl4_afv4_eps_mean) / (anl4_afv4_dts_spe + 0.001)), 8)) - "
        "0.20 * rank(ts_decay_linear(beta_last_60_days_spy, 8)))"
    )
    for thresh in ["0.25", "0.30", "0.35"]:
        for p in [1.25, 1.5]:
            expr = f"trade_when(abs({inner_rank} - 0.5) > {thresh}, group_neutralize(signed_power({inner_rank} - 0.5, {p}), subindustry), -1)"
            candidates.append({
                "name": f"Apex_RankGated_t{thresh}_p{p}_d8",
                "expr": expr,
                "decay": 8,
                "truncation": 0.05,
                "universe": "TOPSP500",
                "neut": "SUBINDUSTRY",
                "category": "apex",
                "hypothesis": f"Apex Tri-Factor rank-gated threshold={thresh} with tail power={p} to eliminate concentrated weight and reach Sharpe >= 1.25",
            })

    return candidates


async def run_top3_precision_strike():
    config = OptionsConfig.from_env()
    store = OptionsStore()
    client = BrainClient(
        username=config.brain_username,
        password=config.brain_password,
        max_concurrent_sims=2,
        db=store.db,
    )

    log.info("=" * 75)
    log.info("STARTING TOP-3 ALPHA BREAKTHROUGH PRECISION STRIKE")
    log.info("Targeting: 1) BAB Sharpe 1.74 | 2) Vol Skew Sharpe 1.28 | 3) Apex Fit 1.01")
    log.info("=" * 75)

    # 1. Authenticate with BRAIN
    await asyncio.to_thread(client.authenticate)
    log.info("[+] Authenticated with WorldQuant BRAIN successfully.")

    # 2. Reference PnLs for correlation gating
    ref_alpha_ids, known_exprs = load_reference_pnls(config.database_url)
    ref_pnls: Dict[str, Dict[str, float]] = {}
    if store.db:
        try:
            ref_pnls = store.db.get_all_cached_alpha_pnls()
        except Exception as e:
            log.warning("Could not load cached PnLs: %s", e)

    missing_aids = [aid for aid in ref_alpha_ids if aid not in ref_pnls]
    for aid in missing_aids[:15]:
        pnl = await client.get_alpha_pnl(aid)
        if pnl:
            ref_pnls[aid] = pnl
            if store.db:
                store.db.save_alpha_pnl(aid, pnl)
    log.info("[+] Loaded %d reference PnLs for correlation gating.", len(ref_pnls))

    # 3. Build & Validate Candidates
    candidates = build_strike_candidates()
    log.info("[+] Generated %d high-precision candidate variations.", len(candidates))

    queue = asyncio.Queue()
    for c in candidates:
        ok, reason = validate_expression(c["expr"])
        if ok:
            queue.put_nowait(c)
        else:
            log.warning("[-] Skipping invalid expression %s: %s", c["name"], reason)

    total_candidates = queue.qsize()
    evaluated_count = 0
    qualified_count = 0

    async def worker(worker_id: int):
        nonlocal evaluated_count, qualified_count
        while not queue.empty():
            try:
                item = queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            evaluated_count += 1
            curr_num = evaluated_count
            name = item["name"]
            expr = item["expr"]
            decay = item["decay"]
            cat = item["category"]
            hyp = item["hypothesis"]
            trunc = item.get("truncation", 0.05)

            log.info("[W#%d #%d/%d] Simulating %s (%s, decay=%d, trunc=%.2f)...",
                     worker_id, curr_num, total_candidates, name, cat.upper(), decay, trunc)

            settings = SimSettings(
                region="USA",
                universe="TOPSP500",
                delay=1,
                decay=decay,
                neutralization="SUBINDUSTRY",
                truncation=trunc,
                pasteurization=True,
            )

            try:
                metrics = await client.simulate_one(expr, settings)
            except Exception as e:
                log.warning("Simulation exception for %s: %s", name, e)
                queue.task_done()
                continue

            if not metrics or not metrics.is_valid:
                log.warning("[-] Invalid metrics returned for %s", name)
                queue.task_done()
                continue

            ret_pct = getattr(metrics, "annualized_return", getattr(metrics, "returns", 0.0)) * 100
            log.info(
                "[* RESULT #%d] %s | Sharpe=%.2f | Fit=%.2f | TO=%.1f%% | Ret=%.1f%% | DD=%.1f%% | Margin=%.1fbps | AID=%s",
                curr_num, name, metrics.sharpe, metrics.fitness,
                metrics.turnover * 100, ret_pct,
                metrics.max_drawdown * 100, metrics.margin * 10000,
                metrics.alpha_id
            )

            # Strict Gate 1 Evaluation (Sharpe >= 1.25, Fitness >= 1.00, Margin >= 4 bps)
            passed_gate1 = (
                metrics.sharpe >= 1.25
                and metrics.fitness >= 1.00
                and 0.01 <= metrics.turnover <= 0.70
                and metrics.margin >= 0.0004
                and metrics.max_drawdown <= 0.35
            )

            # Log to DB
            log_candidate_evaluation(
                db_url=config.database_url,
                expr=expr,
                arch=name,
                src=f"precision_strike_{cat}",
                stage="PRECISION_STRIKE",
                status="PASS" if passed_gate1 else "FAIL",
                metrics=metrics,
            )

            if passed_gate1:
                log.info("[+ GATE 1 PASSED!] Candidate %s (%s) scored Sharpe=%.2f, Fit=%.2f!",
                         metrics.alpha_id, name, metrics.sharpe, metrics.fitness)

                # Gate 2: Correlation Gate (|rho| < 0.70)
                cand_pnl = await client.get_alpha_pnl(metrics.alpha_id)
                max_corr = 0.0
                if cand_pnl and ref_pnls:
                    corrs = [abs(compute_correlation(cand_pnl, p)) for p in list(ref_pnls.values())]
                    max_corr = max(corrs) if corrs else 0.0

                if max_corr < 0.70:
                    log.info("[+ GATE 2 PASSED!] Max correlation = %.4f (< 0.70)", max_corr)

                    # Gate 3: Platform Checklist Gate on BRAIN
                    log.info("[*] Verifying platform checklist on BRAIN for %s...", metrics.alpha_id)
                    chk_passed, chk_msg = verify_checklist_passes(client._session, metrics.alpha_id)
                    if chk_passed:
                        log.info("[*** 100% QUALIFIED & COMMITTED! ***] All 3 Gates passed for %s!", metrics.alpha_id)
                        commit_qualified_alpha(
                            db_url=config.database_url,
                            alpha_id=metrics.alpha_id,
                            expression=expr,
                            archetype=name,
                            hypothesis=hyp,
                            metrics=metrics,
                            max_corr=max_corr,
                            universe="TOPSP500",
                            neutralization="SUBINDUSTRY",
                            decay=decay,
                            category=cat,
                        )
                        if store.db and cand_pnl:
                            store.db.save_alpha_pnl(metrics.alpha_id, cand_pnl)

                        # Send Telegram Notification
                        safe_expr = html.escape(expr)
                        send_tg_message(
                            token=config.telegram_bot_token,
                            chat_id=config.telegram_chat_id,
                            html_text=(
                                f"🏆 <b>PRECISION BREAKTHROUGH QUALIFIED!</b> 🏆\n\n"
                                f"• <b>Alpha ID:</b> <code>{metrics.alpha_id}</code>\n"
                                f"• <b>Archetype:</b> {name}\n"
                                f"• <b>Category:</b> {cat.upper()}\n"
                                f"• <b>Sharpe:</b> <b>{metrics.sharpe:.2f}</b>\n"
                                f"• <b>Fitness:</b> <b>{metrics.fitness:.2f}</b>\n"
                                f"• <b>Annual Return:</b> {ret_pct:.1f}%\n"
                                f"• <b>Turnover:</b> {metrics.turnover*100:.1f}%\n"
                                f"• <b>Margin:</b> {metrics.margin*10000:.1f} bps\n"
                                f"• <b>Max Corr:</b> {max_corr:.4f} (&lt; 0.70)\n"
                                f"• <b>Checklist:</b> 100% PASS\n"
                                f"• <b>Expression:</b>\n<code>{safe_expr}</code>"
                            ),
                        )
                        qualified_count += 1
                        ref_pnls[metrics.alpha_id] = cand_pnl
                    else:
                        log.warning("[-] Gate 3 Checklist failed for %s: %s", metrics.alpha_id, chk_msg)
                else:
                    log.warning("[-] Gate 2 Correlation failed: %.4f >= 0.70", max_corr)

            queue.task_done()
            await asyncio.sleep(1.0)

    workers = [asyncio.create_task(worker(i + 1)) for i in range(2)]
    await asyncio.gather(*workers)

    log.info("=" * 75)
    log.info("PRECISION STRIKE FINISHED: Evaluated %d, Qualified %d Alphas", evaluated_count, qualified_count)
    log.info("=" * 75)


if __name__ == "__main__":
    asyncio.run(run_top3_precision_strike())
