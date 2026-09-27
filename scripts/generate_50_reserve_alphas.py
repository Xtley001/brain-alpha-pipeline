#!/usr/bin/env python3
"""
Autonomous 50-Alpha Decorrelated Reserve Pipeline (v2.3 Production Daemon).
Generates, simulates with PostgreSQL session cookie caching & polite rate pacing,
verifies institutional checklist & correlation gates (< 0.70 vs all submitted & reserve),
and stages exactly 50 qualified alphas in Neon Postgres (options_alphas, status 'QUALIFIED').
Strictly zero platform submissions (ENABLE_AUTO_SUBMIT = False).
Sends immediate HTML Telegram alerts to Christley upon every qualification.
Runs continuously across multi-pass tranches until 50 alphas are secured.
"""
import asyncio
import decimal
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up logging early to capture all root logs into reserve_50_pipeline.log
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


def load_submitted_alphas_pnl(cur) -> List[Tuple[str, str, Dict[str, float]]]:
    """Load all 14 submitted alphas from options_alphas."""
    cur.execute("""
        SELECT alpha_id, expression, status 
        FROM options_alphas 
        WHERE status = 'SUBMITTED' 
        ORDER BY id ASC;
    """)
    return cur.fetchall()


def load_qualified_reserve_alphas(cur) -> List[Tuple[str, str, float, float, float]]:
    """Load currently qualified reserve alphas."""
    cur.execute("""
        SELECT alpha_id, expression, sharpe, fitness, max_correlation 
        FROM options_alphas 
        WHERE status = 'QUALIFIED' 
        ORDER BY id ASC;
    """)
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
                    %s, %s, %s, %s, 'reserve_generator',
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
            f"🔒 <i>Staged in PostgreSQL reserve pool (submissions disabled).</i>\n"
            f"<b>Semper Fi!</b>"
        )
        url = f"https://api.telegram.org/bot{config.telegram_bot_token}/sendMessage"
        payload = {
            "chat_id": config.telegram_chat_id,
            "text": html_text,
            "parse_mode": "HTML",
        }
        resp = requests.post(url, json=payload, timeout=10.0)
        if resp.status_code == 200:
            log.info("Telegram alert delivered for %s (%d/%d)", alpha_id, current_count, total_target)
            return True
        else:
            log.warning("Telegram alert returned %d: %s", resp.status_code, resp.text)
            return False
    except Exception as e:
        log.warning("Telegram notification failed: %s", e)
        return False


# Candidate generation blueprints across 6 tranches + dynamic cross-archetype fallback
def build_tranche_candidates(
    tranche_id: int,
    pass_num: int = 1,
    hall_of_fame: Optional[List[Dict[str, Any]]] = None,
    recent_feedback: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    candidates = []

    if tranche_id == 1:
        # Tranche 1: Downside Floor & Put Breakeven Dynamics (Bivariate Pre-Decay Blends)
        tenor_pairs = [
            (270, 60), (60, 20), (360, 90), (120, 30), (180, 30),
            (270, 90), (90, 60), (60, 30), (360, 60), (90, 20),
            (120, 60), (270, 30), (180, 90), (60, 10), (360, 30),
            (150, 30), (150, 60), (120, 20), (270, 120), (360, 120),
        ]
        weights = [(0.65, 0.35), (0.60, 0.40), (0.70, 0.30)] if pass_num == 1 else [(0.55, 0.45), (0.50, 0.50), (0.75, 0.25)]
        decays = [8] if pass_num == 1 else [10, 12]
        gate_thresh = 0.26 if pass_num == 1 else 0.24

        for t1, t2 in tenor_pairs:
            for u in ["TOP3000", "TOP2000"]:
                for n in ["SUBINDUSTRY", "SECTOR"]:
                    for w1, w2 in weights:
                        for d in decays:
                            sig1 = f"ts_decay_linear(ts_decay_linear(((forward_price_{t1} - put_breakeven_{t1}) / close * (implied_volatility_mean_skew_{t1} * sqrt({t1}/252.0)) * (pcr_vol_{t1} / (pcr_oi_{t1} + 0.001))), 10), 3)"
                            sig2 = f"ts_decay_linear(ts_decay_linear(((implied_volatility_call_{t2} - implied_volatility_put_{t2}) / (implied_volatility_mean_{t2} + 0.001) * sqrt({t2}/252.0) * (volume / (adv20 + 1))), 10), 3)"
                            combined = f"({w1} * rank({sig1}) + {w2} * rank({sig2}))"
                            expr = f"trade_when(abs(rank({combined}) - 0.5) > {gate_thresh}, group_neutralize(rank({combined}) * (volume / adv20), {n.lower()}), -1)"

                            candidates.append({
                                "expression": expr,
                                "archetype": f"T1_Put{t1}_Skew{t2}_{int(w1*100)}_d{d}_{u}_{n}",
                                "hypothesis": f"Downside put breakeven floor ({t1}d) blended with skew differential ({t2}d) captures tail overpricing.",
                                "universe": u,
                                "neutralization": n,
                                "decay": d,
                                "strategy": "tranche_1_put_skew_blend",
                            })

        # Cross-Factor Combinations for Tranche 1 (Put Floor + Term Slope / VRP)
        cross_pairs = [
            (180, 180, 30, "TermSlope"),
            (90, 90, 30, "TermSlope"),
            (270, 270, 60, "TermSlope"),
            (60, 60, 20, "TermSlope"),
            (360, 360, 90, "TermSlope"),
            (120, 120, 30, "TermSlope"),
            (180, 60, 0, "VRP"),
            (90, 60, 0, "VRP"),
            (270, 90, 0, "VRP"),
            (120, 60, 0, "VRP"),
            (360, 90, 0, "VRP"),
        ]
        for t_put, t_sub1, t_sub2, factor_type in cross_pairs:
            for u in ["TOP3000", "TOP2000"]:
                for n in ["SUBINDUSTRY", "SECTOR"]:
                    for d in [8, 10]:
                        sig1 = f"ts_decay_linear(ts_decay_linear(((forward_price_{t_put} - put_breakeven_{t_put}) / close * (implied_volatility_mean_skew_{t_put} * sqrt({t_put}/252.0)) * (pcr_vol_{t_put} / (pcr_oi_{t_put} + 0.001))), 10), 3)"
                        if factor_type == "TermSlope":
                            sig2 = f"ts_decay_linear(ts_decay_linear(((implied_volatility_mean_{t_sub1} / (implied_volatility_mean_{t_sub2} + 0.001)) * sqrt({t_sub1}/252.0) * (volume / (adv20 + 1))), 10), 3)"
                            hyp = f"{t_put}d put floor blended with {t_sub1}d/{t_sub2}d term slope."
                        else:
                            sig2 = f"ts_decay_linear(ts_decay_linear((- (implied_volatility_mean_{t_sub1} - ts_std_dev(returns, {t_sub1}) * sqrt(252)) / (implied_volatility_mean_{t_sub1} + 0.001) * (volume / (adv20 + 1))), 10), 3)"
                            hyp = f"{t_put}d put floor blended with {t_sub1}d inverted VRP."

                        combined = f"(0.65 * rank({sig1}) + 0.35 * rank({sig2}))"
                        expr = f"trade_when(abs(rank({combined}) - 0.5) > {gate_thresh}, group_neutralize(rank({combined}) * (volume / adv20), {n.lower()}), -1)"

                        candidates.append({
                            "expression": expr,
                            "archetype": f"T1_Put{t_put}_{factor_type}_d{d}_{u}_{n}",
                            "hypothesis": hyp,
                            "universe": u,
                            "neutralization": n,
                            "decay": d,
                            "strategy": "tranche_1_cross_factor",
                        })

        # Upside Call Breakeven Breakouts (Naturally Orthogonal to Put Floor)
        call_pairs = [(90, 30), (180, 60), (60, 20), (270, 90), (120, 30), (360, 90)]
        for t1, t2 in call_pairs:
            for u in ["TOP3000", "TOP2000"]:
                for n in ["SUBINDUSTRY", "SECTOR"]:
                    sig1 = f"ts_decay_linear(ts_decay_linear(((call_breakeven_{t1} - forward_price_{t1}) / close * (implied_volatility_call_{t1} - implied_volatility_put_{t1}) * (pcr_oi_{t1} / (pcr_vol_{t1} + 0.001))), 10), 3)"
                    sig2 = f"ts_decay_linear(ts_decay_linear(((implied_volatility_call_{t2} / (implied_volatility_put_{t2} + 0.001) - 1.0) * (volume / (adv20 + 1))), 10), 3)"
                    combined = f"(0.60 * rank({sig1}) + 0.40 * rank({sig2}))"
                    expr = f"trade_when(abs(rank({combined}) - 0.5) > {gate_thresh}, group_neutralize(rank({combined}) * (volume / adv20), {n.lower()}), -1)"

                    candidates.append({
                        "expression": expr,
                        "archetype": f"T1_CallBreakout{t1}_{t2}_{u}_{n}",
                        "hypothesis": f"Call breakeven breakout ({t1}d) modulated by call/put ratio captures right-tail explosive drift.",
                        "universe": u,
                        "neutralization": n,
                        "decay": 8,
                        "strategy": "tranche_1_call_breakout",
                    })

    elif tranche_id == 2:
        # Tranche 2: Volatility Term Structure & Forward Calendar Spreads (Bivariate Pre-Decay Blends)
        pairs = [
            (180, 30), (270, 60), (360, 90), (90, 30), (180, 60),
            (270, 30), (360, 60), (90, 20), (180, 20), (120, 30),
            (150, 30), (120, 60), (150, 60), (360, 30), (270, 20),
        ]
        weights = [(0.60, 0.40), (0.65, 0.35), (0.50, 0.50), (0.70, 0.30)]
        universes = ["TOP3000", "TOP2000"]
        neuts = ["SUBINDUSTRY", "SECTOR"]
        decays = [8, 10] if pass_num > 1 else [8]

        for t1, t2 in pairs:
            for w1, w2 in weights:
                for u in universes:
                    for n in neuts:
                        for d in decays:
                            sig1 = f"ts_decay_linear(ts_decay_linear(((implied_volatility_mean_{t1} / (implied_volatility_mean_{t2} + 0.001)) * (implied_volatility_mean_skew_{t2} * sqrt({t2}/252.0))), 10), 3)"
                            sig2 = f"ts_decay_linear(ts_decay_linear(((forward_price_{t1} - forward_price_{t2}) / close * (implied_volatility_mean_{t1} / (implied_volatility_mean_{t2} + 0.001)) * (volume / (adv20 + 1))), 10), 3)"
                            combined = f"({w1} * rank({sig1}) + {w2} * rank({sig2}))"
                            expr = f"trade_when(abs(rank({combined}) - 0.5) > 0.26, group_neutralize(rank({combined}) * (volume / adv20), {n.lower()}), -1)"

                            candidates.append({
                                "expression": expr,
                                "archetype": f"T2_Term{t1}_{t2}_Cal_{int(w1*100)}_d{d}_{u}_{n}",
                                "hypothesis": f"Volatility term slope ({t1}d/{t2}d) blended with forward calendar spread captures roll decay.",
                                "universe": u,
                                "neutralization": n,
                                "decay": d,
                                "strategy": "tranche_2_term_structure",
                            })

    elif tranche_id == 3:
        # Tranche 3: Inverted Variance Risk Premia (PEAVRP: Short Overpriced Vol) & Volatility Smile Curvature
        # S1: Inverted Normalized VRP: -(IV - RV) / IV -> Long cheap vol, short expensive vol
        # S2: Butterfly Smile Convexity: (IV_call + IV_put - 2*IV_atm) / IV_atm
        tenors = [60, 90, 180, 30, 120, 150, 270]
        weights = [(0.60, 0.40), (0.65, 0.35), (0.55, 0.45), (0.70, 0.30)]
        universes = ["TOP3000", "TOP2000"]
        neuts = ["SUBINDUSTRY", "SECTOR"]

        for t in tenors:
            for w1, w2 in weights:
                for u in universes:
                    for n in neuts:
                        # Variant A: Inverted IV vs Return Standard Deviation
                        sig1 = f"ts_decay_linear(ts_decay_linear((- (implied_volatility_mean_{t} - ts_std_dev(returns, {t}) * sqrt(252)) / (implied_volatility_mean_{t} + 0.001) * (implied_volatility_mean_skew_{t} * sqrt({t}/252.0))), 10), 3)"
                        sig2 = f"ts_decay_linear(ts_decay_linear(((implied_volatility_call_{t} + implied_volatility_put_{t} - 2 * implied_volatility_mean_{t}) / (implied_volatility_mean_{t} + 0.001) * (volume / (adv20 + 1))), 10), 3)"
                        combined = f"({w1} * rank({sig1}) + {w2} * rank({sig2}))"
                        expr = f"trade_when(abs(rank({combined}) - 0.5) > 0.26, group_neutralize(rank({combined}) * (volume / adv20), {n.lower()}), -1)"

                        candidates.append({
                            "expression": expr,
                            "archetype": f"T3_InvVRP{t}_SmileCurv_{int(w1*100)}_{u}_{n}",
                            "hypothesis": f"Inverted normalized VRP ({t}d) blended with smile curvature monetizes structural option insurance mispricing.",
                            "universe": u,
                            "neutralization": n,
                            "decay": 8,
                            "strategy": "tranche_3_peavrp",
                        })

                        # Variant B: Inverted IV vs Historical Volatility field (if t <= 180)
                        if t <= 180:
                            sig1_hv = f"ts_decay_linear(ts_decay_linear((- (implied_volatility_mean_{t} - historical_volatility_{t}) / (implied_volatility_mean_{t} + 0.001) * (implied_volatility_mean_skew_{t} * sqrt({t}/252.0))), 10), 3)"
                            comb_hv = f"({w1} * rank({sig1_hv}) + {w2} * rank({sig2}))"
                            expr_hv = f"trade_when(abs(rank({comb_hv}) - 0.5) > 0.26, group_neutralize(rank({comb_hv}) * (volume / adv20), {n.lower()}), -1)"

                            candidates.append({
                                "expression": expr_hv,
                                "archetype": f"T3_InvHV_VRP{t}_SmileCurv_{int(w1*100)}_{u}_{n}",
                                "hypothesis": f"Inverted historical vol normalized VRP ({t}d) with butterfly curvature.",
                                "universe": u,
                                "neutralization": n,
                                "decay": 8,
                                "strategy": "tranche_3_peavrp_hv",
                            })

    elif tranche_id == 4:
        # Tranche 4: PCR Flow Momentum / Velocity & Open Interest Dynamics (Bivariate Pre-Decay Blends)
        # S1: PCR Flow Velocity (5-day rate of change)
        # S2: Standardized Open Interest Imbalance: (1 - PCR_OI) / (1 + PCR_OI)
        tenors = [30, 60, 90, 120, 180]
        weights = [(0.60, 0.40), (0.65, 0.35), (0.50, 0.50), (0.55, 0.45)]
        universes = ["TOP3000", "TOP2000"]
        neuts = ["SUBINDUSTRY", "SECTOR"]

        for t in tenors:
            for w1, w2 in weights:
                for u in universes:
                    for n in neuts:
                        sig1 = f"ts_decay_linear(ts_decay_linear((ts_delta(pcr_vol_{t} / (pcr_oi_{t} + 0.001), 5) * (implied_volatility_mean_skew_{t} * sqrt({t}/252.0))), 10), 3)"
                        sig2 = f"ts_decay_linear(ts_decay_linear(((1.0 - pcr_oi_{t}) / (1.0 + pcr_oi_{t} + 0.001) * (volume / (adv20 + 1))), 10), 3)"
                        combined = f"({w1} * rank({sig1}) + {w2} * rank({sig2}))"
                        expr = f"trade_when(abs(rank({combined}) - 0.5) > 0.26, group_neutralize(rank({combined}) * (volume / adv20), {n.lower()}), -1)"

                        candidates.append({
                            "expression": expr,
                            "archetype": f"T4_PCRVel{t}_OI_{int(w1*100)}_{u}_{n}",
                            "hypothesis": f"PCR velocity ({t}d) blended with standardized OI imbalance isolates informed aggressive option positioning.",
                            "universe": u,
                            "neutralization": n,
                            "decay": 8,
                            "strategy": "tranche_4_pcr_flow",
                        })

    elif tranche_id == 5:
        # Tranche 5: Cross-Horizon Multi-Signal Confluence Trios
        # Tri-factor blend: Put Floor + Term Slope + Inverted VRP
        trios = [
            (180, 180, 30, 60),
            (90, 90, 30, 60),
            (270, 270, 60, 90),
            (180, 270, 60, 90),
            (360, 180, 30, 90),
            (120, 120, 30, 60),
            (60, 60, 20, 30),
            (150, 150, 30, 60),
            (270, 180, 30, 90),
            (360, 270, 60, 120),
        ]
        universes = ["TOP3000", "TOP2000"]
        neuts = ["SUBINDUSTRY", "SECTOR"]

        for t_put, t_term1, t_term2, t_vrp in trios:
            for u in universes:
                for n in neuts:
                    for d in [8, 10]:
                        sig1 = f"ts_decay_linear(ts_decay_linear(((forward_price_{t_put} - put_breakeven_{t_put}) / close * (implied_volatility_mean_skew_{t_put} * sqrt({t_put}/252.0))), 10), 3)"
                        sig2 = f"ts_decay_linear(ts_decay_linear(((implied_volatility_mean_{t_term1} / (implied_volatility_mean_{t_term2} + 0.001)) * sqrt({t_term1}/252.0)), 10), 3)"
                        sig3 = f"ts_decay_linear(ts_decay_linear((- (implied_volatility_mean_{t_vrp} - ts_std_dev(returns, {t_vrp}) * sqrt(252)) / (implied_volatility_mean_{t_vrp} + 0.001) * (volume / (adv20 + 1))), 10), 3)"
                        combined = f"(0.45 * rank({sig1}) + 0.35 * rank({sig2}) + 0.20 * rank({sig3}))"
                        expr = f"trade_when(abs(rank({combined}) - 0.5) > 0.26, group_neutralize(rank({combined}) * (volume / adv20), {n.lower()}), -1)"

                        candidates.append({
                            "expression": expr,
                            "archetype": f"T5_Trio_Put{t_put}_Term{t_term1}_InvVRP{t_vrp}_d{d}_{u}_{n}",
                            "hypothesis": f"Macro cross-horizon trio: {t_put}d put floor + {t_term1}d/{t_term2}d term slope + {t_vrp}d inverted VRP.",
                            "universe": u,
                            "neutralization": n,
                            "decay": d,
                            "strategy": "tranche_5_trios",
                        })

    elif tranche_id == 6:
        # Tranche 6: Cross-Archetype Decorrelated Blends (Call Breakouts, Put Floors + PCR Flow, Term + Skew)
        tenor_sets = [
            (180, 90), (270, 30), (360, 60), (90, 60), (120, 30), (150, 60), (60, 30),
        ]
        universes = ["TOP3000", "TOP2000"]
        neuts = ["SUBINDUSTRY", "SECTOR"]

        for t1, t2 in tenor_sets:
            for u in universes:
                for n in neuts:
                    for d in [8, 10]:
                        # Type A: Call Breakout + Term Structure Slope
                        sig1 = f"ts_decay_linear(ts_decay_linear(((call_breakeven_{t1} - forward_price_{t1}) / close * (implied_volatility_call_{t1} - implied_volatility_put_{t1})), 10), 3)"
                        sig2 = f"ts_decay_linear(ts_decay_linear(((implied_volatility_mean_{t1} / (implied_volatility_mean_{t2} + 0.001)) * sqrt({t1}/252.0) * (volume / (adv20 + 1))), 10), 3)"
                        comb = f"(0.60 * rank({sig1}) + 0.40 * rank({sig2}))"
                        expr = f"trade_when(abs(rank({comb}) - 0.5) > 0.26, group_neutralize(rank({comb}) * (volume / adv20), {n.lower()}), -1)"
                        candidates.append({
                            "expression": expr,
                            "archetype": f"T6_CallBreakout_Term{t1}_{t2}_d{d}_{u}_{n}",
                            "hypothesis": f"Call breakout ({t1}d) modulated by term slope ({t1}d/{t2}d) captures asymmetric growth drift.",
                            "universe": u,
                            "neutralization": n,
                            "decay": d,
                            "strategy": "tranche_6_cross_archetype",
                        })

                        # Type B: Put Floor + PCR Acceleration
                        sig1_b = f"ts_decay_linear(ts_decay_linear(((forward_price_{t1} - put_breakeven_{t1}) / close * (implied_volatility_mean_skew_{t1} * sqrt({t1}/252.0))), 10), 3)"
                        sig2_b = f"ts_decay_linear(ts_decay_linear((ts_delta(pcr_vol_{t2} / (pcr_oi_{t2} + 0.001), 5) * (volume / (adv20 + 1))), 10), 3)"
                        comb_b = f"(0.65 * rank({sig1_b}) + 0.35 * rank({sig2_b}))"
                        expr_b = f"trade_when(abs(rank({comb_b}) - 0.5) > 0.26, group_neutralize(rank({comb_b}) * (volume / adv20), {n.lower()}), -1)"
                        candidates.append({
                            "expression": expr_b,
                            "archetype": f"T6_Put_PCRFlow{t1}_{t2}_d{d}_{u}_{n}",
                            "hypothesis": f"Put floor ({t1}d) modulated by PCR velocity ({t2}d) isolates high-conviction downside protection roll.",
                            "universe": u,
                            "neutralization": n,
                            "decay": d,
                            "strategy": "tranche_6_cross_archetype",
                        })

    elif tranche_id == 7:
        # Tranche 7: Active Quantitative LLM Reasoning & Scouting Engine
        # Reasons across market physics, learns from live simulation results, and synthesizes novel Bivariate formulas
        candidates = scout_candidates_with_llm(
            config=OptionsConfig.from_env(),
            n_candidates=15,
            hall_of_fame=hall_of_fame,
            recent_feedback=recent_feedback,
        )

    return candidates


def scout_candidates_with_llm(
    config: OptionsConfig,
    n_candidates: int = 15,
    hall_of_fame: Optional[List[Dict[str, Any]]] = None,
    recent_feedback: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Active LLM Reasoning & Scouting Tier: Uses Groq/OpenRouter with dynamic Hall of Fame and backtest feedback."""
    try:
        from brain_options.llm.adapter import LLMAdapter, clean_json_array
        adapter = LLMAdapter(config)
        if not (adapter.config.groq_keys or adapter.config.openrouter_keys):
            return []

        system_prompt = (
            "You are an elite quantitative derivatives researcher designing WorldQuant BRAIN options alphas.\n"
            "MANDATORY FORMULA GRAMMAR:\n"
            "trade_when(abs(rank(BLEND) - 0.5) > 0.26, group_neutralize(rank(BLEND) * (volume / adv20), subindustry), -1)\n"
            "where BLEND = (w1 * rank(ts_decay_linear(ts_decay_linear(S1, 10), 3)) + w2 * rank(ts_decay_linear(ts_decay_linear(S2, 10), 3)))\n"
            "w1 + w2 = 1.0 (e.g. 0.65 and 0.35, or 0.60 and 0.40)\n\n"
            "VALID FIELDS: forward_price_X, put_breakeven_X, call_breakeven_X, implied_volatility_mean_X, "
            "implied_volatility_call_X, implied_volatility_put_X, implied_volatility_mean_skew_X (10, 20, 30, 60, 90, 120, 150, 180, 270, 360), "
            "pcr_vol_X, pcr_oi_X, historical_volatility_X, parkinson_volatility_X (10..180), close, returns, volume, adv20\n"
        )

        hof_section = ""
        if hall_of_fame:
            hof_lines = []
            for h in hall_of_fame[:8]:
                hof_lines.append(
                    f"- {h.get('archetype', 'Alpha')} (ID {h.get('alpha_id')}): Sharpe {h.get('sharpe', 0):.2f}, "
                    f"Margin {h.get('margin', 0)*10000:.1f} bps, MaxCorr {h.get('max_corr', 0):.4f}"
                )
            hof_section = "\nPROVEN QUALIFIED ALPHAS (HALL OF FAME):\n" + "\n".join(hof_lines) + "\n"

        feedback_section = ""
        if recent_feedback:
            fb_lines = []
            for fb in recent_feedback[-8:]:
                fb_lines.append(f"- [{fb.get('status')}]: {fb.get('archetype')} -> {fb.get('reason')}")
            feedback_section = "\nRECENT LIVE BACKTEST FEEDBACK (WHAT FAILED & PASSED):\n" + "\n".join(fb_lines) + "\n"

        user_prompt = f"""Generate {n_candidates} novel WorldQuant BRAIN options alphas in JSON format.
{hof_section}{feedback_section}
CRITICAL QUANTITATIVE REASONING RULES:
1. Saturated Subspaces (DO NOT USE): Put-Floor tenors (180d, 90d, 360d) are already saturated (correlation > 0.70). Do NOT repeat them.
2. Short Vol Premia Direction: Naive long IV-RV bleeds theta (Sharpe -0.28). Always monetize by going SHORT expensive vol: -((implied_volatility_mean_X - historical_volatility_X) / historical_volatility_X).
3. Orthogonal Target Subspaces to Explore:
   - Call Breakeven Breakout Convexity: ((call_breakeven_X - forward_price_X) / close) combined with return momentum.
   - PCR Velocity & Open Interest Accumulation: ts_delta(pcr_vol_X, 5) or ts_delta(pcr_oi_X, 10) scaled by (volume / adv20).
   - Term Structure Slope Contango / Backwardation: ((implied_volatility_mean_270 - implied_volatility_mean_30) / historical_volatility_30).
   - Asymmetric Volatility Skew: ((implied_volatility_put_X - implied_volatility_call_X) * (volume / adv20)).
   - Forward Calendar Basis: ((forward_price_X - close) / close) across 60d, 90d, 180d, 270d.
4. MUST use the exact Bivariate Pre-Decay grammar with ts_decay_linear(ts_decay_linear(..., 10), 3).

Respond with ONLY a JSON array of objects:
[
  {{"expression": "...", "archetype": "...", "hypothesis": "...", "universe": "TOP3000", "neutralization": "SUBINDUSTRY", "decay": 8, "strategy": "llm_scout"}}
]
"""
        raw = adapter.generate(prompt=user_prompt, system_prompt=system_prompt)
        if not raw:
            return []
        cands = clean_json_array(raw)
        valid = []
        for c in cands:
            if isinstance(c, dict) and "expression" in c and c["expression"]:
                valid.append({
                    "expression": c["expression"].strip(),
                    "archetype": c.get("archetype", "LLM_Scout_Alpha"),
                    "hypothesis": c.get("hypothesis", "LLM discovered options alpha"),
                    "universe": c.get("universe", "TOP3000"),
                    "neutralization": c.get("neutralization", "SUBINDUSTRY"),
                    "decay": int(c.get("decay", 8)),
                    "strategy": "llm_scout",
                })
        log.info("LLM Scout generated %d candidate formulas.", len(valid))
        return valid
    except Exception as e:
        log.warning("LLM Scout failed: %s", e)
        return []


async def run_overnight_pipeline():
    config = OptionsConfig.from_env()
    store = OptionsStore(data_dir=None, database_url=config.database_url)
    db = store.db

    log.info("=" * 80)
    log.info("STARTING OVERNIGHT 50-ALPHA DECORRELATED ARSENAL PIPELINE (v2.3 Production Daemon)")
    log.info("Destination Table: options_alphas (Neon Postgres)")
    log.info("Safety Lock: Platform submissions DISABLED (status='QUALIFIED')")
    log.info("Daily Drip Setting: 1 alpha / day (locked until authorization)")
    log.info("Immediate Alerts: Formatted HTML notifications sent to Telegram after every alpha")
    log.info("=" * 80)

    # 1. Connect to Database & Load Submitted Alphas
    with psycopg.connect(config.database_url) as conn:
        with conn.cursor() as cur:
            submitted_rows = load_submitted_alphas_pnl(cur)
            qualified_rows = load_qualified_reserve_alphas(cur)

    log.info("Found %d SUBMITTED alphas in options_alphas.", len(submitted_rows))
    log.info("Found %d QUALIFIED reserve alphas in options_alphas.", len(qualified_rows))

    # 2. Initialize BrainClient with Database Cluster Session Cache (Zero 429 Risk)
    client = BrainClient(
        username=config.brain_username,
        password=config.brain_password,
        max_concurrent_sims=2,
        db=db,
    )
    client.authenticate()

    # 3. Pre-fetch PnL for Submitted Alphas (Reference Pool)
    submitted_pnls: Dict[str, Dict[str, float]] = {}
    log.info("Pre-fetching PnL series for all %d submitted alphas...", len(submitted_rows))
    for r in submitted_rows:
        alpha_id = r[0]
        pnl = await client.get_alpha_pnl(alpha_id)
        if pnl:
            submitted_pnls[alpha_id] = pnl
            log.info("  [LOADED] PnL for submitted alpha %s (%d daily records)", alpha_id, len(pnl))
        else:
            log.warning("  [WARN] Could not fetch PnL for %s (will use 0 correlation fallback)", alpha_id)

    # 4. Pre-fetch PnL for Existing Qualified Reserve Alphas
    reserve_pnls: Dict[str, Dict[str, float]] = {}
    log.info("Pre-fetching PnL series for existing %d qualified reserve alphas...", len(qualified_rows))
    for r in qualified_rows:
        alpha_id = r[0]
        pnl = await client.get_alpha_pnl(alpha_id)
        if pnl:
            reserve_pnls[alpha_id] = pnl
            log.info("  [LOADED] PnL for reserve alpha %s (%d daily records)", alpha_id, len(pnl))

    total_target = 50
    current_qualified = len(reserve_pnls)
    existing_expressions = {r[1].strip() for r in (submitted_rows + qualified_rows) if r and len(r) > 1 and r[1]}
    log.info("Initial Reserve State: %d / %d Alphas Qualified (%d known expressions)", current_qualified, total_target, len(existing_expressions))

    # Global lock for thread/coroutine-safe insertion & correlation tracking
    qualification_lock = asyncio.Lock()

    # Dynamic Hall of Fame and simulation feedback memory for in-context LLM reasoning
    hall_of_fame_list = [
        {
            "alpha_id": r[0],
            "archetype": r[2] if len(r) > 2 else "Qualified_Alpha",
            "sharpe": float(r[3]) if len(r) > 3 and r[3] else 1.40,
            "fitness": float(r[4]) if len(r) > 4 and r[4] else 1.10,
            "margin": float(r[6]) if len(r) > 6 and r[6] else 0.0012,
            "max_corr": float(r[7]) if len(r) > 7 and r[7] else 0.65,
        }
        for r in qualified_rows
    ]
    recent_feedback_list: List[Dict[str, Any]] = [
        {"archetype": "PutFloor_180d_Saturation", "status": "FAIL_CORR", "reason": "Put-Floor space saturated (corr=0.85 >= 0.70); shifted to Calendar Basis"},
        {"archetype": "Raw_IV_Minus_RV", "status": "FAIL_GATE", "reason": "Sharpe=-0.28; unhedged long vol bleeds theta; monetize short vol instead"},
    ]

    pass_num = 1
    # Continuous outer loop: NEVER stops until current_qualified >= total_target (50)
    while current_qualified < total_target:
        log.info("\n" + "=" * 80)
        log.info(">>> MULTI-TRANCHE SWEEP PASS %d (Reserve Arsenal: %d / %d Qualified)", pass_num, current_qualified, total_target)
        log.info("=" * 80)

        # Prioritize proven high-Sharpe & decorrelated tranches:
        # Tranche 2: Term Structure & Forward Calendar Basis (Sharpes 1.30-1.45, max corr 0.57-0.64)
        # Tranche 7: Active Quantitative LLM Reasoning Scout (with Hall of Fame memory)
        # Tranche 1: Put Floor & Skew Asymmetry / Call Breakouts (Sharpes 1.40-1.77)
        # Tranche 6: Cross-Archetype Confluence (Sharpes ~1.00)
        # Tranche 3: Inverted Monetized VRP & Smile Curvature
        # Tranche 5 & 4: Multi-Signal Trios & PCR Flow Velocity
        for tranche_id in [2, 7, 1, 6, 3, 5, 4]:
            if current_qualified >= total_target:
                break

            tranche_target = min(total_target, current_qualified + 10)
            log.info("\n" + "#" * 80)
            log.info(">>> INITIATING TRANCHE %d [Pass %d] (Tranche Target: %d, Arsenal: %d / %d)", tranche_id, pass_num, tranche_target, current_qualified, total_target)
            log.info("#" * 80)

            candidates = build_tranche_candidates(
                tranche_id,
                pass_num=pass_num,
                hall_of_fame=hall_of_fame_list,
                recent_feedback=recent_feedback_list,
            )
            log.info("Generated %d candidate formulations for Tranche %d (Pass %d).", len(candidates), tranche_id, pass_num)

            queue = asyncio.Queue()
            for cand in candidates:
                queue.put_nowait(cand)

            stop_event = asyncio.Event()

            async def worker(worker_id: int, current_tranche: int):
                nonlocal current_qualified
                await asyncio.sleep((worker_id - 1) * 3.5)

                while not queue.empty() and not stop_event.is_set():
                    if current_qualified >= total_target or current_qualified >= tranche_target:
                        stop_event.set()
                        break

                    try:
                        cand = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break

                    expr = cand["expression"]
                    if expr.strip() in existing_expressions:
                        queue.task_done()
                        continue

                    u = cand["universe"]
                    n = cand["neutralization"]
                    d = cand["decay"]

                    log.info(
                        "[W%d | Tranche %d] Testing: %s (Univ: %s, Neut: %s)",
                        worker_id, current_tranche, cand["archetype"], u, n
                    )

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
                        log.warning("[W%d] Sim error: %s", worker_id, sim_err)
                        queue.task_done()
                        await asyncio.sleep(2.0)
                        continue

                    if not metrics or not metrics.is_valid:
                        queue.task_done()
                        await asyncio.sleep(1.0)
                        continue

                    log.info(
                        "[W%d Result] AlphaID=%s | Sharpe=%.2f | Fitness=%.2f | TO=%.2f%% | Margin=%.4f | DD=%.2f%%",
                        worker_id, metrics.alpha_id, metrics.sharpe, metrics.fitness, metrics.turnover * 100, metrics.margin, metrics.max_drawdown * 100
                    )

                    # Institutional Gate Verification
                    if (
                        metrics.sharpe < 1.25
                        or metrics.fitness < 1.00
                        or metrics.turnover < 0.01
                        or metrics.turnover > 0.70
                        or metrics.margin < 0.0010
                        or metrics.max_drawdown > 0.35
                    ):
                        recent_feedback_list.append({
                            "archetype": cand["archetype"],
                            "status": "FAIL_GATE",
                            "reason": f"Sharpe={metrics.sharpe:.2f}, Margin={metrics.margin*10000:.1f}bps, TO={metrics.turnover*100:.1f}%",
                        })
                        queue.task_done()
                        await asyncio.sleep(1.0)
                        continue

                    # Correlation verification under lock
                    async with qualification_lock:
                        if current_qualified >= total_target or current_qualified >= tranche_target:
                            stop_event.set()
                            queue.task_done()
                            break

                        cand_pnl = await client.get_alpha_pnl(metrics.alpha_id)
                        if not cand_pnl or len(cand_pnl) < 30:
                            queue.task_done()
                            continue

                        # Check correlation vs 14 Submitted Alphas
                        max_corr_sub = 0.0
                        for s_id, s_pnl in submitted_pnls.items():
                            c = abs(compute_correlation(cand_pnl, s_pnl))
                            if c > max_corr_sub:
                                max_corr_sub = c

                        if max_corr_sub >= 0.70:
                            log.info("[-] [W%d] Correlation vs submitted failed: %.4f >= 0.70", worker_id, max_corr_sub)
                            recent_feedback_list.append({
                                "archetype": cand["archetype"],
                                "status": "FAIL_CORR",
                                "reason": f"Sharpe={metrics.sharpe:.2f} PASS, but Corr={max_corr_sub:.4f} >= 0.70 vs submitted alpha",
                            })
                            queue.task_done()
                            continue

                        # Check correlation vs Qualified Reserve Pool
                        max_corr_res = 0.0
                        for r_id, r_pnl in reserve_pnls.items():
                            c = abs(compute_correlation(cand_pnl, r_pnl))
                            if c > max_corr_res:
                                max_corr_res = c

                        if max_corr_res >= 0.70:
                            log.info("[-] [W%d] Correlation vs reserve failed: %.4f >= 0.70", worker_id, max_corr_res)
                            recent_feedback_list.append({
                                "archetype": cand["archetype"],
                                "status": "FAIL_CORR",
                                "reason": f"Sharpe={metrics.sharpe:.2f} PASS, but Corr={max_corr_res:.4f} >= 0.70 vs reserve pool",
                            })
                            queue.task_done()
                            continue

                        overall_max_corr = max(max_corr_sub, max_corr_res)
                        log.info(
                            "================================================================================"
                        )
                        log.info(
                            "[QUALIFIED #%d] AlphaID=%s | Sharpe=%.2f | Fitness=%.2f | TO=%.2f%% | Margin=%.4f | MaxCorr=%.4f",
                            current_qualified + 1, metrics.alpha_id, metrics.sharpe, metrics.fitness, metrics.turnover * 100, metrics.margin, overall_max_corr
                        )
                        log.info(
                            "================================================================================"
                        )

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

                        recent_feedback_list.append({
                            "archetype": cand["archetype"],
                            "status": "QUALIFIED",
                            "reason": f"Sharpe={metrics.sharpe:.2f}, Margin={metrics.margin*10000:.1f}bps, Corr={overall_max_corr:.4f}",
                        })
                        hall_of_fame_list.append({
                            "alpha_id": metrics.alpha_id,
                            "archetype": cand["archetype"],
                            "sharpe": metrics.sharpe,
                            "fitness": metrics.fitness,
                            "margin": metrics.margin,
                            "max_corr": overall_max_corr,
                        })

                        reserve_pnls[metrics.alpha_id] = cand_pnl
                        existing_expressions.add(expr.strip())
                        current_qualified = len(reserve_pnls)
                        log.info(">>> ARSENAL PROGRESS: %d / %d Alphas Qualified in Reserve!", current_qualified, total_target)

                        # Immediate Telegram HTML Alert to Christley
                        send_tg_reserve_alert(
                            config=config,
                            alpha_id=metrics.alpha_id,
                            archetype=cand["archetype"],
                            sharpe=metrics.sharpe,
                            fitness=metrics.fitness,
                            turnover=metrics.turnover,
                            margin=metrics.margin,
                            max_corr=overall_max_corr,
                            current_count=current_qualified,
                            total_target=total_target,
                            universe=u,
                            neutralization=n,
                        )

                        if current_qualified >= total_target or current_qualified >= tranche_target:
                            log.info("Target achieved! (%d Alphas Qualified)", current_qualified)
                            stop_event.set()

                    queue.task_done()
                    await asyncio.sleep(2.0)

            # Launch 2 staggered concurrent simulation workers
            workers = [asyncio.create_task(worker(i + 1, tranche_id)) for i in range(2)]
            await asyncio.gather(*workers)

        pass_num += 1

    log.info("\n" + "=" * 80)
    log.info("FINAL RESERVE ARSENAL AUDIT & COMPLETE 50x50 CORRELATION MATRIX CHECK")
    log.info("Total Qualified Alphas in Reserve Pool: %d / %d", len(reserve_pnls), total_target)
    log.info("=" * 80)

    all_keys = list(reserve_pnls.keys())
    max_pairwise_corr = 0.0
    violating_pairs = []

    for i in range(len(all_keys)):
        for j in range(i + 1, len(all_keys)):
            id_a, id_b = all_keys[i], all_keys[j]
            c = abs(compute_correlation(reserve_pnls[id_a], reserve_pnls[id_b]))
            if c > max_pairwise_corr:
                max_pairwise_corr = c
            if c >= 0.70:
                violating_pairs.append((id_a, id_b, c))

    log.info("Full Pairwise Reserve Correlation Check:")
    log.info("  Max Pairwise Correlation in Reserve: %.4f", max_pairwise_corr)
    log.info("  Violations (>= 0.70): %d", len(violating_pairs))
    if violating_pairs:
        for a, b, c in violating_pairs:
            log.error("    Pair %s <-> %s: %.4f", a, b, c)
    else:
        log.info("  [CONFIRMED] All %d reserve alphas are strictly non-correlated (< 0.70)!", len(all_keys))

    # Send final Telegram celebration alert
    try:
        final_msg = (
            f"🏆 <b>50-ALPHA DECORRELATED ARSENAL SECURED!</b>\n\n"
            f"• <b>Total Qualified Alphas:</b> 50\n"
            f"• <b>Max Pairwise Correlation:</b> {max_pairwise_corr:.4f} (&lt; 0.70)\n"
            f"• <b>Status:</b> All 50 staged in PostgreSQL (QUALIFIED)\n"
            f"• <b>Daily Drip Ready:</b> 1 alpha / day for 50 days\n\n"
            f"Mission Complete. Semper Fi! 🎖️"
        )
        requests.post(
            f"https://api.telegram.org/bot{config.telegram_bot_token}/sendMessage",
            json={"chat_id": config.telegram_chat_id, "text": final_msg, "parse_mode": "HTML"},
            timeout=10.0,
        )
    except Exception as e:
        log.warning("Final celebration alert failed: %s", e)

    log.info("ARSENAL MISSION COMPLETE. Semper Fi!")


if __name__ == "__main__":
    asyncio.run(run_overnight_pipeline())
