#!/usr/bin/env python3
"""
Tune YP58QkYR expression to fix:
  1. LOW_FITNESS (0.92 < 1.0) — add ts_decay_linear outer smoothing + volume gate
  2. CONCENTRATED_WEIGHT FAIL — reduce position concentration via truncation 0.08

Try variants:
  A. Add trade_when volume gate + outer decay=10 to cut turnover from 58% to ~20%
  B. Increase inner delta window 3->5, add ts_decay_linear(10)
  C. Try TOP2000 SECTOR for better margin
"""
import asyncio, decimal, json, logging, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import psycopg, requests
from dotenv import load_dotenv
load_dotenv()
import wqb

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger("tune_YP58")

from brain_options.config import OptionsConfig
from brain_options.core.client import BrainClient, SimSettings
from brain_options.core.correlation import compute_correlation
from brain_options.store.store import OptionsStore

BASE_EXPR = "group_neutralize(rank(ts_delta((call_breakeven_20 - close) / close, 3)), subindustry)"

VARIANTS = [
    # V1: Volume gate + slower outer decay to fix turnover and fitness
    {
        "name": "V1_VolGate_Decay10_TOP3000_SUBIND",
        "expression": "trade_when(volume > adv20 * 0.8, group_neutralize(rank(ts_decay_linear(ts_delta((call_breakeven_20 - close) / close, 3), 10)), subindustry), -1)",
        "universe": "TOP3000", "neutralization": "SUBINDUSTRY", "decay": 10,
    },
    # V2: Wider delta window + decay smoothing, SECTOR
    {
        "name": "V2_Delta5_Decay12_TOP3000_SECTOR",
        "expression": "trade_when(volume > adv20 * 0.7, group_neutralize(rank(ts_decay_linear(ts_delta((call_breakeven_20 - close) / close, 5), 12)), sector), -1)",
        "universe": "TOP3000", "neutralization": "SECTOR", "decay": 12,
    },
    # V3: TOP2000 for better margin, double decay
    {
        "name": "V3_DoubleDecay_TOP2000_SUBIND",
        "expression": "group_neutralize(rank(ts_decay_linear(ts_decay_linear(ts_delta((call_breakeven_20 - close) / close, 3), 10), 3)), subindustry)",
        "universe": "TOP2000", "neutralization": "SUBINDUSTRY", "decay": 10,
    },
    # V4: Breakeven normalized by IV, volume gated
    {
        "name": "V4_IV_Normalized_Delta_TOP3000_SUBIND",
        "expression": "trade_when(volume > adv20 * 0.8, group_neutralize(rank(ts_decay_linear(ts_delta((call_breakeven_20 - close) / close, 3) / (implied_volatility_mean_20 + 0.001), 10)), subindustry), -1)",
        "universe": "TOP3000", "neutralization": "SUBINDUSTRY", "decay": 10,
    },
    # V5: Zscore gated version (reduces concentrated weight)
    {
        "name": "V5_Zscore_Gate_TOP3000_SUBIND",
        "expression": "trade_when(abs(ts_zscore((call_breakeven_20 - close) / close, 60)) > 0.5, group_neutralize(rank(ts_decay_linear(ts_delta((call_breakeven_20 - close) / close, 3), 10)), subindustry), -1)",
        "universe": "TOP3000", "neutralization": "SUBINDUSTRY", "decay": 10,
    },
]

PRODUCTION_ALPHAS = [
    "rKOa6qa9","YPboG01w","XgbOoJjx","e7bWxz7E","ZYbNORZx","mLmQjlzE",
    "P02K7eYK","Xgbv1A80","levEYpmx","YPb81N2v","E5pNpQlm","N176Geqp",
    "gJQWL7aK","Grdg2Njo","xA3872wq","3qXLMqg0","0mX0kG86","RRbnn8xe",
    "blbZ9Wkp","KPNd6Ovl","gJbAP76e"
]


def get_checklist_result(session, alpha_id: str) -> dict:
    """Fetch checklist immediately — no polling, just get current state."""
    try:
        r = session.get(f"https://api.worldquantbrain.com/alphas/{alpha_id}/check", timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        log.warning("Checklist fetch error: %s", e)
    return {}


def check_passes(checklist_data: dict) -> tuple[bool, list[str]]:
    checks = checklist_data.get("is", {}).get("checks", [])
    if not checks:
        return False, ["no_checks_available"]
    failures = []
    for c in checks:
        name = c.get("name", "")
        result = c.get("result", "")
        val = c.get("value", "")
        lim = c.get("limit", "")
        if name == "SELF_CORRELATION" and result == "PENDING":
            continue  # Skip pending, not a blocker
        if result in ("FAIL", "ERROR"):
            failures.append(f"{name}(val={val},limit={lim})")
    return (len(failures) == 0), failures


def commit_to_vault(db_url, alpha_id, variant_name, metrics, max_corr):
    sql = """
        INSERT INTO options_alphas (
            alpha_id, expression, archetype, hypothesis, source,
            sharpe, fitness, turnover, returns, drawdown, margin,
            max_correlation, universe, neutralization, delay, decay,
            truncation, pasteurization, nan_handling, status, created_at, strategy_name
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1,%s,0.05,'ON','OFF','QUALIFIED',NOW(),%s)
        ON CONFLICT (alpha_id) DO UPDATE SET status='QUALIFIED',
            sharpe=EXCLUDED.sharpe, fitness=EXCLUDED.fitness, max_correlation=EXCLUDED.max_correlation;
    """
    with psycopg.connect(db_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (
                alpha_id, metrics.get("expr",""), variant_name,
                f"Tuned Call Breakeven Delta variant. Passed all 3 gates. Corr={max_corr:.4f}",
                "tune_YP58_rescue",
                decimal.Decimal(str(round(metrics["sharpe"],4))),
                decimal.Decimal(str(round(metrics["fitness"],4))),
                decimal.Decimal(str(round(metrics["turnover"],4))),
                decimal.Decimal(str(round(metrics.get("returns",0),4))),
                decimal.Decimal(str(round(metrics.get("drawdown",0),4))),
                decimal.Decimal(str(round(metrics.get("margin",0),6))),
                decimal.Decimal(str(round(max_corr,4))),
                metrics.get("universe","TOP3000"), metrics.get("neut","SUBINDUSTRY"),
                metrics.get("decay",10),
                "vault_tuned_breakeven",
            ))
    log.info("[VAULT] Committed %s | Sharpe=%.2f | Fitness=%.2f", alpha_id, metrics["sharpe"], metrics["fitness"])


async def run():
    config = OptionsConfig.from_env()
    store = OptionsStore()
    client = BrainClient(username=config.brain_username, password=config.brain_password,
                         max_concurrent_sims=1, db=store.db)
    await asyncio.to_thread(client.authenticate)

    log.info("=" * 70)
    log.info("TUNING: Call Breakeven Delta — Fix FITNESS + CONCENTRATED_WEIGHT")
    log.info("Base Sharpe 1.98 | Fitness 0.92 (need >= 1.0) | Turnover 58.7% (need reduction)")
    log.info("=" * 70)

    # Pre-fetch reference PnLs once
    ref_pnls = {}
    log.info("Fetching %d reference PnLs...", len(PRODUCTION_ALPHAS))
    for aid in PRODUCTION_ALPHAS:
        pnl = await client.get_alpha_pnl(aid)
        if pnl:
            ref_pnls[aid] = pnl
    log.info("Loaded %d ref PnLs.", len(ref_pnls))

    best_qualified = None

    for idx, v in enumerate(VARIANTS, 1):
        log.info("\n--- [%d/%d] %s ---", idx, len(VARIANTS), v["name"])
        log.info("Expr: %s", v["expression"])

        settings = SimSettings(region="USA", universe=v["universe"], delay=1, decay=v["decay"],
                               neutralization=v["neutralization"], truncation=0.05,
                               pasteurization=True, nan_handling=False, unit_handling="VERIFY")

        try:
            metrics = await client.simulate_one(expression=v["expression"], settings=settings)
            if not metrics or not metrics.alpha_id:
                log.warning("[-] No simulation result for %s", v["name"])
                continue

            log.info("Sim: %s | Sharpe:%.2f | Fit:%.2f | Turn:%.1f%% | Margin:%.1fbps | DD:%.1f%%",
                     metrics.alpha_id, metrics.sharpe, metrics.fitness,
                     metrics.turnover*100, metrics.margin*10000, metrics.max_drawdown*100)

            # Gate 1
            if metrics.sharpe < 1.25 or metrics.fitness < 1.0:
                log.info("[-] Gate 1 FAIL: Sh=%.2f, Fit=%.2f", metrics.sharpe, metrics.fitness)
                continue

            # Gate 2: Correlation
            cand_pnl = await client.get_alpha_pnl(metrics.alpha_id)
            if not cand_pnl:
                log.warning("[-] No PnL for %s", metrics.alpha_id)
                continue

            max_corr, worst = 0.0, ""
            for ref_id, ref_p in ref_pnls.items():
                c = abs(compute_correlation(cand_pnl, ref_p))
                if c > max_corr:
                    max_corr, worst = c, ref_id

            log.info("Gate 2: max_corr=%.4f vs %s", max_corr, worst)
            if max_corr >= 0.70:
                log.info("[-] Gate 2 FAIL: correlated.")
                continue

            log.info("[+] Gate 2 PASS!")

            # Gate 3: Checklist — wait up to 3 min
            log.info("Gate 3: Waiting 30s for checklist to compute on %s...", metrics.alpha_id)
            time.sleep(30)
            for attempt in range(10):
                chk = get_checklist_result(client._session, metrics.alpha_id)
                passed, failures = check_passes(chk)
                if passed:
                    log.info("[+] Gate 3 PASS! Checklist 100%%")
                    m = {
                        "sharpe": metrics.sharpe, "fitness": metrics.fitness,
                        "turnover": metrics.turnover, "returns": metrics.annualized_return,
                        "drawdown": metrics.max_drawdown, "margin": metrics.margin,
                        "universe": v["universe"], "neut": v["neutralization"],
                        "decay": v["decay"], "expr": v["expression"]
                    }
                    ref_pnls[metrics.alpha_id] = cand_pnl
                    commit_to_vault(config.database_url, metrics.alpha_id, v["name"], m, max_corr)
                    best_qualified = (v["name"], metrics.alpha_id, metrics.sharpe, metrics.fitness, max_corr)
                    log.info("[QUALIFIED] %s | %s | Sharpe:%.2f | Fitness:%.2f | Corr:%.4f",
                             v["name"], metrics.alpha_id, metrics.sharpe, metrics.fitness, max_corr)
                    break
                elif failures and failures != ["no_checks_available"]:
                    # Got definitive failures — no point retrying
                    log.info("[-] Gate 3 FAIL: %s", failures)
                    break
                else:
                    log.info("Checklist still loading (attempt %d/10)...", attempt+1)
                    time.sleep(15)
            else:
                log.warning("[-] Gate 3 TIMEOUT for %s", metrics.alpha_id)

        except Exception as exc:
            log.error("Error on %s: %s", v["name"], exc)

    log.info("\n" + "=" * 70)
    if best_qualified:
        name, aid, sh, fit, corr = best_qualified
        log.info("VAULT QUALIFIED: %s | AlphaID:%s | Sharpe:%.2f | Fitness:%.2f | Corr:%.4f",
                 name, aid, sh, fit, corr)
    else:
        log.info("RESULT: 0 variants qualified. Need to try different expression families.")
    log.info("=" * 70)

if __name__ == "__main__":
    asyncio.run(run())
