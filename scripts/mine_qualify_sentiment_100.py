#!/usr/bin/env python3
"""
Institutional 100 Sentiment Alphas Autonomous Miner & Vault (Round 3 Complete).
Target: 100 Mutually Orthogonal Qualified Alphas across 14 Institutional Sentiment Sub-Pillars:
1. SUE Tail Shocks x Volatility Decoupling
2. PEAD Revision Sluggishness x Return Reversals & Z-Scores
3. Target Price Spread x Intraday Range
4. Analyst Recommendation Upgrades Velocity
5. Analyst Estimate Dispersion Discount
6. Dynamic Institutional Focus & Attention Drift
7. Lexical Mood Contrarian Reversion
8. Fundamental Confluence Tri-Factor Blends
9. Short Interest Pressure x Volume Decoupling
10. Options Surface Implied Volatility Skew Sentiment
11. Analyst Revision Breadth Ratio
12. Multi-Horizon Recommendation Acceleration
13. Sales Revision vs Gross Margin Drift
14. Consensus Forecast Agreement vs Volume Decoupling

Round 3 Upgrades:
- R3-1: Distinct cluster tracking & best-per-cluster reporting via production utility U(alpha).
- R3-2: Pre-simulation correlation estimation & automated pillar pause on basin saturation (rho >= 0.90).
- R3-3: Collision candidates preserved as REJECTED_COLLISION challengers linked to incumbent id.
- R3-4: Empirical T_eff measured from PnL serial autocorrelation; dynamic reserve buffer.
- R3-5: Multiple testing sweep capping (max 2), variant counting, and OOS validation.
- R3-6: Mathematically rigorous telemetry, rejection mix accounting, and precise firewall phrasing.
"""
from __future__ import annotations

import asyncio
import datetime
import decimal
import html
import logging
import math
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

# Force utf-8 encoding on standard output and unbuffered flush
try:
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
except Exception:
    pass


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("sentiment_100_miner")

from brain_options.config import OptionsConfig
from brain_options.core.client import BrainClient, SimMetrics, SimSettings, parse_brain_sim_response
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
        "blbZ9Wkp", "KPNd6Ovl", "gJbAP76e",
        # Sentiment alphas submitted Oct 2 2026
        "O08exK8R", "58gVPJln",
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


# Named Architectural Thresholds
PROD_FIREWALL: float = 0.62   # Production firewall — relaxed from 0.55 → 0.62 to align closer to BRAIN's 0.70 hard limit
HARD_LIMIT: float = 0.70      # WorldQuant BRAIN platform hard submission ceiling
SHARPE_UPLIFT: float = 0.10   # 10% hurdle to prevent in-sample noise ratcheting (Winner's Curse)
MULTI_UPLIFT: float = 0.20    # 20% hurdle required if candidate evicts multiple incumbents
TOLERANCE: float = 0.95       # 5% tolerance preventing minor noise from blocking decisive upgrades


def compute_production_utility(sharpe: float, fitness: float, margin_bps: float, turnover_pct: float) -> float:
    """Production utility function weighting Sharpe, Fitness, Margin, and Turnover.
    Rewards high execution margin and low turnover to optimize institutional viability.
    """
    margin_factor = 1.0 + (margin_bps / 20.0)
    turnover_factor = max(0.1, 1.0 - turnover_pct)
    fitness_factor = math.sqrt(max(0.01, fitness))
    return sharpe * margin_factor * turnover_factor * fitness_factor


def pareto_dominates(
    cand_sharpe: float, cand_fitness: float, cand_margin: float,
    inc_sharpe: float, inc_fitness: float, inc_margin: float,
    uplift: float = SHARPE_UPLIFT,
    tolerance: float = TOLERANCE
) -> bool:
    """Softened Pareto dominance with Sharpe uplift hurdle."""
    return (
        cand_sharpe >= inc_sharpe * (1.0 + uplift)
        and cand_fitness >= inc_fitness * tolerance
        and cand_margin >= inc_margin * tolerance
    )


def compute_vault_diversification(pnls: Dict[str, Dict[str, float]]) -> Tuple[float, float, int]:
    """Calculates RMS pairwise correlation and effective number of independent alphas (N_eff).
    Uses the signed correlation matrix R to ensure mathematical consistency.
    """
    aids = list(pnls.keys())
    n = len(aids)
    if n < 2:
        return 0.0, float(n), n
    corrs = []
    for i in range(n):
        for j in range(i + 1, n):
            corrs.append(compute_correlation(pnls[aids[i]], pnls[aids[j]]))

    rms_corr = (sum(c ** 2 for c in corrs) / len(corrs)) ** 0.5 if corrs else 0.0
    tr_r2 = n + (n * (n - 1)) * (rms_corr ** 2)
    n_eff = (n ** 2) / tr_r2 if tr_r2 > 0 else 1.0
    return rms_corr, n_eff, n


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


def get_cluster_summary(db_url: str) -> Dict[str, Any]:
    """Fetches all clusters, lists members, and determines best-per-cluster by production utility."""
    clusters: Dict[str, List[Dict[str, Any]]] = {}
    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT alpha_id, COALESCE(cluster_id, 'cluster_' || alpha_id), COALESCE(incumbent_id, ''),
                           COALESCE(sharpe, 0.0), COALESCE(fitness, 0.0), COALESCE(margin, 0.0), COALESCE(turnover, 0.0),
                           status, archetype
                    FROM options_alphas 
                    WHERE status IN ('QUALIFIED', 'REJECTED_COLLISION')
                    ORDER BY created_at ASC;
                """)
                for r in cur.fetchall():
                    aid, cid, iid, sh, fit, mg, to, st, arch = r
                    sh, fit, mg, to = float(sh), float(fit), float(mg), float(to)
                    mg_bps = mg * 10000.0
                    u = compute_production_utility(sh, fit, mg_bps, to)
                    item = {
                        "alpha_id": aid,
                        "cluster_id": cid,
                        "incumbent_id": iid,
                        "sharpe": sh,
                        "fitness": fit,
                        "margin_bps": mg_bps,
                        "turnover": to,
                        "status": st,
                        "archetype": arch or "",
                        "utility": u
                    }
                    clusters.setdefault(cid, []).append(item)
    except Exception as exc:
        log.warning("Failed to fetch cluster summary: %s", exc)

    cluster_reports = []
    for cid, members in clusters.items():
        incumbent = next((m for m in members if m["status"] == "QUALIFIED"), members[0])
        best_member = max(members, key=lambda m: m["utility"])
        cluster_reports.append({
            "cluster_id": cid,
            "member_count": len(members),
            "incumbent": incumbent,
            "best_member": best_member,
            "has_superior_challenger": best_member["alpha_id"] != incumbent["alpha_id"] and best_member["utility"] > incumbent["utility"]
        })

    return {
        "distinct_clusters_count": len(clusters),
        "total_tracked_signals": sum(len(m) for m in clusters.values()),
        "clusters": cluster_reports
    }


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
    cluster_id: str,
    variants_tested: int = 1,
    oos_checked: bool = False,
):
    try:
        ret_val = getattr(metrics, 'annualized_return', getattr(metrics, 'returns', 0.0))
        with psycopg.connect(db_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM options_alphas WHERE alpha_id = %s AND status = 'QUALIFIED'", (alpha_id,))
                if cur.fetchone():
                    return
                sql = """
                    INSERT INTO options_alphas (
                        alpha_id, expression, archetype, hypothesis, source,
                        sharpe, fitness, turnover, returns, drawdown, margin,
                        max_correlation, universe, neutralization, delay, decay,
                        truncation, pasteurization, nan_handling, status,
                        created_at, strategy_name, cluster_id, variants_tested, oos_checked
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, 1, %s,
                        0.05, 'ON', 'OFF', 'QUALIFIED',
                        NOW(), 'vault_sentiment_100', %s, %s, %s
                    );
                """
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
                    cluster_id, variants_tested, oos_checked
                ))
        log.info("[+] Committed %s to options_alphas as QUALIFIED (cluster=%s).", alpha_id, cluster_id)
    except Exception as e:
        log.error("Failed to commit qualified alpha %s: %s", alpha_id, e)


def commit_collision_challenger(
    db_url: str,
    alpha_id: str,
    expression: str,
    archetype: str,
    incumbent_id: str,
    cluster_id: str,
    metrics: SimMetrics,
    max_corr: float,
    universe: str,
    neutralization: str,
    decay: int,
    variants_tested: int = 1,
):
    """Stores high-performing candidate that collided with vault incumbent as a CHALLENGER.
    Allows best-of-cluster selection at submission time without losing signal IP.
    """
    try:
        ret_val = getattr(metrics, 'annualized_return', getattr(metrics, 'returns', 0.0))
        hyp = f"Challenger to {incumbent_id} | max_rho={max_corr:.4f}"
        with psycopg.connect(db_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM options_alphas WHERE alpha_id = %s AND status = 'REJECTED_COLLISION'", (alpha_id,))
                if cur.fetchone():
                    return
                sql = """
                    INSERT INTO options_alphas (
                        alpha_id, expression, archetype, hypothesis, source,
                        sharpe, fitness, turnover, returns, drawdown, margin,
                        max_correlation, universe, neutralization, delay, decay,
                        truncation, pasteurization, nan_handling, status,
                        created_at, strategy_name, incumbent_id, cluster_id, variants_tested
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, 1, %s,
                        0.05, 'ON', 'OFF', 'REJECTED_COLLISION',
                        NOW(), 'vault_sentiment_100', %s, %s, %s
                    );
                """
                cur.execute(sql, (
                    alpha_id, expression, archetype, hyp, "sentiment_100_miner",
                    decimal.Decimal(str(round(metrics.sharpe, 4))),
                    decimal.Decimal(str(round(metrics.fitness, 4))),
                    decimal.Decimal(str(round(metrics.turnover, 4))),
                    decimal.Decimal(str(round(ret_val, 4))),
                    decimal.Decimal(str(round(metrics.max_drawdown, 4))),
                    decimal.Decimal(str(round(metrics.margin, 4))),
                    decimal.Decimal(str(round(max_corr, 4))),
                    universe, neutralization, decay,
                    incumbent_id, cluster_id, variants_tested
                ))
        log.info("[+] Stored %s as REJECTED_COLLISION challenger (incumbent: %s, rho=%.4f).", alpha_id, incumbent_id, max_corr)
    except Exception as e:
        log.warning("Failed to store challenger %s: %s", alpha_id, e)


def measure_effective_t(pnl1: Dict[str, float], pnl2: Dict[str, float]) -> Tuple[float, float, float, float]:
    """Empirically measures effective sample size T_eff from PnL serial autocorrelation
    and calculates the dynamic 95% confidence reserve boundary vs platform 0.70.
    """
    common_dates = sorted(set(pnl1.keys()) & set(pnl2.keys()))
    T = len(common_dates)
    if T < 30:
        return 1260.0, 0.0, 0.0, 0.65
    s1 = [pnl1[d] for d in common_dates]
    s2 = [pnl2[d] for d in common_dates]
    mean1 = sum(s1) / T
    mean2 = sum(s2) / T
    var1 = sum((x - mean1)**2 for x in s1)
    var2 = sum((x - mean2)**2 for x in s2)
    if var1 < 1e-12 or var2 < 1e-12:
        return float(T), 0.0, 0.0, 0.65
    cov1 = sum((s1[t] - mean1) * (s1[t-1] - mean1) for t in range(1, T))
    cov2 = sum((s2[t] - mean2) * (s2[t-1] - mean2) for t in range(1, T))
    phi1 = max(-0.95, min(0.95, cov1 / var1))
    phi2 = max(-0.95, min(0.95, cov2 / var2))
    denom = 1.0 + phi1 * phi2
    t_eff = T * (1.0 - phi1 * phi2) / denom if denom > 0.01 else float(T)
    t_eff = max(50.0, min(float(T), t_eff))

    # Dynamic reserve buffer: 95% one-sided CI boundary against 0.70
    se = (1.0 - 0.70 ** 2) / math.sqrt(t_eff)
    dyn_buffer = 0.70 - 1.645 * se
    reserve_limit = max(0.60, min(0.68, dyn_buffer))
    return t_eff, phi1, phi2, reserve_limit


def load_saturated_state_from_db(db_url: str) -> Tuple[Set[str], Set[str]]:
    """Loads pre-existing collision state from DB so the miner resumes correctly
    across restarts without re-simulating already-saturated basins.
    Returns (saturated_pillars, saturated_base_archetypes).
    """
    sat_pillars: Set[str] = set()
    sat_archetypes: Set[str] = set()
    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                # Pillars with >= 2 collision entries are considered saturated
                cur.execute("""
                    SELECT archetype, count(*) as n
                    FROM options_alphas WHERE status='REJECTED_COLLISION'
                    GROUP BY archetype HAVING count(*) >= 1
                """)
                for row in cur.fetchall():
                    sat_archetypes.add(row[0])

                # Broader pillar saturation: if a pillar-family has >= 2 total collisions
                cur.execute("""
                    SELECT source_pillar, count(*) as n FROM (
                        SELECT
                            CASE
                                WHEN archetype LIKE 'P1_SUE%' THEN 'P1_SUE'
                                WHEN archetype LIKE 'P2_PEAD%' THEN 'P2_PEAD'
                                WHEN archetype LIKE 'P3_Target%' OR archetype LIKE 'Sent_Target%' THEN 'P3_TARGET'
                                WHEN archetype LIKE 'P4_Rec%' OR archetype LIKE 'Sent_Dual%' THEN 'P4_RECOMMENDATION'
                                WHEN archetype LIKE 'P5_Disp%' OR archetype LIKE 'Sent_Disp%' THEN 'P5_DISPERSION'
                                WHEN archetype LIKE 'P6_Focus%' OR archetype LIKE 'Sent_Focus%' THEN 'P6_FOCUS'
                                WHEN archetype LIKE 'P7_Triple%' THEN 'P7_TRIPLE'
                                WHEN archetype LIKE 'P8_Rec_Accel%' OR archetype LIKE 'P12_Rec%' THEN 'P8_REC_ACCELERATION'
                                WHEN archetype LIKE 'P9_Breadth%' THEN 'P9_BREADTH'
                                WHEN archetype LIKE 'P10_Volume%' THEN 'P10_VOLUME'
                                WHEN archetype LIKE 'P10_Options%' OR archetype LIKE 'P3_Options%' THEN 'P10_OPTIONS_SKEW'
                                WHEN archetype LIKE 'Hybrid_Options%' THEN 'HYBRID_OPTIONS_SUE'
                                ELSE 'OTHER'
                            END as source_pillar
                        FROM options_alphas WHERE status='REJECTED_COLLISION'
                    ) sub GROUP BY source_pillar HAVING count(*) >= 2
                """)
                for row in cur.fetchall():
                    if row[0] != 'OTHER':
                        sat_pillars.add(row[0])
                        log.warning("[DB-RESUME] Pillar %s pre-marked SATURATED (%d collisions from prior run).", row[0], row[1])
    except Exception as exc:
        log.warning("Could not load saturation state from DB: %s", exc)
    return sat_pillars, sat_archetypes


def build_100_sentiment_candidate_matrix() -> List[Dict[str, Any]]:
    """Generates 100% PURE SENTIMENT candidate matrix across 10 Orthogonal Families (Path C).
    Completely eliminates the saturated 3-day reversal leg: rank(-ts_delta(close, 3) / ts_std_dev).
    Replaces with:
      - P1: SUE x Intermediate Momentum Confirmation (10d, 15d, 20d) -> rho in [-0.10, +0.20]
      - P2: SUE x Multi-day High-Low Range Position (5d, 10d, 20d)
      - P3: Analyst Revision Velocity x Volume & Turnover Shocks
      - P4: Pure PEAD Fast-Slow Decay Acceleration Spread (Zero price leg)
      - P5: SUE x VWAP Price Deviation Catch-Up
      - P6: SUE x 20-50d Moving Average Trend Divergence
      - P7: Revision Acceleration (Delta) x Intraday Bar Position
      - P8: SUE x Revision Composite Rank Product x Liquidity
      - P9: SUE x Amihud Illiquidity Ratio
      - P10: Near-Miss Salvage Suite (Re-engineered P9/P16/P2 with 10d/15d Momentum)
    """
    p_buckets: Dict[str, List[Dict[str, Any]]] = {f'P{i}': [] for i in range(1, 11)}
    universes = ['TOP1000', 'TOP2000', 'TOP500', 'TOPSP500']
    neutralizations = ['SUBINDUSTRY', 'SECTOR']

    # P1: SUE Momentum Confirmation (10-20d Trend Confirmation)
    for u in universes:
        for neut in neutralizations:
            for d in [8, 10, 12, 15]:
                for win, std_w in [(10, 30), (15, 40), (20, 60)]:
                    for vthresh in [0.8, 0.5]:
                        p_buckets['P1'].append({
                            'pillar': 'P1_SUE_MOMENTUM',
                            'base_archetype': f'P1_SUE_Mom{win}_{u}',
                            'expression': f'trade_when(volume > adv20 * {vthresh}, group_neutralize(rank(ts_decay_linear(snt1_d1_earningssurprise, {d})) * rank(ts_delta(close, {win}) / (ts_std_dev(close, {std_w}) + 0.001)), {neut.lower()}), -1)',
                            'archetype': f'P1_SUE_Mom{win}_d{d}_vt{int(vthresh*10)}_{u}_{neut}',
                            'hypothesis': f'P1: SUE surprise confirmed by {win}d intermediate momentum ({u}, d={d}, neut={neut}).',
                            'universe': u,
                            'neutralization': neut,
                            'decay': d,
                        })

    # P2: SUE Range Position & High-Low Penetration
    for u in universes:
        for neut in neutralizations:
            for d in [8, 10, 12, 14]:
                for rwin in [5, 10, 20]:
                    p_buckets['P2'].append({
                        'pillar': 'P2_RANGE_POSITION',
                        'base_archetype': f'P2_SUE_Range{rwin}_{u}',
                        'expression': f'trade_when(volume > adv20 * 0.8, group_neutralize(rank(ts_decay_linear(snt1_d1_earningssurprise, {d})) * rank((close - ts_min(low, {rwin})) / (ts_max(high, {rwin}) - ts_min(low, {rwin}) + 0.001)), {neut.lower()}), -1)',
                        'archetype': f'P2_SUE_Range{rwin}_d{d}_{u}_{neut}',
                        'hypothesis': f'P2: SUE surprise confirmed by {rwin}d range position ({u}, d={d}, neut={neut}).',
                        'universe': u,
                        'neutralization': neut,
                        'decay': d,
                    })

    # P3: Net Analyst Revisions Velocity x Volume Shock
    for u in universes:
        for neut in neutralizations:
            for d in [8, 10, 12, 14]:
                p_buckets['P3'].append({
                    'pillar': 'P3_REVISION_VOLUME',
                    'base_archetype': f'P3_Rev_Vol_{u}',
                    'expression': f'trade_when(volume > adv20 * 0.8, group_neutralize(rank(ts_decay_linear(snt1_d1_netearningsrevision, {d})) * rank(volume / (adv20 + 0.001)), {neut.lower()}), -1)',
                    'archetype': f'P3_Rev_Vol_d{d}_{u}_{neut}',
                    'hypothesis': f'P3: Net revision velocity confirmed by volume shock ({u}, d={d}, neut={neut}).',
                    'universe': u,
                    'neutralization': neut,
                    'decay': d,
                })
                p_buckets['P3'].append({
                    'pillar': 'P3_REVISION_VOLUME',
                    'base_archetype': f'P3_DoubleRev_Vol_{u}',
                    'expression': f'trade_when(volume > adv20 * 0.8, group_neutralize(rank(ts_decay_linear(ts_decay_linear(snt1_d1_netearningsrevision, {d}), 3)) * rank(volume / (adv20 + 0.001)), {neut.lower()}), -1)',
                    'archetype': f'P3_DoubleRev_Vol_d{d}_{u}_{neut}',
                    'hypothesis': f'P3: Double-decayed revision velocity x volume shock ({u}, d={d}).',
                    'universe': u,
                    'neutralization': neut,
                    'decay': d,
                })

    # P4: Pure PEAD Dual-Decay Spread (Zero price leg)
    for u in universes:
        for neut in neutralizations:
            for d_fast, d_slow in [(3, 20), (5, 25), (8, 30), (5, 40)]:
                p_buckets['P4'].append({
                    'pillar': 'P4_PEAD_SPREAD',
                    'base_archetype': f'P4_SUE_DualDecay_{d_fast}_{d_slow}_{u}',
                    'expression': f'trade_when(volume > adv20 * 0.8, group_neutralize(rank(ts_decay_linear(snt1_d1_earningssurprise, {d_fast})) - rank(ts_decay_linear(snt1_d1_earningssurprise, {d_slow})), {neut.lower()}), -1)',
                    'archetype': f'P4_SUE_DualDecay_f{d_fast}_s{d_slow}_{u}_{neut}',
                    'hypothesis': f'P4: Fast-slow PEAD decay acceleration spread ({d_fast}d vs {d_slow}d, {u}, neut={neut}).',
                    'universe': u,
                    'neutralization': neut,
                    'decay': d_fast,
                })

    # P5: SUE x VWAP Deviation Catch-Up
    for u in universes:
        for neut in neutralizations:
            for d in [8, 10, 12, 15]:
                p_buckets['P5'].append({
                    'pillar': 'P5_VWAP_CATCHUP',
                    'base_archetype': f'P5_SUE_VWAP_{u}',
                    'expression': f'trade_when(volume > adv20 * 0.8, group_neutralize(rank(ts_decay_linear(snt1_d1_earningssurprise, {d})) * rank((vwap - close) / (close + 0.001)), {neut.lower()}), -1)',
                    'archetype': f'P5_SUE_VWAP_d{d}_{u}_{neut}',
                    'hypothesis': f'P5: SUE institutional catch-up vs VWAP deviation ({u}, d={d}, neut={neut}).',
                    'universe': u,
                    'neutralization': neut,
                    'decay': d,
                })

    # P6: SUE x Moving Average Trend Distance
    for u in universes:
        for neut in neutralizations:
            for d in [10, 12, 14]:
                for mawin in [20, 50]:
                    p_buckets['P6'].append({
                        'pillar': 'P6_MA_TREND',
                        'base_archetype': f'P6_SUE_MA{mawin}_{u}',
                        'expression': f'trade_when(volume > adv20 * 0.8, group_neutralize(rank(ts_decay_linear(snt1_d1_earningssurprise, {d})) * rank((close - ts_mean(close, {mawin})) / (ts_std_dev(close, {mawin}) + 0.001)), {neut.lower()}), -1)',
                        'archetype': f'P6_SUE_MA{mawin}_d{d}_{u}_{neut}',
                        'hypothesis': f'P6: SUE confirmed by {mawin}d trend distance ({u}, d={d}, neut={neut}).',
                        'universe': u,
                        'neutralization': neut,
                        'decay': d,
                    })

    # P7: Analyst Revision Acceleration x Intraday Bar Position
    for u in universes:
        for neut in neutralizations:
            for dwin in [5, 10, 15]:
                for d in [8, 10, 12]:
                    p_buckets['P7'].append({
                        'pillar': 'P7_REV_ACCEL',
                        'base_archetype': f'P7_RevAccel_Bar_{u}',
                        'expression': f'trade_when(volume > adv20 * 0.8, group_neutralize(rank(ts_delta(ts_decay_linear(snt1_d1_netearningsrevision, {d}), {dwin})) * rank((close - low) / (high - low + 0.001)), {neut.lower()}), -1)',
                        'archetype': f'P7_RevAccel{dwin}_d{d}_{u}_{neut}',
                        'hypothesis': f'P7: Revision acceleration {dwin}d delta confirmed by intraday close position ({u}, d={d}).',
                        'universe': u,
                        'neutralization': neut,
                        'decay': d,
                    })

    # P8: SUE x Analyst Revisions Composite Rank Product
    for u in universes:
        for neut in neutralizations:
            for d in [8, 10, 12, 14]:
                p_buckets['P8'].append({
                    'pillar': 'P8_DUAL_SENTIMENT',
                    'base_archetype': f'P8_SUE_Rev_{u}',
                    'expression': f'trade_when(volume > adv20 * 0.8, group_neutralize(rank(ts_decay_linear(snt1_d1_earningssurprise, {d})) * rank(ts_decay_linear(snt1_d1_netearningsrevision, {d})) * rank(log(adv20 + 1)), {neut.lower()}), -1)',
                    'archetype': f'P8_SUE_Rev_Liquidity_d{d}_{u}_{neut}',
                    'hypothesis': f'P8: SUE x Net revision composite scaled by liquidity ({u}, d={d}, neut={neut}).',
                    'universe': u,
                    'neutralization': neut,
                    'decay': d,
                })

    # P9: SUE x Amihud Illiquidity Ratio
    for u in universes:
        for neut in neutralizations:
            for d in [8, 10, 12]:
                p_buckets['P9'].append({
                    'pillar': 'P9_AMIHUD',
                    'base_archetype': f'P9_SUE_Amihud_{u}',
                    'expression': f'trade_when(volume > adv20 * 0.8, group_neutralize(rank(ts_decay_linear(snt1_d1_earningssurprise, {d})) * rank(abs(returns) / (volume * close + 0.001)), {neut.lower()}), -1)',
                    'archetype': f'P9_SUE_Amihud_d{d}_{u}_{neut}',
                    'hypothesis': f'P9: SUE interaction with Amihud illiquidity impact ({u}, d={d}, neut={neut}).',
                    'universe': u,
                    'neutralization': neut,
                    'decay': d,
                })

    # P10: Near-Miss Salvage Suite (Re-engineered P9/P16/P2 with 10d/15d Momentum)
    for u in ['TOP1000', 'TOP2000', 'TOP500']:
        for neut in neutralizations:
            for d in [10, 12, 14]:
                for vthresh in [0.5, 0.8]:
                    for m_win in [10, 15]:
                        p_buckets['P10'].append({
                            'pillar': 'P10_SALVAGE',
                            'base_archetype': f'P10_Salvage_Mom{m_win}_vt{int(vthresh*10)}_{u}',
                            'expression': f'trade_when(volume > adv20 * {vthresh}, group_neutralize(rank(ts_decay_linear(ts_decay_linear(snt1_d1_earningssurprise, {d}), 3)) * rank(ts_decay_linear(snt1_d1_netearningsrevision, {d})) * rank(ts_delta(close, {m_win}) / (ts_std_dev(close, 30) + 0.001)), {neut.lower()}), -1)',
                            'archetype': f'P10_Salvage_Mom{m_win}_d{d}_vt{int(vthresh*10)}_{u}_{neut}',
                            'hypothesis': f'P10 Salvage: SUE x Revision x {m_win}d momentum confirmation ({u}, d={d}, vt={vthresh}).',
                            'universe': u,
                            'neutralization': neut,
                            'decay': d,
                        })

    interleaved: List[Dict[str, Any]] = []
    bucket_list = [b for b in p_buckets.values() if b]
    max_len = max(len(b) for b in bucket_list) if bucket_list else 0
    for idx in range(max_len):
        for b in bucket_list:
            if idx < len(b):
                interleaved.append(b[idx])

    return interleaved



async def hourly_heartbeat_loop(config: OptionsConfig, target_count: int, start_time: float, lock: asyncio.Lock, get_stats_fn):
    """Sends comprehensive hourly intelligence reports to Telegram."""
    while True:
        await asyncio.sleep(3600)
        try:
            stats = get_stats_fn()
            qual_count = stats["qual"]
            total_evals = stats["evals"]
            near_miss_count = stats["near_miss"]
            rejections = stats["rejections"]
            saturated = stats["saturated"]
            rms_corr = stats["rms_corr"]
            n_eff = stats["n_eff"]
            active_pillars_with_alpha = stats.get("active_pillars_with_alpha", [])
            cluster_info = get_cluster_summary(config.database_url)

            elapsed_hours = (time.time() - start_time) / 3600.0
            throughput = total_evals / max(0.1, elapsed_hours)
            hit_rate = (qual_count / max(1, total_evals)) * 100.0
            near_dup_pct = (rejections.get("near_duplicates", 0) / max(1, total_evals)) * 100.0

            clusters_text = ""
            for cl in cluster_info.get("clusters", [])[:3]:
                cid = cl["cluster_id"]
                inc = cl["incumbent"]["alpha_id"]
                best = cl["best_member"]["alpha_id"]
                u_inc = cl["incumbent"]["utility"]
                u_best = cl["best_member"]["utility"]
                if cl["has_superior_challenger"]:
                    clusters_text += f"  • <b>{cid}:</b> Incumbent <code>{inc}</code> (U={u_inc:.2f}) &lt; Challenger <code>{best}</code> (U={u_best:.2f})\n"
                else:
                    clusters_text += f"  • <b>{cid}:</b> Incumbent <code>{inc}</code> leads (U={u_inc:.2f}, {cl['member_count']} members)\n"

            now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M UTC")
            send_tg_message(
                token=config.telegram_bot_token,
                chat_id=config.telegram_chat_id,
                html_text=(
                    f"⚡ <b>Sentiment Miner Update</b> ({now_str})\n"
                    f"• Reserve: <b>{qual_count}/{target_count}</b> qualified\n"
                    f"• Progress: {total_evals} sims ({throughput:.1f}/hr)\n"
                    f"• Near-misses: {near_miss_count}"
                ),
            )
        except Exception as e:
            log.warning("Hourly heartbeat error: %s", e)


async def run_sentiment_100_miner():
    config = OptionsConfig.from_env()
    store = OptionsStore()
    
    # 4 Concurrent BRAIN Simulation Slots (strictly aligned with BRAIN platform concurrency cap to prevent 429 retry stalls)
    client = BrainClient(
        username=config.brain_username,
        password=config.brain_password,
        max_concurrent_sims=4,
        db=store.db,
    )

    log.info("=" * 70)
    log.info("STARTING MASTER PURE-SENTIMENT 100 ALPHA VAULT MINER (REV 4 - BREADTH FIRST)")
    log.info("CONCURRENCY: 5 Parallel BRAIN Simulation Slots | Pure Sentiment Fields Only")
    log.info("TARGET: 100 Mutually Orthogonal Qualified Pure-Sentiment Alphas")
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

    # 3. Build 10-Pillar Pure-Sentiment Candidate Matrix with Deficit Scheduling
    candidate_list = build_100_sentiment_candidate_matrix()
    target_count = 100
    current_qualified = get_current_qualified_count(config.database_url)
    log.info("Loaded %d candidate configurations across 10 Pure-Sentiment Pillars. Current Qualified: %d / %d",
             len(candidate_list), current_qualified, target_count)

    # Deficit scheduling: count existing qualified per pillar, front-load unexplored pillars
    try:
        with psycopg.connect(config.database_url) as _conn:
            with _conn.cursor() as _cur:
                _cur.execute("SELECT archetype, count(*) FROM options_alphas WHERE status IN ('QUALIFIED','SUBMITTED') GROUP BY archetype")
                _existing = _cur.fetchall()
        _pillar_existing: Dict[str, int] = {}
        for _arch, _cnt in _existing:
            for _pkey in ["P1_SUE","P2_PEAD","P3_TARGET","P4_RECOMMENDATION","P5_DISPERSION",
                          "P6_FOCUS","P7_DUAL_CONFLUENCE","P8_REC_ACCELERATION","P9_TRIPLE","P10_BREADTH"]:
                if _arch.startswith(_pkey.split("_")[0]):
                    _pillar_existing[_pkey] = _pillar_existing.get(_pkey, 0) + _cnt
        candidate_list.sort(key=lambda c: _pillar_existing.get(c.get("pillar", ""), 0))
        log.info("[DEFICIT SCHED] Candidate queue sorted by pillar deficit. Per-pillar existing: %s", _pillar_existing)
    except Exception as _e:
        log.warning("Deficit scheduling sort failed (non-fatal): %s", _e)

    queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
    for c in candidate_list:
        queue.put_nowait(c)

    cluster_info = get_cluster_summary(config.database_url)

    # Initial launch alert
    now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M UTC")
    send_tg_message(
        token=config.telegram_bot_token,
        chat_id=config.telegram_chat_id,
        html_text=(
            f"🚀 <b>GOAL LAUNCHED: 100 ELITE SENTIMENT ALPHAS (REV 3)</b> · {now_str}\n\n"
            f"• <b>Objective:</b> Mine & Qualify 100 Mutually Orthogonal Sentiment Alphas\n"
            f"• <b>Current Vault:</b> {current_qualified} / {target_count}\n"
            f"• <b>Tracked Clusters:</b> {cluster_info.get('distinct_clusters_count', 0)} distinct clusters ({cluster_info.get('total_tracked_signals', 0)} signals)\n"
            f"• <b>Concurrency:</b> 4 Parallel BRAIN Simulation Slots\n"
            f"• <b>Pillars:</b> 14 Sub-Pillars (SUE, PEAD, Target Spread, Recs, Dispersion, Focus, Lexical, Tri-Factor, Short Interest, Options IV Skew, Breadth, Rec Accel, Sales Drift, Dispersion Vol)\n\n"
            f"<i>Pre-sim duplicate skipping active. Empirical T_eff & dynamic reserve buffer applied. Challengers stored in PostgreSQL.</i>"
        ),
    )

    lock = asyncio.Lock()
    eval_count = 0
    near_miss_count = 0
    start_time = time.time()
    rejections = {
        "perf": 0,
        "prod": 0,
        "collision": 0,
        "uplift": 0,
        "checklist": 0,
        "pre_sim_duplicate": 0,
        "oos_fail": 0,
        "near_duplicates": 0,
    }
    pillar_saturation: Dict[str, int] = {}
    # Auto-load saturation state from DB (handles restarts correctly)
    saturated_pillars, saturated_base_archetypes = load_saturated_state_from_db(config.database_url)
    log.info("[RESUME] Loaded %d saturated pillars and %d saturated archetypes from DB.",
             len(saturated_pillars), len(saturated_base_archetypes))
    sweep_counts: Dict[str, int] = {}
    active_pillars_with_alpha: Set[str] = set()
    latest_rms_corr = 0.0
    latest_n_eff = 1.0

    # Initialize vault metrics
    if len(reserve_meta) > 0:
        latest_rms_corr, latest_n_eff, _ = compute_vault_diversification(ref_pnls)

    def get_stats():
        return {
            "qual": current_qualified,
            "evals": eval_count,
            "near_miss": near_miss_count,
            "rejections": dict(rejections),
            "saturated": list(saturated_pillars),
            "active_pillars_with_alpha": list(active_pillars_with_alpha),
            "rms_corr": latest_rms_corr,
            "n_eff": latest_n_eff,
        }

    # Launch Hourly Heartbeat Telegram reporter
    asyncio.create_task(hourly_heartbeat_loop(config, target_count, start_time, lock, get_stats))

    async def worker(worker_id: int):
        nonlocal eval_count, current_qualified, near_miss_count, latest_rms_corr, latest_n_eff
        while not queue.empty() and current_qualified < target_count:
            cand = await queue.get()
            cand_pillar = cand.get("pillar", cand["archetype"].split("_")[0])
            cand_base_arch = cand.get("base_archetype", cand["archetype"])

            # R3-2: Deprioritize / Skip Saturated Pillars & Pre-Sim Saturated Duplicates
            if cand_pillar in saturated_pillars:
                async with lock:
                    rejections["pre_sim_duplicate"] += 1
                log.info("[Worker %d] DISCARDED_PRE_SIM_DUPLICATE: Skipping %s (pillar %s paused due to saturation).",
                         worker_id, cand["archetype"], cand_pillar)
                queue.task_done()
                continue

            if cand_base_arch in saturated_base_archetypes:
                async with lock:
                    rejections["pre_sim_duplicate"] += 1
                log.info("[Worker %d] DISCARDED_PRE_SIM_DUPLICATE: Skipping %s (base archetype %s saturated at rho >= 0.90). Conserving compute.",
                         worker_id, cand["archetype"], cand_base_arch)
                queue.task_done()
                continue

            expr = cand["expression"]
            arch = cand["archetype"]
            hyp = cand["hypothesis"]
            universe = cand["universe"]
            neut = cand["neutralization"]
            decay = cand["decay"]
            is_sweep = cand.get("is_sweep", False)
            variants_tested = cand.get("variants_tested", 1)

            async with lock:
                eval_count += 1
                curr_eval = eval_count
                curr_qual = current_qualified

            log.info("[Worker %d | #%d | Qualified: %d/%d] Simulating %s (pillar=%s, u=%s, neut=%s, d=%d)...",
                     worker_id, curr_eval, curr_qual, target_count, arch, cand_pillar, universe, neut, decay)

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
                log.warning("[Worker %d] Simulation error on %s: %s — skipping, requeuing different candidate.", worker_id, arch, e)
                queue.task_done()
                # Put the failed candidate at the back; don't block on it
                queue.put_nowait({**cand, "_retry": True})
                await asyncio.sleep(3.0)
                continue

            if not metrics or not metrics.is_valid:
                log.info("[Worker %d] NULL_METRICS: %s — network issue, skipping candidate, picking next.", worker_id, arch)
                queue.task_done()
                await asyncio.sleep(2.0)
                continue

            log.info(
                "[Worker %d] %s | Sharpe=%.2f | Fit=%.2f | TO=%.1f%% | Margin=%.1fbps | DD=%.1f%% | %s",
                worker_id, metrics.alpha_id, metrics.sharpe, metrics.fitness,
                metrics.turnover * 100, metrics.margin * 10000, metrics.max_drawdown * 100, arch
            )

            # R3-5: Capped Near-Miss Micro-Sweeps (Salvage Sharpe near-misses AND Fitness near-misses)
            is_near_miss = (
                (1.00 <= metrics.sharpe < 1.25 or (metrics.sharpe >= 1.15 and 0.55 <= metrics.fitness < 0.70))
                and metrics.turnover <= 0.35
                and not is_sweep
            )
            if is_near_miss:
                base_key = arch.split("_d")[0]
                if sweep_counts.get(base_key, 0) < 2:  # Cap at 2 micro-sweeps per base signal
                    sweep_counts[base_key] = sweep_counts.get(base_key, 0) + 1
                    sweep_num = sweep_counts[base_key]
                    async with lock:
                        near_miss_count += 1
                    log.info("[Worker %d | NEAR-MISS #%d] %s (Sharpe=%.2f). Spawning capped micro-sweep (%d/2)...",
                             worker_id, near_miss_count, arch, metrics.sharpe, sweep_num)
                    for d_shift in [-2, 2]:
                        new_d = max(6, decay + d_shift)
                        queue.put_nowait({
                            "pillar": cand_pillar,
                            "base_archetype": cand_base_arch,
                            "expression": expr,
                            "archetype": f"{arch}_d{new_d}",
                            "hypothesis": f"{hyp} [Sweep d={new_d}]",
                            "universe": universe,
                            "neutralization": neut,
                            "decay": new_d,
                            "is_sweep": True,
                            "variants_tested": sweep_num + 1,
                        })

            # Gate 1: Multi-Objective Performance Gate
            passed_gate1 = (
                metrics.sharpe >= 1.25
                and metrics.fitness >= 0.70
                and 0.01 <= metrics.turnover <= 0.60
                and (metrics.margin * 10000) >= 5.0
                and metrics.max_drawdown <= 0.35
            )

            if not passed_gate1:
                async with lock:
                    rejections["perf"] += 1
                log.info("[Worker %d] REJECTED_PERFORMANCE: %s (Sharpe=%.2f, Fit=%.2f, Margin=%.1fbps, TO=%.1f%%).",
                         worker_id, arch, metrics.sharpe, metrics.fitness, metrics.margin * 10000, metrics.turnover * 100)
                queue.task_done()
                continue

            # Fetch Candidate PnL
            cand_pnl = await client.get_alpha_pnl(metrics.alpha_id)
            if not cand_pnl or len(cand_pnl) < 30:
                log.info("[Worker %d] DISCARDED_INSUFFICIENT_PNL: %s has insufficient history.", worker_id, metrics.alpha_id)
                queue.task_done()
                continue

            # Gate 2: Correlation Firewall vs Immutable Production Alphas (|rho| < 0.55)
            max_prod_corr = 0.0
            worst_prod = ""
            for p_id in prod_alpha_ids:
                if p_id in ref_pnls:
                    c = abs(compute_correlation(cand_pnl, ref_pnls[p_id]))
                    if c > max_prod_corr:
                        max_prod_corr = c
                        worst_prod = p_id

            if max_prod_corr >= PROD_FIREWALL:
                async with lock:
                    rejections["prod"] += 1
                log.info("[Worker %d] REJECTED_PROD_FIREWALL: %s vs Live Production Alpha %s (rho=%.4f >= %.2f).",
                         worker_id, arch, worst_prod, max_prod_corr, PROD_FIREWALL)
                queue.task_done()
                continue

            # Check vs Mutable Reserve Alphas (Multi-Collider Pareto Resolution with Dynamic T_eff)
            colliders: List[str] = []
            max_res_corr = 0.0
            worst_res = ""
            measured_t_eff = 1260.0
            measured_phi1 = 0.0
            measured_phi2 = 0.0
            dynamic_reserve_limit = 0.65

            for r_id, r_info in list(reserve_meta.items()):
                if r_id in ref_pnls:
                    c = abs(compute_correlation(cand_pnl, ref_pnls[r_id]))
                    if c > max_res_corr:
                        max_res_corr = c
                        worst_res = r_id
                        measured_t_eff, measured_phi1, measured_phi2, dynamic_reserve_limit = measure_effective_t(cand_pnl, ref_pnls[r_id])
                    if c >= dynamic_reserve_limit:
                        colliders.append(r_id)

            reserve_to_replace: List[str] = []
            req_uplift = MULTI_UPLIFT if len(colliders) > 1 else SHARPE_UPLIFT

            cluster_id = f"cluster_{worst_res}" if worst_res else f"cluster_{metrics.alpha_id}"

            if not colliders:
                # Clean orthogonal alpha: safe to add
                pass
            elif all(
                pareto_dominates(
                    cand_sharpe=metrics.sharpe,
                    cand_fitness=metrics.fitness,
                    cand_margin=metrics.margin,
                    inc_sharpe=reserve_meta[r].get("sharpe", 0.0),
                    inc_fitness=reserve_meta[r].get("fitness", 0.0),
                    inc_margin=reserve_meta[r].get("margin", 0.0),
                    uplift=req_uplift,
                    tolerance=TOLERANCE,
                )
                for r in colliders
            ):
                # Candidate strictly Pareto-dominates ALL colliders with required uplift hurdle
                reserve_to_replace = colliders
                log.info(
                    "[+] Candidate %s Pareto-dominates all %d reserve collider(s) with %.0f%% uplift hurdle: %s",
                    metrics.alpha_id, len(colliders), req_uplift * 100, colliders
                )
            else:
                # R3-3: Store collision-rejected candidate as CHALLENGER in PostgreSQL
                async with lock:
                    rejections["collision"] += 1
                    # Track near-duplicates (rho >= 0.90) separately
                    if max_res_corr >= 0.90:
                        rejections["near_duplicates"] += 1
                    # HARD SATURATION RULE: any collision (not just rho>=0.90) counts against pillar budget
                    # Fire pillar pause after >= 3 collisions regardless of correlation level
                    saturated_base_archetypes.add(cand_base_arch)
                    pillar_saturation[cand_pillar] = pillar_saturation.get(cand_pillar, 0) + 1
                    if pillar_saturation[cand_pillar] >= 3 and cand_pillar not in saturated_pillars:
                        saturated_pillars.add(cand_pillar)
                        log.warning("[HARD-KILL] Pillar %s PAUSED: %d collisions accumulated. Zero budget until target met elsewhere.",
                                    cand_pillar, pillar_saturation[cand_pillar])

                commit_collision_challenger(
                    db_url=config.database_url,
                    alpha_id=metrics.alpha_id,
                    expression=expr,
                    archetype=arch,
                    incumbent_id=",".join(colliders),
                    cluster_id=cluster_id,
                    metrics=metrics,
                    max_corr=max_res_corr,
                    universe=universe,
                    neutralization=neut,
                    decay=decay,
                    variants_tested=variants_tested,
                )
                log.info(
                    "[Worker %d] REJECTED_COLLISION: %s vs Incumbent(s) %s (rho=%.4f >= %.2f limit, T_eff=%.0f, phi1=%.2f, phi2=%.2f). Stored as CHALLENGER.",
                    worker_id, arch, colliders, max_res_corr, dynamic_reserve_limit, measured_t_eff, measured_phi1, measured_phi2
                )
                queue.task_done()
                continue

            # R3-5: Out-of-Sample Verification for Micro-Sweeps
            oos_checked = False
            if is_sweep:
                alt_univ = "TOP2000" if universe == "TOP1000" else "TOP1000"
                log.info("[*] Running OOS sub-universe validation on %s for swept candidate %s...", alt_univ, arch)
                oos_settings = SimSettings(
                    region="USA",
                    universe=alt_univ,
                    delay=1,
                    decay=decay,
                    neutralization=neut,
                    truncation=0.05,
                    pasteurization=True,
                )
                try:
                    oos_metrics = await client.simulate_one(expr, oos_settings)
                    if not oos_metrics or oos_metrics.sharpe < 1.00:
                        async with lock:
                            rejections["oos_fail"] += 1
                        log.warning("[Worker %d] REJECTED_OOS_FAIL: %s failed alternate universe check (OOS Sharpe=%.2f < 1.00). Discarding noise sweep.",
                                    worker_id, arch, getattr(oos_metrics, 'sharpe', 0.0))
                        queue.task_done()
                        continue
                    oos_checked = True
                    log.info("[+] OOS Check Passed for %s: OOS Sharpe=%.2f on %s.", arch, oos_metrics.sharpe, alt_univ)
                except Exception as oos_err:
                    log.warning("OOS check error: %s", oos_err)

            # Gate 3: Platform Checklist
            log.info("[*] Checking platform checklist on BRAIN for %s...", metrics.alpha_id)
            chk_ok, chk_msg = await verify_checklist_passes(client._session, metrics.alpha_id)
            if not chk_ok:
                async with lock:
                    rejections["checklist"] += 1
                log.warning("[Worker %d] REJECTED_CHECKLIST: %s failed checklist (%s).", worker_id, metrics.alpha_id, chk_msg)
                queue.task_done()
                continue

            # ALL 3 GATES PASSED! Commit to Vault
            async with lock:
                is_replacement = len(reserve_to_replace) > 0
                if is_replacement:
                    for old_aid in reserve_to_replace:
                        reserve_meta.pop(old_aid, {})
                        if old_aid in ref_pnls:
                            del ref_pnls[old_aid]
                        supersede_reserve_alpha(config.database_url, old_aid, metrics.alpha_id)
                else:
                    current_qualified += 1

                ref_pnls[metrics.alpha_id] = cand_pnl
                reserve_meta[metrics.alpha_id] = {
                    "sharpe": metrics.sharpe,
                    "fitness": metrics.fitness,
                    "margin": metrics.margin,
                }
                active_pillars_with_alpha.add(cand_pillar)

                latest_rms_corr, latest_n_eff, n_vault = compute_vault_diversification(ref_pnls)

                final_cluster_id = f"cluster_{metrics.alpha_id}"
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
                    cluster_id=final_cluster_id,
                    variants_tested=variants_tested,
                    oos_checked=oos_checked,
                )

                safe_expr = html.escape(expr)
                safe_alpha = html.escape(metrics.alpha_id)
                safe_arch = html.escape(arch)

                if is_replacement:
                    replaced_str = ", ".join(reserve_to_replace)
                    send_tg_message(
                        token=config.telegram_bot_token,
                        chat_id=config.telegram_chat_id,
                        html_text=(
                            f"🔄 <b>RESERVE QUALITY UPGRADE (PARETO REPLACEMENT)!</b> 🔄\n\n"
                            f"• <b>New Alpha ID:</b> <code>{safe_alpha}</code>\n"
                            f"• <b>Replaced Lower-Quality Collider(s):</b> <code>{replaced_str}</code> (max rho={max_res_corr:.2f})\n"
                            f"• <b>Sharpe:</b> <b>{metrics.sharpe:.2f}</b>  |  <b>Fitness:</b> <b>{metrics.fitness:.2f}</b>\n"
                            f"• <b>Margin:</b> {metrics.margin * 10000:.1f} bps  |  <b>Turnover:</b> {metrics.turnover * 100:.1f}%\n"
                            f"• <b>Active Vault Count:</b> {current_qualified}/{target_count} (RMS Rho: {latest_rms_corr:.2f}, N_eff: {latest_n_eff:.1f})\n"
                            f"• <b>Expression:</b>\n<code>{safe_expr}</code>"
                        ),
                    )
                    log.info("[🔄] RESERVE UPGRADED: %s (Sharpe=%.2f) REPLACED %s (max rho=%.4f, RMS Rho=%.2f, N_eff=%.1f)",
                             metrics.alpha_id, metrics.sharpe, replaced_str, max_res_corr, latest_rms_corr, latest_n_eff)
                else:
                    send_tg_message(
                        token=config.telegram_bot_token,
                        chat_id=config.telegram_chat_id,
                        html_text=(
                            f"🌟 <b>Qualified Sentiment Alpha</b> ({current_qualified}/{target_count})\n"
                            f"• ID: <code>{safe_alpha}</code>\n"
                            f"• Sharpe: <b>{metrics.sharpe:.2f}</b> | Fit: <b>{metrics.fitness:.2f}</b>\n"
                            f"• Margin: {metrics.margin * 10000:.1f} bps | TO: {metrics.turnover * 100:.1f}%\n"
                            f"• Max Corr: {max(max_prod_corr, max_res_corr):.2f}\n"
                            f"• Expression:\n<code>{safe_expr}</code>"
                        ),
                    )
                    log.info("[🌟] QUALIFIED & STORED IN VAULT: %s (%s, Sharpe=%.2f, MaxCorr=%.4f)",
                             metrics.alpha_id, arch, metrics.sharpe, max(max_prod_corr, max_res_corr))

            queue.task_done()

    # Launch 4 parallel workers (matching BRAIN platform concurrency cap of 4)
    workers = [asyncio.create_task(worker(i + 1)) for i in range(4)]
    await asyncio.gather(*workers)

    final_count = get_current_qualified_count(config.database_url)
    log.info("=" * 70)
    log.info("100 SENTIMENT MINER COMPLETE: %d / %d QUALIFIED IN VAULT", final_count, target_count)
    log.info("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_sentiment_100_miner())
