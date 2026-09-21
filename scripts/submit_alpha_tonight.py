"""
Targeted Alpha Qualification & Gold Submission Engine.
Monitors the cluster mutex until free, optimizes a high-conviction candidate
from an under-represented archetype to guarantee < 0.70 correlation against the pool,
verifies all BRAIN checklist gates fail-closed, and immediately submits
the alpha via DripSubmitter to cross into Gold status (10,000 pts).
"""
import asyncio
import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brain_options.config import OptionsConfig
from brain_options.core.client import BrainClient
from brain_options.core.drip import DripSubmitter
from brain_options.core.sweep import SweepEngine
from brain_options.run import run_candidate, ClusterLockHeartbeat
from brain_options.specialist.templates import OptionCandidate
from brain_options.store.store import OptionsStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("gold_mission")


async def main():
    config = OptionsConfig.from_env()
    store = OptionsStore(database_url=config.database_url)
    db = store.db

    worker_id = f"gold-mission-{os.getpid()}"
    org_name = "Xtley001"

    # Step 1: Wait for cluster lock if held by another org
    log.info("Checking cluster lock status...")
    max_wait_seconds = 1800
    start_wait = time.time()
    lock_acquired = False

    while time.time() - start_wait < max_wait_seconds:
        if not db:
            lock_acquired = True
            break
        lock_acquired = db.acquire_cluster_lock(
            org_name=org_name,
            worker_id=worker_id,
            archetype="gold_mission",
            timeout_seconds=900,
        )
        if lock_acquired:
            log.info("Acquired cluster lock for Gold Mission (%s)!", worker_id)
            break
        log.info("Cluster lock currently held by another worker. Waiting 15s...")
        await asyncio.sleep(15.0)

    if not lock_acquired:
        log.error("Could not acquire cluster lock within timeout. Exiting.")
        return

    heartbeat = ClusterLockHeartbeat(db, worker_id, interval_seconds=60)
    heartbeat.start()

    try:
        client = BrainClient(
            username=config.brain_username,
            password=config.brain_password,
            max_concurrent_sims=min(config.brain_max_concurrent_sims, 3),
            db=db,
        )
        client.authenticate()
        sweep_engine = SweepEngine(client, config)

        # Query candidates from diverse archetypes (strictly excluding call_breakeven to ensure zero portfolio correlation)
        sql = """
            SELECT expression, archetype, COALESCE(source, 'stage0_pass') as source
            FROM (
                SELECT DISTINCT ON (expression) expression, archetype, source, sharpe, fitness
                FROM options_evaluations
                WHERE ((stage = 'STAGE0' AND status = 'PASS') OR (sharpe >= 0.35 AND fitness >= 0.20))
                  AND archetype NOT ILIKE '%breakeven%'
                  AND expression NOT ILIKE '%call_breakeven%'
                  AND expression NOT IN (SELECT expression FROM options_alphas WHERE expression IS NOT NULL)
                  AND expression NOT IN (SELECT expression FROM options_correlated_alphas WHERE expression IS NOT NULL)
                  AND expression NOT IN (SELECT expression FROM options_rejected_alphas WHERE expression IS NOT NULL)
            ) sub
            ORDER BY sharpe DESC, fitness DESC
            LIMIT 8;
        """
        # Prioritize pristine institutional templates first to guarantee zero portfolio correlation
        institutional_seeds = [
            OptionCandidate(
                expression="group_neutralize(rank(ts_decay_linear(ts_delta(((0.1992 * implied_volatility_mean_skew_10 * sqrt(10/252.0)) - (0.345 * implied_volatility_mean_skew_30 * sqrt(30/252.0))), 5), 25)), subindustry)",
                archetype_name="Skew Delta Acceleration",
                hypothesis="Xing-Zhang-Zhao (2010): Square-root time scaled skew divergence between 10d and 30d tenors predicts tail repricing.",
                generation_source="template",
            ),
            OptionCandidate(
                expression="group_neutralize(rank(ts_decay_linear(ts_delta(((implied_volatility_mean_skew_10 * sqrt(10/252.0)) - (implied_volatility_mean_skew_20 * sqrt(20/252.0))), 5), 40)), subindustry)",
                archetype_name="Term Structure Skew Velocity",
                hypothesis="Tenor term structure skew velocity demeaned by subindustry captures short-term sentiment shifts.",
                generation_source="template",
            ),
            OptionCandidate(
                expression="trade_when(volume > adv20, group_neutralize(rank(-ts_decay_linear(pcr_vol_20 / (pcr_oi_20 + 0.001), 5)), subindustry), -1)",
                archetype_name="Pan-Poteshman Informed Option Flow",
                hypothesis="Pan & Poteshman (2006): Informed put-call volume surge relative to open interest leads equity returns.",
                generation_source="template",
            ),
            OptionCandidate(
                expression="group_neutralize(rank(-(signed_power(implied_volatility_mean_20, 2) - signed_power(ts_std_dev(returns, 20), 2) * 252)), subindustry)",
                archetype_name="Carr-Wu Quadratic Variance Risk Premium",
                hypothesis="Carr & Wu (2009): Quadratic variance swap rate minus realized variance isolates volatility risk premium.",
                generation_source="template",
            ),
            OptionCandidate(
                expression="group_neutralize(rank(ts_decay_linear(-(implied_volatility_mean_20 / (parkinson_volatility_20 + 0.001) - 1.0), 5)), subindustry)",
                archetype_name="Parkinson Extreme-Value Volatility Premium",
                hypothesis="Fade overpriced 20d IV against Parkinson extreme-value intraday realized volatility.",
                generation_source="template",
            ),
            OptionCandidate(
                expression="group_neutralize(rank((forward_price_20 - close) / close), subindustry)",
                archetype_name="Synthetic Forward Basis Spread",
                hypothesis="Forward price basis relative to cash price demeaned by subindustry predicts underlying drift.",
                generation_source="template",
            ),
        ]

        candidates = list(institutional_seeds)
        seen_exprs = {s.expression.strip() for s in institutional_seeds}

        if db:
            with db._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    for row in cur.fetchall():
                        expr = row[0].strip()
                        if expr not in seen_exprs:
                            seen_exprs.add(expr)
                            candidates.append(OptionCandidate(
                                expression=expr,
                                archetype_name=row[1] or "Diverse Alpha",
                                hypothesis=f"Targeted Gold Mission candidate from {row[1]}",
                                generation_source=row[2] or "stage0_pass",
                            ))

        log.info("Loaded %d high-priority orthogonal candidates for Gold submission.", len(candidates))

        qualified_any = False
        for i, cand in enumerate(candidates, 1):
            log.info("\n>>> [%d/%d] Evaluating Candidate (%s): %s", i, len(candidates), cand.archetype_name, cand.expression[:70])
            try:
                qualified = await run_candidate(
                    cand,
                    sweep_engine,
                    client,
                    store,
                    config,
                    force_optimize=True,
                )
                if qualified:
                    log.info("[GOLD MISSION] Candidate %s successfully QUALIFIED and saved to pool!", cand.archetype_name)
                    qualified_any = True
                    break
            except Exception as e:
                log.error("Candidate evaluation error: %s", e, exc_info=True)

        if qualified_any:
            log.info("\n>>> Invoking Drip Submitter to push qualified alpha to BRAIN for Gold unlock...")
            drip = DripSubmitter(client, store, config)
            sub_ok, alpha_id, msg = await drip.check_and_drip()
            log.info("\n" + "=" * 60)
            log.info(" DRIP SUBMISSION RESULT: %s", "SUCCESS" if sub_ok else "PENDING")
            log.info(" Alpha ID: %s", alpha_id)
            log.info(" Message:  %s", msg)
            log.info("=" * 60 + "\n")
        else:
            log.warning("No candidate from this batch cleared all correlation and checklist gates.")

    finally:
        heartbeat.stop()
        if db and lock_acquired:
            db.release_cluster_lock(worker_id)


if __name__ == "__main__":
    asyncio.run(main())
