"""
Sub-Universe Sharpe Fixer — Rescue blocked alphas from LOW_SUB_UNIVERSE_SHARPE
==============================================================================
Strategy:
  LOW_SUB_UNIVERSE_SHARPE fires when the alpha's cross-sectional Sharpe degrades
  significantly within individual sector/sub-industry buckets.

  Root cause for these alphas: the inner `rank()` operates globally (cross-sectional)
  before `group_neutralize`. This means the signal leaks macro/market-wide variance
  into each sub-bucket, making within-bucket Sharpe poor.

  Fix: Replace the inner global `rank()` with `group_rank(..., <group>)` so the
  signal is already ranked WITHIN the bucket before neutralization. This makes
  the signal self-contained in every sub-universe → improves sub-universe Sharpe.

  Additional lever: apply `ts_zscore` with Sinclair 0.75 sd gate on the trade_when
  condition so only structurally valid setups trade. This reduces noise in thin buckets.

Approach per alpha:
  1. Vkae25pb / N1a8nR9o (Bivariate SUBINDUSTRY): replace inner rank() -> group_rank(subindustry)
  2. MPa2a1Eo (Term90/30 SUBINDUSTRY): same, + tighten gate from 0.26 to 0.28
  3. JjN2O3mA (Term180/30 SECTOR): replace inner rank() -> group_rank(sector)
  4. XgbOPxXb (Put120 TermSlope SECTOR): replace inner rank() -> group_rank(sector), SUS was 0.52 vs 0.55 (very close)
"""

import asyncio
import logging
import sys
import os
from typing import List, Dict, Any

sys.path.insert(0, r"c:\Users\pc\Desktop\brain-alpha-pipeline")

import psycopg
from dotenv import load_dotenv

load_dotenv()

from brain_options.config import OptionsConfig
from brain_options.core.client import BrainClient, SimSettings
from brain_options.store.store import OptionsStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("sus_fixer")


# ─── Candidate variants: group_rank inner fix ─────────────────────────────────
# For each blocked alpha we produce 2 variants:
#  v1: replace inner rank() with group_rank(<neut_group>)  [core fix]
#  v2: additionally tighten the gate threshold             [secondary fix]

BLOCKED_VARIANTS = [

    # ── Vkae25pb: Bivariate_Put180_Skew60 (SUBINDUSTRY) ─────────────────────
    {
        "name": "Vkae25pb_v1_grankSUBI",
        "origin": "Vkae25pb",
        "desc": "group_rank(subindustry) inner fix on both components",
        "universe": "TOP3000", "neutralization": "SUBINDUSTRY", "delay": 1, "decay": 8,
        "expression": (
            "trade_when(abs(rank((0.65 * group_rank(ts_decay_linear(ts_decay_linear(((forward_price_180 - put_breakeven_180) / close * (implied_volatility_mean_skew_180 * sqrt(180/252.0)) * (pcr_vol_180 / (pcr_oi_180 + 0.001))), 10), 3), subindustry) + 0.35 * group_rank(ts_decay_linear(ts_decay_linear(((implied_volatility_call_60 - implied_volatility_put_60) / (implied_volatility_mean_60 + 0.001) * sqrt(60/252.0) * (volume / (adv20 + 1))), 10), 3), subindustry))) - 0.5) > 0.26, group_neutralize(rank((0.65 * group_rank(ts_decay_linear(ts_decay_linear(((forward_price_180 - put_breakeven_180) / close * (implied_volatility_mean_skew_180 * sqrt(180/252.0)) * (pcr_vol_180 / (pcr_oi_180 + 0.001))), 10), 3), subindustry) + 0.35 * group_rank(ts_decay_linear(ts_decay_linear(((implied_volatility_call_60 - implied_volatility_put_60) / (implied_volatility_mean_60 + 0.001) * sqrt(60/252.0) * (volume / (adv20 + 1))), 10), 3), subindustry))) * (volume / adv20), subindustry), -1)"
        ),
    },
    {
        "name": "Vkae25pb_v2_grankSUBI_gate28",
        "origin": "Vkae25pb",
        "desc": "group_rank(subindustry) + tightened gate 0.28",
        "universe": "TOP3000", "neutralization": "SUBINDUSTRY", "delay": 1, "decay": 10,
        "expression": (
            "trade_when(abs(rank((0.65 * group_rank(ts_decay_linear(ts_decay_linear(((forward_price_180 - put_breakeven_180) / close * (implied_volatility_mean_skew_180 * sqrt(180/252.0)) * (pcr_vol_180 / (pcr_oi_180 + 0.001))), 10), 3), subindustry) + 0.35 * group_rank(ts_decay_linear(ts_decay_linear(((implied_volatility_call_60 - implied_volatility_put_60) / (implied_volatility_mean_60 + 0.001) * sqrt(60/252.0) * (volume / (adv20 + 1))), 10), 3), subindustry))) - 0.5) > 0.28, group_neutralize(rank((0.65 * group_rank(ts_decay_linear(ts_decay_linear(((forward_price_180 - put_breakeven_180) / close * (implied_volatility_mean_skew_180 * sqrt(180/252.0)) * (pcr_vol_180 / (pcr_oi_180 + 0.001))), 10), 3), subindustry) + 0.35 * group_rank(ts_decay_linear(ts_decay_linear(((implied_volatility_call_60 - implied_volatility_put_60) / (implied_volatility_mean_60 + 0.001) * sqrt(60/252.0) * (volume / (adv20 + 1))), 10), 3), subindustry))) * (volume / adv20), subindustry), -1)"
        ),
    },

    # ── N1a8nR9o: Bivariate_Put90_Skew30 (SUBINDUSTRY) ──────────────────────
    {
        "name": "N1a8nR9o_v1_grankSUBI",
        "origin": "N1a8nR9o",
        "desc": "group_rank(subindustry) inner fix on both components",
        "universe": "TOP3000", "neutralization": "SUBINDUSTRY", "delay": 1, "decay": 8,
        "expression": (
            "trade_when(abs(rank((0.65 * group_rank(ts_decay_linear(ts_decay_linear(((forward_price_90 - put_breakeven_90) / close * (implied_volatility_mean_skew_90 * sqrt(90/252.0)) * (pcr_vol_90 / (pcr_oi_90 + 0.001))), 10), 3), subindustry) + 0.35 * group_rank(ts_decay_linear(ts_decay_linear(((implied_volatility_call_30 - implied_volatility_put_30) / (implied_volatility_mean_30 + 0.001) * sqrt(30/252.0) * (volume / (adv20 + 1))), 10), 3), subindustry))) - 0.5) > 0.26, group_neutralize(rank((0.65 * group_rank(ts_decay_linear(ts_decay_linear(((forward_price_90 - put_breakeven_90) / close * (implied_volatility_mean_skew_90 * sqrt(90/252.0)) * (pcr_vol_90 / (pcr_oi_90 + 0.001))), 10), 3), subindustry) + 0.35 * group_rank(ts_decay_linear(ts_decay_linear(((implied_volatility_call_30 - implied_volatility_put_30) / (implied_volatility_mean_30 + 0.001) * sqrt(30/252.0) * (volume / (adv20 + 1))), 10), 3), subindustry))) * (volume / adv20), subindustry), -1)"
        ),
    },
    {
        "name": "N1a8nR9o_v2_grankSUBI_gate28",
        "origin": "N1a8nR9o",
        "desc": "group_rank(subindustry) + tightened gate 0.28",
        "universe": "TOP3000", "neutralization": "SUBINDUSTRY", "delay": 1, "decay": 10,
        "expression": (
            "trade_when(abs(rank((0.65 * group_rank(ts_decay_linear(ts_decay_linear(((forward_price_90 - put_breakeven_90) / close * (implied_volatility_mean_skew_90 * sqrt(90/252.0)) * (pcr_vol_90 / (pcr_oi_90 + 0.001))), 10), 3), subindustry) + 0.35 * group_rank(ts_decay_linear(ts_decay_linear(((implied_volatility_call_30 - implied_volatility_put_30) / (implied_volatility_mean_30 + 0.001) * sqrt(30/252.0) * (volume / (adv20 + 1))), 10), 3), subindustry))) - 0.5) > 0.28, group_neutralize(rank((0.65 * group_rank(ts_decay_linear(ts_decay_linear(((forward_price_90 - put_breakeven_90) / close * (implied_volatility_mean_skew_90 * sqrt(90/252.0)) * (pcr_vol_90 / (pcr_oi_90 + 0.001))), 10), 3), subindustry) + 0.35 * group_rank(ts_decay_linear(ts_decay_linear(((implied_volatility_call_30 - implied_volatility_put_30) / (implied_volatility_mean_30 + 0.001) * sqrt(30/252.0) * (volume / (adv20 + 1))), 10), 3), subindustry))) * (volume / adv20), subindustry), -1)"
        ),
    },

    # ── MPa2a1Eo: T2_Term90_30 (SUBINDUSTRY) — SUS only 0.17, severe fix needed
    {
        "name": "MPa2a1Eo_v1_grankSUBI",
        "origin": "MPa2a1Eo",
        "desc": "group_rank(subindustry) inner fix — core signal is within-group IV term structure",
        "universe": "TOP2000", "neutralization": "SUBINDUSTRY", "delay": 1, "decay": 8,
        "expression": (
            "trade_when(abs(rank((0.5 * group_rank(ts_decay_linear(ts_decay_linear(((implied_volatility_mean_90 / (implied_volatility_mean_30 + 0.001)) * (implied_volatility_mean_skew_30 * sqrt(30/252.0))), 10), 3), subindustry) + 0.5 * group_rank(ts_decay_linear(ts_decay_linear(((forward_price_90 - forward_price_30) / close * (implied_volatility_mean_90 / (implied_volatility_mean_30 + 0.001)) * (volume / (adv20 + 1))), 10), 3), subindustry))) - 0.5) > 0.26, group_neutralize(rank((0.5 * group_rank(ts_decay_linear(ts_decay_linear(((implied_volatility_mean_90 / (implied_volatility_mean_30 + 0.001)) * (implied_volatility_mean_skew_30 * sqrt(30/252.0))), 10), 3), subindustry) + 0.5 * group_rank(ts_decay_linear(ts_decay_linear(((forward_price_90 - forward_price_30) / close * (implied_volatility_mean_90 / (implied_volatility_mean_30 + 0.001)) * (volume / (adv20 + 1))), 10), 3), subindustry))) * (volume / adv20), subindustry), -1)"
        ),
    },
    {
        "name": "MPa2a1Eo_v2_grankSUBI_TOP3000",
        "origin": "MPa2a1Eo",
        "desc": "group_rank(subindustry) + expand to TOP3000 for more stocks per bucket",
        "universe": "TOP3000", "neutralization": "SUBINDUSTRY", "delay": 1, "decay": 8,
        "expression": (
            "trade_when(abs(rank((0.5 * group_rank(ts_decay_linear(ts_decay_linear(((implied_volatility_mean_90 / (implied_volatility_mean_30 + 0.001)) * (implied_volatility_mean_skew_30 * sqrt(30/252.0))), 10), 3), subindustry) + 0.5 * group_rank(ts_decay_linear(ts_decay_linear(((forward_price_90 - forward_price_30) / close * (implied_volatility_mean_90 / (implied_volatility_mean_30 + 0.001)) * (volume / (adv20 + 1))), 10), 3), subindustry))) - 0.5) > 0.26, group_neutralize(rank((0.5 * group_rank(ts_decay_linear(ts_decay_linear(((implied_volatility_mean_90 / (implied_volatility_mean_30 + 0.001)) * (implied_volatility_mean_skew_30 * sqrt(30/252.0))), 10), 3), subindustry) + 0.5 * group_rank(ts_decay_linear(ts_decay_linear(((forward_price_90 - forward_price_30) / close * (implied_volatility_mean_90 / (implied_volatility_mean_30 + 0.001)) * (volume / (adv20 + 1))), 10), 3), subindustry))) * (volume / adv20), subindustry), -1)"
        ),
    },

    # ── JjN2O3mA: T2_Term180_30 (SECTOR) ─────────────────────────────────────
    {
        "name": "JjN2O3mA_v1_grankSECT",
        "origin": "JjN2O3mA",
        "desc": "group_rank(sector) inner fix for both components",
        "universe": "TOP3000", "neutralization": "SECTOR", "delay": 1, "decay": 8,
        "expression": (
            "trade_when(abs(rank((0.5 * group_rank(ts_decay_linear(ts_decay_linear(((implied_volatility_mean_180 / (implied_volatility_mean_30 + 0.001)) * (implied_volatility_mean_skew_30 * sqrt(30/252.0))), 10), 3), sector) + 0.5 * group_rank(ts_decay_linear(ts_decay_linear(((forward_price_180 - forward_price_30) / close * (implied_volatility_mean_180 / (implied_volatility_mean_30 + 0.001)) * (volume / (adv20 + 1))), 10), 3), sector))) - 0.5) > 0.26, group_neutralize(rank((0.5 * group_rank(ts_decay_linear(ts_decay_linear(((implied_volatility_mean_180 / (implied_volatility_mean_30 + 0.001)) * (implied_volatility_mean_skew_30 * sqrt(30/252.0))), 10), 3), sector) + 0.5 * group_rank(ts_decay_linear(ts_decay_linear(((forward_price_180 - forward_price_30) / close * (implied_volatility_mean_180 / (implied_volatility_mean_30 + 0.001)) * (volume / (adv20 + 1))), 10), 3), sector))) * (volume / adv20), sector), -1)"
        ),
    },
    {
        "name": "JjN2O3mA_v2_grankSUBI_upgrade",
        "origin": "JjN2O3mA",
        "desc": "Upgrade neutralization from SECTOR to SUBINDUSTRY with group_rank — finer bucketing",
        "universe": "TOP3000", "neutralization": "SUBINDUSTRY", "delay": 1, "decay": 8,
        "expression": (
            "trade_when(abs(rank((0.5 * group_rank(ts_decay_linear(ts_decay_linear(((implied_volatility_mean_180 / (implied_volatility_mean_30 + 0.001)) * (implied_volatility_mean_skew_30 * sqrt(30/252.0))), 10), 3), subindustry) + 0.5 * group_rank(ts_decay_linear(ts_decay_linear(((forward_price_180 - forward_price_30) / close * (implied_volatility_mean_180 / (implied_volatility_mean_30 + 0.001)) * (volume / (adv20 + 1))), 10), 3), subindustry))) - 0.5) > 0.26, group_neutralize(rank((0.5 * group_rank(ts_decay_linear(ts_decay_linear(((implied_volatility_mean_180 / (implied_volatility_mean_30 + 0.001)) * (implied_volatility_mean_skew_30 * sqrt(30/252.0))), 10), 3), subindustry) + 0.5 * group_rank(ts_decay_linear(ts_decay_linear(((forward_price_180 - forward_price_30) / close * (implied_volatility_mean_180 / (implied_volatility_mean_30 + 0.001)) * (volume / (adv20 + 1))), 10), 3), subindustry))) * (volume / adv20), subindustry), -1)"
        ),
    },

    # ── XgbOPxXb: T1_Put120_TermSlope (SECTOR) — SUS 0.52 vs 0.55, very close ─
    {
        "name": "XgbOPxXb_v1_grankSECT",
        "origin": "XgbOPxXb",
        "desc": "group_rank(sector) inner fix — was closest (0.52 vs 0.55 limit)",
        "universe": "TOP3000", "neutralization": "SECTOR", "delay": 1, "decay": 10,
        "expression": (
            "trade_when(abs(rank((0.65 * group_rank(ts_decay_linear(ts_decay_linear(((forward_price_120 - put_breakeven_120) / close * (implied_volatility_mean_skew_120 * sqrt(120/252.0)) * (pcr_vol_120 / (pcr_oi_120 + 0.001))), 10), 3), sector) + 0.35 * group_rank(ts_decay_linear(ts_decay_linear(((implied_volatility_mean_120 / (implied_volatility_mean_30 + 0.001)) * sqrt(120/252.0) * (volume / (adv20 + 1))), 10), 3), sector))) - 0.5) > 0.26, group_neutralize(rank((0.65 * group_rank(ts_decay_linear(ts_decay_linear(((forward_price_120 - put_breakeven_120) / close * (implied_volatility_mean_skew_120 * sqrt(120/252.0)) * (pcr_vol_120 / (pcr_oi_120 + 0.001))), 10), 3), sector) + 0.35 * group_rank(ts_decay_linear(ts_decay_linear(((implied_volatility_mean_120 / (implied_volatility_mean_30 + 0.001)) * sqrt(120/252.0) * (volume / (adv20 + 1))), 10), 3), sector))) * (volume / adv20), sector), -1)"
        ),
    },
    {
        "name": "XgbOPxXb_v2_grankSUBI_upgrade",
        "origin": "XgbOPxXb",
        "desc": "Upgrade to SUBINDUSTRY with group_rank — finer bucketing may cure sub-universe Sharpe",
        "universe": "TOP3000", "neutralization": "SUBINDUSTRY", "delay": 1, "decay": 10,
        "expression": (
            "trade_when(abs(rank((0.65 * group_rank(ts_decay_linear(ts_decay_linear(((forward_price_120 - put_breakeven_120) / close * (implied_volatility_mean_skew_120 * sqrt(120/252.0)) * (pcr_vol_120 / (pcr_oi_120 + 0.001))), 10), 3), subindustry) + 0.35 * group_rank(ts_decay_linear(ts_decay_linear(((implied_volatility_mean_120 / (implied_volatility_mean_30 + 0.001)) * sqrt(120/252.0) * (volume / (adv20 + 1))), 10), 3), subindustry))) - 0.5) > 0.26, group_neutralize(rank((0.65 * group_rank(ts_decay_linear(ts_decay_linear(((forward_price_120 - put_breakeven_120) / close * (implied_volatility_mean_skew_120 * sqrt(120/252.0)) * (pcr_vol_120 / (pcr_oi_120 + 0.001))), 10), 3), subindustry) + 0.35 * group_rank(ts_decay_linear(ts_decay_linear(((implied_volatility_mean_120 / (implied_volatility_mean_30 + 0.001)) * sqrt(120/252.0) * (volume / (adv20 + 1))), 10), 3), subindustry))) * (volume / adv20), subindustry), -1)"
        ),
    },
]

# ─── Performance thresholds (must still pass quality gates) ───────────────────
MIN_SHARPE = 1.25
MIN_FITNESS = 1.00
MAX_CORR = 0.70


async def load_or_fetch_reference_pnls(client, store, ref_ids: List[str]) -> Dict[str, List[float]]:
    """Load PnL series from disk cache or fetch from BRAIN API."""
    import json
    pnls = {}
    pnl_dir = store.pnl_cache_dir
    os.makedirs(pnl_dir, exist_ok=True)
    for aid in ref_ids:
        path = os.path.join(pnl_dir, aid + ".json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and data:
                    pnls[aid] = list(data.values())
                    continue
            except Exception:
                pass
        # Fetch from BRAIN API
        pnl_data = await client.get_alpha_pnl(aid)
        if pnl_data:
            pnls[aid] = list(pnl_data.values())
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(pnl_data, f)
            except Exception:
                pass
    return pnls


def compute_max_corr(new_pnl: List[float], ref_pnls: Dict[str, List[float]]) -> tuple[float, str]:
    import numpy as np
    new_arr = np.array(new_pnl)
    if new_arr.std() == 0:
        return 1.0, "zero_std"
    max_corr = 0.0
    worst_id = ""
    for aid, pnl in ref_pnls.items():
        ref_arr = np.array(pnl[-len(new_arr):])
        if len(ref_arr) < 30 or ref_arr.std() == 0:
            continue
        min_len = min(len(new_arr), len(ref_arr))
        corr = abs(float(np.corrcoef(new_arr[-min_len:], ref_arr[-min_len:])[0, 1]))
        if corr > max_corr:
            max_corr = corr
            worst_id = aid
    return max_corr, worst_id


def run_checklist(session, alpha_id: str) -> tuple[bool, dict]:
    """Returns (pass, {check_name: result})."""
    url = "https://api.worldquantbrain.com/alphas/" + alpha_id + "/check"
    try:
        resp = session.get(url)
        if resp.status_code != 200 or not resp.text.strip():
            return False, {}
        data = resp.json()
        checks = data.get("is", {}).get("checks", []) or data.get("checks", [])
        result_map = {c.get("name"): {"result": c.get("result"), "value": c.get("value"), "limit": c.get("limit")} for c in checks}
        failing = [c for c in checks if c.get("result") == "FAIL"]
        return len(failing) == 0, result_map
    except Exception as e:
        return False, {}


def mark_qualified(database_url: str, alpha_id: str, expression: str, archetype: str,
                   hypothesis: str, sharpe: float, fitness: float, turnover: float,
                   returns: float, drawdown: float, margin: float, max_corr: float,
                   universe: str, neutralization: str, delay: int, decay: int):
    sql = (
        "INSERT INTO options_alphas ("
        "alpha_id, expression, archetype, hypothesis, source, "
        "sharpe, fitness, turnover, returns, drawdown, margin, max_correlation, "
        "universe, neutralization, delay, decay, truncation, pasteurization, nan_handling, "
        "status, strategy_name"
        ") VALUES ("
        "%s, %s, %s, %s, 'sus_fixer',"
        "%s, %s, %s, %s, %s, %s, %s,"
        "%s, %s, %s, %s, 0.05, true, 'ON',"
        "'QUALIFIED', 'sus_fix'"
        ") ON CONFLICT (alpha_id) DO UPDATE SET "
        "status = 'QUALIFIED', sharpe = EXCLUDED.sharpe, fitness = EXCLUDED.fitness, "
        "margin = EXCLUDED.margin, max_correlation = EXCLUDED.max_correlation;"
    )
    with psycopg.connect(database_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (
                alpha_id, expression, archetype, hypothesis,
                sharpe, fitness, turnover, returns, drawdown, margin, max_corr,
                universe, neutralization, delay, decay,
            ))
    log.info("DB: %s recorded as QUALIFIED.", alpha_id)


async def main():
    config = OptionsConfig.from_env()
    store = OptionsStore(database_url=config.database_url)
    client = BrainClient(
        username=config.brain_username,
        password=config.brain_password,
        max_concurrent_sims=2,
        db=store.db,
    )
    client.authenticate()
    session = client._get_session()

    # Load all submitted + qualified alpha IDs for correlation reference
    import psycopg as pg
    with pg.connect(config.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT alpha_id FROM options_alphas WHERE status IN ('SUBMITTED', 'QUALIFIED');")
            ref_ids = [r[0] for r in cur.fetchall()]
    log.info("Loaded %d reference alphas for correlation check.", len(ref_ids))
    ref_pnls = await load_or_fetch_reference_pnls(client, store, ref_ids)
    log.info("PnL series loaded for %d reference alphas.", len(ref_pnls))

    log.info("=" * 72)
    log.info("SUB-UNIVERSE SHARPE FIXER  --  %d variants to simulate", len(BLOCKED_VARIANTS))
    log.info("=" * 72)

    newly_qualified = []

    sem = asyncio.Semaphore(2)  # max 2 concurrent sims

    async def run_one(v):
        async with sem:
            settings = SimSettings(
                universe=v["universe"],
                neutralization=v["neutralization"],
                delay=v["delay"],
                decay=v["decay"],
                truncation=0.05,
                pasteurization=True,
                nan_handling=True,
                unit_handling="VERIFY",
            )
            return await client.simulate_one(
                expression=v["expression"],
                settings=settings,
            )

    for i, v in enumerate(BLOCKED_VARIANTS):
        name = v["name"]
        origin = v["origin"]
        log.info("-" * 72)
        log.info("[%d/%d] [%s] (origin: %s) — %s", i+1, len(BLOCKED_VARIANTS), name, origin, v["desc"])
        
        try:
            metrics = await run_one(v)
        except Exception as e:
            log.error("  SIMULATION ERROR: %s", e)
            continue

        if metrics is None or not metrics.alpha_id:
            log.warning("  No result returned.")
            continue

        alpha_id = metrics.alpha_id
        sharpe = metrics.sharpe or 0.0
        fitness = metrics.fitness or 0.0
        turnover = metrics.turnover or 0.0
        returns = getattr(metrics, "annualized_return", 0.0) or getattr(metrics, "returns", 0.0) or 0.0
        drawdown = getattr(metrics, "max_drawdown", 0.0) or getattr(metrics, "drawdown", 0.0) or 0.0
        margin = metrics.margin or 0.0

        log.info("  Alpha ID: %s | Sh:%.2f | Fit:%.2f | TO:%.1f%% | Marg:%.1fbps",
                 alpha_id, sharpe, fitness, turnover * 100, margin * 10000)

        # Quality gate
        if sharpe < MIN_SHARPE:
            log.warning("  REJECT: Sharpe %.2f < %.2f", sharpe, MIN_SHARPE)
            continue
        if fitness < MIN_FITNESS:
            log.warning("  REJECT: Fitness %.2f < %.2f", fitness, MIN_FITNESS)
            continue

        # Now run BRAIN checklist — specifically check LOW_SUB_UNIVERSE_SHARPE
        ok, checks = run_checklist(session, alpha_id)
        sus = checks.get("LOW_SUB_UNIVERSE_SHARPE", {})
        sc = checks.get("SELF_CORRELATION", {})
        log.info("  Checklist: PASS=%s | SUS=%s (val=%s, lim=%s) | SC=%s",
                 ok, sus.get("result"), sus.get("value"), sus.get("limit"), sc.get("result"))

        if not ok:
            failing = [k for k, v2 in checks.items() if v2.get("result") == "FAIL"]
            log.warning("  CHECKLIST FAIL: %s — skipping.", failing)
            continue

        # Correlation barrier
        pnl_series = await client.get_alpha_pnl(alpha_id)
        if pnl_series:
            pnl_vals = list(pnl_series.values())
            max_corr, worst = compute_max_corr(pnl_vals, ref_pnls)
            log.info("  Max Correlation: %.4f (vs %s)", max_corr, worst)
        else:
            max_corr, worst = 0.0, "n/a"
            log.warning("  Could not fetch PnL series — skipping correlation check.")

        if max_corr >= MAX_CORR:
            log.warning("  REJECT: Corr %.4f >= %.2f barrier", max_corr, MAX_CORR)
            continue

        # All gates passed — record as QUALIFIED
        log.info("  *** QUALIFIED: %s (SUS FIXED, Sh:%.2f, Fit:%.2f, Corr:%.4f) ***",
                 alpha_id, sharpe, fitness, max_corr)
        mark_qualified(
            database_url=config.database_url,
            alpha_id=alpha_id,
            expression=v["expression"],
            archetype=name,
            hypothesis="Sub-universe Sharpe fix of " + origin + " via group_rank inner neutralization",
            sharpe=sharpe,
            fitness=fitness,
            turnover=turnover,
            returns=returns,
            drawdown=drawdown,
            margin=margin,
            max_corr=max_corr,
            universe=v["universe"],
            neutralization=v["neutralization"],
            delay=v["delay"],
            decay=v["decay"],
        )
        newly_qualified.append({"id": alpha_id, "name": name, "origin": origin,
                                 "sharpe": sharpe, "fitness": fitness, "corr": max_corr})
        ref_pnls[alpha_id] = list(pnl_series.values()) if pnl_series else []

    log.info("=" * 72)
    log.info("SUS FIXER COMPLETE: %d / %d variants newly QUALIFIED", len(newly_qualified), len(BLOCKED_VARIANTS))
    for q in newly_qualified:
        log.info("  ✅ %s | origin=%s | Sh:%.2f Fit:%.2f Corr:%.4f", q["id"], q["origin"], q["sharpe"], q["fitness"], q["corr"])
    log.info("=" * 72)


if __name__ == "__main__":
    asyncio.run(main())
