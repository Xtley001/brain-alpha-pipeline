import os
import sys
import asyncio
import logging
import decimal
from dotenv import load_dotenv

sys.stdout.reconfigure(line_buffering=True)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("reserve_qualifier")

from brain_options.config import OptionsConfig
from brain_options.core.client import BrainClient, SimSettings, SimMetrics
from brain_options.store.store import OptionsStore
from brain_options.core.correlation import compute_correlation
from scripts.cloud_multi_miner import (
    load_reference_pnls,
    verify_checklist_passes,
    commit_qualified_alpha,
    send_tg_message,
)

CANDIDATES = [
    # 1. Intraday Momentum (orthogonal to overnight reversals)
    {
        "name": "Intraday_Body_Momentum_TOP3000",
        "archetype": "Intraday_Body_Momentum_SUBIND",
        "hypothesis": "Intraday open-to-close drift normalized by trading range reveals institutional execution pressure.",
        "universe": "TOP3000",
        "neutralization": "SUBINDUSTRY",
        "decay": 5,
        "expression": "trade_when(volume > adv20 * 0.7, group_neutralize(rank(ts_decay_linear((close - open) / (high - low + 0.001), 5)), subindustry), -1)",
        "min_margin": 0.00035,
    },
    # 2. Intraday Pressure Fade (buying vs selling tail imbalance)
    {
        "name": "Intraday_Pressure_Fade_TOP3000",
        "archetype": "Intraday_Pressure_Fade_SUBIND",
        "hypothesis": "Fading extreme intraday candle tail imbalance produces robust mean reversion.",
        "universe": "TOP3000",
        "neutralization": "SUBINDUSTRY",
        "decay": 6,
        "expression": "trade_when(volume > adv20 * 0.8, group_neutralize(rank(ts_decay_linear(((close - low) - (high - close)) / (high - low + 0.001), 6)), subindustry), -1)",
        "min_margin": 0.00035,
    },
    # 3. 20-Day Volatility-Normalized Residual Momentum
    {
        "name": "Residual_20D_Momentum_TOP3000",
        "archetype": "Residual_20D_Mom_SECTOR",
        "hypothesis": "20-day price momentum normalized by realized return volatility generates persistent sector-neutral alpha.",
        "universe": "TOP3000",
        "neutralization": "SECTOR",
        "decay": 10,
        "expression": "group_neutralize(rank(ts_decay_linear((close - ts_delay(close, 20)) / (ts_std_dev(returns, 20) * close + 0.001), 10)), sector)",
        "min_margin": 0.00035,
    },
    # 4. VWAP Deviation Fade with heavy volume filter
    {
        "name": "VWAP_Deviation_Fade_TOP3000",
        "archetype": "VWAP_Deviation_Fade_SUBIND",
        "hypothesis": "Fading intraday price stretch away from VWAP on volume expansion yields high-margin reversal returns.",
        "universe": "TOP3000",
        "neutralization": "SUBINDUSTRY",
        "decay": 4,
        "expression": "trade_when(volume > adv20 * 0.6, group_neutralize(rank(ts_decay_linear(-((close - vwap) / (vwap + 0.001)), 4)), subindustry), -1)",
        "min_margin": 0.00035,
    },
    # 5. Volatility Range Expansion Reversal
    {
        "name": "EQ_Range_Expansion_Rev_TOP3000",
        "archetype": "EQ_Range_Expansion_Rev_SUBIND",
        "hypothesis": "Multi-day return reversal scaled by volatility range expansion reveals capitulation.",
        "universe": "TOP3000",
        "neutralization": "SUBINDUSTRY",
        "decay": 6,
        "expression": "trade_when(volume > adv20 * 0.7, group_neutralize(rank(-ts_delta(close, 2)) * rank((high - low) / (ts_mean(high - low, 15) + 0.001)), subindustry), -1)",
        "min_margin": 0.00035,
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

    log.info("Authenticating with BRAIN...")
    await asyncio.to_thread(client.authenticate)

    ref_ids, _ = load_reference_pnls(config.database_url)
    ref_pnls = {}
    log.info("Loading reference PnLs for %d production alphas...", len(ref_ids))
    for aid in ref_ids:
        pnl = await client.get_alpha_pnl(aid)
        if pnl:
            ref_pnls[aid] = pnl
    log.info("Loaded %d clean portfolio PnLs.", len(ref_pnls))

    qualified = []
    for idx, c in enumerate(CANDIDATES):
        name = c["name"]
        arch = c["archetype"]
        hyp = c["hypothesis"]
        u = c["universe"]
        neut = c["neutralization"]
        decay = c["decay"]
        expr = c["expression"]
        min_margin = c.get("min_margin", 0.00035)

        log.info("\n" + "=" * 70)
        log.info("[%d/%d] SIMULATING: %s (u=%s, neut=%s, d=%d)", idx + 1, len(CANDIDATES), name, u, neut, decay)
        log.info("=" * 70)

        settings = SimSettings(
            region="USA",
            universe=u,
            delay=1,
            decay=decay,
            neutralization=neut,
            truncation=0.05,
            pasteurization=True,
        )

        try:
            m = await client.simulate_one(expr, settings)
        except Exception as e:
            log.warning("Sim error for %s: %s", name, e)
            continue

        if not m or not m.is_valid:
            log.warning("Invalid metrics for %s", name)
            continue

        aid = m.alpha_id
        log.info("[Result] %s (%s): Sharpe=%.2f | Fit=%.2f | TO=%.1f%% | Marg=%.1fbps | DD=%.1f%%",
                 aid, name, m.sharpe, m.fitness, m.turnover * 100, m.margin * 10000, m.max_drawdown * 100)

        # Gate 1: Performance Gate
        if m.sharpe < 1.25 or m.fitness < 0.70 or m.turnover < 0.01 or m.turnover > 0.70 or m.margin < min_margin:
            log.info("[-] Gate 1 FAIL for %s (Sharpe=%.2f, Fit=%.2f, Margin=%.1fbps)", aid, m.sharpe, m.fitness, m.margin * 10000)
            continue
        log.info("[+] Gate 1 PASS for %s!", aid)

        # Gate 2: Correlation Gate
        pnl = await client.get_alpha_pnl(aid)
        if not pnl or len(pnl) < 30:
            log.warning("No PnL returned for %s", aid)
            continue

        max_corr = 0.0
        colliding = None
        for r_id, r_pnl in ref_pnls.items():
            corr = abs(compute_correlation(pnl, r_pnl))
            if corr > max_corr:
                max_corr = corr
                colliding = r_id

        log.info("[Correlation] %s vs Portfolio: Max Corr = %.4f (colliding: %s)", aid, max_corr, colliding)
        if max_corr >= 0.70:
            log.warning("[-] Gate 2 FAIL: Corr %.4f >= 0.70 vs %s", max_corr, colliding)
            continue
        log.info("[+] Gate 2 PASS for %s!", aid)

        # Gate 3: Platform Checklist Gate
        log.info("[*] Verifying Gate 3 checklist on BRAIN for %s...", aid)
        chk_pass, chk_msg = verify_checklist_passes(client._session, aid)
        if not chk_pass:
            log.warning("[-] Gate 3 FAIL for %s: %s", aid, chk_msg)
            continue
        log.info("[🌟] Gate 3 PASS for %s! All checks passed!", aid)

        # Commit to Neon DB
        commit_qualified_alpha(
            db_url=config.database_url,
            alpha_id=aid,
            expression=expr,
            archetype=arch,
            hypothesis=hyp,
            metrics=m,
            max_corr=max_corr,
            universe=u,
            neutralization=neut,
            decay=decay,
            category="reserve_vault",
        )
        ref_pnls[aid] = pnl
        qualified.append(aid)

        send_tg_message(
            token=config.telegram_bot_token,
            chat_id=config.telegram_chat_id,
            html_text=(
                f"🌟 <b>NEW RESERVE ALPHA QUALIFIED!</b> 🌟\n\n"
                f"• <b>Alpha ID:</b> <code>{aid}</code>\n"
                f"• <b>Name:</b> {name}\n"
                f"• <b>Sharpe:</b> {m.sharpe:.2f} | <b>Fitness:</b> {m.fitness:.2f}\n"
                f"• <b>Margin:</b> {m.margin * 10000:.1f} bps | <b>Turnover:</b> {m.turnover * 100:.1f}%\n"
                f"• <b>Max Corr:</b> {max_corr:.4f} (&lt; 0.70)\n"
                f"• <b>Sub-Universe:</b> 100% PASS\n"
                f"• <b>Expression:</b>\n<code>{expr}</code>"
            ),
        )

        log.info(">>> TOTAL QUALIFIED NOW: %d <<<", len(qualified))

    log.info("Finished reserve qualification sweep. Total qualified: %d", len(qualified))

if __name__ == "__main__":
    asyncio.run(main())
