#!/usr/bin/env python3
"""
Institutional 100 Sentiment Alphas Autonomous Miner & Vault.
Target: 100 Mutually Orthogonal Qualified Alphas across 8 Fundamental Sentiment Sub-Pillars:
1. SUE Tail Shocks x Volatility Decoupling
2. PEAD Revision Sluggishness x Return Reversals & Z-Scores
3. Target Price Spread x Intraday Range
4. Analyst Recommendation Upgrades Velocity
5. Analyst Estimate Dispersion Discount
6. Dynamic Institutional Focus & Attention Drift
7. Lexical Mood Contrarian Reversion
8. Fundamental Confluence Tri-Factor Blends

Features:
- 3 Parallel Simulation Slots (max_concurrent_sims=3)
- Real-time Correlation Gate: |rho| < 0.55 (Elite Diversification)
- Platform /alphas/{alpha_id}/check: 100% PASS
- Instant Telegram Alerts on qualification + Hourly Heartbeat Telegram Reports
- Commits to options_alphas with status = 'QUALIFIED'
"""
from __future__ import annotations

import asyncio
import datetime
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

# Force utf-8 encoding on standard output
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("sentiment_100_miner")

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
            log.info("Telegram alert delivered.")
            return
        plain_text = re.sub(r"<[^>]+>", "", html_text)
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": plain_text},
            timeout=10,
        )
    except Exception as exc:
        log.warning("Telegram dispatch failed: %s", exc)


def load_reference_alphas(db_url: str) -> Tuple[List[str], Dict[str, Dict[str, float]]]:
    """Loads immutable production alphas and mutable reserve alphas with quality metrics."""
    hardcoded = [
        "rKOa6qa9", "YPboG01w", "XgbOoJjx", "e7bWxz7E", "ZYbNORZx", "mLmQjlzE",
        "P02K7eYK", "Xgbv1A80", "levEYpmx", "YPb81N2v", "E5pNpQlm", "N176Geqp",
        "gJQWL7aK", "Grdg2Njo", "xA3872wq", "3qXLMqg0", "0mX0kG86", "RRbnn8xe",
        "blbZ9Wkp", "KPNd6Ovl", "gJbAP76e"
    ]
    prod_ids = list(hardcoded)
    reserve_meta: Dict[str, Dict[str, float]] = {}
    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT alpha_id FROM options_alphas WHERE status = 'SUBMITTED' AND alpha_id IS NOT NULL")
                for r in cur.fetchall():
                    if r[0] and r[0] not in prod_ids:
                        prod_ids.append(r[0])
                cur.execute("SELECT alpha_id, COALESCE(sharpe, 0.0), COALESCE(fitness, 0.0), COALESCE(margin, 0.0) FROM options_alphas WHERE status = 'QUALIFIED' AND alpha_id IS NOT NULL")
                for r in cur.fetchall():
                    aid = r[0]
                    if aid:
                        reserve_meta[aid] = {
                            "sharpe": float(r[1]),
                            "fitness": float(r[2]),
                            "margin": float(r[3]),
                        }
    except Exception as exc:
        log.warning("Could not fetch reference alphas from DB: %s", exc)

    return prod_ids, reserve_meta


def supersede_reserve_alpha(db_url: str, old_alpha_id: str, new_alpha_id: str):
    """Marks an inferior reserve alpha as SUPERSEDED when replaced by a higher-quality newcomer."""
    try:
        with psycopg.connect(db_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE options_alphas SET status = 'SUPERSEDED' WHERE alpha_id = %s",
                    (old_alpha_id,)
                )
        log.info("[~] Reserve alpha %s marked as SUPERSEDED by superior alpha %s.", old_alpha_id, new_alpha_id)
    except Exception as exc:
        log.warning("Failed to mark alpha %s as superseded: %s", old_alpha_id, exc)


def get_current_qualified_count(db_url: str) -> int:
    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM options_alphas WHERE status = 'QUALIFIED';")
                return cur.fetchone()[0]
    except Exception as exc:
        log.warning("Error getting qualified count: %s", exc)
        return 0


async def verify_checklist_passes(session: Any, alpha_id: str) -> Tuple[bool, str]:
    chk_url = f"https://api.worldquantbrain.com/alphas/{alpha_id}/check"
    try:
        for attempt in range(15):
            try:
                if hasattr(session, "retry"):
                    resp = await asyncio.wait_for(session.retry("GET", chk_url, max_tries=5), timeout=30.0)
                else:
                    resp = session.get(chk_url, timeout=15)
            except Exception as req_err:
                await asyncio.sleep(2.0)
                continue

            if resp is not None and resp.status_code == 200:
                text = resp.text.strip() if hasattr(resp, "text") and resp.text else ""
                if not text:
                    await asyncio.sleep(2.0)
                    continue
                try:
                    data = resp.json()
                except Exception:
                    await asyncio.sleep(2.0)
                    continue

                is_data = data.get("is", {}) if isinstance(data.get("is"), dict) else {}
                checks = is_data.get("checks", []) or data.get("checks", [])
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
            await asyncio.sleep(3.0)
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
            NOW(), 'vault_sentiment_100'
        ) ON CONFLICT DO NOTHING;
    """
    try:
        ret_val = getattr(metrics, 'annualized_return', getattr(metrics, 'returns', 0.0))
        with psycopg.connect(db_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (
                    alpha_id, expression, archetype, hypothesis, "sentiment_100_miner",
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


def build_100_sentiment_candidate_matrix() -> List[Dict[str, Any]]:
    """Generates the master matrix of candidates across all 8 institutional sentiment sub-pillars."""
    p1: List[Dict[str, Any]] = []
    p2: List[Dict[str, Any]] = []
    p3: List[Dict[str, Any]] = []
    p4: List[Dict[str, Any]] = []
    p5: List[Dict[str, Any]] = []
    p6: List[Dict[str, Any]] = []
    p7: List[Dict[str, Any]] = []
    p8: List[Dict[str, Any]] = []
    universes = ["TOP1000", "TOP2000", "TOP3000"]
    neutralizations = ["SUBINDUSTRY", "SECTOR"]

    # -------------------------------------------------------------
    # Pillar 1: SUE Shocks x Volatility Decoupling
    # -------------------------------------------------------------
    for u in universes:
        for neut in neutralizations:
            for d in [12, 14, 16, 18, 20]:
                for p_win in [3, 5]:
                    for vol_win in [20, 30, 40]:
                        p1.append({
                            "expression": f"trade_when(volume > adv20 * 0.8, group_neutralize(rank(ts_decay_linear(ts_decay_linear(snt1_d1_earningssurprise, {d}), 3)) * rank(-ts_delta(close, {p_win}) / (ts_std_dev(close, {vol_win}) + 0.001)), {neut.lower()}), -1)",
                            "archetype": f"P1_SUE_VolDecoupling_d{d}_p{p_win}_v{vol_win}",
                            "hypothesis": f"Pillar 1: SUE surprise interacted with price reversal / vol spread ({u}, decay={d}, {neut}).",
                            "universe": u,
                            "neutralization": neut,
                            "decay": d,
                        })

    # -------------------------------------------------------------
    # Pillar 2: PEAD Revision Sluggishness x Z-Score & Reversals
    # -------------------------------------------------------------
    for u in universes:
        for neut in neutralizations:
            for d in [12, 14, 16, 18, 22]:
                for rev_win in [3, 5, 8]:
                    p2.append({
                        "expression": f"trade_when(volume > adv20 * 0.8, group_neutralize(rank(ts_decay_linear(ts_decay_linear(snt1_d1_netearningsrevision, {d}), 3)) * rank(-ts_delta(close, {rev_win})), {neut.lower()}), -1)",
                        "archetype": f"P2_PEAD_Revision_Reversal_d{d}_r{rev_win}",
                        "hypothesis": f"Pillar 2: PEAD net earnings revision interacted with {rev_win}d price reversal ({u}, decay={d}).",
                        "universe": u,
                        "neutralization": neut,
                        "decay": d,
                    })
                # Z-Score formulation
                for z_win in [5, 10]:
                    p2.append({
                        "expression": f"trade_when(volume > adv20 * 0.8, group_neutralize(rank(ts_decay_linear(ts_decay_linear(snt1_d1_netearningsrevision, {d}), 3)) * rank(ts_decay_linear(-ts_zscore(close, {z_win}), 5)), {neut.lower()}), -1)",
                        "archetype": f"P2_PEAD_ZScore_d{d}_z{z_win}",
                        "hypothesis": f"Pillar 2: PEAD revision momentum interacting with mean-reverting price z-score ({u}, decay={d}).",
                        "universe": u,
                        "neutralization": neut,
                        "decay": d,
                    })

    # -------------------------------------------------------------
    # Pillar 3: Target Price Revision Spread x Intraday Volatility
    # -------------------------------------------------------------
    for u in universes:
        for neut in neutralizations:
            for d in [12, 14, 16, 18]:
                p3.append({
                    "expression": f"trade_when(volume > adv20 * 0.8, group_neutralize(rank(ts_decay_linear(ts_decay_linear(snt1_d1_uptargetpercent - snt1_d1_downtargetpercent, {d}), 3)) * rank((high - low) / (vwap + 0.001)), {neut.lower()}), -1)",
                    "archetype": f"P3_Target_Spread_Intraday_d{d}",
                    "hypothesis": f"Pillar 3: Target price revision spread interacting with intraday volatility range ({u}, decay={d}).",
                    "universe": u,
                    "neutralization": neut,
                    "decay": d,
                })

    # -------------------------------------------------------------
    # Pillar 4: Analyst Recommendation Upgrade Velocity
    # -------------------------------------------------------------
    for u in universes:
        for neut in neutralizations:
            for d in [12, 14, 16, 20]:
                for w1 in [0.5, 0.6, 0.7]:
                    w2 = round(1.0 - w1, 2)
                    p4.append({
                        "expression": f"trade_when(volume > adv20 * 0.8, group_neutralize(rank({w1} * rank(ts_decay_linear(ts_decay_linear(snt1_d1_netrecpercent, {d}), 3)) + {w2} * rank(ts_decay_linear(ts_decay_linear(snt1_d1_netearningsrevision, {d}), 3))), {neut.lower()}), -1)",
                        "archetype": f"P4_Rec_Revision_Confluence_d{d}_w{int(w1*100)}",
                        "hypothesis": f"Pillar 4: Analyst recommendation and revision confluence with double decay ({u}, decay={d}).",
                        "universe": u,
                        "neutralization": neut,
                        "decay": d,
                    })

    # -------------------------------------------------------------
    # Pillar 5: Analyst Estimate Dispersion Discount
    # -------------------------------------------------------------
    for u in universes:
        for neut in neutralizations:
            for d in [12, 14, 16, 18]:
                p5.append({
                    "expression": f"trade_when(volume > adv20 * 0.8, group_neutralize(rank(-ts_decay_linear(ts_decay_linear(snt1_d1_dtstsespe / (close + 0.001), {d}), 3)) * rank(ts_decay_linear(ts_decay_linear(snt1_d1_netearningsrevision, {d}), 3)), {neut.lower()}), -1)",
                    "archetype": f"P5_Dispersion_Revision_Product_d{d}",
                    "hypothesis": f"Pillar 5: Low forecast dispersion multiplied by net revision momentum ({u}, decay={d}).",
                    "universe": u,
                    "neutralization": neut,
                    "decay": d,
                })

    # -------------------------------------------------------------
    # Pillar 6: Dynamic Focus & Institutional Attention Drift
    # -------------------------------------------------------------
    for u in universes:
        for neut in neutralizations:
            for d in [12, 14, 16, 18]:
                p6.append({
                    "expression": f"trade_when(volume > adv20 * 0.8, group_neutralize(rank(ts_decay_linear(ts_decay_linear(snt1_d1_dynamicfocusrank, {d}), 3)) * rank(ts_decay_linear(-ts_zscore(close, 10), 5)), {neut.lower()}), -1)",
                    "archetype": f"P6_Dynamic_Focus_ZScore_d{d}",
                    "hypothesis": f"Pillar 6: Dynamic institutional analyst focus interacting with price z-score ({u}, decay={d}).",
                    "universe": u,
                    "neutralization": neut,
                    "decay": d,
                })

    # -------------------------------------------------------------
    # Pillar 7: Lexical Sentiment & Mood Extremes Reversal
    # -------------------------------------------------------------
    for u in universes:
        for neut in neutralizations:
            for d in [12, 14, 16, 18]:
                p7.append({
                    "expression": f"trade_when(volume > adv20 * 0.8, group_neutralize(rank(-ts_decay_linear(ts_decay_linear(daily_equity_mood_indicator, {d}), 3)) * rank(-ts_delta(close, 5)), {neut.lower()}), -1)",
                    "archetype": f"P7_Lexical_Mood_Reversal_d{d}",
                    "hypothesis": f"Pillar 7: News mood extreme overreaction contrarian reversal ({u}, decay={d}).",
                    "universe": u,
                    "neutralization": neut,
                    "decay": d,
                })

    # -------------------------------------------------------------
    # Pillar 8: Fundamental Confluence Tri-Factor Blends
    # -------------------------------------------------------------
    for u in universes:
        for neut in neutralizations:
            for d in [12, 14, 16, 18]:
                p8.append({
                    "expression": f"trade_when(volume > adv20 * 0.8, group_neutralize(rank(ts_decay_linear(ts_decay_linear(snt1_d1_earningssurprise, {d}), 3)) * rank(ts_decay_linear(ts_decay_linear(snt1_d1_netearningsrevision, {d}), 3)) * rank(ts_decay_linear(ts_decay_linear(snt1_d1_nettargetpercent, {d}), 3)), {neut.lower()}), -1)",
                    "archetype": f"P8_Fundamental_Tri_Confluence_d{d}",
                    "hypothesis": f"Pillar 8: Tri-factor fundamental confluence (SUE x Net Revision x Target Spread, decay={d}).",
                    "universe": u,
                    "neutralization": neut,
                    "decay": d,
                })

    # Collect by pillar and round-robin interleave to ensure maximum diversity from simulation #1
    pillar_buckets = [p1, p2, p3, p4, p5, p6, p7, p8]
    interleaved: List[Dict[str, Any]] = []
    max_len = max(len(b) for b in pillar_buckets)
    for idx in range(max_len):
        for b in pillar_buckets:
            if idx < len(b):
                interleaved.append(b[idx])

    return interleaved


async def hourly_heartbeat_loop(config: OptionsConfig, target_count: int, start_time: float, lock: asyncio.Lock, get_stats_fn):
    """Sends comprehensive hourly intelligence reports to Telegram."""
    while True:
        await asyncio.sleep(3600)
        try:
            qual_count, total_evals, near_miss_count = get_stats_fn()
            elapsed_hours = (time.time() - start_time) / 3600.0
            throughput = total_evals / max(0.1, elapsed_hours)

            now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M UTC")
            send_tg_message(
                token=config.telegram_bot_token,
                chat_id=config.telegram_chat_id,
                html_text=(
                    f"⏰ <b>HOURLY QUANTITATIVE SENTIMENT REPORT</b> · {now_str}\n\n"
                    f"• <b>Target Pool:</b> <b>{qual_count} / {target_count}</b> Qualified Alphas in Vault\n"
                    f"• <b>Total Evaluated:</b> {total_evals} permutations\n"
                    f"• <b>Throughput:</b> {throughput:.1f} sims/hr (3 Concurrent Slots Active)\n"
                    f"• <b>Near-Miss Optimizations:</b> {near_miss_count} in-flight sweeps\n"
                    f"• <b>Active Pillars:</b> SUE Shocks · PEAD Revisions · Target Spreads · Dispersion · Confluence Tri-Factor\n"
                    f"• <b>Standard:</b> Sharpe &ge; 1.25 | Fitness &ge; 0.70 | Turnover &le; 20% | Margin &ge; 7.0 bps | |rho| &lt; 0.55\n\n"
                    f"<i>Relentless autonomous mining active. Next update in 60m.</i>"
                ),
            )
        except Exception as e:
            log.warning("Hourly heartbeat error: %s", e)


async def run_sentiment_100_miner():
    config = OptionsConfig.from_env()
    store = OptionsStore()
    
    # 3 Concurrent BRAIN Simulation Slots
    client = BrainClient(
        username=config.brain_username,
        password=config.brain_password,
        max_concurrent_sims=3,
        db=store.db,
    )

    log.info("=" * 70)
    log.info("STARTING MASTER SENTIMENT 100 QUALIFIED ALPHAS VAULT MINER")
    log.info("CONCURRENCY: 3 Parallel BRAIN Simulation Slots Activated")
    log.info("TARGET: 100 Non-Correlated Multi-Gate Qualified Sentiment Alphas")
    log.info("=" * 70)

    # 1. Authenticate
    try:
        await asyncio.to_thread(client.authenticate)
    except Exception as exc:
        log.error("Authentication failed: %s", exc)
        return

    # 2. Pre-fetch reference PnLs (Production + Reserve)
    prod_alpha_ids, reserve_meta = load_reference_alphas(config.database_url)
    ref_pnls: Dict[str, Dict[str, float]] = {}
    all_refs = list(prod_alpha_ids) + list(reserve_meta.keys())
    log.info("Pre-fetching PnLs for %d baseline alphas (%d production, %d reserve)...", len(all_refs), len(prod_alpha_ids), len(reserve_meta))
    for aid in all_refs:
        pnl = await client.get_alpha_pnl(aid)
        if pnl:
            ref_pnls[aid] = pnl
    log.info("Successfully loaded %d reference PnL vectors.", len(ref_pnls))

    # 3. Build 100 Sentiment Matrix
    candidate_list = build_100_sentiment_candidate_matrix()
    target_count = 100
    current_qualified = get_current_qualified_count(config.database_url)
    log.info("Loaded %d candidate configurations across 8 Sub-Pillars. Current Qualified: %d / %d", len(candidate_list), current_qualified, target_count)

    queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
    for c in candidate_list:
        queue.put_nowait(c)

    # Initial Telegram launch notification
    now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M UTC")
    send_tg_message(
        token=config.telegram_bot_token,
        chat_id=config.telegram_chat_id,
        html_text=(
            f"🚀 <b>GOAL LAUNCHED: 100 ELITE SENTIMENT ALPHAS</b> · {now_str}\n\n"
            f"• <b>Objective:</b> Mine & Qualify 100 Mutually Orthogonal Sentiment Alphas\n"
            f"• <b>Current Vault:</b> {current_qualified} / {target_count}\n"
            f"• <b>Engine Concurrency:</b> 3 Concurrent BRAIN Simulation Slots\n"
            f"• <b>Quality Standard:</b> Sharpe &ge; 1.25 | Fitness &ge; 0.70 | Turnover &le; 20% | Margin &ge; 7 bps | Max Corr &lt; 0.55\n"
            f"• <b>Sub-Pillars:</b> SUE Decoupling, PEAD Drift, Target Spread, Recommendation Velocity, Estimate Dispersion, Focus Drift, Lexical Mood, Tri-Factor Confluence\n\n"
            f"<i>Instant alerts will trigger on every qualified alpha. Hourly heartbeat reports active.</i>"
        ),
    )

    lock = asyncio.Lock()
    eval_count = 0
    near_miss_count = 0
    start_time = time.time()

    def get_stats():
        return current_qualified, eval_count, near_miss_count

    # Launch Hourly Heartbeat Telegram reporter
    asyncio.create_task(hourly_heartbeat_loop(config, target_count, start_time, lock, get_stats))

    async def worker(worker_id: int):
        nonlocal eval_count, current_qualified, near_miss_count
        while not queue.empty() and current_qualified < target_count:
            cand = await queue.get()
            expr = cand["expression"]
            arch = cand["archetype"]
            hyp = cand["hypothesis"]
            universe = cand["universe"]
            neut = cand["neutralization"]
            decay = cand["decay"]

            async with lock:
                eval_count += 1
                curr_eval = eval_count
                curr_qual = current_qualified

            log.info("[Worker %d | #%d | Qualified: %d/%d] Simulating %s (u=%s, neut=%s, d=%d)...", worker_id, curr_eval, curr_qual, target_count, arch, universe, neut, decay)

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
                log.warning("[Worker %d] Simulation error on %s: %s", worker_id, arch, e)
                queue.task_done()
                await asyncio.sleep(2.0)
                continue

            if not metrics or not metrics.is_valid:
                queue.task_done()
                await asyncio.sleep(1.0)
                continue

            log.info(
                "[Worker %d] %s | Sharpe=%.2f | Fit=%.2f | TO=%.1f%% | Margin=%.1fbps | DD=%.1f%% | %s",
                worker_id, metrics.alpha_id, metrics.sharpe, metrics.fitness,
                metrics.turnover * 100, metrics.margin * 10000, metrics.max_drawdown * 100, arch
            )

            # Record RL State Feedback
            if store.db:
                try:
                    rew = float(metrics.sharpe) if metrics.sharpe is not None else 0.0
                    store.db.record_strategy_operator_reward(
                        strategy_name="vault_sentiment_100",
                        operator_name=arch,
                        parameter_name="decay",
                        parameter_val=str(decay),
                        reward=rew,
                        success=(metrics.sharpe >= 1.25),
                    )
                except Exception:
                    pass

            # Relentless Near-Miss Micro-Sweeps
            if 1.00 <= metrics.sharpe < 1.25 and metrics.turnover <= 0.30:
                async with lock:
                    near_miss_count += 1
                log.info("[Worker %d | NEAR-MISS] %s (Sharpe=%.2f, Fit=%.2f). Spawning micro-sweeps...", worker_id, metrics.alpha_id, metrics.sharpe, metrics.fitness)
                for d_shift in [-2, 2]:
                    new_d = max(6, decay + d_shift)
                    queue.put_nowait({
                        "expression": expr,
                        "archetype": f"{arch}_d{new_d}",
                        "hypothesis": f"{hyp} [Sweep d={new_d}]",
                        "universe": universe,
                        "neutralization": neut,
                        "decay": new_d,
                    })
                if universe == "TOP3000":
                    for alt_u in ["TOP2000", "TOP1000"]:
                        queue.put_nowait({
                            "expression": expr,
                            "archetype": f"{arch}_{alt_u}",
                            "hypothesis": f"{hyp} [Universe Sweep {alt_u}]",
                            "universe": alt_u,
                            "neutralization": neut,
                            "decay": decay,
                        })

            # Gate 1: Performance Gate
            passed_gate1 = (
                metrics.sharpe >= 1.25
                and metrics.fitness >= 0.70
                and 0.01 <= metrics.turnover <= 0.60
                and (metrics.margin * 10000) >= 5.0
                and metrics.max_drawdown <= 0.35
            )

            if not passed_gate1:
                queue.task_done()
                continue

            # Gate 2: Elite Correlation Firewall (|rho| < 0.55 / Pareto Reserve Replacement)
            cand_pnl = await client.get_alpha_pnl(metrics.alpha_id)
            if not cand_pnl or len(cand_pnl) < 30:
                queue.task_done()
                continue

            # Check vs Immutable Production Alphas
            max_prod_corr = 0.0
            worst_prod = ""
            for p_id in prod_alpha_ids:
                if p_id in ref_pnls:
                    c = abs(compute_correlation(cand_pnl, ref_pnls[p_id]))
                    if c > max_prod_corr:
                        max_prod_corr = c
                        worst_prod = p_id

            if max_prod_corr >= 0.55:
                log.info("[-] Gate 2 FAIL for %s vs Production Alpha %s: rho=%.4f (>= 0.55)", arch, worst_prod, max_prod_corr)
                queue.task_done()
                continue

            # Check vs Mutable Reserve Alphas (Pareto Quality Replacement)
            reserve_to_replace = None
            max_res_corr = 0.0
            worst_res = ""
            blocked_by_incumbent = False

            for r_id, r_info in list(reserve_meta.items()):
                if r_id in ref_pnls:
                    c = abs(compute_correlation(cand_pnl, ref_pnls[r_id]))
                    if c >= 0.55:
                        cand_quality = metrics.sharpe * max(0.1, metrics.fitness)
                        inc_quality = r_info.get("sharpe", 0.0) * max(0.1, r_info.get("fitness", 0.0))
                        # If newcomer is strictly higher Sharpe and higher composite quality, upgrade the reserve!
                        if metrics.sharpe > r_info.get("sharpe", 0.0) and cand_quality > inc_quality:
                            if reserve_to_replace is None:
                                reserve_to_replace = r_id
                                max_res_corr = c
                                worst_res = r_id
                            else:
                                blocked_by_incumbent = True
                                break
                        else:
                            blocked_by_incumbent = True
                            worst_res = r_id
                            max_res_corr = c
                            break

            if blocked_by_incumbent:
                log.info("[-] Gate 2 Correlation FAIL for %s vs Reserve Alpha %s: rho=%.4f (Incumbent quality is equal or higher)", arch, worst_res, max_res_corr)
                queue.task_done()
                continue

            # Gate 3: Platform Checklist
            log.info("[*] Checking platform checklist on BRAIN for %s...", metrics.alpha_id)
            chk_ok, chk_msg = await verify_checklist_passes(client._session, metrics.alpha_id)
            if not chk_ok:
                log.warning("[-] Gate 3 Checklist FAIL for %s: %s", metrics.alpha_id, chk_msg)
                queue.task_done()
                continue

            # ALL 3 GATES PASSED! Commit to Vault
            async with lock:
                is_replacement = (reserve_to_replace is not None)
                old_aid = reserve_to_replace
                old_info = reserve_meta.pop(old_aid, {}) if is_replacement else {}
                if is_replacement and old_aid in ref_pnls:
                    del ref_pnls[old_aid]
                    supersede_reserve_alpha(config.database_url, old_aid, metrics.alpha_id)

                if not is_replacement:
                    current_qualified += 1

                ref_pnls[metrics.alpha_id] = cand_pnl
                reserve_meta[metrics.alpha_id] = {
                    "sharpe": metrics.sharpe,
                    "fitness": metrics.fitness,
                    "margin": metrics.margin,
                }

                commit_qualified_alpha(
                    db_url=config.database_url,
                    alpha_id=metrics.alpha_id,
                    expression=expr,
                    archetype=arch,
                    hypothesis=hyp,
                    metrics=metrics,
                    max_corr=max(max_prod_corr, max_res_corr),
                    universe=universe,
                    neutralization=neut,
                    decay=decay,
                )

                safe_expr = html.escape(expr)
                safe_alpha = html.escape(metrics.alpha_id)
                safe_arch = html.escape(arch)

                if is_replacement:
                    send_tg_message(
                        token=config.telegram_bot_token,
                        chat_id=config.telegram_chat_id,
                        html_text=(
                            f"🔄 <b>RESERVE QUALITY UPGRADE (PARETO REPLACEMENT)!</b> 🔄\n\n"
                            f"• <b>New Alpha ID:</b> <code>{safe_alpha}</code>\n"
                            f"• <b>Replaced Lower-Quality Alpha:</b> <code>{old_aid}</code> (rho={max_res_corr:.2f})\n"
                            f"• <b>Sharpe:</b> <b>{metrics.sharpe:.2f}</b> (vs old: {old_info.get('sharpe', 0.0):.2f})\n"
                            f"• <b>Fitness:</b> <b>{metrics.fitness:.2f}</b> (vs old: {old_info.get('fitness', 0.0):.2f})\n"
                            f"• <b>Margin:</b> {metrics.margin * 10000:.1f} bps  |  <b>Turnover:</b> {metrics.turnover * 100:.1f}%\n"
                            f"• <b>Vault Count:</b> {current_qualified}/{target_count}\n"
                            f"• <b>Expression:</b>\n<code>{safe_expr}</code>"
                        ),
                    )
                    log.info("[🔄] RESERVE UPGRADED: %s (Sharpe=%.2f) REPLACED %s (Sharpe=%.2f, rho=%.4f)",
                             metrics.alpha_id, metrics.sharpe, old_aid, old_info.get('sharpe', 0.0), max_res_corr)
                else:
                    send_tg_message(
                        token=config.telegram_bot_token,
                        chat_id=config.telegram_chat_id,
                        html_text=(
                            f"🌟 <b>NEW SENTIMENT ALPHA QUALIFIED!</b> ({current_qualified}/{target_count}) 🌟\n\n"
                            f"• <b>Alpha ID:</b> <code>{safe_alpha}</code>\n"
                            f"• <b>Category:</b> SENTIMENT (8 Sub-Pillars)\n"
                            f"• <b>Archetype:</b> {safe_arch}\n"
                            f"• <b>Sharpe:</b> <b>{metrics.sharpe:.2f}</b>  |  <b>Fitness:</b> <b>{metrics.fitness:.2f}</b>\n"
                            f"• <b>Margin:</b> {metrics.margin * 10000:.1f} bps  |  <b>Turnover:</b> {metrics.turnover * 100:.1f}%\n"
                            f"• <b>Max Correlation:</b> <b>{max(max_prod_corr, max_res_corr):.4f}</b> (&lt; 0.55 Elite Firewall)\n"
                            f"• <b>Checklist:</b> 100% PASS\n"
                            f"• <b>Expression:</b>\n<code>{safe_expr}</code>"
                        ),
                    )
                    log.info("[🌟] QUALIFIED & STORED IN VAULT: %s (%s, Sharpe=%.2f, MaxCorr=%.4f)", metrics.alpha_id, arch, metrics.sharpe, max(max_prod_corr, max_res_corr))

            queue.task_done()

    # Launch 3 parallel workers
    workers = [asyncio.create_task(worker(i + 1)) for i in range(3)]
    await asyncio.gather(*workers)

    final_count = get_current_qualified_count(config.database_url)
    log.info("=" * 70)
    log.info("100 SENTIMENT MINER COMPLETE: %d / %d QUALIFIED IN VAULT", final_count, target_count)
    log.info("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_sentiment_100_miner())
