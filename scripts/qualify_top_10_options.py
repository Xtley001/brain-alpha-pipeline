"""
Evaluates the 38 pre-simulated institutional options alphas against clean portfolio reference PnLs,
selects 10 mutually uncorrelated alphas (|rho| < 0.70), verifies BRAIN platform checklist,
and commits them to PostgreSQL as QUALIFIED.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import time
import logging
import decimal
import dotenv
import psycopg
import requests
import numpy as np

dotenv.load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("qualify_top_10")

from brain_options.config import OptionsConfig
from brain_options.core.client import BrainClient
from brain_options.store.store import OptionsStore
from scripts.cloud_multi_miner import (
    load_reference_pnls,
    compute_correlation,
    verify_checklist_passes,
    commit_qualified_alpha,
    send_tg_message
)

# 38 candidate alpha IDs discovered overnight by the options miner
CANDIDATE_IDS = [
    "RR6Jg5Ma", "JjQjVJzx", "A1v11nKX", "XgJj3EKm", "N1VXP33w", "vR2KYOow",
    "zqbvxAdK", "RR6JGLYd", "P0gJVj5E", "blOYeAql", "leKLwK5n", "qM0KwQRO",
    "blOY1LZN", "88P8m73v", "2rm12EMZ", "0mrbLxrG", "xAbK5Rkg", "leKeplM7",
    "WjejM2WQ", "gJZYNk1J", "7868WkW8", "LLZPM0Je", "A1v1jVLY", "JjQVzkEO",
    "gJZYdeRQ", "JjQVPoWl", "omWm723l", "akxkk8g6", "rKeKKNKa", "qM0M9Z5A",
    "MP3PW3r8", "WjejqEGQ", "N1V10VLE", "MP3jeXw6", "kqgqdX1l", "omWm1Gnn",
    "786keY68", "LLZPzJp6"
]

import asyncio

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

    # Load clean reference PnLs
    ref_alpha_ids, known_exprs = load_reference_pnls(config.database_url)
    ref_pnls = {}
    log.info("Fetching PnL for %d clean reference alphas...", len(ref_alpha_ids))
    for aid in ref_alpha_ids:
        pnl = await client.get_alpha_pnl(aid)
        if pnl:
            ref_pnls[aid] = pnl
    log.info("Loaded %d clean reference PnLs.", len(ref_pnls))

    # Fetch metadata and PnL for each of the 38 candidates
    valid_candidates = []
    log.info("Evaluating %d candidate alphas from overnight logs...", len(CANDIDATE_IDS))

    for aid in CANDIDATE_IDS:
        try:
            # Fetch alpha details from BRAIN
            session = client._get_session()
            resp = session.get(f"https://api.worldquantbrain.com/alphas/{aid}", timeout=15)
            if resp.status_code != 200:
                log.warning("Could not fetch alpha %s: %s", aid, resp.status_code)
                continue
            adata = resp.json()
            is_data = adata.get("is", {})
            sharpe = float(is_data.get("sharpe", 0.0) or 0.0)
            fitness = float(is_data.get("fitness", 0.0) or 0.0)
            turnover = float(is_data.get("turnover", 0.0) or 0.0)
            margin = float(is_data.get("margin", 0.0) or 0.0)
            drawdown = float(is_data.get("drawdown", 0.0) or 0.0)
            settings = adata.get("settings", {})
            expr = adata.get("regular", {}).get("code", "") or adata.get("code", "")
            universe = settings.get("universe", "TOP3000")
            neut = settings.get("neutralization", "SUBINDUSTRY")
            decay = int(settings.get("decay", 14))

            # Fetch PnL
            pnl = await client.get_alpha_pnl(aid)
            if not pnl or len(pnl) < 30:
                log.warning("No PnL available for %s", aid)
                continue

            # Gate 2: Check correlation vs clean reference alphas
            max_ref_corr = 0.0
            if ref_pnls:
                corrs = [abs(compute_correlation(pnl, ref_p)) for ref_p in ref_pnls.values()]
                max_ref_corr = max(corrs) if corrs else 0.0

            log.info("Alpha %s: Sharpe=%.2f | Fit=%.2f | TO=%.1f%% | Max Portfolio Corr=%.4f", aid, sharpe, fitness, turnover*100, max_ref_corr)

            if max_ref_corr < 0.70:
                valid_candidates.append({
                    "alpha_id": aid,
                    "sharpe": sharpe,
                    "fitness": fitness,
                    "turnover": turnover,
                    "margin": margin,
                    "drawdown": drawdown,
                    "universe": universe,
                    "neutralization": neut,
                    "decay": decay,
                    "expression": expr,
                    "pnl": pnl,
                    "max_ref_corr": max_ref_corr,
                })
        except Exception as e:
            log.warning("Error fetching alpha %s: %s", aid, e)

    log.info("=" * 70)
    log.info("Candidate Alphas Passing Portfolio Correlation Gate: %d / %d", len(valid_candidates), len(CANDIDATE_IDS))
    log.info("=" * 70)

    # Greedily select up to 10 mutually uncorrelated alphas (|rho_ij| < 0.70)
    # Sort by Sharpe descending to prioritize the highest-quality alphas
    valid_candidates.sort(key=lambda x: x["sharpe"], reverse=True)

    selected_alphas = []
    selected_pnls = {}

    for cand in valid_candidates:
        aid = cand["alpha_id"]
        cand_pnl = cand["pnl"]

        # Check correlation vs already selected candidates in this batch
        batch_corrs = [abs(compute_correlation(cand_pnl, p)) for p in selected_pnls.values()]
        max_batch_corr = max(batch_corrs) if batch_corrs else 0.0

        if max_batch_corr < 0.70:
            # Candidate is uncorrelated with existing portfolio AND this batch!
            # Now verify Gate 3: Platform Checklist on BRAIN
            log.info("[*] Testing Gate 3 platform checklist for %s (Sharpe=%.2f)...", aid, cand["sharpe"])
            chk_passed, chk_msg = verify_checklist_passes(client._session, aid)
            if chk_passed:
                log.info("[✓] Gate 3 PASSED for %s: %s", aid, chk_msg)
                cand["max_batch_corr"] = max(cand["max_ref_corr"], max_batch_corr)
                selected_alphas.append(cand)
                selected_pnls[aid] = cand_pnl
                ref_pnls[aid] = cand_pnl

                # Commit to DB immediately
                from brain_options.core.client import SimMetrics
                metrics = SimMetrics(
                    alpha_id=aid,
                    sharpe=cand["sharpe"],
                    fitness=cand["fitness"],
                    turnover=cand["turnover"],
                    annualized_return=0.0,
                    max_drawdown=cand["drawdown"],
                    margin=cand["margin"],
                    status="COMPLETE"
                )
                commit_qualified_alpha(
                    db_url=config.database_url,
                    alpha_id=aid,
                    expression=cand["expression"],
                    archetype="options_surface_smirk",
                    hypothesis=f"Institutional options surface smirk with Sharpe={cand['sharpe']:.2f}, Fit={cand['fitness']:.2f}",
                    metrics=metrics,
                    max_corr=cand["max_batch_corr"],
                    universe=cand["universe"],
                    neutralization=cand["neutralization"],
                    decay=cand["decay"],
                    category="options"
                )
                # Send telegram notification
                send_tg_message(
                    token=config.telegram_bot_token,
                    chat_id=config.telegram_chat_id,
                    html_text=(
                        f"🌟 <b>NEW OPTIONS ALPHA QUALIFIED!</b> 🌟\n\n"
                        f"• <b>Alpha ID:</b> <code>{aid}</code>\n"
                        f"• <b>Category:</b> options\n"
                        f"• <b>Sharpe:</b> {cand['sharpe']:.2f} | <b>Fitness:</b> {cand['fitness']:.2f}\n"
                        f"• <b>Margin:</b> {cand['margin'] * 10000:.1f} bps | <b>Turnover:</b> {cand['turnover'] * 100:.1f}%\n"
                        f"• <b>Max Correlation:</b> {cand['max_batch_corr']:.4f} (&lt; 0.70)\n"
                        f"• <b>Sub-Universe Check:</b> 100% PASS\n"
                        f"• <b>Expression:</b>\n<code>{cand['expression']}</code>"
                    )
                )

                if len(selected_alphas) >= 10:
                    log.info("Target of 10 mutually uncorrelated qualified alphas reached!")
                    break
            else:
                log.warning("[-] Gate 3 failed for %s: %s", aid, chk_msg)

    print("\n" + "=" * 70)
    print(f"QUALIFICATION COMPLETE: {len(selected_alphas)} / 10 ALPHAS COMMITTED")
    print("=" * 70)
    for a in selected_alphas:
        print(f"Alpha {a['alpha_id']}: Sharpe={a['sharpe']:.2f}, Fit={a['fitness']:.2f}, TO={a['turnover']*100:.1f}%, Margin={a['margin']*10000:.1f}bps, MaxCorr={a['max_batch_corr']:.4f}")

if __name__ == "__main__":
    asyncio.run(main())
