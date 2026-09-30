#!/usr/bin/env python3
"""
Re-simulate YP58QkYR (Call Breakeven Hurdle Acceleration, Sharpe 1.91)
with fresh simulation + full 3-gate check.
This alpha PASSED the correlation gate (rho=0.657 < 0.70) but
failed checklist due to alpha ID expiry. Fresh sim = fresh alpha ID.
"""
import asyncio, decimal, logging, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import psycopg, requests
from dotenv import load_dotenv
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger("fresh_sim")
from brain_options.config import OptionsConfig
from brain_options.core.client import BrainClient, SimSettings
from brain_options.core.correlation import compute_correlation
from brain_options.store.store import OptionsStore

EXPRESSION = "group_neutralize(rank(ts_delta((call_breakeven_20 - close) / close, 3)), subindustry)"
ARCHETYPE  = "Call_Breakeven_Hurdle_Acceleration"
HYPOTHESIS = "Short-horizon delta of call breakeven premium normalized to close captures rapid supply-demand shifts. Subindustry neutralization isolates alpha. Proven Sharpe 1.91, corr=0.657 vs portfolio."

PRODUCTION_ALPHAS = [
    "rKOa6qa9","YPboG01w","XgbOoJjx","e7bWxz7E","ZYbNORZx","mLmQjlzE",
    "P02K7eYK","Xgbv1A80","levEYpmx","YPb81N2v","E5pNpQlm","N176Geqp",
    "gJQWL7aK","Grdg2Njo","xA3872wq","3qXLMqg0","0mX0kG86","RRbnn8xe",
    "blbZ9Wkp","KPNd6Ovl","gJbAP76e"
]

def verify_checklist(session, alpha_id):
    url = f"https://api.worldquantbrain.com/alphas/{alpha_id}/check"
    for _ in range(20):
        try:
            r = session.get(url, timeout=15)
            if r.status_code == 200:
                data = r.json()
                checks = data.get("checks", [])
                if checks:
                    fails = [c.get("name") for c in checks if c.get("result") in ("FAIL","ERROR")]
                    return (False, f"FAIL: {fails}") if fails else (True, "100% PASS")
        except Exception as e:
            log.warning("Checklist poll error: %s", e)
        time.sleep(4)
    return False, "Timeout"

def commit_to_vault(db_url, alpha_id, metrics, max_corr):
    sql = """
        INSERT INTO options_alphas (
            alpha_id, expression, archetype, hypothesis, source,
            sharpe, fitness, turnover, returns, drawdown, margin,
            max_correlation, universe, neutralization, delay, decay,
            truncation, pasteurization, nan_handling, status, created_at, strategy_name
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1,6,0.05,'ON','OFF','QUALIFIED',NOW(),%s)
        ON CONFLICT (alpha_id) DO UPDATE SET status='QUALIFIED',
            sharpe=EXCLUDED.sharpe, fitness=EXCLUDED.fitness, max_correlation=EXCLUDED.max_correlation;
    """
    with psycopg.connect(db_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (
                alpha_id, EXPRESSION, ARCHETYPE, HYPOTHESIS, "fresh_sim_rescue",
                decimal.Decimal(str(round(metrics.sharpe,4))),
                decimal.Decimal(str(round(metrics.fitness,4))),
                decimal.Decimal(str(round(metrics.turnover,4))),
                decimal.Decimal(str(round(metrics.annualized_return,4))),
                decimal.Decimal(str(round(metrics.max_drawdown,4))),
                decimal.Decimal(str(round(metrics.margin,6))),
                decimal.Decimal(str(round(max_corr,4))),
                "TOP3000", "SUBINDUSTRY", "vault_rescue"
            ))
    log.info("[VAULT] Committed %s (Sharpe=%.2f) as QUALIFIED.", alpha_id, metrics.sharpe)

async def run():
    config = OptionsConfig.from_env()
    store = OptionsStore()
    client = BrainClient(username=config.brain_username, password=config.brain_password, max_concurrent_sims=1, db=store.db)
    await asyncio.to_thread(client.authenticate)

    log.info("=== FRESH SIMULATION: Call Breakeven Hurdle Acceleration ===")
    log.info("Expression: %s", EXPRESSION)

    settings = SimSettings(region="USA", universe="TOP3000", delay=1, decay=6,
                           neutralization="SUBINDUSTRY", truncation=0.05,
                           pasteurization=True, nan_handling=False, unit_handling="VERIFY")

    metrics = await client.simulate_one(expression=EXPRESSION, settings=settings)
    if not metrics or not metrics.alpha_id:
        log.error("Simulation failed. BRAIN may be at capacity.")
        return

    log.info("RESULT | Alpha: %s | Sharpe: %.2f | Fitness: %.2f | Turnover: %.1f%% | Margin: %.1f bps | DD: %.1f%%",
             metrics.alpha_id, metrics.sharpe, metrics.fitness,
             metrics.turnover*100, metrics.margin*10000, metrics.max_drawdown*100)

    # Gate 1 check
    if metrics.sharpe < 1.20:
        log.warning("Gate 1 FAIL: Sharpe %.2f < 1.20", metrics.sharpe)
        return

    # Gate 2: Correlation
    log.info("Fetching PnL for correlation check...")
    cand_pnl = await client.get_alpha_pnl(metrics.alpha_id)
    if not cand_pnl:
        log.error("No PnL returned — cannot verify correlation.")
        return

    ref_pnls = {}
    for aid in PRODUCTION_ALPHAS:
        pnl = await client.get_alpha_pnl(aid)
        if pnl:
            ref_pnls[aid] = pnl

    max_corr, worst = 0.0, ""
    for ref_id, ref_p in ref_pnls.items():
        c = abs(compute_correlation(cand_pnl, ref_p))
        if c > max_corr:
            max_corr, worst = c, ref_id

    log.info("Gate 2 | max_corr=%.4f vs %s", max_corr, worst)
    if max_corr >= 0.70:
        log.warning("Gate 2 FAIL: rho=%.4f vs %s — CORRELATED", max_corr, worst)
        return

    log.info("Gate 2 PASS!")

    # Gate 3: Checklist
    log.info("Gate 3 | Running platform checklist on %s...", metrics.alpha_id)
    chk_ok, chk_msg = verify_checklist(client._session, metrics.alpha_id)
    log.info("Checklist result: %s", chk_msg)
    if not chk_ok:
        log.warning("Gate 3 FAIL: %s", chk_msg)
        return

    # QUALIFIED!
    commit_to_vault(config.database_url, metrics.alpha_id, metrics, max_corr)
    log.info("=== VAULT POPULATED! Alpha %s | Sharpe %.2f | Corr %.4f ===",
             metrics.alpha_id, metrics.sharpe, max_corr)

if __name__ == "__main__":
    asyncio.run(run())
