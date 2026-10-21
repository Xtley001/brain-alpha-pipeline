#!/usr/bin/env python3
"""
Precision Breakthrough Sniper.
Directly targets the two near-miss breakthrough alphas discovered today:
1. Apex1 Tri-Factor (Sharpe 1.14, Fitness 0.96) -> tests signed_power [1.25, 1.5, 1.75, 2.0] + liquidity hurdle escalation
2. Volatility Skew Steepness (Sharpe 1.19, Fitness 0.63) -> tests conviction gating [0.30, 0.38, 0.42] + tail power

Simulates them with 2-slot concurrency, qualifies, checks correlation, and commits to DB.
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
log = logging.getLogger("precision_sniper")

from brain_options.config import OptionsConfig
from brain_options.core.client import BrainClient, SimMetrics, SimSettings
from brain_options.core.correlation import compute_correlation
from brain_options.core.validator import validate_expression
from brain_options.specialist.convex_mutator import _wrap_neutralize_with_signed_power
from brain_options.store.store import OptionsStore
from scripts.cloud_multi_miner import (
    commit_qualified_alpha,
    log_candidate_evaluation,
    send_tg_message,
    verify_checklist_passes,
    load_reference_pnls,
)


def build_precision_candidates() -> List[Dict[str, Any]]:
    seed_apex = (
        "trade_when(volume > adv20 * 0.75, group_neutralize(rank(0.45 * "
        "rank(ts_decay_linear(((call_breakeven_60 - forward_price_60) / (close + 0.001)), 8)) + "
        "0.35 * rank(ts_decay_linear(((anl4_af_eps_value - anl4_afv4_eps_mean) / (anl4_afv4_dts_spe + 0.001)), 8)) - "
        "0.20 * rank(ts_decay_linear(beta_last_60_days_spy, 8))), subindustry), -1)"
    )

    seed_skew = (
        "trade_when(abs(rank(ts_decay_linear(-ts_delta(implied_volatility_mean_skew_30, 10), 5)) - 0.5) > 0.35, "
        "group_neutralize(rank(ts_decay_linear(-ts_delta(implied_volatility_mean_skew_30, 10), 5)), subindustry), -1)"
    )

    candidates: List[Dict[str, Any]] = []

    # ── Apex Tri-Factor Power Concentration Sweeps ──
    for p in [1.25, 1.5, 1.75, 2.0]:
        wrapped = _wrap_neutralize_with_signed_power(seed_apex, p)
        if wrapped:
            for d in [6, 8, 10]:
                candidates.append({
                    "name": f"Apex1_Power{p}_d{d}",
                    "expr": wrapped,
                    "decay": d,
                    "universe": "TOPSP500",
                    "neut": "SUBINDUSTRY",
                    "category": "apex",
                    "hypothesis": f"Apex Tri-Factor Tail Power p={p} decay={d}",
                })

    # ── Apex Higher Liquidity Hurdles + Tail Power ──
    for hurdle in ["0.85", "1.0", "1.15"]:
        gated = seed_apex.replace("volume > adv20 * 0.75", f"volume > adv20 * {hurdle}")
        wrapped = _wrap_neutralize_with_signed_power(gated, 1.5)
        candidates.append({
            "name": f"Apex1_Gated{hurdle}_Power1.5_d8",
            "expr": wrapped or gated,
            "decay": 8,
            "universe": "TOPSP500",
            "neut": "SUBINDUSTRY",
            "category": "apex",
            "hypothesis": f"Apex Tri-Factor Gated hurdle={hurdle} + Power 1.5",
        })

    # ── Volatility Skew Steepness Conviction Hurdle Sweeps (Base Sharpe 1.19) ──
    for thresh in ["0.28", "0.32", "0.38", "0.42"]:
        t_expr = seed_skew.replace("> 0.35", f"> {thresh}")
        for d in [4, 5, 6, 8]:
            candidates.append({
                "name": f"SkewSteepness_t{thresh}_d{d}",
                "expr": t_expr,
                "decay": d,
                "universe": "TOPSP500",
                "neut": "SUBINDUSTRY",
                "category": "options",
                "hypothesis": f"Vol Skew Steepness conviction thresh={thresh} decay={d}",
            })

    # ── Volatility Skew Tail Power Concentration ──
    for p in [1.5, 2.0]:
        wrapped_skew = _wrap_neutralize_with_signed_power(seed_skew, p)
        if wrapped_skew:
            for d in [4, 5, 6]:
                candidates.append({
                    "name": f"SkewSteepness_Power{p}_d{d}",
                    "expr": wrapped_skew,
                    "decay": d,
                    "universe": "TOPSP500",
                    "neut": "SUBINDUSTRY",
                    "category": "options",
                    "hypothesis": f"Vol Skew Steepness Power p={p} decay={d}",
                })

    return candidates


async def run_sniper():
    config = OptionsConfig.from_env()
    store = OptionsStore()
    client = BrainClient(
        username=config.brain_username,
        password=config.brain_password,
        max_concurrent_sims=2,
        db=store.db,
    )

    log.info("=" * 70)
    log.info("LAUNCHING PRECISION BREAKTHROUGH SNIPER (Targeting 1.19 & 1.14 Seeds)")
    log.info("=" * 70)

    # 1. Authenticate with BRAIN
    await asyncio.to_thread(client.authenticate)
    log.info("[+] Authenticated with WorldQuant BRAIN.")

    # 2. Reference PnLs for correlation gate
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

    # 3. Build Candidates
    candidates = build_precision_candidates()
    log.info("[+] Built %d targeted precision candidates.", len(candidates))

    queue = asyncio.Queue()
    for c in candidates:
        ok, reason = validate_expression(c["expr"])
        if ok:
            queue.put_nowait(c)
        else:
            log.warning("[-] Skipping invalid expression %s: %s", c["name"], reason)

    total_to_sim = queue.qsize()
    sim_count = 0
    qualified_count = 0

    async def worker(worker_id: int):
        nonlocal sim_count, qualified_count
        while not queue.empty():
            try:
                item = queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            sim_count += 1
            curr_num = sim_count
            name = item["name"]
            expr = item["expr"]
            decay = item["decay"]
            cat = item["category"]
            hyp = item["hypothesis"]
            universe = item["universe"]
            neut = item["neut"]

            log.info("[W#%d Sim #%d/%d] Testing %s (decay=%d, u=%s)...",
                     worker_id, curr_num, total_to_sim, name, decay, universe)

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
            except Exception as e:
                log.warning("Simulation exception: %s", e)
                queue.task_done()
                continue

            if not metrics or not metrics.is_valid:
                log.warning("[-] Metrics invalid for %s", name)
                queue.task_done()
                continue

            log.info(
                "[* RESULT #%d] %s | Sharpe=%.2f | Fit=%.2f | TO=%.1f%% | Margin=%.1fbps | DD=%.1f%% | AID=%s",
                curr_num, name, metrics.sharpe, metrics.fitness,
                metrics.turnover * 100, metrics.margin * 10000,
                metrics.max_drawdown * 100, metrics.alpha_id
            )

            # Gate 1 Performance Check
            fit_thresh = 0.70 if cat == "options" else 0.90
            passed_gate1 = (
                metrics.sharpe >= 1.25
                and metrics.fitness >= fit_thresh
                and 0.01 <= metrics.turnover <= 0.70
                and metrics.margin >= 0.0008
                and metrics.max_drawdown <= 0.35
            )

            # Log to DB
            log_candidate_evaluation(
                db_url=config.database_url,
                expr=expr,
                arch=name,
                src=f"precision_sniper_{cat}",
                stage="PRECISION_STRIKE",
                status="PASS" if passed_gate1 else "FAIL",
                metrics=metrics,
            )

            if passed_gate1:
                log.info("[+ GATE 1 PASSED!] Candidate %s (%s) scored Sharpe=%.2f, Fit=%.2f!",
                         metrics.alpha_id, name, metrics.sharpe, metrics.fitness)

                # Gate 2: Correlation Gate
                cand_pnl = await client.get_alpha_pnl(metrics.alpha_id)
                max_corr = 0.0
                if cand_pnl and ref_pnls:
                    corrs = [abs(compute_correlation(cand_pnl, p)) for p in list(ref_pnls.values())]
                    max_corr = max(corrs) if corrs else 0.0

                if max_corr < 0.70:
                    log.info("[+ GATE 2 PASSED!] Max correlation = %.4f (< 0.70)", max_corr)

                    # Gate 3: Platform Checklist Check
                    log.info("[*] Running platform checklist verification on BRAIN...")
                    chk_passed, chk_msg = verify_checklist_passes(client._session, metrics.alpha_id)
                    if chk_passed:
                        log.info("[*** 100% QUALIFIED! ***] All 3 Gates passed for %s!", metrics.alpha_id)
                        commit_qualified_alpha(
                            db_url=config.database_url,
                            alpha_id=metrics.alpha_id,
                            expression=expr,
                            archetype=name,
                            hypothesis=hyp,
                            metrics=metrics,
                            max_corr=max_corr,
                            universe=universe,
                            neutralization=neut,
                            decay=decay,
                            category=cat,
                        )
                        if store.db and cand_pnl:
                            store.db.save_alpha_pnl(metrics.alpha_id, cand_pnl)

                        # Telegram Notification
                        safe_expr = html.escape(expr)
                        send_tg_message(
                            token=config.telegram_bot_token,
                            chat_id=config.telegram_chat_id,
                            html_text=(
                                f"🏆 <b>PRECISION BREAKTHROUGH ALPHA QUALIFIED!</b> 🏆\n\n"
                                f"• <b>Alpha ID:</b> <code>{metrics.alpha_id}</code>\n"
                                f"• <b>Strategy:</b> {name}\n"
                                f"• <b>Category:</b> {cat.upper()}\n"
                                f"• <b>Sharpe:</b> <b>{metrics.sharpe:.2f}</b>\n"
                                f"• <b>Fitness:</b> <b>{metrics.fitness:.2f}</b>\n"
                                f"• <b>Turnover:</b> {metrics.turnover*100:.1f}%\n"
                                f"• <b>Margin:</b> {metrics.margin*10000:.1f} bps\n"
                                f"• <b>Max Corr:</b> {max_corr:.4f} (&lt; 0.70)\n"
                                f"• <b>Checklist:</b> PASS\n"
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

    # Run 2 concurrent workers for high throughput
    workers = [asyncio.create_task(worker(i + 1)) for i in range(2)]
    await asyncio.gather(*workers)

    log.info("=" * 70)
    log.info("PRECISION SNIPER FINISHED: Evaluated %d, Qualified %d Alphas", sim_count, qualified_count)
    log.info("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_sniper())
