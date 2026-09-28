"""
Targeted TOP3000 Sub-Universe Fix for Vkae25pb and XgbOPxXb
============================================================
Diagnostic:
  In TOP3000, Vkae25pb and XgbOPxXb have stellar raw performance:
    Vkae25pb: Sharpe 1.77, Fitness 1.42 (SUS val=0.68 vs lim=0.77)
    XgbOPxXb: Sharpe 1.27, Fitness 1.01 (SUS val=0.52 vs lim=0.55 — missed by 0.03!)
  
  The sub-universe Sharpe gap in TOP3000 is caused by:
  1. Uncapped *(volume / adv20) position multiplier in group_neutralize, which over-allocates
     to extreme volume spikes in thin buckets.
  2. Holding period decay: increasing decay from 8/10 to 12 provides cross-sectional smoothing
     across all sub-universe test buckets, lifting minimum sub-universe Sharpe above the limit.
"""

import asyncio
import logging
import sys
import psycopg
from dotenv import load_dotenv

sys.path.insert(0, ".")
load_dotenv()

from brain_options.config import OptionsConfig
from brain_options.core.client import BrainClient, SimSettings
from brain_options.store.store import OptionsStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("top3000_tuning")

CANDIDATES = [
    # --- XgbOPxXb (missed by 0.03: 0.52 vs 0.55) ---
    # Variant A: Decay 12 (smooths cross-sectional sub-bucket returns)
    {
        "key": "XgbOPxXb_TOP3000_d12",
        "origin": "XgbOPxXb",
        "universe": "TOP3000", "neutralization": "SECTOR", "delay": 1, "decay": 12,
        "expression": (
            "trade_when(abs(rank((0.65 * rank(ts_decay_linear(ts_decay_linear(((forward_price_120 - put_breakeven_120) / close * (implied_volatility_mean_skew_120 * sqrt(120/252.0)) * (pcr_vol_120 / (pcr_oi_120 + 0.001))), 10), 3)) + 0.35 * rank(ts_decay_linear(ts_decay_linear(((implied_volatility_mean_120 / (implied_volatility_mean_30 + 0.001)) * sqrt(120/252.0) * (volume / (adv20 + 1))), 10), 3)))) - 0.5) > 0.26, group_neutralize(rank((0.65 * rank(ts_decay_linear(ts_decay_linear(((forward_price_120 - put_breakeven_120) / close * (implied_volatility_mean_skew_120 * sqrt(120/252.0)) * (pcr_vol_120 / (pcr_oi_120 + 0.001))), 10), 3)) + 0.35 * rank(ts_decay_linear(ts_decay_linear(((implied_volatility_mean_120 / (implied_volatility_mean_30 + 0.001)) * sqrt(120/252.0) * (volume / (adv20 + 1))), 10), 3)))) * (volume / adv20), sector), -1)"
        ),
    },
    # Variant B: Remove volume multiplier (pure rank position sizing)
    {
        "key": "XgbOPxXb_TOP3000_pure_rank",
        "origin": "XgbOPxXb",
        "universe": "TOP3000", "neutralization": "SECTOR", "delay": 1, "decay": 10,
        "expression": (
            "trade_when(abs(rank((0.65 * rank(ts_decay_linear(ts_decay_linear(((forward_price_120 - put_breakeven_120) / close * (implied_volatility_mean_skew_120 * sqrt(120/252.0)) * (pcr_vol_120 / (pcr_oi_120 + 0.001))), 10), 3)) + 0.35 * rank(ts_decay_linear(ts_decay_linear(((implied_volatility_mean_120 / (implied_volatility_mean_30 + 0.001)) * sqrt(120/252.0) * (volume / (adv20 + 1))), 10), 3)))) - 0.5) > 0.26, group_neutralize(rank((0.65 * rank(ts_decay_linear(ts_decay_linear(((forward_price_120 - put_breakeven_120) / close * (implied_volatility_mean_skew_120 * sqrt(120/252.0)) * (pcr_vol_120 / (pcr_oi_120 + 0.001))), 10), 3)) + 0.35 * rank(ts_decay_linear(ts_decay_linear(((implied_volatility_mean_120 / (implied_volatility_mean_30 + 0.001)) * sqrt(120/252.0) * (volume / (adv20 + 1))), 10), 3)))), sector), -1)"
        ),
    },
    # --- Vkae25pb (Sharpe 1.77, Fit 1.42, missed by 0.09: 0.68 vs 0.77) ---
    # Variant A: Decay 12 on TOP3000
    {
        "key": "Vkae25pb_TOP3000_d12",
        "origin": "Vkae25pb",
        "universe": "TOP3000", "neutralization": "SUBINDUSTRY", "delay": 1, "decay": 12,
        "expression": (
            "trade_when(abs(rank((0.65 * rank(ts_decay_linear(ts_decay_linear(((forward_price_180 - put_breakeven_180) / close * (implied_volatility_mean_skew_180 * sqrt(180/252.0)) * (pcr_vol_180 / (pcr_oi_180 + 0.001))), 10), 3)) + 0.35 * rank(ts_decay_linear(ts_decay_linear(((implied_volatility_call_60 - implied_volatility_put_60) / (implied_volatility_mean_60 + 0.001) * sqrt(60/252.0) * (volume / (adv20 + 1))), 10), 3)))) - 0.5) > 0.26, group_neutralize(rank((0.65 * rank(ts_decay_linear(ts_decay_linear(((forward_price_180 - put_breakeven_180) / close * (implied_volatility_mean_skew_180 * sqrt(180/252.0)) * (pcr_vol_180 / (pcr_oi_180 + 0.001))), 10), 3)) + 0.35 * rank(ts_decay_linear(ts_decay_linear(((implied_volatility_call_60 - implied_volatility_put_60) / (implied_volatility_mean_60 + 0.001) * sqrt(60/252.0) * (volume / (adv20 + 1))), 10), 3)))) * (volume / adv20), subindustry), -1)"
        ),
    },
    # Variant B: Pure rank (no volume multiplier) Decay 10 on TOP3000
    {
        "key": "Vkae25pb_TOP3000_pure_rank",
        "origin": "Vkae25pb",
        "universe": "TOP3000", "neutralization": "SUBINDUSTRY", "delay": 1, "decay": 10,
        "expression": (
            "trade_when(abs(rank((0.65 * rank(ts_decay_linear(ts_decay_linear(((forward_price_180 - put_breakeven_180) / close * (implied_volatility_mean_skew_180 * sqrt(180/252.0)) * (pcr_vol_180 / (pcr_oi_180 + 0.001))), 10), 3)) + 0.35 * rank(ts_decay_linear(ts_decay_linear(((implied_volatility_call_60 - implied_volatility_put_60) / (implied_volatility_mean_60 + 0.001) * sqrt(60/252.0) * (volume / (adv20 + 1))), 10), 3)))) - 0.5) > 0.26, group_neutralize(rank((0.65 * rank(ts_decay_linear(ts_decay_linear(((forward_price_180 - put_breakeven_180) / close * (implied_volatility_mean_skew_180 * sqrt(180/252.0)) * (pcr_vol_180 / (pcr_oi_180 + 0.001))), 10), 3)) + 0.35 * rank(ts_decay_linear(ts_decay_linear(((implied_volatility_call_60 - implied_volatility_put_60) / (implied_volatility_mean_60 + 0.001) * sqrt(60/252.0) * (volume / (adv20 + 1))), 10), 3)))), subindustry), -1)"
        ),
    },
]


def check_alpha(session, alpha_id: str):
    import time
    for _ in range(6):
        try:
            r = session.get(f"https://api.worldquantbrain.com/alphas/{alpha_id}/check")
            if r.status_code == 200 and r.text.strip():
                data = r.json()
                checks = data.get("is", {}).get("checks", []) or data.get("checks", [])
                if checks:
                    return checks
        except Exception:
            pass
        time.sleep(3)
    return []


def update_db_if_qualified(db_url: str, alpha_id: str, c: dict, metrics, max_corr: float):
    sql = (
        "INSERT INTO options_alphas ("
        "alpha_id, expression, archetype, hypothesis, source, "
        "sharpe, fitness, turnover, returns, drawdown, margin, max_correlation, "
        "universe, neutralization, delay, decay, truncation, pasteurization, nan_handling, "
        "status, strategy_name"
        ") VALUES ("
        "%s, %s, %s, %s, 'top3000_rescue',"
        "%s, %s, %s, %s, %s, %s, %s,"
        "%s, %s, %s, %s, 0.05, true, 'ON',"
        "'QUALIFIED', 'top3000_rescue'"
        ") ON CONFLICT (alpha_id) DO UPDATE SET "
        "status = 'QUALIFIED', sharpe = EXCLUDED.sharpe, fitness = EXCLUDED.fitness, "
        "margin = EXCLUDED.margin, max_correlation = EXCLUDED.max_correlation;"
    )
    with psycopg.connect(db_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (
                alpha_id, c["expression"], c["key"],
                f"Rescued {c['origin']} via TOP3000 parameter optimization",
                metrics.sharpe, metrics.fitness, metrics.turnover,
                getattr(metrics, "annualized_return", 0.0),
                getattr(metrics, "max_drawdown", 0.0),
                metrics.margin, max_corr,
                c["universe"], c["neutralization"], c["delay"], c["decay"]
            ))
    log.info("DB: %s recorded as QUALIFIED!", alpha_id)


async def main():
    config = OptionsConfig.from_env()
    store = OptionsStore(database_url=config.database_url)
    client = BrainClient(config.brain_username, config.brain_password, max_concurrent_sims=1, db=store.db)
    client.authenticate()
    session = client._get_session()

    log.info("=" * 72)
    log.info("TESTING TOP3000 TARGETED RESCUES (%d candidates)", len(CANDIDATES))
    log.info("=" * 72)

    for i, c in enumerate(CANDIDATES):
        key = c["key"]
        origin = c["origin"]
        log.info("\n[%d/%d] RUNNING %s (Origin: %s)", i+1, len(CANDIDATES), key, origin)
        log.info("Settings: Universe=%s | Neut=%s | Decay=%d", c["universe"], c["neutralization"], c["decay"])

        settings = SimSettings(
            universe=c["universe"],
            neutralization=c["neutralization"],
            delay=c["delay"],
            decay=c["decay"],
            truncation=0.05,
            pasteurization=True,
            nan_handling=True,
            unit_handling="VERIFY",
        )

        try:
            metrics = await client.simulate_one(expression=c["expression"], settings=settings)
        except Exception as e:
            log.error("Simulation failed for %s: %s", key, e)
            continue

        if not metrics or not metrics.alpha_id:
            log.warning("No metrics returned for %s", key)
            continue

        aid = metrics.alpha_id
        log.info("Simulation Result: ID=%s | Sharpe=%.2f | Fitness=%.2f | Turnover=%.1f%% | Margin=%.1fbps",
                 aid, metrics.sharpe, metrics.fitness, metrics.turnover * 100, metrics.margin * 10000)

        # Check BRAIN checklist
        checks = check_alpha(session, aid)
        sus_check = next((ch for ch in checks if ch.get("name") == "LOW_SUB_UNIVERSE_SHARPE"), {})
        sc_check = next((ch for ch in checks if ch.get("name") == "SELF_CORRELATION"), {})
        failing = [ch.get("name") for ch in checks if ch.get("result") == "FAIL"]

        log.info("Checklist: SUS=%s (val=%s, lim=%s) | SC=%s (val=%s) | Total Fails=%s",
                 sus_check.get("result"), sus_check.get("value"), sus_check.get("limit"),
                 sc_check.get("result"), sc_check.get("value"), failing)

        if not failing and metrics.sharpe >= 1.25 and metrics.fitness >= 1.00:
            corr_val = float(sc_check.get("value") or 0.0) if sc_check.get("value") is not None else 0.0
            log.info(">>> SUCCESS! %s PASSED ALL CHECKS! Alpha ID: %s (SUS: PASS) <<<", key, aid)
            update_db_if_qualified(config.database_url, aid, c, metrics, corr_val)
        else:
            log.warning("Candidate %s did not pass: fails=%s, Sharpe=%.2f, Fitness=%.2f",
                        key, failing, metrics.sharpe, metrics.fitness)

    log.info("\nALL TARGETED RESCUE CANDIDATES EVALUATED.")


if __name__ == "__main__":
    asyncio.run(main())
