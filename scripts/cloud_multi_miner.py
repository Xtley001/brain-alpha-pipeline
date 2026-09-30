#!/usr/bin/env python3
"""
Dedicated Cloud Multi-Category Alpha Miner for GitHub Actions.
Supports:
- category: options   (option8/option9, ValueScore=5-6, Vol Surface & PCR)
- category: sentiment (sentiment1/2, ValueScore=8.0, PEAD & SUE)
- category: risk_model (model51/52, ValueScore=7.0, BAB & Factor Divergence)
- category: apex (tri-category orthogonal synthesis)

Configured for Concurrency = 1 per job.
All three verticals run as separate GitHub Actions jobs:
  mine_options.yml     cron: 0  */6 * * *  (fires at :00)
  mine_sentiment.yml   cron: 15 */6 * * *  (fires at :15)
  mine_risk_model.yml  cron: 45 */6 * * *  (fires at :45)
This fills all 3 BRAIN simulation slots 24/7 with zero local PC dependency.
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

from brain_options.specialist.generator import OptionsGenerator
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
    """Verify all critical platform checklist checks pass on BRAIN."""
    for attempt in range(18):  # up to 180 seconds total
        try:
            r = session.get(f"https://api.worldquantbrain.com/alphas/{alpha_id}/check", timeout=20)
            if r.status_code == 200 and r.text.strip():
                data = r.json()
                checks = data.get("is", {}).get("checks", []) or data.get("checks", [])
                if checks:
                    # Check if any asynchronous check is still PENDING
                    pending = [c.get("name", "") for c in checks if c.get("result") == "PENDING"]
                    if pending and attempt < 17:
                        log.info("[*] Checklist for %s has in-flight checks (%s), waiting... (attempt %d/18)", alpha_id, ", ".join(pending), attempt + 1)
                        time.sleep(10)
                        continue

                    failures = []
                    for c in checks:
                        name = c.get("name", "")
                        result = c.get("result", "")
                        # Non-blocking warnings (e.g., UNITS, DATA_PREVIEW) do NOT fail submission on BRAIN
                        if result in ("PASS", "WARNING"):
                            continue
                        failures.append(f"{name}:{result}")

                    if failures:
                        return False, ", ".join(failures)
                    return True, "ALL_PASSED"
        except Exception as e:
            log.warning("Checklist fetch attempt %d for %s failed: %s", attempt + 1, alpha_id, e)
        time.sleep(10)
    return False, "Checklist timed out or unavailable"


def load_reference_pnls(db_url: str) -> Tuple[List[str], Dict[str, Dict[str, float]]]:
    """Load submitted and reserve alpha IDs from Neon PostgreSQL."""
    known_exprs = set()
    ref_alpha_ids = []
    if not db_url:
        return ref_alpha_ids, known_exprs

    try:
        with psycopg.connect(
            db_url,
            keepalives=1, keepalives_idle=30, keepalives_interval=10, keepalives_count=5
        ) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT alpha_id, expression FROM options_alphas WHERE status IN ('SUBMITTED', 'QUALIFIED') AND status != 'REJECTED_SUBUNIVERSE' AND alpha_id IS NOT NULL;")
                rows = cur.fetchall()
                for r in rows:
                    if r[0]:
                        ref_alpha_ids.append(r[0])
                    if r[1]:
                        known_exprs.add(r[1].strip())
        log.info("Loaded %d reference alpha IDs and %d known expressions from DB.", len(ref_alpha_ids), len(known_exprs))
    except Exception as e:
        log.error("CRITICAL: Failed to load reference alphas from DB — correlation gate will run BLIND: %s", e)
        # Abort rather than run with empty correlation reference (risk of qualifying correlated alphas)
        raise RuntimeError(f"Cannot start cloud miner without DB reference data: {e}") from e
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
        with psycopg.connect(
            db_url, autocommit=True,
            keepalives=1, keepalives_idle=30, keepalives_interval=10, keepalives_count=5
        ) as conn:
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


def pre_screen_expression(expr: str) -> Tuple[bool, str]:
    """Fast local syntactic and structural filter before submitting to BRAIN."""
    clean = expr.strip()
    if clean.count("(") != clean.count(")"):
        return False, "Unbalanced parentheses"
    if len(clean) < 10:
        return False, "Expression too short"
    if ",," in clean or "(," in clean or ",)" in clean:
        return False, "Malformed comma syntax"
    if "rank(rank(" in clean:
        return False, "Redundant nested rank"
    return True, "OK"


async def evaluate_candidate_qualification(
    client: BrainClient,
    metrics: SimMetrics,
    expr: str,
    arch: str,
    hyp: str,
    universe: str,
    neut: str,
    decay: int,
    category: str,
    config: Any,
    ref_pnls: Dict[str, Dict[str, float]],
) -> bool:
    """Decoupled Gate 2 & Gate 3 verification pipeline executed asynchronously."""
    try:
        # Gate 2: Cross-Portfolio Correlation Gate (|rho| < 0.70)
        cand_pnl = await client.get_alpha_pnl(metrics.alpha_id)
        if not cand_pnl or len(cand_pnl) < 30:
            log.warning("[-] Could not retrieve PnL for %s — skipping.", metrics.alpha_id)
            return False

        max_corr = 0.0
        if ref_pnls:
            corrs = [abs(compute_correlation(cand_pnl, p)) for p in list(ref_pnls.values())]
            max_corr = max(corrs) if corrs else 0.0

        if max_corr >= 0.70:
            log.info("[-] Correlation failure (%.4f >= 0.70) for %s vs portfolio.", max_corr, metrics.alpha_id)
            return False

        # Gate 3: Platform Checklist Gate (Sub-Universe Sharpe)
        log.info("[*] Verifying platform checklist on BRAIN for %s...", metrics.alpha_id)
        chk_passed, chk_msg = verify_checklist_passes(client._session, metrics.alpha_id)
        if not chk_passed:
            log.warning("[-] Checklist check FAILED for %s: %s", metrics.alpha_id, chk_msg)
            return False

        # Passed all 3 gates!
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
        log.info("[🌟] QUALIFIED & COMMITTED: %s (%s, Sharpe=%.2f, Fit=%.2f)", metrics.alpha_id, arch, metrics.sharpe, metrics.fitness)
        return True
    except Exception as exc:
        log.error("Error in asynchronous qualification pipeline for %s: %s", metrics.alpha_id, exc)
        return False


async def run_cloud_miner(category: str, max_candidates: int, timeout_mins: int):
    config = OptionsConfig.from_env()
    store = OptionsStore()
    llm = LLMAdapter(config)
    client = BrainClient(
        username=config.brain_username,
        password=config.brain_password,
        max_concurrent_sims=1,
        db=store.db,
    )

    log.info("=" * 70)
    log.info("STARTING CLOUD MULTI-MINER: Category=%s | Batch=%d | Timeout=%dm", category.upper(), max_candidates, timeout_mins)
    log.info("Concurrency: 1 (Reserved Single-Slot Mode to prevent collisions with Local PC)")
    log.info("=" * 70)

    # 1. Authenticate with WorldQuant BRAIN (resumes PostgreSQL cluster session cache)
    try:
        await asyncio.to_thread(client.authenticate)
    except Exception as auth_err:
        log.error("Failed to authenticate with WorldQuant BRAIN: %s", auth_err)
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
    if category == "options":
        generator = OptionsGenerator(db=store.db, llm_adapter=llm)
        log.info("Options generator loaded. Mining option8/option9 (138 fields, PCR+Vol Surface).")
    elif category == "sentiment":
        generator = SentimentGenerator(db=store.db, llm_adapter=llm)
    elif category == "risk_model":
        generator = RiskModelGenerator(db=store.db, llm_adapter=llm)
    elif category == "apex":
        apex_candidates = generate_apex_candidates()
        log.info("Loaded %d static apex tri-factor candidates.", len(apex_candidates))
    else:
        raise ValueError(f"Unknown category: {category}")

    candidates_evaluated = 0
    start_time = time.time()
    max_duration_sec = timeout_mins * 60
    priority_queue: List[Dict[str, Any]] = []
    background_eval_tasks: set[asyncio.Task] = set()

    while candidates_evaluated < max_candidates:
        if time.time() - start_time > max_duration_sec:
            log.info("Time budget (%d mins) reached. Wrapping up cloud batch.", timeout_mins)
            break

        # Pull next candidate (priority near-miss sweep first, then generator)
        if priority_queue:
            cand_obj = priority_queue.pop(0)
            expr = cand_obj["expression"]
            arch = cand_obj["archetype"]
            hyp = cand_obj["hypothesis"]
            universe = cand_obj["universe"]
            neut = cand_obj["neutralization"]
            decay = cand_obj["decay"]
            region = cand_obj.get("region", "USA")
        elif category == "apex":
            if not apex_candidates:
                break
            cand_obj = apex_candidates.pop(0)
            expr = cand_obj.expression
            arch = cand_obj.name
            hyp = cand_obj.hypothesis
            universe = cand_obj.universe
            neut = cand_obj.neutralization
            decay = cand_obj.decay
            region = getattr(cand_obj, "region", "USA")
        else:
            cand_obj = generator.generate_candidate()
            expr = cand_obj.expression
            arch = getattr(cand_obj, "archetype", None) or getattr(cand_obj, "archetype_name", "general")
            hyp = getattr(cand_obj, "hypothesis", "")
            universe = getattr(cand_obj, "universe", "TOP3000")
            neut = getattr(cand_obj, "neutralization", "SUBINDUSTRY")
            decay = getattr(cand_obj, "decay", 18)
            region = getattr(cand_obj, "region", "USA")

        if expr in known_exprs:
            continue
        known_exprs.add(expr)

        # Fast local pre-screening
        ok, reason = pre_screen_expression(expr)
        if not ok:
            log.warning("[-] Pre-screening rejected expression (%s): %s", reason, expr[:60])
            continue

        candidates_evaluated += 1
        settings = SimSettings(
            region=region,
            universe=universe,
            delay=1,
            decay=decay,
            neutralization=neut,
            truncation=0.05,
            pasteurization=True,
        )

        log.info("[%s Sim #%d/%d] Simulating %s (decay=%d, u=%s, r=%s)...", category.upper(), candidates_evaluated, max_candidates, arch, decay, universe, region)
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
        fitness_threshold = 0.70 if category == "options" else 1.00
        if (
            metrics.sharpe >= 1.25
            and metrics.fitness >= fitness_threshold
            and 0.01 <= metrics.turnover <= 0.70
            and metrics.margin >= 0.0008
            and metrics.max_drawdown <= 0.35
        ):
            log.info("[+] Candidate %s passed Gate 1! Spawning async Gate 2 & Gate 3 verification pipeline...", metrics.alpha_id)
            eval_task = asyncio.create_task(
                evaluate_candidate_qualification(
                    client=client,
                    metrics=metrics,
                    expr=expr,
                    arch=arch,
                    hyp=hyp,
                    universe=universe,
                    neut=neut,
                    decay=decay,
                    category=category,
                    config=config,
                    ref_pnls=ref_pnls,
                )
            )
            background_eval_tasks.add(eval_task)
            eval_task.add_done_callback(background_eval_tasks.discard)

        # Convex Surface Near-Miss Sweep: If Sharpe in [1.05, 1.24] and Fitness meets threshold, generate micro-sweeps
        elif (
            1.05 <= metrics.sharpe < 1.25
            and metrics.fitness >= (0.40 if category == "options" else 0.65)
            and 0.01 <= metrics.turnover <= 0.70
            and len(priority_queue) < 15
        ):
            log.info("[⚡] Near-Miss detected for %s (Sharpe=%.2f, Fit=%.2f). Enqueuing convex surface gradient mutations...", metrics.alpha_id, metrics.sharpe, metrics.fitness)
            for d_shift in (-3, 3):
                new_d = max(5, decay + d_shift)
                priority_queue.append({
                    "expression": expr,
                    "archetype": arch,
                    "hypothesis": f"{hyp} [Convex Sweep d={new_d}]",
                    "universe": universe,
                    "neutralization": neut,
                    "decay": new_d,
                    "region": region,
                })
            alt_neut = "SECTOR" if neut.upper() == "SUBINDUSTRY" else "SUBINDUSTRY"
            priority_queue.append({
                "expression": expr,
                "archetype": arch,
                "hypothesis": f"{hyp} [Convex Sweep neut={alt_neut}]",
                "universe": universe,
                "neutralization": alt_neut,
                "decay": decay,
                "region": region,
            })

    if background_eval_tasks:
        log.info("[*] Waiting for %d in-flight qualification evaluation tasks to complete...", len(background_eval_tasks))
        await asyncio.gather(*background_eval_tasks, return_exceptions=True)

    log.info("=" * 70)
    log.info("CLOUD MINER COMPLETE: %d evaluated.", candidates_evaluated)
    log.info("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Dedicated Cloud Multi-Category Alpha Miner")
    parser.add_argument("--category", choices=["options", "sentiment", "risk_model", "apex"], required=True, help="Category to mine")
    parser.add_argument("--candidates", type=int, default=25, help="Max candidates to simulate")
    parser.add_argument("--timeout-mins", type=int, default=20, help="Max time in minutes")
    args = parser.parse_args()

    asyncio.run(run_cloud_miner(category=args.category, max_candidates=args.candidates, timeout_mins=args.timeout_mins))


if __name__ == "__main__":
    main()
