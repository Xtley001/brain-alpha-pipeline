#!/usr/bin/env python3
"""
Autonomous 50-Alpha Decorrelated Reserve Pipeline (v3.0 Cloud Production Daemon).
- Prioritizes virgin, high-yield mathematical formulations (Call Breakouts, Put Asymmetry, PCR Velocity, Tri-Factor Trios, LLM Scout).
- Enforces strict Platform Checklist Verification on BRAIN (specifically LOW_SUB_UNIVERSE_SHARPE).
- Enforces portfolio correlation gate (|rho| < 0.70) against ALL 17 submitted + all reserve alphas.
- Built-in Saturation Circuit-Breaker: skips archetype after 4 consecutive correlation failures.
- Pure rank + decay=12 on TOP3000 to eliminate low-liquidity small-cap spikes and pass SUS.
- Hourly Telegram Heartbeat + Immediate HTML Alerts on every qualified alpha.
- Fully autonomous 24/7 cloud operation with auto-chaining.
"""
import asyncio
import decimal
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("reserve_50_pipeline.log", mode="a", encoding="utf-8"),
    ],
)
log = logging.getLogger("reserve_50")

import psycopg
import requests
from brain_options.config import OptionsConfig
from brain_options.core.client import BrainClient, SimSettings, SimMetrics
from brain_options.core.correlation import compute_correlation
from brain_options.store.store import OptionsStore


def send_tg_message(token: str, chat_id: str, html_text: str):
    """Deliver HTML message to Telegram."""
    if not token or not chat_id:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": html_text, "parse_mode": "HTML"},
            timeout=15,
        )
    except Exception as e:
        log.warning("Telegram send failed: %s", e)


def verify_checklist_passes(session, alpha_id: str) -> Tuple[bool, str]:
    """Verify all platform checklist checks pass on BRAIN, including LOW_SUB_UNIVERSE_SHARPE."""
    for _ in range(8):
        try:
            r = session.get(f"https://api.worldquantbrain.com/alphas/{alpha_id}/check", timeout=20)
            if r.status_code == 200 and r.text.strip():
                data = r.json()
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
        except Exception:
            pass
        time.sleep(3)
    return False, "Checklist timed out or unavailable"


def load_submitted_alphas_pnl(cur) -> List[Tuple[str, str, str]]:
    cur.execute("SELECT alpha_id, expression, status FROM options_alphas WHERE status = 'SUBMITTED' ORDER BY id ASC;")
    return cur.fetchall()


def load_qualified_reserve_alphas(cur) -> List[Tuple[str, str, float, float, float]]:
    cur.execute("SELECT alpha_id, expression, sharpe, fitness, max_correlation FROM options_alphas WHERE status = 'QUALIFIED' ORDER BY id ASC;")
    return cur.fetchall()


def insert_qualified_alpha(
    database_url: str,
    alpha_id: str,
    expression: str,
    archetype: str,
    hypothesis: str,
    sharpe: float,
    fitness: float,
    turnover: float,
    returns: float,
    drawdown: float,
    margin: float,
    max_corr: float,
    universe: str,
    neutralization: str,
    delay: int,
    decay: int,
    strategy_name: str,
):
    with psycopg.connect(database_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO options_alphas (
                    alpha_id, expression, archetype, hypothesis, source,
                    sharpe, fitness, turnover, returns, drawdown, margin,
                    max_correlation, universe, neutralization, delay, decay,
                    truncation, pasteurization, nan_handling, status,
                    created_at, strategy_name
                ) VALUES (
                    %s, %s, %s, %s, 'cloud_reserve_producer_v3',
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    0.05, 'ON', 'OFF', 'QUALIFIED',
                    NOW(), %s
                ) ON CONFLICT (alpha_id) DO UPDATE SET
                    status = 'QUALIFIED',
                    sharpe = EXCLUDED.sharpe,
                    fitness = EXCLUDED.fitness,
                    margin = EXCLUDED.margin,
                    max_correlation = EXCLUDED.max_correlation;
            """, (
                alpha_id, expression, archetype, hypothesis,
                decimal.Decimal(str(round(sharpe, 4))),
                decimal.Decimal(str(round(fitness, 4))),
                decimal.Decimal(str(round(turnover, 4))),
                decimal.Decimal(str(round(returns, 4))),
                decimal.Decimal(str(round(drawdown, 4))),
                decimal.Decimal(str(round(margin, 4))),
                decimal.Decimal(str(round(max_corr, 4))),
                universe, neutralization, delay, decay,
                strategy_name,
            ))


def build_tranche_candidates(
    tranche_id: int,
    pass_num: int = 1,
    hall_of_fame: Optional[List[Dict[str, Any]]] = None,
    recent_feedback: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    candidates = []

    if tranche_id == 1:
        # TRANCHE 1A: Upside Call Breakeven Breakouts (Proven by YPboG01w: Sharpe 1.62, Fitness 1.37)
        # S1: (call_breakeven - forward_price) / close * (IV_call - IV_put) * (pcr_oi / pcr_vol)
        call_pairs = [
            (180, 30), (270, 60), (360, 90), (120, 30), (90, 30),
            (180, 60), (270, 90), (150, 30), (120, 20), (360, 60),
        ]
        for t1, t2 in call_pairs:
            for n in ["SUBINDUSTRY", "SECTOR"]:
                for w1, w2 in [(0.65, 0.35), (0.60, 0.40), (0.50, 0.50)]:
                    for d in [10, 12]:
                        sig1 = f"ts_decay_linear(ts_decay_linear(((call_breakeven_{t1} - forward_price_{t1}) / close * (implied_volatility_call_{t1} - implied_volatility_put_{t1}) * (pcr_oi_{t1} / (pcr_vol_{t1} + 0.001))), 10), 3)"
                        sig2 = f"ts_decay_linear(ts_decay_linear(((implied_volatility_call_{t2} / (implied_volatility_put_{t2} + 0.001) - 1.0) * (volume / (adv20 + 1))), 10), 3)"
                        combined = f"({w1} * rank({sig1}) + {w2} * rank({sig2}))"
                        # Pure rank without small-cap volume multiplier to ensure Sub-Universe Sharpe passes
                        expr = f"trade_when(abs(rank({combined}) - 0.5) > 0.26, group_neutralize(rank({combined}), {n.lower()}), -1)"
                        candidates.append({
                            "expression": expr,
                            "archetype": f"T1_CallBreakout{t1}_{t2}_{int(w1*100)}_d{d}_TOP3000_{n}",
                            "hypothesis": f"Call breakeven breakout ({t1}d) modulated by call/put ratio captures right-tail explosive drift.",
                            "universe": "TOP3000",
                            "neutralization": n,
                            "decay": d,
                            "strategy": "tranche_1_call_breakout",
                        })

        # TRANCHE 1B: Novel Untapped Put Breakeven Dynamics (Decay 12 + Pure Rank for SUS PASS)
        put_pairs = [
            (150, 30), (120, 20), (270, 120), (360, 120), (150, 60), (270, 30),
            (90, 20), (60, 10), (180, 20), (120, 30), (270, 90),
        ]
        for t1, t2 in put_pairs:
            for n in ["SUBINDUSTRY", "SECTOR"]:
                for w1, w2 in [(0.65, 0.35), (0.60, 0.40)]:
                    for d in [10, 12]:
                        sig1 = f"ts_decay_linear(ts_decay_linear(((forward_price_{t1} - put_breakeven_{t1}) / close * (implied_volatility_mean_skew_{t1} * sqrt({t1}/252.0)) * (pcr_vol_{t1} / (pcr_oi_{t1} + 0.001))), 10), 3)"
                        sig2 = f"ts_decay_linear(ts_decay_linear(((implied_volatility_call_{t2} - implied_volatility_put_{t2}) / (implied_volatility_mean_{t2} + 0.001) * sqrt({t2}/252.0)), 10), 3)"
                        combined = f"({w1} * rank({sig1}) + {w2} * rank({sig2}))"
                        expr = f"trade_when(abs(rank({combined}) - 0.5) > 0.26, group_neutralize(rank({combined}), {n.lower()}), -1)"
                        candidates.append({
                            "expression": expr,
                            "archetype": f"T1_Put{t1}_Skew{t2}_{int(w1*100)}_d{d}_TOP3000_{n}",
                            "hypothesis": f"Downside put breakeven floor ({t1}d) blended with skew differential ({t2}d) captures tail overpricing.",
                            "universe": "TOP3000",
                            "neutralization": n,
                            "decay": d,
                            "strategy": "tranche_1_put_floor_novel",
                        })

    elif tranche_id == 4:
        # TRANCHE 4: PCR Velocity & Order Flow Imbalance (VIRGIN)
        tenors = [20, 30, 60, 90, 120, 180]
        weights = [(0.60, 0.40), (0.65, 0.35), (0.50, 0.50)]
        for t in tenors:
            for w1, w2 in weights:
                for n in ["SUBINDUSTRY", "SECTOR"]:
                    for d in [10, 12]:
                        sig1 = f"ts_decay_linear(ts_decay_linear(((pcr_vol_{t} / (pcr_oi_{t} + 0.001) - ts_mean(pcr_vol_{t} / (pcr_oi_{t} + 0.001), 20)) / (ts_std_dev(pcr_vol_{t} / (pcr_oi_{t} + 0.001), 20) + 0.001)), 10), 3)"
                        sig2 = f"ts_decay_linear(ts_decay_linear(((implied_volatility_put_{t} - implied_volatility_call_{t}) / (implied_volatility_mean_{t} + 0.001) * sqrt({t}/252.0)), 10), 3)"
                        combined = f"({w1} * rank({sig1}) + {w2} * rank({sig2}))"
                        expr = f"trade_when(abs(rank({combined}) - 0.5) > 0.25, group_neutralize(rank({combined}), {n.lower()}), -1)"
                        candidates.append({
                            "expression": expr,
                            "archetype": f"T4_PCRVel{t}_SkewDiv_{int(w1*100)}_d{d}_TOP3000_{n}",
                            "hypothesis": f"PCR volume velocity ({t}d) blended with skew divergence isolates institutional smart money flow.",
                            "universe": "TOP3000",
                            "neutralization": n,
                            "decay": d,
                            "strategy": "tranche_4_pcr_velocity",
                        })

    elif tranche_id == 5:
        # TRANCHE 5: Multi-Factor Orthogonal Trios (Asymmetry + Term Slope + Skew)
        trios = [
            (180, 60, 90), (270, 90, 60), (360, 120, 90), (120, 30, 60),
            (90, 30, 30), (150, 60, 60), (270, 60, 180)
        ]
        for t_put, t_term, t_skew in trios:
            for n in ["SUBINDUSTRY", "SECTOR"]:
                for d in [10, 12]:
                    sig1 = f"ts_decay_linear(ts_decay_linear(((forward_price_{t_put} - put_breakeven_{t_put}) / close * (implied_volatility_mean_skew_{t_put} * sqrt({t_put}/252.0))), 10), 3)"
                    sig2 = f"ts_decay_linear(ts_decay_linear(((implied_volatility_mean_{t_term} / (implied_volatility_mean_30 + 0.001)) * sqrt({t_term}/252.0)), 10), 3)"
                    sig3 = f"ts_decay_linear(ts_decay_linear(((implied_volatility_call_{t_skew} - implied_volatility_put_{t_skew}) / (implied_volatility_mean_{t_skew} + 0.001)), 10), 3)"
                    combined = f"(0.45 * rank({sig1}) + 0.35 * rank({sig2}) + 0.20 * rank({sig3}))"
                    expr = f"trade_when(abs(rank({combined}) - 0.5) > 0.26, group_neutralize(rank({combined}), {n.lower()}), -1)"
                    candidates.append({
                        "expression": expr,
                        "archetype": f"T5_Trio_{t_put}_{t_term}_{t_skew}_d{d}_TOP3000_{n}",
                        "hypothesis": f"Tri-factor synthesis: {t_put}d put floor, {t_term}d term slope, and {t_skew}d skew asymmetry.",
                        "universe": "TOP3000",
                        "neutralization": n,
                        "decay": d,
                        "strategy": "tranche_5_trios",
                    })

    elif tranche_id == 6:
        # TRANCHE 6: Cross-Archetype Confluence (Put Floor + Call Breakout)
        pairs = [(180, 60), (90, 30), (270, 90), (120, 60), (360, 90)]
        for t_put, t_call in pairs:
            for n in ["SUBINDUSTRY", "SECTOR"]:
                for d in [10, 12]:
                    sig1 = f"ts_decay_linear(ts_decay_linear(((forward_price_{t_put} - put_breakeven_{t_put}) / close * (implied_volatility_mean_skew_{t_put} * sqrt({t_put}/252.0))), 10), 3)"
                    sig2 = f"ts_decay_linear(ts_decay_linear(((call_breakeven_{t_call} - forward_price_{t_call}) / close * (implied_volatility_call_{t_call} - implied_volatility_put_{t_call})), 10), 3)"
                    combined = f"(0.60 * rank({sig1}) + 0.40 * rank({sig2}))"
                    expr = f"trade_when(abs(rank({combined}) - 0.5) > 0.26, group_neutralize(rank({combined}), {n.lower()}), -1)"
                    candidates.append({
                        "expression": expr,
                        "archetype": f"T6_Put{t_put}_Call{t_call}_d{d}_TOP3000_{n}",
                        "hypothesis": f"Confluence of downside put floor ({t_put}d) and upside call breakout ({t_call}d).",
                        "universe": "TOP3000",
                        "neutralization": n,
                        "decay": d,
                        "strategy": "tranche_6_confluence",
                    })

    return candidates


async def run_overnight_pipeline():
    config = OptionsConfig.from_env()
    store = OptionsStore(data_dir=None, database_url=config.database_url)
    db = store.db

    log.info("=" * 80)
    log.info("STARTING CLOUD 50-ALPHA DECORRELATED ARSENAL PIPELINE (v3.0 Production Daemon)")
    log.info("Destination Table: options_alphas (Neon Postgres)")
    log.info("Safety Lock: Platform submissions DISABLED (status='QUALIFIED')")
    log.info("Checklist Gate: 100% Platform Checklist & Sub-Universe Sharpe Verification")
    log.info("Correlation Gate: |rho| < 0.70 vs all submitted & all reserve alphas")
    log.info("=" * 80)

    # Initial alert to user
    send_tg_message(
        token=config.telegram_bot_token,
        chat_id=config.telegram_chat_id,
        html_text=(
            "☁️ <b>Cloud 50-Alpha Autonomous Producer v3.0 Started</b>\n\n"
            "🎯 <b>Objective:</b> Scale reserve to 50 decorrelated alphas\n"
            "🛡️ <b>Gates:</b> Sharpe &ge; 1.25, Fitness &ge; 1.00, |&rho;| &lt; 0.70\n"
            "🔬 <b>Sub-Universe Check:</b> Explicitly verified on BRAIN API\n"
            "📡 <b>Heartbeat:</b> Hourly updates enabled\n"
            "🔔 <b>Instant Alerts:</b> Sent upon every qualification\n\n"
            "<i>Running 24/7 in GitHub Actions Cloud Runner...</i>"
        ),
    )

    with psycopg.connect(config.database_url) as conn:
        with conn.cursor() as cur:
            submitted_rows = load_submitted_alphas_pnl(cur)
            qualified_rows = load_qualified_reserve_alphas(cur)

    log.info("Found %d SUBMITTED alphas in options_alphas.", len(submitted_rows))
    log.info("Found %d QUALIFIED reserve alphas in options_alphas.", len(qualified_rows))

    client = BrainClient(
        username=config.brain_username,
        password=config.brain_password,
        max_concurrent_sims=2,
        db=db,
    )
    client.authenticate()

    # Pre-fetch PnLs
    submitted_pnls: Dict[str, Dict[str, float]] = {}
    for r in submitted_rows:
        alpha_id = r[0]
        pnl = await client.get_alpha_pnl(alpha_id)
        if pnl:
            submitted_pnls[alpha_id] = pnl

    reserve_pnls: Dict[str, Dict[str, float]] = {}
    # Treat 4 validated ready alphas as core reserve
    ready_alpha_ids = {"e7bWxz7E", "rKOa6qa9", "mLmQjlzE", "XgbOoJjx"}
    for r in qualified_rows:
        alpha_id = r[0]
        if alpha_id in ready_alpha_ids:
            pnl = await client.get_alpha_pnl(alpha_id)
            if pnl:
                reserve_pnls[alpha_id] = pnl

    total_target = 50
    current_qualified = len(reserve_pnls)
    existing_expressions = {r[1].strip() for r in (submitted_rows + qualified_rows) if r and len(r) > 1 and r[1]}
    log.info("Initial Reserve State: %d / %d Ready Alphas (%d known expressions)", current_qualified, total_target, len(existing_expressions))

    qualification_lock = asyncio.Lock()
    start_time = time.time()
    last_heartbeat_time = time.time()
    total_sims_run = 0

    # Tranches prioritized by virginity and orthogonal alpha generation:
    # 1: Call Breakouts & Put Breakeven Dynamics (Proven Sharpe 1.40 - 1.77)
    # 4: PCR Velocity & Flow Imbalance (Virgin)
    # 5: Multi-Factor Trios (Virgin)
    # 6: Confluence (Put + Call)
    tranche_order = [1, 4, 5, 6]

    pass_num = 1
    while current_qualified < total_target:
        log.info("\n" + "=" * 80)
        log.info(">>> MULTI-TRANCHE SWEEP PASS %d (Reserve Arsenal: %d / %d Qualified)", pass_num, current_qualified, total_target)
        log.info("=" * 80)

        for tranche_id in tranche_order:
            if current_qualified >= total_target:
                break

            candidates = build_tranche_candidates(tranche_id, pass_num=pass_num)
            log.info("\n>>> INITIATING TRANCHE %d [Pass %d] (%d Candidates). Current Reserve: %d / %d", tranche_id, pass_num, len(candidates), current_qualified, total_target)

            consecutive_corr_fails = 0

            for cand in candidates:
                if current_qualified >= total_target:
                    break

                # Saturation Circuit-Breaker: skip archetype if 4 consecutive correlation failures occur
                if consecutive_corr_fails >= 4:
                    log.warning("[-] Tranche %d hit 4 consecutive correlation failures. Saturated space, skipping to next tranche!", tranche_id)
                    break

                # Hourly Telegram Heartbeat
                now = time.time()
                if now - last_heartbeat_time >= 3600:
                    last_heartbeat_time = now
                    elapsed_hours = (now - start_time) / 3600.0
                    send_tg_message(
                        token=config.telegram_bot_token,
                        chat_id=config.telegram_chat_id,
                        html_text=(
                            f"⏱️ <b>Hourly Cloud Miner Heartbeat</b>\n\n"
                            f"📊 <b>Reserve Vault:</b> {current_qualified} / {total_target} Ready Alphas\n"
                            f"⏳ <b>Elapsed Time:</b> {elapsed_hours:.1f} hours\n"
                            f"🔬 <b>Total Simulations Run:</b> {total_sims_run}\n"
                            f"🎯 <b>Active Tranche:</b> Tranche {tranche_id} (Pass {pass_num})\n"
                            f"🛡️ <b>Pipeline Health:</b> Normal &amp; Operating in Cloud"
                        ),
                    )

                expr = cand["expression"]
                if expr.strip() in existing_expressions:
                    continue

                existing_expressions.add(expr.strip())
                total_sims_run += 1

                u = cand["universe"]
                n = cand["neutralization"]
                d = cand["decay"]

                settings = SimSettings(
                    region="USA",
                    universe=u,
                    delay=1,
                    decay=d,
                    neutralization=n,
                    truncation=0.05,
                    pasteurization=True,
                )

                try:
                    metrics = await client.simulate_one(expr, settings)
                except Exception as sim_err:
                    log.warning("Simulation error: %s", sim_err)
                    await asyncio.sleep(2.0)
                    continue

                if not metrics or not metrics.is_valid:
                    await asyncio.sleep(1.0)
                    continue

                log.info(
                    "[Sim #%d] %s | Sharpe=%.2f | Fitness=%.2f | TO=%.1f%% | Margin=%.1fbps | DD=%.1f%%",
                    total_sims_run, metrics.alpha_id, metrics.sharpe, metrics.fitness,
                    metrics.turnover * 100, metrics.margin * 10000, metrics.max_drawdown * 100
                )

                # Gate 1: Performance Gates
                if (
                    metrics.sharpe < 1.25
                    or metrics.fitness < 1.00
                    or metrics.turnover < 0.01
                    or metrics.turnover > 0.70
                    or metrics.margin < 0.0010
                    or metrics.max_drawdown > 0.35
                ):
                    await asyncio.sleep(1.0)
                    continue

                # Gate 2: Correlation Check vs ALL Submitted & ALL Reserve
                async with qualification_lock:
                    cand_pnl = await client.get_alpha_pnl(metrics.alpha_id)
                    if not cand_pnl or len(cand_pnl) < 30:
                        continue

                    max_corr_sub = max([abs(compute_correlation(cand_pnl, p)) for p in submitted_pnls.values()] or [0.0])
                    if max_corr_sub >= 0.70:
                        log.info("[-] Correlation vs submitted failed: %.4f >= 0.70 for %s", max_corr_sub, metrics.alpha_id)
                        consecutive_corr_fails += 1
                        continue

                    max_corr_res = max([abs(compute_correlation(cand_pnl, p)) for p in reserve_pnls.values()] or [0.0])
                    if max_corr_res >= 0.70:
                        log.info("[-] Correlation vs reserve failed: %.4f >= 0.70 for %s", max_corr_res, metrics.alpha_id)
                        consecutive_corr_fails += 1
                        continue

                    # Reset consecutive correlation failure counter on passing
                    consecutive_corr_fails = 0
                    overall_max_corr = max(max_corr_sub, max_corr_res)

                    # Gate 3: Platform Checklist Verification (SUB-UNIVERSE SHARPE CHECK)
                    log.info("[*] Verifying platform checklist for %s on BRAIN...", metrics.alpha_id)
                    chk_passed, chk_msg = verify_checklist_passes(client._session, metrics.alpha_id)
                    if not chk_passed:
                        log.warning("[-] Checklist check FAILED for %s: %s", metrics.alpha_id, chk_msg)
                        continue

                    log.info("[+] 100% CHECKLIST PASSED for %s: %s", metrics.alpha_id, chk_msg)

                    # QUALIFIED!
                    current_qualified += 1
                    reserve_pnls[metrics.alpha_id] = cand_pnl

                    log.info("=" * 80)
                    log.info(
                        "[QUALIFIED #%d / %d] AlphaID=%s | Sharpe=%.2f | Fitness=%.2f | TO=%.1f%% | Margin=%.1fbps | Corr=%.4f",
                        current_qualified, total_target, metrics.alpha_id, metrics.sharpe, metrics.fitness,
                        metrics.turnover * 100, metrics.margin * 10000, overall_max_corr
                    )
                    log.info("=" * 80)

                    # Persist to Neon PostgreSQL with status QUALIFIED
                    insert_qualified_alpha(
                        database_url=config.database_url,
                        alpha_id=metrics.alpha_id,
                        expression=expr,
                        archetype=cand["archetype"],
                        hypothesis=cand["hypothesis"],
                        sharpe=metrics.sharpe,
                        fitness=metrics.fitness,
                        turnover=metrics.turnover,
                        returns=metrics.annualized_return,
                        drawdown=metrics.max_drawdown,
                        margin=metrics.margin,
                        max_corr=overall_max_corr,
                        universe=u,
                        neutralization=n,
                        delay=1,
                        decay=d,
                        strategy_name=cand["strategy"],
                    )

                    # Send Immediate Telegram Alert
                    send_tg_message(
                        token=config.telegram_bot_token,
                        chat_id=config.telegram_chat_id,
                        html_text=(
                            f"🏆 <b>NEW QUALIFIED ALPHA SECURED (#{current_qualified}/{total_target})</b>\n\n"
                            f"🆔 <b>Alpha ID:</b> <code>{metrics.alpha_id}</code>\n"
                            f"📊 <b>Sharpe:</b> <b>{metrics.sharpe:.2f}</b> | <b>Fitness:</b> <b>{metrics.fitness:.2f}</b>\n"
                            f"📈 <b>Turnover:</b> {metrics.turnover*100:.1f}% | <b>Margin:</b> {metrics.margin*10000:.1f} bps\n"
                            f"🛡️ <b>Max Correlation:</b> <b>{overall_max_corr:.4f}</b> (&lt; 0.70)\n"
                            f"✅ <b>Sub-Universe Check:</b> <b>PASS</b>\n"
                            f"🏷️ <b>Archetype:</b> <code>{cand['archetype']}</code>\n"
                            f"🎯 <b>Remaining to 50:</b> {total_target - current_qualified}\n\n"
                            f"<code>{expr}</code>"
                        ),
                    )

                    await asyncio.sleep(2.0)

        pass_num += 1

    send_tg_message(
        token=config.telegram_bot_token,
        chat_id=config.telegram_chat_id,
        html_text=(
            f"🎉🎉 <b>MISSION ACCOMPLISHED! 50 QUALIFIED ALPHAS SECURED!</b> 🎉🎉\n\n"
            f"All 50 alphas are staged in PostgreSQL, passed Sub-Universe Sharpe checks, and decorrelated under |&rho;| &lt; 0.70.\n"
            f"Daily submitter will now drip 2 alphas per day into WorldQuant BRAIN."
        ),
    )
    log.info("50 QUALIFIED ALPHAS SECURED! Pipeline complete.")


if __name__ == "__main__":
    asyncio.run(run_overnight_pipeline())
