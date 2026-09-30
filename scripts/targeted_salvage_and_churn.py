"""
Targeted Salvage and High-Yield Churn Pipeline
1. Salvages the 4 flawed alphas on TOP2000 with volume weighting & sector neutralization
2. Churns out uncorrelated virgin alphas from VPIN, Gamma Pinning, and Hybrid Confluence
3. Executes Gates 1, 2, and 3 (verifying LOW_SUB_UNIVERSE_SHARPE and SELF_CORRELATION)
4. Commits qualified alphas to Neon DB and sends Telegram alerts
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
log = logging.getLogger("targeted_salvage")

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

CANDIDATES = [
    # --- 1. PROVEN HIGH-SHARPE CASH EQUITY & REVERSALS (Orthogonal to Options & Sentiment) ---
    {
        "name": "EQ_Demeaned_1D_Reversal_TOP2000",
        "archetype": "EQ_Demeaned_1D_Rev_TOP2000_SUBIND",
        "hypothesis": "Idiosyncratic 1-day price reversal demeaned against subindustry peer group with liquidity filter.",
        "universe": "TOP2000",
        "neutralization": "SUBINDUSTRY",
        "decay": 6,
        "expression": (
            "trade_when(volume > adv20 * 0.8, group_neutralize(rank(-(ts_delta(close, 1) - group_mean(ts_delta(close, 1), 1, subindustry))), subindustry), -1)"
        ),
    },
    {
        "name": "EQ_Intraday_Range_Expansion_TOP2000",
        "archetype": "EQ_Range_Expansion_Rev_TOP2000_SUBIND",
        "hypothesis": "1-day return reversal scaled by volatility range expansion reveals retail capitulation.",
        "universe": "TOP2000",
        "neutralization": "SUBINDUSTRY",
        "decay": 8,
        "expression": (
            "trade_when(volume > adv20 * 0.7, group_neutralize(rank(-ts_delta(close, 1)) * rank((high - low) / (ts_mean(high - low, 20) + 0.001)), subindustry), -1)"
        ),
    },
    # --- 2. VIRGIN OPTIONS FLOW & TOXICITY FADE ---
    {
        "name": "VPIN_Volume_Toxicity_Fade_TOP2000",
        "archetype": "VPIN_Flow_Toxicity_Fade_TOP2000_SUBIND",
        "hypothesis": "Fading retail intraday price overreaction relative to VWAP on heavy volume produces sustained reversal returns.",
        "universe": "TOP2000",
        "neutralization": "SUBINDUSTRY",
        "decay": 8,
        "expression": (
            "trade_when(volume > adv20 * 0.8, group_neutralize(rank(ts_decay_linear(-((close - vwap) / (high - low + 0.001)) * (volume / adv20), 8)), subindustry), -1)"
        ),
    },
    {
        "name": "Pan_Poteshman_Informed_Flow_Fade_TOP2000",
        "archetype": "Pan_Poteshman_Informed_Flow_TOP2000_SUBIND",
        "hypothesis": "Fading short-horizon PCR volume spikes relative to open interest captures excessive retail hedging overreaction.",
        "universe": "TOP2000",
        "neutralization": "SUBINDUSTRY",
        "decay": 8,
        "expression": (
            "trade_when(volume > adv20, group_neutralize(rank(-ts_decay_linear(pcr_vol_20 / (pcr_oi_20 + 0.001), 8)), subindustry), -1)"
        ),
    },
    {
        "name": "Hybrid_IV_Sentiment_Fade_TOP2000",
        "archetype": "Hybrid_IV_Sentiment_TOP2000_SECTOR",
        "hypothesis": "Low implied volatility combined with positive trading volume acceleration signals asymmetric upside breakout.",
        "universe": "TOP2000",
        "neutralization": "SECTOR",
        "decay": 8,
        "expression": (
            "trade_when(volume > adv20, group_neutralize(rank(ts_decay_linear(-implied_volatility_mean_30 * ts_decay_linear(returns, 5), 8)), sector), -1)"
        ),
    },
    {
        "name": "JjN2O3mA_TOP2000_SECTOR",
        "archetype": "T2_Term180_30_Cal_50_d8_TOP2000_SECTOR",
        "hypothesis": "Rescued JjN2O3mA on dense TOP2000 universe with volume-weighted sector neutralization.",
        "universe": "TOP2000",
        "neutralization": "SECTOR",
        "decay": 8,
        "expression": (
            "trade_when(abs(rank((0.5 * rank(ts_decay_linear(ts_decay_linear(((implied_volatility_mean_180 / (implied_volatility_mean_30 + 0.001)) * (implied_volatility_mean_skew_30 * sqrt(30/252.0))), 10), 3)) + 0.5 * rank(ts_decay_linear(ts_decay_linear(((forward_price_180 - forward_price_30) / close * (implied_volatility_mean_180 / (implied_volatility_mean_30 + 0.001)) * (volume / (adv20 + 1))), 10), 3)))) - 0.5) > 0.26, group_neutralize(rank((0.5 * rank(ts_decay_linear(ts_decay_linear(((implied_volatility_mean_180 / (implied_volatility_mean_30 + 0.001)) * (implied_volatility_mean_skew_30 * sqrt(30/252.0))), 10), 3)) + 0.5 * rank(ts_decay_linear(ts_decay_linear(((forward_price_180 - forward_price_30) / close * (implied_volatility_mean_180 / (implied_volatility_mean_30 + 0.001)) * (volume / (adv20 + 1))), 10), 3)))) * (volume / adv20), sector), -1)"
        ),
    },
    {
        "name": "MPa2a1Eo_TOP2000_SECTOR",
        "archetype": "T2_Term90_30_Cal_50_d8_TOP2000_SECTOR",
        "hypothesis": "Rescued MPa2a1Eo on dense TOP2000 universe with volume-weighted sector neutralization.",
        "universe": "TOP2000",
        "neutralization": "SECTOR",
        "decay": 8,
        "expression": (
            "trade_when(abs(rank((0.5 * rank(ts_decay_linear(ts_decay_linear(((implied_volatility_mean_90 / (implied_volatility_mean_30 + 0.001)) * (implied_volatility_mean_skew_30 * sqrt(30/252.0))), 10), 3)) + 0.5 * rank(ts_decay_linear(ts_decay_linear(((forward_price_90 - forward_price_30) / close * (implied_volatility_mean_90 / (implied_volatility_mean_30 + 0.001)) * (volume / (adv20 + 1))), 10), 3)))) - 0.5) > 0.26, group_neutralize(rank((0.5 * rank(ts_decay_linear(ts_decay_linear(((implied_volatility_mean_90 / (implied_volatility_mean_30 + 0.001)) * (implied_volatility_mean_skew_30 * sqrt(30/252.0))), 10), 3)) + 0.5 * rank(ts_decay_linear(ts_decay_linear(((forward_price_90 - forward_price_30) / close * (implied_volatility_mean_90 / (implied_volatility_mean_30 + 0.001)) * (volume / (adv20 + 1))), 10), 3)))) * (volume / adv20), sector), -1)"
        ),
    },
    # Near-miss decay tuning variants (kqgqGOqL d=12, d=14)
    {
        "name": "kqgqGOqL_decay12",
        "archetype": "T2_Term180_30_Cal_50_d12_TOP2000_SECTOR",
        "hypothesis": "Decay extension on kqgqGOqL to reduce turnover and lift Sharpe past 1.25 hurdle.",
        "universe": "TOP2000",
        "neutralization": "SECTOR",
        "decay": 12,
        "expression": (
            "trade_when(abs(rank((0.5 * rank(ts_decay_linear(ts_decay_linear(((implied_volatility_mean_180 / (implied_volatility_mean_30 + 0.001)) * (implied_volatility_mean_skew_30 * sqrt(30/252.0))), 10), 3)) + 0.5 * rank(ts_decay_linear(ts_decay_linear(((forward_price_180 - forward_price_30) / close * (implied_volatility_mean_180 / (implied_volatility_mean_30 + 0.001)) * (volume / (adv20 + 1))), 10), 3)))) - 0.5) > 0.26, group_neutralize(rank((0.5 * rank(ts_decay_linear(ts_decay_linear(((implied_volatility_mean_180 / (implied_volatility_mean_30 + 0.001)) * (implied_volatility_mean_skew_30 * sqrt(30/252.0))), 10), 3)) + 0.5 * rank(ts_decay_linear(ts_decay_linear(((forward_price_180 - forward_price_30) / close * (implied_volatility_mean_180 / (implied_volatility_mean_30 + 0.001)) * (volume / (adv20 + 1))), 10), 3)))), sector), -1)"
        ),
    },
    # --- 2. VIRGIN STRATEGY CANDIDATES (VPIN, Gamma Pinning, Hybrid Confluence) ---
    {
        "name": "VPIN_Volume_Toxicity_TOP2000",
        "archetype": "VPIN_Flow_Toxicity_TOP2000_SUBIND",
        "hypothesis": "Intraday VWAP divergence weighted by volume intensity reveals toxic informed institutional accumulation.",
        "universe": "TOP2000",
        "neutralization": "SUBINDUSTRY",
        "decay": 12,
        "expression": (
            "trade_when(volume > adv20 * 0.8, group_neutralize(rank(ts_decay_linear(((close - vwap) / (high - low + 0.001)) * (volume / adv20), 12)), subindustry), -1)"
        ),
    },
    {
        "name": "VPIN_Equity_Options_Confluence",
        "archetype": "VPIN_PCR_Confluence_TOP2000_SUBIND",
        "hypothesis": "Cash flow direction amplified by call volume dominance generates sustained multi-week excess returns.",
        "universe": "TOP2000",
        "neutralization": "SUBINDUSTRY",
        "decay": 15,
        "expression": (
            "trade_when(volume > adv20 * 0.7, group_neutralize(rank(ts_decay_linear(((close - open) / (high - low + 0.001)) * (1.0 / (pcr_vol_20 / (pcr_oi_20 + 0.001) + 0.01)), 15)), subindustry), -1)"
        ),
    },
    {
        "name": "Gamma_Pinning_Delta_Pull",
        "archetype": "Gamma_Pinning_TOP2000_SUBIND",
        "hypothesis": "Concentrated call open interest creates market maker dynamic delta hedging pull toward forward strike.",
        "universe": "TOP2000",
        "neutralization": "SUBINDUSTRY",
        "decay": 12,
        "expression": (
            "trade_when(volume > adv20 * 0.8, group_neutralize(rank(ts_decay_linear(((forward_price_30 - close) / close) * (1.0 / (pcr_oi_30 + 0.001)), 12)), subindustry), -1)"
        ),
    },
    {
        "name": "Gamma_Pinning_Strike_Magnet",
        "archetype": "Gamma_Strike_Magnet_TOP2000_SUBIND",
        "hypothesis": "Disproportional options volume surges relative to open interest break pinning constraints into directional moves.",
        "universe": "TOP2000",
        "neutralization": "SUBINDUSTRY",
        "decay": 15,
        "expression": (
            "trade_when(volume > adv20 * 1.1, group_neutralize(rank(ts_decay_linear(((close - forward_price_30) / (close * implied_volatility_mean_30 * sqrt(30 / 252.0) + 0.001)) * (pcr_vol_30 / (pcr_oi_30 + 0.001)), 15)), subindustry), -1)"
        ),
    },
    {
        "name": "Pan_Poteshman_Informed_Flow_d10",
        "archetype": "Pan_Poteshman_Informed_Flow_TOP2000",
        "hypothesis": "Opening put-call volume surge relative to open interest captures informed directional institutional hedging.",
        "universe": "TOP2000",
        "neutralization": "SUBINDUSTRY",
        "decay": 10,
        "expression": (
            "trade_when(volume > adv20, group_neutralize(rank(ts_decay_linear(pcr_vol_20 / (pcr_oi_20 + 0.001), 10)), subindustry), -1)"
        ),
    },
    {
        "name": "Hybrid_IV_Sentiment_Confluence",
        "archetype": "Hybrid_IV_Sentiment_TOP2000",
        "hypothesis": "Low implied volatility combined with positive trading volume acceleration signals asymmetric upside breakout.",
        "universe": "TOP2000",
        "neutralization": "SECTOR",
        "decay": 10,
        "expression": (
            "trade_when(volume > adv20, group_neutralize(rank(ts_decay_linear(-implied_volatility_mean_30 * ts_decay_linear(returns, 5), 10)), sector), -1)"
        ),
    },
    {
        "name": "Term_Structure_Curve_Slope_d12",
        "archetype": "Term_Slope_360_30_TOP2000_SECTOR",
        "hypothesis": "Steep long-horizon IV term structure slope (360d vs 30d) signals institutional variance risk premium capture.",
        "universe": "TOP2000",
        "neutralization": "SECTOR",
        "decay": 12,
        "expression": (
            "trade_when(abs(rank(ts_decay_linear((implied_volatility_mean_360 - implied_volatility_mean_30) / (implied_volatility_mean_30 + 0.001), 10)) - 0.5) > 0.25, group_neutralize(rank(ts_decay_linear((implied_volatility_mean_360 - implied_volatility_mean_30) / (implied_volatility_mean_30 + 0.001), 10) * (volume / adv20)), sector), -1)"
        ),
    },
]

async def run_pipeline():
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

    # Pre-fetch clean reference PnLs
    ref_alpha_ids, known_exprs = load_reference_pnls(config.database_url)
    ref_pnls = {}
    log.info("Loading reference PnLs for %d portfolio alphas...", len(ref_alpha_ids))
    for aid in ref_alpha_ids:
        pnl = await client.get_alpha_pnl(aid)
        if pnl:
            ref_pnls[aid] = pnl
    log.info("Loaded %d clean portfolio PnLs.", len(ref_pnls))

    qualified_alphas = []

    for idx, c in enumerate(CANDIDATES):
        expr = c["expression"]
        name = c["name"]
        arch = c["archetype"]
        hyp = c["hypothesis"]
        universe = c["universe"]
        neut = c["neutralization"]
        decay = c["decay"]

        log.info("\n" + "=" * 75)
        log.info("[%d/%d] SIMULATING: %s (u=%s, neut=%s, d=%d)", idx + 1, len(CANDIDATES), name, universe, neut, decay)
        log.info("Expr: %s", expr[:100] + "...")
        log.info("=" * 75)

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
            log.warning("Simulation exception for %s: %s", name, e)
            continue

        if not metrics or not metrics.is_valid:
            log.warning("Invalid metrics for %s", name)
            continue

        aid = metrics.alpha_id
        log.info("[Result] %s (%s): Sharpe=%.2f | Fit=%.2f | TO=%.1f%% | Margin=%.1fbps | DD=%.1f%%",
                 aid, name, metrics.sharpe, metrics.fitness, metrics.turnover * 100, metrics.margin * 10000, metrics.max_drawdown * 100)

        # Gate 1: Performance Gate
        if metrics.sharpe < 1.25 or metrics.fitness < 0.70 or metrics.turnover < 0.01 or metrics.turnover > 0.70 or metrics.margin < 0.0008:
            log.info("[-] Gate 1 failure for %s (Sharpe=%.2f, Fit=%.2f, Margin=%.1fbps, TO=%.1f%%)",
                     aid, metrics.sharpe, metrics.fitness, metrics.margin * 10000, metrics.turnover * 100)
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
                corr = abs(compute_correlation(pnl, r_pnl))
                if corr > max_corr:
                    max_corr = corr
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

        # Commit to Neon DB
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
            "name": name,
            "sharpe": metrics.sharpe,
            "fitness": metrics.fitness,
            "turnover": metrics.turnover,
            "margin": metrics.margin,
            "max_corr": max_corr,
            "archetype": arch,
        })

        # Telegram Notification
        send_tg_message(
            token=config.telegram_bot_token,
            chat_id=config.telegram_chat_id,
            html_text=(
                f"🌟 <b>NEW QUALIFIED OPTIONS ALPHA ({name.upper()})!</b> 🌟\n\n"
                f"• <b>Alpha ID:</b> <code>{aid}</code>\n"
                f"• <b>Archetype:</b> {arch}\n"
                f"• <b>Sharpe:</b> {metrics.sharpe:.2f} | <b>Fitness:</b> {metrics.fitness:.2f}\n"
                f"• <b>Margin:</b> {metrics.margin * 10000:.1f} bps | <b>Turnover:</b> {metrics.turnover * 100:.1f}%\n"
                f"• <b>Max Portfolio Corr:</b> {max_corr:.4f} (&lt; 0.70)\n"
                f"• <b>Sub-Universe Check:</b> 100% PASS\n"
                f"• <b>Expression:</b>\n<code>{expr}</code>"
            )
        )

        log.info("TOTAL QUALIFIED IN THIS RUN: %d", len(qualified_alphas))

    print("\n" + "=" * 75)
    print(f"PIPELINE RUN COMPLETE: {len(qualified_alphas)} NEW QUALIFIED ALPHAS")
    print("=" * 75)
    for q in qualified_alphas:
        print(f"Alpha {q['alpha_id']} ({q['name']}): Sharpe={q['sharpe']:.2f}, Fit={q['fitness']:.2f}, TO={q['turnover']*100:.1f}%, Margin={q['margin']*10000:.1f}bps, MaxCorr={q['max_corr']:.4f}")

if __name__ == "__main__":
    asyncio.run(run_pipeline())
