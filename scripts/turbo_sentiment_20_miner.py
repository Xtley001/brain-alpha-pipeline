#!/usr/bin/env python3
"""
Turbo Sentiment 20 Alphas Qualifier (3 Concurrent Simulation Slots).
Exclusively focuses on institutional Sentiment & PEAD factor interactions:
- Standardized Unexpected Earnings (SUE) Tail Shocks x Volatility Decoupling
- Post-Earnings Announcement Drift (PEAD) Net Revisions x Short-term Price Reversal
- Analyst Recommendation & Target Price Upgrades Confluence
- Dynamic Focus & Media Buzz Reversals

Relentless Multi-Slot Feedback:
- 3 Parallel Simulation Slots (max_concurrent_sims=3)
- Relentless Near-Miss Optimization: Automatically sweeps decay (8..20), universe (TOP2000/TOP1000), and reversal windows
- Real-time Correlation Gate: |rho| < 0.70 vs all 21 production alphas & mutually in reserve
- Platform Checklist Verification: 100% PASS on /alphas/{alpha_id}/check
- Commits to options_alphas with status = 'QUALIFIED'
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
log = logging.getLogger("turbo_sentiment_miner")

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
                    alpha_id, expression, archetype, hypothesis, "turbo_sentiment_miner",
                    decimal.Decimal(str(round(metrics.sharpe, 4))),
                    decimal.Decimal(str(round(metrics.fitness, 4))),
                    decimal.Decimal(str(round(metrics.turnover, 4))),
                    decimal.Decimal(str(round(ret_val, 4))),
                    decimal.Decimal(str(round(metrics.max_drawdown, 4))),
                    decimal.Decimal(str(round(metrics.margin, 4))),
                    decimal.Decimal(str(round(max_corr, 4))),
                    universe, neutralization, decay,
                ))
        log.info("[+] Successfully committed %s to options_alphas as QUALIFIED.", alpha_id)
    except Exception as e:
        log.error("Failed to commit qualified alpha %s: %s", alpha_id, e)


def build_priority_sentiment_matrix() -> List[Dict[str, Any]]:
    """Builds priority candidate matrix prioritizing TOP2000 and TOP1000 for high margin and fitness."""
    candidates = []
    # TOP2000 and TOP1000 have superior liquidity and margin execution (>8 bps)
    universes = ["TOP2000", "TOP1000", "TOP3000"]
    neutralizations = ["SUBINDUSTRY", "SECTOR"]

    # 1. SUE Shock x Volatility Decoupling (Proven high-Sharpe candidate)
    for u in universes:
        for neut in neutralizations:
            for d in [10, 12, 14, 16, 18, 20]:
                for p_win in [3, 5]:
                    for vol_win in [20, 30, 40]:
                        candidates.append({
                            "expression": f"trade_when(volume > adv20 * 0.8, group_neutralize(rank(ts_decay_linear(ts_decay_linear(snt1_d1_earningssurprise, {d}), 3)) * rank(-ts_delta(close, {p_win}) / (ts_std_dev(close, {vol_win}) + 0.001)), {neut.lower()}), -1)",
                            "archetype": f"SUE_VolDecoupling_d{d}_p{p_win}_v{vol_win}",
                            "hypothesis": f"SUE shock interacted with {p_win}d reversal / {vol_win}d vol spread ({u}, decay={d}, {neut}).",
                            "universe": u,
                            "neutralization": neut,
                            "decay": d,
                        })

    # 2. PEAD Revision Sluggishness x Return Reversal
    for u in universes:
        for neut in neutralizations:
            for d in [10, 12, 14, 16, 18, 22]:
                for rev_win in [3, 5, 8]:
                    candidates.append({
                        "expression": f"trade_when(volume > adv20 * 0.8, group_neutralize(rank(ts_decay_linear(ts_decay_linear(snt1_d1_netearningsrevision, {d}), 3)) * rank(-ts_delta(close, {rev_win})), {neut.lower()}), -1)",
                        "archetype": f"PEAD_Revision_Reversal_d{d}_r{rev_win}",
                        "hypothesis": f"Net earnings revisions with double decay ({d}d, 3d) interacting with {rev_win}d price reversal.",
                        "universe": u,
                        "neutralization": neut,
                        "decay": d,
                    })

    # 3. Target Price Spread x Intraday Price Range
    for u in universes:
        for neut in neutralizations:
            for d in [12, 14, 16, 18]:
                candidates.append({
                    "expression": f"trade_when(volume > adv20 * 0.8, group_neutralize(rank(ts_decay_linear(ts_decay_linear(snt1_d1_uptargetpercent - snt1_d1_downtargetpercent, {d}), 3)) * rank((high - low) / (vwap + 0.001)), {neut.lower()}), -1)",
                    "archetype": f"Target_Spread_Intraday_d{d}",
                    "hypothesis": f"Target price revision spread interacting with intraday volatility range ({u}, decay={d}).",
                    "universe": u,
                    "neutralization": neut,
                    "decay": d,
                })

    # 4. Multi-Factor Recommendation & Revision Alignment
    for u in universes:
        for neut in neutralizations:
            for d in [12, 14, 16, 20]:
                for w1 in [0.5, 0.6, 0.7]:
                    w2 = round(1.0 - w1, 2)
                    candidates.append({
                        "expression": f"trade_when(volume > adv20 * 0.8, group_neutralize(rank({w1} * rank(ts_decay_linear(ts_decay_linear(snt1_d1_netrecpercent, {d}), 3)) + {w2} * rank(ts_decay_linear(ts_decay_linear(snt1_d1_netearningsrevision, {d}), 3))), {neut.lower()}), -1)",
                        "archetype": f"Rec_Revision_Confluence_d{d}_w{int(w1*100)}",
                        "hypothesis": f"Analyst recommendation and revision confluence with double decay ({u}, decay={d}).",
                        "universe": u,
                        "neutralization": neut,
                        "decay": d,
                    })

    # 5. Pure Fundamental Confluence (SUE Surprise x Net Revision Consensus)
    for u in universes:
        for neut in neutralizations:
            for d in [12, 14, 16, 18]:
                candidates.append({
                    "expression": f"trade_when(volume > adv20 * 0.8, group_neutralize(rank(ts_decay_linear(ts_decay_linear(snt1_d1_earningssurprise, {d}), 3)) * rank(ts_decay_linear(ts_decay_linear(snt1_d1_netearningsrevision, {d}), 3)), {neut.lower()}), -1)",
                    "archetype": f"SUE_PEAD_Fundamental_Confluence_d{d}",
                    "hypothesis": f"Multiplicative cross-sectional ranking of earnings surprise and net revision momentum ({u}, decay={d}).",
                    "universe": u,
                    "neutralization": neut,
                    "decay": d,
                })

    # 6. SUE Surprise x Price Z-Score Mean Reversion
    for u in universes:
        for neut in neutralizations:
            for d in [12, 14, 16, 18]:
                for z_win in [5, 10]:
                    candidates.append({
                        "expression": f"trade_when(volume > adv20 * 0.8, group_neutralize(rank(ts_decay_linear(ts_decay_linear(snt1_d1_earningssurprise, {d}), 3)) * rank(ts_decay_linear(-ts_zscore(close, {z_win}), 5)), {neut.lower()}), -1)",
                        "archetype": f"SUE_ZScore_Reversal_d{d}_z{z_win}",
                        "hypothesis": f"Earnings surprise shock interacting with mean-reverting price z-score ({u}, decay={d}).",
                        "universe": u,
                        "neutralization": neut,
                        "decay": d,
                    })

    return candidates


async def run_turbo_miner():
    config = OptionsConfig.from_env()
    store = OptionsStore()
    
    # Enable 3 Concurrent Simulation Slots
    client = BrainClient(
        username=config.brain_username,
        password=config.brain_password,
        max_concurrent_sims=3,
        db=store.db,
    )

    log.info("=" * 70)
    log.info("STARTING TURBO SENTIMENT 20 QUALIFIED ALPHAS MINER")
    log.info("CONCURRENCY: 3 Parallel BRAIN Simulation Slots Activated")
    log.info("TARGET: 20 Non-Correlated Multi-Gate Qualified Alphas")
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
    log.info("Successfully loaded %d reference PnL vectors.", len(ref_pnls))

    # 3. Setup Candidates Queue & Concurrency Pool
    candidate_list = build_priority_sentiment_matrix()
    target_count = 20
    current_qualified = get_current_qualified_count(config.database_url)
    log.info("Loaded %d candidate configurations. Current Qualified: %d / %d", len(candidate_list), current_qualified, target_count)

    queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
    for c in candidate_list:
        queue.put_nowait(c)

    seen_expressions: Set[str] = {c["expression"] for c in candidate_list}
    lock = asyncio.Lock()
    eval_count = 0

    async def worker(worker_id: int):
        nonlocal eval_count, current_qualified
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
                        strategy_name="vault_sentiment",
                        operator_name=arch,
                        parameter_name="decay",
                        parameter_val=str(decay),
                        reward=rew,
                        success=(metrics.sharpe >= 1.25),
                    )
                except Exception:
                    pass

            # Near-Miss Relentless Closed-Loop Feedback
            if 1.00 <= metrics.sharpe < 1.25 and metrics.turnover <= 0.35:
                log.info("[Worker %d | NEAR-MISS] %s (Sharpe=%.2f, Fit=%.2f). Spawning micro-sweeps...", worker_id, metrics.alpha_id, metrics.sharpe, metrics.fitness)
                # Sweep adjacent decays
                for d_shift in [-2, 2]:
                    new_d = max(6, decay + d_shift)
                    mut_cand = {
                        "expression": expr,
                        "archetype": f"{arch}_d{new_d}",
                        "hypothesis": f"{hyp} [Sweep d={new_d}]",
                        "universe": universe,
                        "neutralization": neut,
                        "decay": new_d,
                    }
                    queue.put_nowait(mut_cand)
                # If on TOP3000, immediately test TOP2000 and TOP1000 for higher margin!
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

            # Gate 2: Correlation Firewall
            cand_pnl = await client.get_alpha_pnl(metrics.alpha_id)
            if not cand_pnl or len(cand_pnl) < 30:
                queue.task_done()
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
                queue.task_done()
                continue

            # Gate 3: Platform Checklist
            log.info("[*] Checking platform checklist on BRAIN for %s...", metrics.alpha_id)
            chk_ok, chk_msg = verify_checklist_passes(client._session, metrics.alpha_id)
            if not chk_ok:
                log.warning("[-] Gate 3 Checklist FAIL for %s: %s", metrics.alpha_id, chk_msg)
                queue.task_done()
                continue

            # ALL 3 GATES PASSED! Commit to Vault
            async with lock:
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

            queue.task_done()

    # Launch 3 parallel workers
    workers = [asyncio.create_task(worker(i + 1)) for i in range(3)]
    await asyncio.gather(*workers)

    final_count = get_current_qualified_count(config.database_url)
    log.info("=" * 70)
    log.info("TURBO SENTIMENT MINER COMPLETE: %d / 20 QUALIFIED IN VAULT", final_count)
    log.info("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_turbo_miner())
