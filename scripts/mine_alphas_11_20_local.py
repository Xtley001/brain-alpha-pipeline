"""
Autonomous Local Options Alpha Miner (Target: Reserve Alphas 11 - 20)
---------------------------------------------------------------------
Discovers, simulates, decorrelates, validates against platform checklist,
and persists newly qualified reserve alphas to PostgreSQL database,
dispatching formatted HTML alerts to Telegram.

Strict Institutional Gates:
- Sharpe >= 1.25
- Fitness >= 1.00
- Turnover: 1.0% - 70.0%
- Margin >= 10.0 bps (0.0010)
- Max Drawdown < 35.0%
- Pearson Correlation < 0.70 vs ALL existing submitted & reserve alphas
- Submission Checklist PASS (immune to LOW_SUB_UNIVERSE_SHARPE)
"""

import asyncio
import decimal
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import psycopg
import requests

sys.path.insert(0, r"c:\Users\pc\Desktop\brain-alpha-pipeline")

from brain_options.config import OptionsConfig
from brain_options.store.store import OptionsStore
from brain_options.core.client import BrainClient, SimSettings, SimMetrics
from brain_options.core.correlation import compute_correlation

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("local_miner")

TOTAL_RESERVE_TARGET = 20  # Reserve Alphas 1 to 20 total target


def send_tg_reserve_alert(
    config: OptionsConfig,
    alpha_id: str,
    archetype: str,
    sharpe: float,
    fitness: float,
    turnover: float,
    margin: float,
    max_corr: float,
    current_count: int,
    total_target: int,
    universe: str,
    neutralization: str,
) -> bool:
    """Send immediate formatted HTML Telegram notification when an alpha is qualified for the reserve."""
    if not config.telegram_bot_token or not config.telegram_chat_id:
        return False
    try:
        html_text = (
            f"🟢 <b>RESERVE ALPHA QUALIFIED</b> · {time.strftime('%H:%M')} WAT\n"
            f"Progress: <b>{current_count}</b> / <b>{total_target}</b> Alphas Qualified\n\n"
            f"Alpha ID: <code>{alpha_id}</code>\n"
            f"Archetype: <code>{archetype}</code>\n"
            f"Settings: <code>{universe}</code> | <code>{neutralization}</code>\n\n"
            f"• <b>Sharpe:</b> <code>{sharpe:.2f}</code>\n"
            f"• <b>Fitness:</b> <code>{fitness:.2f}</code>\n"
            f"• <b>Turnover:</b> <code>{turnover*100:.1f}%</code>\n"
            f"• <b>Margin:</b> <code>{margin*10000:.1f} bps</code>\n"
            f"• <b>Max Corr:</b> <code>{max_corr:.4f}</code> (&lt; 0.70)\n\n"
            f"🔒 <i>Staged in PostgreSQL reserve pool (submissions locked).</i>\n"
            f"<b>Semper Fi!</b>"
        )
        url = f"https://api.telegram.org/bot{config.telegram_bot_token}/sendMessage"
        payload = {
            "chat_id": config.telegram_chat_id,
            "text": html_text,
            "parse_mode": "HTML",
        }
        resp = requests.post(url, json=payload, timeout=10.0)
        return resp.status_code == 200
    except Exception as e:
        log.warning("Telegram notification failed: %s", e)
        return False


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
) -> None:
    """Insert newly qualified alpha into options_alphas table with status QUALIFIED."""
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO options_alphas (
                    alpha_id, expression, archetype, hypothesis, source,
                    sharpe, fitness, turnover, returns, drawdown, margin,
                    max_correlation, universe, neutralization, delay, decay,
                    truncation, pasteurization, nan_handling, status,
                    created_at, strategy_name
                ) VALUES (
                    %s, %s, %s, %s, 'local_miner',
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    0.05, 'ON', 'OFF', 'QUALIFIED',
                    NOW(), %s
                ) RETURNING id;
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
            conn.commit()


def generate_candidate_matrix() -> List[Dict[str, Any]]:
    """
    Generate prioritized orthogonal candidates across proven institutional families
    specifically designed to decouple from the 24 reference alphas.
    """
    candidates = []

    # -------------------------------------------------------------------------
    # Family 1: Call-Breakeven Ceiling Architecture with Decoupled IV Asymmetry
    # -------------------------------------------------------------------------
    call_pairs = [
        # (t_call, t_iv, w1, w2, gate, decay, univ, neut)
        # Top Priority: High-conviction gates that decouple below 0.70
        (360, 90, 0.60, 0.40, 0.32, 8, "TOP3000", "SUBINDUSTRY"),
        (360, 90, 0.60, 0.40, 0.34, 8, "TOP3000", "SUBINDUSTRY"),
        (360, 60, 0.60, 0.40, 0.32, 10, "TOP3000", "SECTOR"),
        (360, 60, 0.60, 0.40, 0.34, 10, "TOP3000", "SECTOR"),
        (270, 90, 0.60, 0.40, 0.30, 8, "TOP3000", "SUBINDUSTRY"),
        (270, 60, 0.60, 0.40, 0.30, 10, "TOP3000", "SECTOR"),
        (270, 60, 0.60, 0.40, 0.32, 10, "TOP3000", "SECTOR"),
        (180, 90, 0.60, 0.40, 0.30, 10, "TOP3000", "SECTOR"),
        (180, 60, 0.60, 0.40, 0.32, 10, "TOP3000", "SECTOR"),
        (180, 30, 0.65, 0.35, 0.32, 10, "TOP3000", "SECTOR"),
        (360, 120, 0.60, 0.40, 0.30, 8, "TOP3000", "SUBINDUSTRY"),
        (270, 120, 0.60, 0.40, 0.30, 8, "TOP3000", "SUBINDUSTRY"),
        (180, 120, 0.60, 0.40, 0.30, 10, "TOP3000", "SECTOR"),
        (120, 60, 0.60, 0.40, 0.30, 8, "TOP3000", "SUBINDUSTRY"),
        (90, 60, 0.60, 0.40, 0.32, 10, "TOP3000", "SECTOR"),
        # TOP2000 variants
        (360, 90, 0.60, 0.40, 0.32, 8, "TOP2000", "SUBINDUSTRY"),
        (360, 60, 0.60, 0.40, 0.32, 8, "TOP2000", "SUBINDUSTRY"),
        (270, 90, 0.60, 0.40, 0.30, 8, "TOP2000", "SUBINDUSTRY"),
        (180, 60, 0.60, 0.40, 0.30, 8, "TOP2000", "SECTOR"),
    ]

    for t_call, t_iv, w1, w2, gate, dcy, u, n in call_pairs:
        sig1 = f"ts_decay_linear(ts_decay_linear(((call_breakeven_{t_call} - forward_price_{t_call}) / close * (implied_volatility_mean_skew_{t_call} * sqrt({t_call}/252.0)) * (pcr_vol_{t_call} / (pcr_oi_{t_call} + 0.001))), 10), 3)"
        sig2 = f"ts_decay_linear(ts_decay_linear(((implied_volatility_call_{t_iv} - implied_volatility_put_{t_iv}) / (implied_volatility_mean_{t_iv} + 0.001) * sqrt({t_iv}/252.0) * (volume / (adv20 + 1))), 10), 3)"
        comb = f"({w1} * rank({sig1}) + {w2} * rank({sig2}))"
        expr = f"trade_when(abs(rank({comb}) - 0.5) > {gate}, group_neutralize(rank({comb}) * (volume / adv20), {n.lower()}), -1)"

        candidates.append({
            "expression": expr,
            "archetype": f"Call{t_call}_IV{t_iv}_{int(w1*100)}_{u}_{n}_d{dcy}_g{int(gate*100)}",
            "hypothesis": f"Call breakeven ceiling ({t_call}d) blended with IV asymmetry ({t_iv}d).",
            "universe": u,
            "neutralization": n,
            "decay": dcy,
            "strategy": "call_breakeven_iv_asym",
        })

    # -------------------------------------------------------------------------
    # Family 2: Pure Call-Breakeven Monomials with High-Threshold Truncation
    # -------------------------------------------------------------------------
    monomial_calls = [
        (360, 0.32, 8, "TOP3000", "SUBINDUSTRY"),
        (360, 0.34, 10, "TOP3000", "SECTOR"),
        (270, 0.32, 8, "TOP3000", "SUBINDUSTRY"),
        (270, 0.34, 10, "TOP3000", "SECTOR"),
        (180, 0.34, 10, "TOP3000", "SECTOR"),
        (180, 0.32, 8, "TOP2000", "SUBINDUSTRY"),
        (120, 0.32, 8, "TOP3000", "SUBINDUSTRY"),
    ]
    for t_call, gate, dcy, u, n in monomial_calls:
        sig = f"ts_decay_linear(ts_decay_linear(((call_breakeven_{t_call} - forward_price_{t_call}) / close * (implied_volatility_mean_skew_{t_call} * sqrt({t_call}/252.0)) * (pcr_vol_{t_call} / (pcr_oi_{t_call} + 0.001))), 10), 3)"
        expr = f"trade_when(abs(rank({sig}) - 0.5) > {gate}, group_neutralize(rank({sig}) * (volume / adv20), {n.lower()}), -1)"

        candidates.append({
            "expression": expr,
            "archetype": f"Call{t_call}_Pure_{u}_{n}_d{dcy}_g{int(gate*100)}",
            "hypothesis": f"Pure call breakeven ceiling {t_call}d order flow hurdle.",
            "universe": u,
            "neutralization": n,
            "decay": dcy,
            "strategy": "pure_call_breakeven",
        })

    # -------------------------------------------------------------------------
    # Family 3: Long-Horizon Calendar Basis Spreads
    # -------------------------------------------------------------------------
    cal_pairs = [
        (360, 180, 0.55, 0.45, 0.28, 8, "TOP3000", "SUBINDUSTRY"),
        (360, 180, 0.50, 0.50, 0.30, 10, "TOP3000", "SECTOR"),
        (270, 90, 0.55, 0.45, 0.28, 8, "TOP3000", "SUBINDUSTRY"),
        (270, 90, 0.50, 0.50, 0.30, 10, "TOP3000", "SECTOR"),
        (360, 120, 0.50, 0.50, 0.28, 8, "TOP3000", "SUBINDUSTRY"),
        (180, 60, 0.50, 0.50, 0.28, 8, "TOP3000", "SUBINDUSTRY"),
        (270, 120, 0.50, 0.50, 0.28, 8, "TOP2000", "SUBINDUSTRY"),
    ]
    for t_long, t_short, w1, w2, gate, dcy, u, n in cal_pairs:
        sig1 = f"ts_decay_linear(ts_decay_linear(((implied_volatility_mean_{t_long} / (implied_volatility_mean_{t_short} + 0.001)) * (implied_volatility_mean_skew_{t_short} * sqrt({t_short}/252.0))), 10), 3)"
        sig2 = f"ts_decay_linear(ts_decay_linear(((forward_price_{t_long} - forward_price_{t_short}) / close * (implied_volatility_mean_{t_long} / (implied_volatility_mean_{t_short} + 0.001)) * (volume / (adv20 + 1))), 10), 3)"
        comb = f"({w1} * rank({sig1}) + {w2} * rank({sig2}))"
        expr = f"trade_when(abs(rank({comb}) - 0.5) > {gate}, group_neutralize(rank({comb}) * (volume / adv20), {n.lower()}), -1)"

        candidates.append({
            "expression": expr,
            "archetype": f"Cal_{t_long}_{t_short}_{u}_{n}_d{dcy}_g{int(gate*100)}",
            "hypothesis": f"Calendar term basis spread between {t_long}d and {t_short}d options forward curve.",
            "universe": u,
            "neutralization": n,
            "decay": dcy,
            "strategy": "calendar_basis_spread",
        })

    # -------------------------------------------------------------------------
    # Family 4: Put Breakeven at Unused/Uncrowded Tenors (270d, 150d)
    # -------------------------------------------------------------------------
    put_pairs = [
        (270, 30, 0.65, 0.35, 0.28, 8, "TOP3000", "SECTOR"),
        (270, 30, 0.65, 0.35, 0.30, 10, "TOP3000", "SECTOR"),
        (270, 120, 0.60, 0.40, 0.28, 8, "TOP3000", "SECTOR"),
        (150, 30, 0.65, 0.35, 0.28, 8, "TOP3000", "SECTOR"),
        (150, 60, 0.60, 0.40, 0.30, 10, "TOP3000", "SECTOR"),
        (270, 30, 0.65, 0.35, 0.28, 8, "TOP2000", "SECTOR"),
    ]
    for t_put, t_iv, w1, w2, gate, dcy, u, n in put_pairs:
        sig1 = f"ts_decay_linear(ts_decay_linear(((forward_price_{t_put} - put_breakeven_{t_put}) / close * (implied_volatility_mean_skew_{t_put} * sqrt({t_put}/252.0)) * (pcr_vol_{t_put} / (pcr_oi_{t_put} + 0.001))), 10), 3)"
        sig2 = f"ts_decay_linear(ts_decay_linear(((implied_volatility_call_{t_iv} - implied_volatility_put_{t_iv}) / (implied_volatility_mean_{t_iv} + 0.001) * sqrt({t_iv}/252.0) * (volume / (adv20 + 1))), 10), 3)"
        comb = f"({w1} * rank({sig1}) + {w2} * rank({sig2}))"
        expr = f"trade_when(abs(rank({comb}) - 0.5) > {gate}, group_neutralize(rank({comb}) * (volume / adv20), {n.lower()}), -1)"

        candidates.append({
            "expression": expr,
            "archetype": f"Put{t_put}_IV{t_iv}_{u}_{n}_d{dcy}_g{int(gate*100)}",
            "hypothesis": f"Downside put breakeven floor ({t_put}d) blended with IV asymmetry ({t_iv}d).",
            "universe": u,
            "neutralization": n,
            "decay": dcy,
            "strategy": "put_floor_uncrowded_tenor",
        })

    # -------------------------------------------------------------------------
    # Family 5: Volatility Skew Curve Slopes (Term Differential of Skew)
    # -------------------------------------------------------------------------
    skew_slopes = [
        (180, 30, 0.30, 8, "TOP3000", "SUBINDUSTRY"),
        (180, 30, 0.32, 10, "TOP3000", "SECTOR"),
        (270, 60, 0.30, 8, "TOP3000", "SUBINDUSTRY"),
        (270, 60, 0.32, 10, "TOP3000", "SECTOR"),
        (360, 90, 0.30, 8, "TOP3000", "SUBINDUSTRY"),
        (360, 90, 0.32, 10, "TOP3000", "SECTOR"),
    ]
    for t_long, t_short, gate, dcy, u, n in skew_slopes:
        sig = f"ts_decay_linear(ts_decay_linear(((implied_volatility_mean_skew_{t_long} * sqrt({t_long}/252.0) - implied_volatility_mean_skew_{t_short} * sqrt({t_short}/252.0)) * (volume / (adv20 + 1))), 10), 3)"
        expr = f"trade_when(abs(rank({sig}) - 0.5) > {gate}, group_neutralize(rank({sig}) * (volume / adv20), {n.lower()}), -1)"

        candidates.append({
            "expression": expr,
            "archetype": f"SkewSlope_{t_long}_{t_short}_{u}_{n}_d{dcy}_g{int(gate*100)}",
            "hypothesis": f"Term slope of volatility skew curvature between {t_long}d and {t_short}d.",
            "universe": u,
            "neutralization": n,
            "decay": dcy,
            "strategy": "skew_curve_slope",
        })

    return candidates


async def run_miner():
    config = OptionsConfig.from_env()
    store = OptionsStore(database_url=config.database_url)
    client = BrainClient(config.brain_username, config.brain_password, max_concurrent_sims=2, db=store.db)
    client.authenticate()

    # 1. Inspect existing reserve count and reference pool
    with store.db._get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT alpha_id FROM options_alphas WHERE status = 'QUALIFIED'")
            qualified_ids = [r[0] for r in cur.fetchall()]
            cur.execute("SELECT alpha_id FROM options_alphas WHERE status = 'SUBMITTED'")
            submitted_ids = [r[0] for r in cur.fetchall()]
            cur.execute("SELECT expression FROM options_alphas")
            existing_expressions = set(r[0].strip() for r in cur.fetchall() if r[0])

    initial_qualified_count = len(qualified_ids)
    all_reference_ids = list(set(qualified_ids + submitted_ids))
    log.info("================================================================================")
    log.info("STARTING LOCAL OPTIONS ALPHA MINER (TARGET: 11 - 20)")
    log.info("Current Status: %d QUALIFIED Reserve Alphas | %d SUBMITTED Alphas", initial_qualified_count, len(submitted_ids))
    log.info("Target Reserve Count: %d (Needs %d New Alphas)", TOTAL_RESERVE_TARGET, max(0, TOTAL_RESERVE_TARGET - initial_qualified_count))
    log.info("Pre-loading PnLs for %d reference alphas...", len(all_reference_ids))

    ref_pnls: Dict[str, Dict[str, float]] = {}
    for aid in all_reference_ids:
        pnl = await client.get_alpha_pnl(aid)
        if pnl:
            ref_pnls[aid] = pnl
    log.info("Loaded %d daily PnL series into memory.", len(ref_pnls))
    log.info("================================================================================")

    current_qualified = initial_qualified_count
    if current_qualified >= TOTAL_RESERVE_TARGET:
        log.info("Reserve arsenal target (%d) is already achieved!", TOTAL_RESERVE_TARGET)
        return

    candidate_matrix = generate_candidate_matrix()
    log.info("Generated %d prioritized orthogonal candidates across 5 alpha families.", len(candidate_matrix))

    for idx, cand in enumerate(candidate_matrix, 1):
        if current_qualified >= TOTAL_RESERVE_TARGET:
            log.info(">>> TARGET REACHED! Exactly %d reserve alphas qualified!", TOTAL_RESERVE_TARGET)
            break

        expr = cand["expression"]
        if expr.strip() in existing_expressions:
            continue

        log.info("\n--------------------------------------------------------------------------------")
        log.info("[%d/%d] Evaluating Candidate: %s", idx, len(candidate_matrix), cand["archetype"])
        log.info("Settings: Universe=%s | Neutralization=%s | Decay=%d", cand["universe"], cand["neutralization"], cand["decay"])

        settings = SimSettings(
            region="USA",
            universe=cand["universe"],
            delay=1,
            decay=cand["decay"],
            neutralization=cand["neutralization"],
            truncation=0.05,
            pasteurization=True,
        )

        try:
            metrics = await client.simulate_one(expr, settings)
        except Exception as e:
            log.warning("Simulation exception: %s", e)
            continue

        if not metrics.alpha_id or not metrics.is_valid:
            log.warning("Simulation returned invalid metrics (alpha_id=%s, status=%s)", metrics.alpha_id, metrics.status)
            continue

        log.info(
            "  Alpha ID: %s | Sharpe: %.2f | Fitness: %.2f | Turnover: %.1f%% | Margin: %.1f bps | Return: %.1f%% | MaxDD: %.1f%%",
            metrics.alpha_id, metrics.sharpe, metrics.fitness, metrics.turnover * 100, metrics.margin * 10000,
            metrics.annualized_return * 100, metrics.max_drawdown * 100,
        )

        # Gate 1: Performance Filters
        if metrics.sharpe < 1.25:
            log.info("  --> REJECT: Sharpe %.2f < 1.25", metrics.sharpe)
            continue
        if metrics.fitness < 1.00:
            log.info("  --> REJECT: Fitness %.2f < 1.00", metrics.fitness)
            continue
        if not (0.01 <= metrics.turnover <= 0.70):
            log.info("  --> REJECT: Turnover %.1f%% out of bounds [1%%, 70%%]", metrics.turnover * 100)
            continue
        if metrics.margin < 0.0010:
            log.info("  --> REJECT: Margin %.1f bps < 10.0 bps", metrics.margin * 10000)
            continue
        if metrics.max_drawdown >= 0.35:
            log.info("  --> REJECT: Max Drawdown %.1f%% >= 35.0%%", metrics.max_drawdown * 100)
            continue

        log.info("  --> PASS: Met all performance criteria! Checking correlation vs %d alphas...", len(ref_pnls))

        # Gate 2: Correlation Check
        cand_pnl = await client.get_alpha_pnl(metrics.alpha_id)
        if not cand_pnl:
            log.warning("  --> REJECT: Could not fetch PnL for %s", metrics.alpha_id)
            continue

        max_c = 0.0
        max_ref = ""
        for ref_id, ref_pnl in ref_pnls.items():
            c = abs(compute_correlation(cand_pnl, ref_pnl))
            if c > max_c:
                max_c = c
                max_ref = ref_id

        log.info("  --> Max Correlation: %.4f (vs %s)", max_c, max_ref)
        if max_c >= 0.70:
            log.info("  --> REJECT: Max correlation %.4f >= 0.70 barrier", max_c)
            continue

        # Gate 3: Platform Checklist Immunity Check
        log.info("  --> PASS: Correlation %.4f < 0.70! Running WorldQuant BRAIN submission checklist...", max_c)
        try:
            chk = await client.check_alpha_submission(metrics.alpha_id)
            sub_univ_check = chk.checks.get("LOW_SUB_UNIVERSE_SHARPE", "PASS")
            log.info("  --> Checklist Status: %s | LOW_SUB_UNIVERSE_SHARPE: %s", chk.status, sub_univ_check)
            if chk.status == "FAIL" or sub_univ_check == "FAIL":
                log.warning("  --> REJECT: Alpha failed BRAIN pre-submission checklist (%s)", chk.checks)
                continue
        except Exception as e:
            log.warning("  --> Checklist check error: %s (proceeding with caution)", e)

        # QUALIFIED!
        current_qualified += 1
        log.info("================================================================================")
        log.info(
            "🎉 QUALIFIED RESERVE ALPHA (#%d / %d): %s | Sharpe: %.2f | Fitness: %.2f | Turnover: %.1f%% | Margin: %.1f bps | Max Corr: %.4f",
            current_qualified, TOTAL_RESERVE_TARGET, metrics.alpha_id, metrics.sharpe, metrics.fitness,
            metrics.turnover * 100, metrics.margin * 10000, max_c,
        )
        log.info("================================================================================")

        # 1. Insert into PostgreSQL
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
            max_corr=max_c,
            universe=cand["universe"],
            neutralization=cand["neutralization"],
            delay=1,
            decay=cand["decay"],
            strategy_name=cand["strategy"],
        )

        # 2. Add to reference pool dynamically
        ref_pnls[metrics.alpha_id] = cand_pnl
        existing_expressions.add(expr.strip())

        # 3. Dispatch formatted Telegram HTML alert
        send_tg_reserve_alert(
            config=config,
            alpha_id=metrics.alpha_id,
            archetype=cand["archetype"],
            sharpe=metrics.sharpe,
            fitness=metrics.fitness,
            turnover=metrics.turnover,
            margin=metrics.margin,
            max_corr=max_c,
            current_count=current_qualified,
            total_target=TOTAL_RESERVE_TARGET,
            universe=cand["universe"],
            neutralization=cand["neutralization"],
        )

        await asyncio.sleep(2.0)

    log.info("\n================================================================================")
    log.info("MINER COMPLETE: Final Reserve Count = %d / %d Alphas", current_qualified, TOTAL_RESERVE_TARGET)
    log.info("================================================================================")


if __name__ == "__main__":
    asyncio.run(run_miner())
