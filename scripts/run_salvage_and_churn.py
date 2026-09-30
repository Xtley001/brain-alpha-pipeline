"""
Salvage flawed alphas via TOP2000 re-tuning and churn out new uncorrelated
alphas across the 24 virgin strategy modules (pcr_flow, order_flow_vpin, gamma_pinning).
"""
import os
import sys
import time
import logging
import asyncio
import decimal
import dotenv
import psycopg
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
dotenv.load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("salvage_and_churn")

from brain_options.config import OptionsConfig
from brain_options.core.client import BrainClient, SimSettings, SimMetrics
from brain_options.store.store import OptionsStore
from brain_options.core.correlation import compute_correlation
from scripts.cloud_multi_miner import (
    load_reference_pnls,
    verify_checklist_passes,
    commit_qualified_alpha,
    send_tg_message
)
from brain_options.strategies import generate_modular_candidates

# 1. Five Rescue Candidates (TOP2000 parameterization to pass Sub-Universe Sharpe)
RESCUE_CANDIDATES = [
    {
        "name": "Vkae25pb_TOP2000",
        "archetype": "Bivariate_Put180_Skew60_TOP2000_SUBIND",
        "hypothesis": "Rescued Vkae25pb on dense TOP2000 universe to eliminate illiquid microcap spread distortion.",
        "universe": "TOP2000",
        "neutralization": "SUBINDUSTRY",
        "decay": 8,
        "expression": (
            "trade_when(abs(rank((0.65 * rank(ts_decay_linear(ts_decay_linear(((forward_price_180 - put_breakeven_180) / close * (implied_volatility_mean_skew_180 * sqrt(180/252.0)) * (pcr_vol_180 / (pcr_oi_180 + 0.001))), 10), 3)) + 0.35 * rank(ts_decay_linear(ts_decay_linear(((implied_volatility_call_60 - implied_volatility_put_60) / (implied_volatility_mean_60 + 0.001) * sqrt(60/252.0) * (volume / (adv20 + 1))), 10), 3)))) - 0.5) > 0.26, group_neutralize(rank((0.65 * rank(ts_decay_linear(ts_decay_linear(((forward_price_180 - put_breakeven_180) / close * (implied_volatility_mean_skew_180 * sqrt(180/252.0)) * (pcr_vol_180 / (pcr_oi_180 + 0.001))), 10), 3)) + 0.35 * rank(ts_decay_linear(ts_decay_linear(((implied_volatility_call_60 - implied_volatility_put_60) / (implied_volatility_mean_60 + 0.001) * sqrt(60/252.0) * (volume / (adv20 + 1))), 10), 3)))), subindustry), -1)"
        ),
    },
    {
        "name": "N1a8nR9o_TOP2000",
        "archetype": "Bivariate_Put90_Skew30_TOP2000_SUBIND",
        "hypothesis": "Rescued N1a8nR9o on dense TOP2000 universe without volume weighting distortion.",
        "universe": "TOP2000",
        "neutralization": "SUBINDUSTRY",
        "decay": 8,
        "expression": (
            "trade_when(abs(rank((0.65 * rank(ts_decay_linear(ts_decay_linear(((forward_price_90 - put_breakeven_90) / close * (implied_volatility_mean_skew_90 * sqrt(90/252.0)) * (pcr_vol_90 / (pcr_oi_90 + 0.001))), 10), 3)) + 0.35 * rank(ts_decay_linear(ts_decay_linear(((implied_volatility_call_30 - implied_volatility_put_30) / (implied_volatility_mean_30 + 0.001) * sqrt(30/252.0) * (volume / (adv20 + 1))), 10), 3)))) - 0.5) > 0.26, group_neutralize(rank((0.65 * rank(ts_decay_linear(ts_decay_linear(((forward_price_90 - put_breakeven_90) / close * (implied_volatility_mean_skew_90 * sqrt(90/252.0)) * (pcr_vol_90 / (pcr_oi_90 + 0.001))), 10), 3)) + 0.35 * rank(ts_decay_linear(ts_decay_linear(((implied_volatility_call_30 - implied_volatility_put_30) / (implied_volatility_mean_30 + 0.001) * sqrt(30/252.0) * (volume / (adv20 + 1))), 10), 3)))), subindustry), -1)"
        ),
    },
    {
        "name": "JjN2O3mA_TOP2000",
        "archetype": "T2_Term180_30_Cal_50_d8_TOP2000_SECTOR",
        "hypothesis": "Rescued JjN2O3mA using SECTOR neutralization on TOP2000 universe (matching XgbOoJjx winning structure).",
        "universe": "TOP2000",
        "neutralization": "SECTOR",
        "decay": 8,
        "expression": (
            "trade_when(abs(rank((0.5 * rank(ts_decay_linear(ts_decay_linear(((implied_volatility_mean_180 / (implied_volatility_mean_30 + 0.001)) * (implied_volatility_mean_skew_30 * sqrt(30/252.0))), 10), 3)) + 0.5 * rank(ts_decay_linear(ts_decay_linear(((forward_price_180 - forward_price_30) / close * (implied_volatility_mean_180 / (implied_volatility_mean_30 + 0.001)) * (volume / (adv20 + 1))), 10), 3)))) - 0.5) > 0.26, group_neutralize(rank((0.5 * rank(ts_decay_linear(ts_decay_linear(((implied_volatility_mean_180 / (implied_volatility_mean_30 + 0.001)) * (implied_volatility_mean_skew_30 * sqrt(30/252.0))), 10), 3)) + 0.5 * rank(ts_decay_linear(ts_decay_linear(((forward_price_180 - forward_price_30) / close * (implied_volatility_mean_180 / (implied_volatility_mean_30 + 0.001)) * (volume / (adv20 + 1))), 10), 3)))), sector), -1)"
        ),
    },
    {
        "name": "MPa2a1Eo_SECTOR_d10",
        "archetype": "T2_Term90_30_Cal_50_d10_TOP2000_SECTOR",
        "hypothesis": "Rescued MPa2a1Eo using SECTOR neutralization + decay 10 on TOP2000.",
        "universe": "TOP2000",
        "neutralization": "SECTOR",
        "decay": 10,
        "expression": (
            "trade_when(abs(rank((0.5 * rank(ts_decay_linear(ts_decay_linear(((implied_volatility_mean_90 / (implied_volatility_mean_30 + 0.001)) * (implied_volatility_mean_skew_30 * sqrt(30/252.0))), 10), 3)) + 0.5 * rank(ts_decay_linear(ts_decay_linear(((forward_price_90 - forward_price_30) / close * (implied_volatility_mean_90 / (implied_volatility_mean_30 + 0.001)) * (volume / (adv20 + 1))), 10), 3)))) - 0.5) > 0.26, group_neutralize(rank((0.5 * rank(ts_decay_linear(ts_decay_linear(((implied_volatility_mean_90 / (implied_volatility_mean_30 + 0.001)) * (implied_volatility_mean_skew_30 * sqrt(30/252.0))), 10), 3)) + 0.5 * rank(ts_decay_linear(ts_decay_linear(((forward_price_90 - forward_price_30) / close * (implied_volatility_mean_90 / (implied_volatility_mean_30 + 0.001)) * (volume / (adv20 + 1))), 10), 3)))), sector), -1)"
        ),
    },
]

async def main():
    config = OptionsConfig.from_env()
    store = OptionsStore()
    client = BrainClient(
        username=config.brain_username,
        password=config.brain_password,
        max_concurrent_sims=1,
        db=store.db,
    )

    log.info("Authenticating with WorldQuant BRAIN...")
    await asyncio.to_thread(client.authenticate)

    # 1. Pre-fetch clean reference PnLs
    ref_alpha_ids, known_exprs = load_reference_pnls(config.database_url)
    ref_pnls = {}
    log.info("Loading reference PnLs for %d portfolio alphas...", len(ref_alpha_ids))
    for aid in ref_alpha_ids:
        pnl = await client.get_alpha_pnl(aid)
        if pnl:
            ref_pnls[aid] = pnl
    log.info("Loaded %d clean portfolio PnLs.", len(ref_pnls))

    # 2. Build candidate queue: Rescue candidates + Virgin modular candidates
    candidate_queue = []

    # Add Rescue Candidates
    for rc in RESCUE_CANDIDATES:
        candidate_queue.append({
            "expression": rc["expression"],
            "archetype": rc["archetype"],
            "hypothesis": rc["hypothesis"],
            "universe": rc["universe"],
            "neutralization": rc["neutralization"],
            "decay": rc["decay"],
            "source": "sus_rescue"
        })

    # Add Virgin Modular Candidates (PCR flow, VPIN, Gamma Pinning, Realized Jumps)
    virgin_strats = [
        "pcr_flow",
        "order_flow_vpin",
        "gamma_pinning_clustering",
        "realized_jump_intensity",
        "dynamic_short_squeeze",
        "distance_to_default_debt",
    ]
    virgin_cands = generate_modular_candidates(virgin_strats)
    for vc in virgin_cands[:20]:
        candidate_queue.append({
            "expression": vc.expression,
            "archetype": vc.archetype_name,
            "hypothesis": vc.hypothesis,
            "universe": getattr(vc, "universe", "TOP2000"),
            "neutralization": getattr(vc, "neutralization", "SUBINDUSTRY"),
            "decay": getattr(vc, "decay", 18),
            "source": "virgin_strategy"
        })

    log.info("Candidate execution queue constructed: %d total candidates.", len(candidate_queue))

    qualified_alphas = []
    
    for idx, item in enumerate(candidate_queue):
        expr = item["expression"]
        arch = item["archetype"]
        hyp = item["hypothesis"]
        universe = item["universe"]
        neut = item["neutralization"]
        decay = item["decay"]
        src = item["source"]

        if expr in known_exprs:
            log.info("[%d/%d] Skipping known expression: %s", idx + 1, len(candidate_queue), arch)
            continue
        known_exprs.add(expr)

        settings = SimSettings(
            region="USA",
            universe=universe,
            delay=1,
            decay=decay,
            neutralization=neut,
            truncation=0.05,
            pasteurization=True,
        )

        log.info("\n" + "=" * 70)
        log.info("[%d/%d] SIMULATING: %s (Source: %s, u=%s, d=%d, neut=%s)", idx + 1, len(candidate_queue), arch, src, universe, decay, neut)
        log.info("=" * 70)

        try:
            metrics = await client.simulate_one(expr, settings)
        except Exception as e:
            log.warning("Simulation exception for %s: %s", arch, e)
            continue

        if not metrics or not metrics.is_valid:
            log.warning("Invalid metrics for %s", arch)
            continue

        aid = metrics.alpha_id
        log.info("[Sim Result] %s: Sharpe=%.2f | Fit=%.2f | TO=%.1f%% | Margin=%.1fbps | DD=%.1f%%",
                 aid, metrics.sharpe, metrics.fitness, metrics.turnover * 100, metrics.margin * 10000, metrics.max_drawdown * 100)

        # Gate 1: Performance Gate (Sharpe >= 1.25, Fitness >= 0.70, Margin >= 8 bps, Turnover <= 70%)
        if metrics.sharpe < 1.25 or metrics.fitness < 0.70 or metrics.turnover < 0.01 or metrics.turnover > 0.70 or metrics.margin < 0.0008:
            log.info("[-] Gate 1 failure for %s (Sharpe=%.2f, Fit=%.2f, Margin=%.1fbps)", aid, metrics.sharpe, metrics.fitness, metrics.margin * 10000)
            continue

        log.info("[+] Gate 1 PASS for %s!", aid)

        # Gate 2: Correlation Gate vs Portfolio (|rho| < 0.70)
        pnl = await client.get_alpha_pnl(aid)
        if not pnl or len(pnl) < 30:
            log.warning("No PnL returned for %s", aid)
            continue

        max_corr = 0.0
        colliding_id = None
        if ref_pnls:
            for r_id, r_pnl in ref_pnls.items():
                c = abs(compute_correlation(pnl, r_pnl))
                if c > max_corr:
                    max_corr = c
                    colliding_id = r_id

        log.info("[Correlation] %s vs Portfolio: Max Corr = %.4f (colliding: %s)", aid, max_corr, colliding_id)
        if max_corr >= 0.70:
            log.warning("[-] Gate 2 Correlation failure (%.4f >= 0.70 vs %s) for %s", max_corr, colliding_id, aid)
            continue

        log.info("[+] Gate 2 PASS for %s!", aid)

        # Gate 3: Platform Checklist Gate (Sub-Universe Sharpe >= 0.80)
        log.info("[*] Testing Gate 3 platform checklist on BRAIN for %s...", aid)
        chk_passed, chk_msg = verify_checklist_passes(client._session, aid)
        if not chk_passed:
            log.warning("[-] Gate 3 Checklist failure for %s: %s", aid, chk_msg)
            continue

        log.info("[🌟] Gate 3 ALL CHECKS PASSED for %s!", aid)

        # Passed all 3 gates! Commit to DB
        commit_qualified_alpha(
            db_url=config.database_url,
            alpha_id=aid,
            expression=expr,
            archetype=arch,
            hypothesis=hyp,
            metrics=metrics,
            max_corr=max_corr,
            universe=universe,
            neutralization=neut,
            decay=decay,
            category="options"
        )
        ref_pnls[aid] = pnl
        qualified_alphas.append({
            "alpha_id": aid,
            "sharpe": metrics.sharpe,
            "fitness": metrics.fitness,
            "turnover": metrics.turnover,
            "margin": metrics.margin,
            "max_corr": max_corr,
            "archetype": arch,
            "source": src
        })

        # Telegram Notification
        send_tg_message(
            token=config.telegram_bot_token,
            chat_id=config.telegram_chat_id,
            html_text=(
                f"🌟 <b>NEW QUALIFIED OPTIONS ALPHA ({src.upper()})!</b> 🌟\n\n"
                f"• <b>Alpha ID:</b> <code>{aid}</code>\n"
                f"• <b>Archetype:</b> {arch}\n"
                f"• <b>Sharpe:</b> {metrics.sharpe:.2f} | <b>Fitness:</b> {metrics.fitness:.2f}\n"
                f"• <b>Margin:</b> {metrics.margin * 10000:.1f} bps | <b>Turnover:</b> {metrics.turnover * 100:.1f}%\n"
                f"• <b>Max Portfolio Corr:</b> {max_corr:.4f} (&lt; 0.70)\n"
                f"• <b>Sub-Universe Check:</b> 100% PASS\n"
                f"• <b>Expression:</b>\n<code>{expr}</code>"
            )
        )

        log.info("QUALIFIED SO FAR: %d alphas.", len(qualified_alphas))
        if len(qualified_alphas) >= 10:
            log.info("Target of 10 newly qualified alphas reached!")
            break

    print("\n" + "=" * 70)
    print(f"SALVAGE & CHURN PIPELINE COMPLETE: {len(qualified_alphas)} NEW QUALIFIED ALPHAS")
    print("=" * 70)
    for q in qualified_alphas:
        print(f"Alpha {q['alpha_id']}: Sharpe={q['sharpe']:.2f}, Fit={q['fitness']:.2f}, TO={q['turnover']*100:.1f}%, Margin={q['margin']*10000:.1f}bps, MaxCorr={q['max_corr']:.4f} | {q['archetype']}")

if __name__ == "__main__":
    asyncio.run(main())
