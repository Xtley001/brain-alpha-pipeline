#!/usr/bin/env python3
"""
Dedicated Cloud Multi-Category Alpha Miner for GitHub Actions.
Supports:
- category: sentiment (sentiment1/2, ValueScore=8.0, PEAD & SUE)
- category: risk_model (model51/52, ValueScore=7.0, BAB & Factor Divergence)
- category: apex (tri-category orthogonal synthesis)

Configured for Concurrency = 1 (Single Slot Execution)
Leaves 1 simulation slot permanently open for Local PC Options mining,
guaranteeing zero 429 concurrency limit collisions on WorldQuant BRAIN.
"""
from __future__ import annotations

import argparse
import asyncio
import decimal
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg
import requests
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("cloud_miner")

from brain_options.config import OptionsConfig
from brain_options.core.client import BrainClient, SimMetrics, SimSettings
from brain_options.core.correlation import compute_correlation
from brain_options.llm.adapter import LLMAdapter
from brain_options.store.store import OptionsStore

from brain_sentiment.specialist.generator import SentimentGenerator
from brain_risk_model.specialist.generator import RiskModelGenerator
from brain_synthesis.apex_generator import generate_apex_candidates


def send_tg_message(token: str, chat_id: str, html_text: str):
    """Deliver HTML message to Telegram."""
    if not token or not chat_id:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": html_text, "parse_mode": "HTML"},
            timeout=15,
        )
    except Exception as e:
        log.warning("Telegram alert failed: %s", e)


def verify_checklist_passes(session, alpha_id: str) -> Tuple[bool, str]:
    """Verify all platform checklist checks pass on BRAIN."""
    for _ in range(8):
        try:
            r = session.get(f"https://api.worldquantbrain.com/alphas/{alpha_id}/check", timeout=20)
            if r.status_code == 200 and r.text.strip():
                data = r.json()
                checks = data.get("is", {}).get("checks", []) or data.get("checks", [])
                if checks:
                    failures = []
                    for c in checks:
                        name = c.get("name", "")
                        result = c.get("result", "")
                        if result != "PASS":
                            failures.append(f"{name}:{result}")
                    if failures:
                        return False, ", ".join(failures)
                    return True, "ALL_PASSED"
        except Exception:
            pass
        time.sleep(3)
    return False, "Checklist timed out or unavailable"


def load_reference_pnls(db_url: str) -> Tuple[List[str], Dict[str, Dict[str, float]]]:
    """Load submitted and reserve alpha IDs from Neon PostgreSQL."""
    known_exprs = set()
    ref_alpha_ids = []
    if not db_url:
        return ref_alpha_ids, known_exprs

    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT alpha_id, expression FROM options_alphas WHERE status IN ('SUBMITTED', 'QUALIFIED') AND alpha_id IS NOT NULL;")
                rows = cur.fetchall()
                for r in rows:
                    if r[0]:
                        ref_alpha_ids.append(r[0])
                    if r[1]:
                        known_exprs.add(r[1].strip())
    except Exception as e:
        log.warning("Failed to load reference alphas: %s", e)
    return ref_alpha_ids, known_exprs


def commit_qualified_alpha(
    db_url: str,
    alpha_id: str,
    expression: str,
    archetype: str,
    hypothesis: str,
    metrics: SimMetrics,
    max_corr: float,
    universe: str,
    neutralization: str,
    decay: int,
    category: str,
):
    """Commit newly qualified multi-category alpha to Neon DB."""
    if not db_url:
        return

    sql = """
        INSERT INTO options_alphas (
            alpha_id, expression, archetype, hypothesis, source,
            sharpe, fitness, turnover, returns, drawdown, margin,
            max_correlation, universe, neutralization, delay, decay,
            truncation, pasteurization, nan_handling, status,
            created_at, strategy_name
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, 1, %s,
            0.05, 'ON', 'OFF', 'QUALIFIED',
            NOW(), %s
        ) ON CONFLICT (alpha_id) DO UPDATE SET
            status = 'QUALIFIED',
            sharpe = EXCLUDED.sharpe,
            fitness = EXCLUDED.fitness,
            margin = EXCLUDED.margin,
            max_correlation = EXCLUDED.max_correlation;
    """
    try:
        with psycopg.connect(db_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (
                    alpha_id, expression, archetype, hypothesis, f"cloud_miner_{category}",
                    decimal.Decimal(str(round(metrics.sharpe, 4))),
                    decimal.Decimal(str(round(metrics.fitness, 4))),
                    decimal.Decimal(str(round(metrics.turnover, 4))),
                    decimal.Decimal(str(round(metrics.returns, 4))),
                    decimal.Decimal(str(round(metrics.max_drawdown, 4))),
                    decimal.Decimal(str(round(metrics.margin, 4))),
                    decimal.Decimal(str(round(max_corr, 4))),
                    universe, neutralization, decay,
                    f"cloud_{category}",
                ))
        log.info("[+] Successfully committed %s to options_alphas as QUALIFIED.", alpha_id)
    except Exception as e:
        log.error("Failed to commit qualified alpha %s: %s", alpha_id, e)


async def run_cloud_miner(category: str, max_candidates: int, timeout_mins: int):
    config = OptionsConfig()
    store = OptionsStore()
    llm = LLMAdapter(config)
    client = BrainClient(config)

    log.info("=" * 70)
    log.info("STARTING CLOUD MULTI-MINER: Category=%s | Batch=%d | Timeout=%dm", category.upper(), max_candidates, timeout_mins)
    log.info("Concurrency: 1 (Reserved Single-Slot Mode to prevent collisions with Local PC)")
    log.info("=" * 70)

    # 1. Login to WorldQuant BRAIN
    login_ok = await client.login()
    if not login_ok:
        log.error("Failed to authenticate with WorldQuant BRAIN.")
        return

    # 2. Pre-fetch reference PnLs for correlation gate
    ref_alpha_ids, known_exprs = load_reference_pnls(config.database_url)
    ref_pnls: Dict[str, Dict[str, float]] = {}
    log.info("Pre-fetching PnL for %d portfolio reference alphas...", len(ref_alpha_ids))
    for aid in ref_alpha_ids:
        pnl = await client.get_alpha_pnl(aid)
        if pnl:
            ref_pnls[aid] = pnl

    # 3. Initialize generator based on category
    generator = None
    if category == "sentiment":
        generator = SentimentGenerator(db=store.db, llm_adapter=llm)
    elif category == "risk_model":
        generator = RiskModelGenerator(db=store.db, llm_adapter=llm)
    elif category == "apex":
        apex_candidates = generate_apex_candidates()
        log.info("Loaded %d static apex tri-factor candidates.", len(apex_candidates))
    else:
        raise ValueError(f"Unknown category: {category}")

    candidates_evaluated = 0
    qualified_count = 0
    start_time = time.time()
    max_duration_sec = timeout_mins * 60

    while candidates_evaluated < max_candidates:
        if time.time() - start_time > max_duration_sec:
            log.info("Time budget (%d mins) reached. Wrapping up cloud batch.", timeout_mins)
            break

        # Pull next candidate
        if category == "apex":
            if not apex_candidates:
                break
            cand_obj = apex_candidates.pop(0)
            expr = cand_obj.expression
            arch = cand_obj.name
            hyp = cand_obj.hypothesis
            universe = cand_obj.universe
            neut = cand_obj.neutralization
            decay = cand_obj.decay
        else:
            cand_obj = generator.generate_candidate()
            expr = cand_obj.expression
            arch = cand_obj.archetype
            hyp = cand_obj.hypothesis
            universe = cand_obj.universe
            neut = cand_obj.neutralization
            decay = cand_obj.decay

        if expr in known_exprs:
            continue
        known_exprs.add(expr)

        candidates_evaluated += 1
        settings = SimSettings(
            region="USA",
            universe=universe,
            delay=1,
            decay=decay,
            neutralization=neut,
            truncation=0.05,
            pasteurization=True,
        )

        log.info("[%s Sim #%d/%d] Simulating %s (decay=%d, u=%s)...", category.upper(), candidates_evaluated, max_candidates, arch, decay, universe)
        try:
            metrics = await client.simulate_one(expr, settings)
        except Exception as e:
            log.warning("Simulation exception: %s", e)
            await asyncio.sleep(2.0)
            continue

        if not metrics or not metrics.is_valid:
            await asyncio.sleep(1.0)
            continue

        log.info(
            "[%s Sim #%d] %s | Sharpe=%.2f | Fitness=%.2f | TO=%.1f%% | Margin=%.1fbps | DD=%.1f%% | %s",
            category.upper(), candidates_evaluated, metrics.alpha_id, metrics.sharpe, metrics.fitness,
            metrics.turnover * 100, metrics.margin * 10000, metrics.max_drawdown * 100, arch
        )

        # Gate 1: Performance Gate
        if (
            metrics.sharpe < 1.25
            or metrics.fitness < 1.00
            or metrics.turnover < 0.01
            or metrics.turnover > 0.70
            or metrics.margin < 0.0008
            or metrics.max_drawdown > 0.35
        ):
            await asyncio.sleep(0.5)
            continue

        # Gate 2: Cross-Portfolio Correlation Gate (|rho| < 0.70)
        cand_pnl = await client.get_alpha_pnl(metrics.alpha_id)
        if not cand_pnl or len(cand_pnl) < 30:
            continue

        max_corr = 0.0
        if ref_pnls:
            corrs = [abs(compute_correlation(cand_pnl, p)) for p in ref_pnls.values()]
            max_corr = max(corrs) if corrs else 0.0

        if max_corr >= 0.70:
            log.info("[-] Correlation failure (%.4f >= 0.70) for %s vs portfolio.", max_corr, metrics.alpha_id)
            continue

        # Gate 3: Platform Checklist Gate (Sub-Universe Sharpe)
        log.info("[*] Verifying platform checklist on BRAIN for %s...", metrics.alpha_id)
        chk_passed, chk_msg = verify_checklist_passes(client._session, metrics.alpha_id)
        if not chk_passed:
            log.warning("[-] Checklist check FAILED for %s: %s", metrics.alpha_id, chk_msg)
            continue

        # Passed all 3 gates!
        qualified_count += 1
        ref_pnls[metrics.alpha_id] = cand_pnl
        commit_qualified_alpha(
            db_url=config.database_url,
            alpha_id=metrics.alpha_id,
            expression=expr,
            archetype=arch,
            hypothesis=hyp,
            metrics=metrics,
            max_corr=max_corr,
            universe=universe,
            neutralization=neut,
            decay=decay,
            category=category,
        )

        # Telegram Alert
        send_tg_message(
            token=config.telegram_bot_token,
            chat_id=config.telegram_chat_id,
            html_text=(
                f"🌟 <b>NEW {category.upper()} ALPHA QUALIFIED ON CLOUD!</b> 🌟\n\n"
                f"• <b>Alpha ID:</b> <code>{metrics.alpha_id}</code>\n"
                f"• <b>Category:</b> {category}\n"
                f"• <b>Archetype:</b> {arch}\n"
                f"• <b>Sharpe:</b> {metrics.sharpe:.2f} | <b>Fitness:</b> {metrics.fitness:.2f}\n"
                f"• <b>Margin:</b> {metrics.margin * 10000:.1f} bps | <b>Turnover:</b> {metrics.turnover * 100:.1f}%\n"
                f"• <b>Max Correlation:</b> {max_corr:.4f} (&lt; 0.70)\n"
                f"• <b>Sub-Universe Check:</b> 100% PASS\n"
                f"• <b>Expression:</b>\n<code>{expr}</code>"
            ),
        )

    log.info("=" * 70)
    log.info("CLOUD MINER COMPLETE: %d evaluated | %d QUALIFIED", candidates_evaluated, qualified_count)
    log.info("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Dedicated Cloud Multi-Category Alpha Miner")
    parser.add_argument("--category", choices=["sentiment", "risk_model", "apex"], required=True, help="Category to mine")
    parser.add_argument("--candidates", type=int, default=25, help="Max candidates to simulate")
    parser.add_argument("--timeout-mins", type=int, default=20, help="Max time in minutes")
    args = parser.parse_args()

    asyncio.run(run_cloud_miner(category=args.category, max_candidates=args.candidates, timeout_mins=args.timeout_mins))


if __name__ == "__main__":
    main()
