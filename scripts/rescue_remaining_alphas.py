"""
Rescue the remaining 3 blocked alphas: Vkae25pb, N1a8nR9o, JjN2O3mA
Using the proven winning formula: TOP3000 with decay 12 smoothing!
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
log = logging.getLogger("rescue_remaining")

CANDIDATES = [
    # 1. Vkae25pb with decay 12 (was 8)
    {
        "key": "Vkae25pb_TOP3000_d12",
        "origin": "Vkae25pb",
        "archetype": "Bivariate_Put180_Skew60_d12_TOP3000_SUBIND",
        "universe": "TOP3000", "neutralization": "SUBINDUSTRY", "delay": 1, "decay": 12,
        "expression": (
            "trade_when(abs(rank((0.65 * rank(ts_decay_linear(ts_decay_linear(((forward_price_180 - put_breakeven_180) / close * (implied_volatility_mean_skew_180 * sqrt(180/252.0)) * (pcr_vol_180 / (pcr_oi_180 + 0.001))), 10), 3)) + 0.35 * rank(ts_decay_linear(ts_decay_linear(((implied_volatility_call_60 - implied_volatility_put_60) / (implied_volatility_mean_60 + 0.001) * sqrt(60/252.0) * (volume / (adv20 + 1))), 10), 3)))) - 0.5) > 0.26, group_neutralize(rank((0.65 * rank(ts_decay_linear(ts_decay_linear(((forward_price_180 - put_breakeven_180) / close * (implied_volatility_mean_skew_180 * sqrt(180/252.0)) * (pcr_vol_180 / (pcr_oi_180 + 0.001))), 10), 3)) + 0.35 * rank(ts_decay_linear(ts_decay_linear(((implied_volatility_call_60 - implied_volatility_put_60) / (implied_volatility_mean_60 + 0.001) * sqrt(60/252.0) * (volume / (adv20 + 1))), 10), 3)))) * (volume / adv20), subindustry), -1)"
        ),
    },
    # 2. N1a8nR9o with decay 12 (was 8)
    {
        "key": "N1a8nR9o_TOP3000_d12",
        "origin": "N1a8nR9o",
        "archetype": "Bivariate_Put90_Skew30_d12_TOP3000_SUBIND",
        "universe": "TOP3000", "neutralization": "SUBINDUSTRY", "delay": 1, "decay": 12,
        "expression": (
            "trade_when(abs(rank((0.65 * rank(ts_decay_linear(ts_decay_linear(((forward_price_90 - put_breakeven_90) / close * (implied_volatility_mean_skew_90 * sqrt(90/252.0)) * (pcr_vol_90 / (pcr_oi_90 + 0.001))), 10), 3)) + 0.35 * rank(ts_decay_linear(ts_decay_linear(((implied_volatility_call_30 - implied_volatility_put_30) / (implied_volatility_mean_30 + 0.001) * sqrt(30/252.0) * (volume / (adv20 + 1))), 10), 3)))) - 0.5) > 0.26, group_neutralize(rank((0.65 * rank(ts_decay_linear(ts_decay_linear(((forward_price_90 - put_breakeven_90) / close * (implied_volatility_mean_skew_90 * sqrt(90/252.0)) * (pcr_vol_90 / (pcr_oi_90 + 0.001))), 10), 3)) + 0.35 * rank(ts_decay_linear(ts_decay_linear(((implied_volatility_call_30 - implied_volatility_put_30) / (implied_volatility_mean_30 + 0.001) * sqrt(30/252.0) * (volume / (adv20 + 1))), 10), 3)))) * (volume / adv20), subindustry), -1)"
        ),
    },
    # 3. JjN2O3mA with decay 12 (was 8)
    {
        "key": "JjN2O3mA_TOP3000_d12",
        "origin": "JjN2O3mA",
        "archetype": "T2_Term180_30_Cal_50_d12_TOP3000_SECTOR",
        "universe": "TOP3000", "neutralization": "SECTOR", "delay": 1, "decay": 12,
        "expression": (
            "trade_when(abs(rank((0.5 * rank(ts_decay_linear(ts_decay_linear(((implied_volatility_mean_180 / (implied_volatility_mean_30 + 0.001)) * (implied_volatility_mean_skew_30 * sqrt(30/252.0))), 10), 3)) + 0.5 * rank(ts_decay_linear(ts_decay_linear(((forward_price_180 - forward_price_30) / close * (implied_volatility_mean_180 / (implied_volatility_mean_30 + 0.001)) * (volume / (adv20 + 1))), 10), 3)))) - 0.5) > 0.26, group_neutralize(rank((0.5 * rank(ts_decay_linear(ts_decay_linear(((implied_volatility_mean_180 / (implied_volatility_mean_30 + 0.001)) * (implied_volatility_mean_skew_30 * sqrt(30/252.0))), 10), 3)) + 0.5 * rank(ts_decay_linear(ts_decay_linear(((forward_price_180 - forward_price_30) / close * (implied_volatility_mean_180 / (implied_volatility_mean_30 + 0.001)) * (volume / (adv20 + 1))), 10), 3)))) * (volume / adv20), sector), -1)"
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


def save_to_vault(db_url: str, alpha_id: str, c: dict, metrics, max_corr: float):
    sql = (
        "INSERT INTO options_alphas ("
        "alpha_id, expression, archetype, hypothesis, source, "
        "sharpe, fitness, turnover, returns, drawdown, margin, max_correlation, "
        "universe, neutralization, delay, decay, truncation, pasteurization, nan_handling, "
        "status, strategy_name"
        ") VALUES ("
        "%s, %s, %s, %s, 'rescue_formula',"
        "%s, %s, %s, %s, %s, %s, %s,"
        "%s, %s, %s, %s, 0.05, true, 'ON',"
        "'QUALIFIED', 'rescue_formula'"
        ") ON CONFLICT DO NOTHING;"
    )
    with psycopg.connect(db_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (
                alpha_id, c["expression"], c["archetype"],
                f"Rescued {c['origin']} via TOP3000 decay 12 smoothing",
                metrics.sharpe, metrics.fitness, metrics.turnover,
                getattr(metrics, "annualized_return", 0.0),
                getattr(metrics, "max_drawdown", 0.0),
                metrics.margin, max_corr,
                c["universe"], c["neutralization"], c["delay"], c["decay"]
            ))
            # Also mark original as SUPERSEDED
            cur.execute("UPDATE options_alphas SET status = 'SUPERSEDED' WHERE alpha_id = %s;", (c["origin"],))
    log.info("DB: %s recorded as QUALIFIED! (Old %s -> SUPERSEDED)", alpha_id, c["origin"])


async def main():
    config = OptionsConfig.from_env()
    store = OptionsStore(database_url=config.database_url)
    client = BrainClient(config.brain_username, config.brain_password, max_concurrent_sims=1, db=store.db)
    client.authenticate()
    session = client._get_session()

    log.info("=" * 72)
    log.info("RUNNING RESCUE BATCH: Vkae25pb, N1a8nR9o, JjN2O3mA with DECAY 12")
    log.info("=" * 72)

    for i, c in enumerate(CANDIDATES):
        key = c["key"]
        origin = c["origin"]
        log.info("\n[%d/%d] RUNNING %s (Origin: %s)", i+1, len(CANDIDATES), key, origin)

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
            save_to_vault(config.database_url, aid, c, metrics, corr_val)
        else:
            log.warning("Candidate %s did not pass: fails=%s, Sharpe=%.2f, Fitness=%.2f",
                        key, failing, metrics.sharpe, metrics.fitness)

    log.info("\nRESCUE BATCH COMPLETE.")


if __name__ == "__main__":
    asyncio.run(main())
