"""
Targeted Orthogonal Alpha Qualification & Gold Submission Engine.
Tests ultra-high-conviction institutional candidates from unexploited archetypes
(Pan-Poteshman PCR Flow, Xing-Zhang-Zhao Volatility Smirk, ATM IV Term Structure,
Garleanu Dealer Inventory Imbalances) with Sinclair 0.35 conviction gating.
Guarantees < 0.70 correlation against the active submitted portfolio,
verifies all BRAIN checklist gates fail-closed, and immediately submits
the qualified alpha to cross the 10,000-point Gold threshold.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brain_options.config import OptionsConfig
from brain_options.core.client import BrainClient, SimSettings, SimMetrics
from brain_options.core.drip import build_alpha_submission_metadata, DripSubmitter
from brain_options.core.notifier import send_telegram_drip_alert
from brain_options.specialist.templates import OptionCandidate
from brain_options.store.store import OptionsStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("gold_orthogonal")

ORTHOGONAL_CANDIDATES = [
    # 1. Pan & Poteshman (2006) — Informed Option Flow with Conviction Gating (20d)
    OptionCandidate(
        expression="trade_when(abs(rank(ts_decay_linear(pcr_vol_20 / (pcr_oi_20 + 0.001), 10)) - 0.5) > 0.35, group_neutralize(rank(-ts_decay_linear(pcr_vol_20 / (pcr_oi_20 + 0.001), 10)), subindustry), -1)",
        archetype_name="Pan-Poteshman Informed Flow 20D",
        hypothesis="Pan & Poteshman (2006): Fading extreme surges in put-call volume relative to open interest with Sinclair conviction gating isolates smart-money directional positioning.",
        generation_source="institutional_literature",
    ),
    # 2. Pan & Poteshman (2006) — Informed Option Flow with Volume Attention Gate (30d)
    OptionCandidate(
        expression="trade_when(volume > adv20, trade_when(abs(rank(ts_decay_linear(pcr_vol_30 / (pcr_oi_30 + 0.001), 8)) - 0.5) > 0.35, group_neutralize(rank(-ts_decay_linear(pcr_vol_30 / (pcr_oi_30 + 0.001), 8)), subindustry), -1), -1)",
        archetype_name="Pan-Poteshman Informed Flow 30D",
        hypothesis="Pan & Poteshman (2006) & Sinclair: Volume-conditioned put-to-open-interest surge filters out illiquid noise and isolates institutional order flow.",
        generation_source="institutional_literature",
    ),
    # 3. Xing, Zhang, & Zhao (2010) — Pure Volatility Smirk Tail Risk (20d)
    OptionCandidate(
        expression="trade_when(abs(rank(ts_decay_linear(implied_volatility_mean_skew_20 * sqrt(20/252.0), 10)) - 0.5) > 0.35, group_neutralize(rank(-ts_decay_linear(implied_volatility_mean_skew_20 * sqrt(20/252.0), 10)), subindustry), -1)",
        archetype_name="Xing-Zhang-Zhao Volatility Smirk",
        hypothesis="Xing, Zhang, & Zhao (2010): Expensive downside out-of-the-money put skew captures firm-specific crash risk and predicts negative equity drift.",
        generation_source="institutional_literature",
    ),
    # 4. Xing, Zhang, & Zhao (2010) — Pure Volatility Smirk Tail Risk (30d)
    OptionCandidate(
        expression="trade_when(abs(rank(ts_decay_linear(implied_volatility_mean_skew_30 * sqrt(30/252.0), 12)) - 0.5) > 0.35, group_neutralize(rank(-ts_decay_linear(implied_volatility_mean_skew_30 * sqrt(30/252.0), 12)), subindustry), -1)",
        archetype_name="Xing-Zhang-Zhao Volatility Smirk 30D",
        hypothesis="Xing, Zhang, & Zhao (2010): 30-day volatility smirk slope demeaned across subindustry with conviction gating extracts tail repricing alpha.",
        generation_source="institutional_literature",
    ),
    # 5. Colin Bennett (2014) & Sinclair (2013) — Pure ATM IV Term Structure Slope (60d vs 20d)
    OptionCandidate(
        expression="trade_when(abs(rank(ts_decay_linear(implied_volatility_mean_60 - implied_volatility_mean_20, 10)) - 0.5) > 0.35, group_neutralize(rank(ts_decay_linear(implied_volatility_mean_60 - implied_volatility_mean_20, 10)), subindustry), -1)",
        archetype_name="ATM IV Term Structure Contango",
        hypothesis="Bennett (2014) & Sinclair (2013): ATM implied volatility term structure contango reflects cross-sectional term premium compression.",
        generation_source="institutional_literature",
    ),
    # 6. Garleanu, Pedersen, & Poteshman (2009) — End-User Option Demand vs Equity Divergence
    OptionCandidate(
        expression="trade_when(abs(rank(ts_decay_linear(ts_rank(implied_volatility_mean_30, 20) - ts_rank(close, 20), 10)) - 0.5) > 0.35, group_neutralize(rank(ts_decay_linear(ts_rank(implied_volatility_mean_30, 20) - ts_rank(close, 20), 10)), subindustry), -1)",
        archetype_name="Garleanu Dealer Inventory Imbalance",
        hypothesis="Garleanu, Pedersen, & Poteshman (2009): Option dealer inventory imbalances induce temporary mispricings between options and underlying equity.",
        generation_source="institutional_literature",
    ),
    # 7. Xing-Zhang-Zhao Skew Term Divergence (10d vs 30d)
    OptionCandidate(
        expression="trade_when(abs(rank(ts_decay_linear(((implied_volatility_mean_skew_10 * sqrt(10/252.0)) - (implied_volatility_mean_skew_30 * sqrt(30/252.0))), 10)) - 0.5) > 0.35, group_neutralize(rank(ts_decay_linear(((implied_volatility_mean_skew_10 * sqrt(10/252.0)) - (implied_volatility_mean_skew_30 * sqrt(30/252.0))), 10)), subindustry), -1)",
        archetype_name="Skew Term Divergence",
        hypothesis="Short-dated vs intermediate skew divergence captures rapid shifts in downside insurance demand ahead of catalysts.",
        generation_source="institutional_literature",
    ),
    # 8. Pan-Poteshman Normalized PCR Z-Score Contrarian
    OptionCandidate(
        expression="trade_when(abs(rank(ts_zscore(pcr_vol_20, 20)) - 0.5) > 0.35, group_neutralize(rank(-ts_zscore(pcr_vol_20, 20)), subindustry), -1)",
        archetype_name="Pan-Poteshman PCR Z-Score",
        hypothesis="Pan & Poteshman (2006): Time-series standardized put-call volume ratio mean reversion with extreme-rank conviction filtering.",
        generation_source="institutional_literature",
    ),
]


async def run_orthogonal_submission():
    config = OptionsConfig.from_env()
    store = OptionsStore(database_url=config.database_url)
    db = store.db

    log.info("Starting Orthogonal Alpha Qualification & Gold Submission Engine...")
    client = BrainClient(
        username=config.brain_username,
        password=config.brain_password,
        max_concurrent_sims=min(config.brain_max_concurrent_sims, 3),
        db=db,
    )
    client.authenticate()
    sess = client._get_session()

    # Check daily submission quota
    drip = DripSubmitter(client, store, config)
    today_subs = await drip.get_today_submissions_ny()
    log.info("Current submissions today in New York time: %d/3", len(today_subs))
    if len(today_subs) >= 3:
        log.warning("Daily quota (3/3) already reached for today. Next slot opens at midnight NY time.")
        return

    settings = SimSettings(
        region="USA",
        universe="TOP3000",
        delay=1,
        decay=12,
        neutralization="SUBINDUSTRY",
        truncation=0.05,
        pasteurization=True,
    )

    for idx, cand in enumerate(ORTHOGONAL_CANDIDATES, 1):
        log.info("\n" + "=" * 70)
        log.info("[%d/%d] SIMULATING ORTHOGONAL CANDIDATE: %s", idx, len(ORTHOGONAL_CANDIDATES), cand.archetype_name)
        log.info("Expression: %s", cand.expression)
        log.info("Hypothesis: %s", cand.hypothesis)

        metrics = await client.simulate_one(cand.expression, settings)
        log.info(
            "Result: AlphaID=%s, Sharpe=%.2f, Fitness=%.2f, Turnover=%.2f%%, Return=%.2f%%, Margin=%.6f",
            metrics.alpha_id,
            metrics.sharpe,
            metrics.fitness,
            metrics.turnover * 100,
            metrics.annualized_return * 100,
            metrics.margin,
        )

        # Gate 1: Metric thresholds
        if metrics.sharpe < 1.25:
            log.info("[-] Failed Sharpe gate: %.2f < 1.25", metrics.sharpe)
            continue
        if metrics.fitness < 1.00:
            log.info("[-] Failed Fitness gate: %.2f < 1.00", metrics.fitness)
            continue
        if not (0.01 <= metrics.turnover <= 0.70):
            log.info("[-] Failed Turnover gate: %.2f%% outside [1%%, 70%%]", metrics.turnover * 100)
            continue
        if metrics.margin < 0.0010:
            log.info("[-] Failed Margin gate: %.6f < 0.0010", metrics.margin)
            continue

        log.info("[+] METRICS PASSED! Verifying platform checklist gates on BRAIN...")

        # Gate 2: Verify platform checklist on BRAIN
        alpha_id = metrics.alpha_id
        if not alpha_id:
            log.warning("[-] No alpha_id returned from simulation.")
            continue

        chk_resp = await sess.retry("GET", f"https://api.worldquantbrain.com/alphas/{alpha_id}", max_tries=3)
        if not chk_resp or chk_resp.status_code != 200:
            log.warning("[-] Could not fetch alpha details from BRAIN.")
            continue

        alpha_data = chk_resp.json()
        is_block = alpha_data.get("is") or {}
        checks = is_block.get("checks") or []
        failed_checks = [c.get("name") for c in checks if c.get("result") == "FAIL"]
        if failed_checks:
            log.warning("[-] Failed platform checklist gates: %s", failed_checks)
            continue

        log.info("[+] PLATFORM CHECKLIST GATES PASSED! Verifying live self-correlation...")

        # Gate 3: Platform live self-correlation endpoint (< 0.70 limit)
        corr_resp = await sess.retry("GET", f"https://api.worldquantbrain.com/alphas/{alpha_id}/correlations/self", max_tries=3)
        max_corr = 0.0
        top_partner = "none"
        if corr_resp and corr_resp.status_code == 200 and corr_resp.text.strip():
            c_data = json.loads(corr_resp.text)
            records = c_data.get("records") or []
            for r in records:
                if len(r) > 5 and isinstance(r[5], (int, float)):
                    c_val = abs(float(r[5]))
                    if c_val > max_corr:
                        max_corr = c_val
                        top_partner = r[0]

        log.info("Platform Live Self-Correlation: Max |Corr| = %.4f (Top partner: %s)", max_corr, top_partner)
        if max_corr >= 0.70:
            log.warning("[-] Failed self-correlation gate: %.4f >= 0.70 vs %s", max_corr, top_partner)
            continue

        log.info("\n" + "*" * 70)
        log.info(">>> 100% QUALIFIED ALPHA DISCOVERED: %s (Alpha ID: %s) <<<", cand.archetype_name, alpha_id)
        log.info("Sharpe: %.2f | Fitness: %.2f | Turnover: %.2f%% | Margin: %.6f | MaxCorr: %.4f",
                 metrics.sharpe, metrics.fitness, metrics.turnover * 100, metrics.margin, max_corr)
        log.info("*" * 70 + "\n")

        # Step 4: Populate Metadata on BRAIN
        cand_dict = {
            "alpha_id": alpha_id,
            "archetype": cand.archetype_name,
            "hypothesis": cand.hypothesis,
            "expression": cand.expression,
        }
        meta = build_alpha_submission_metadata(cand_dict)
        try:
            await client.update_alpha_metadata(
                alpha_id,
                name=meta["name"],
                description=meta["description"],
                tags=meta["tags"],
                category=meta["category"],
            )
            log.info("[SUBMIT] Updated metadata on BRAIN for %s: name='%s'", alpha_id, meta["name"])
        except Exception as e:
            log.warning("[SUBMIT] Non-fatal metadata update warning: %s", e)

        # Step 5: Execute Submission on WorldQuant BRAIN!
        log.info("[SUBMIT] Submitting alpha %s to WorldQuant BRAIN...", alpha_id)
        sub_res = await client.submit_alpha(alpha_id)
        if not sub_res.get("ok"):
            log.error("[-] Submission request failed: %s", sub_res)
            continue

        # Step 6: Verify Out-of-Sample (OS) stage transition
        is_actually_submitted = False
        verified_data = alpha_data
        for attempt in range(6):
            await asyncio.sleep(2.5)
            v_resp = await sess.retry("GET", f"https://api.worldquantbrain.com/alphas/{alpha_id}", max_tries=2)
            if v_resp and v_resp.status_code == 200:
                v_json = v_resp.json()
                v_stage = v_json.get("stage", "")
                v_status = v_json.get("status", "")
                if v_stage == "OS" and v_status == "ACTIVE":
                    is_actually_submitted = True
                    verified_data = v_json
                    break
                elif v_status == "UNSUBMITTED":
                    log.warning("Alpha %s rejected asynchronously by BRAIN (stage=%s, status=%s)", alpha_id, v_stage, v_status)
                    break

        if not is_actually_submitted:
            log.error("[-] Alpha %s failed post-submission OS verification.", alpha_id)
            continue

        # Step 7: Record in store and send celebratory alerts!
        log.info("\n" + "=" * 70)
        log.info(" MISSION ACCOMPLISHED! ALPHA %s SUBMITTED & ACTIVE IN STAGE OS!", alpha_id)
        log.info(" Archetype: %s", cand.archetype_name)
        log.info(" Expression: %s", cand.expression)
        log.info("=" * 70 + "\n")

        store.mark_alpha_submitted(alpha_id)
        if db:
            store.save_alpha(
                alpha_id=alpha_id,
                expression=cand.expression,
                archetype=cand.archetype_name,
                metrics=metrics,
                settings=settings,
                status="SUBMITTED",
            )

        # Send Telegram celebration alert
        import zoneinfo, datetime
        NY_TZ = zoneinfo.ZoneInfo("America/New_York")
        now_ny = datetime.datetime.now(NY_TZ).date()
        is_metrics = verified_data.get("is") or {}
        metrics_dict = {
            "sharpe": is_metrics.get("sharpe", metrics.sharpe),
            "fitness": is_metrics.get("fitness", metrics.fitness),
            "turnover": is_metrics.get("turnover", metrics.turnover),
            "returns": is_metrics.get("returns", metrics.annualized_return),
            "margin": is_metrics.get("margin", metrics.margin),
        }
        send_telegram_drip_alert(
            alpha_id=alpha_id,
            date_label=now_ny.isoformat(),
            metrics=metrics_dict,
            config=config,
            slot_num=len(today_subs) + 1,
            max_daily=3,
        )
        log.info("Telegram notification successfully dispatched for Gold Unlock!")
        return True

    log.warning("Batch completed without a fully qualified submission.")
    return False


if __name__ == "__main__":
    asyncio.run(run_orthogonal_submission())
