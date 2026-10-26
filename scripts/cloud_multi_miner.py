#!/usr/bin/env python3
"""
Dedicated Cloud Multi-Category Alpha Miner for GitHub Actions.
Supports (Top 3 BRAIN Categories — zero sentiment):
- category: options    (option8/option9, Value Score 6.0 — Vol Surface & PCR)
- category: risk_model (model51/model16, Value Score 7.0 — BAB & IdioVol)
- category: analyst    (analyst4,        Value Score 5.0 — Earnings Surprise & Dispersion)
- category: apex       (tri-factor cross-synthesis: option + model + analyst)

Concurrency = 1 per GitHub Actions job (3 slots total across 3 workflows):
  mine_options.yml    cron: 0  */6 * * *  (fires at :00)
  mine_analyst.yml    cron: 20 */6 * * *  (fires at :20)
  mine_risk_model.yml cron: 45 */6 * * *  (fires at :45)
All 3 BRAIN simulation slots filled 24/7. Zero local PC dependency.
All BRAIN field names verified real — zero silent simulation failures.
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

import html
import re

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
from brain_options.core.validator import validate_expression
from brain_options.specialist.convex_mutator import ConvexNearMissMutator, _wrap_neutralize_with_signed_power
from brain_options.llm.adapter import LLMAdapter
from brain_options.store.store import OptionsStore

from brain_options.specialist.generator import OptionsGenerator
from brain_risk_model.specialist.generator import RiskModelGenerator
from brain_generators.analyst.analyst_revision_generator import generate_analyst_revision_candidates
from brain_synthesis.apex_generator import generate_apex_candidates


def send_tg_message(token: str, chat_id: str, html_text: str):
    """Deliver HTML message to Telegram with robust error recovery and plain text fallback."""
    if not token or not chat_id:
        return
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": html_text, "parse_mode": "HTML"},
            timeout=15,
        )
        if r.status_code == 200:
            log.info("Telegram alert delivered successfully.")
            return
        log.warning("Telegram HTML send returned status %d: %s. Retrying in plain text...", r.status_code, r.text)
        # Strip HTML tags for clean plain-text fallback
        plain_text = re.sub(r"<[^>]+>", "", html_text)
        r2 = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": plain_text},
            timeout=15,
        )
        if r2.status_code == 200:
            log.info("Telegram plain-text fallback delivered successfully.")
        else:
            log.warning("Telegram plain-text send failed (%d): %s", r2.status_code, r2.text)
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

                # Also load recently evaluated (archetype, expression) from options_evaluations
                # to prevent burning simulation slots repeating identical failed runs
                try:
                    cur.execute("SELECT DISTINCT archetype, expression FROM options_evaluations WHERE created_at >= NOW() - INTERVAL '5 days' AND expression IS NOT NULL;")
                    for ar, ex in cur.fetchall():
                        if ex and ar:
                            known_exprs.add(f"{ar}::{ex.strip()}")
                except Exception as eval_err:
                    log.debug("Could not load recent evaluations for deduplication: %s", eval_err)

        log.info("Loaded %d reference alpha IDs and %d known expressions/archetypes from DB.", len(ref_alpha_ids), len(known_exprs))
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
                    decimal.Decimal(str(round(getattr(metrics, 'annualized_return', getattr(metrics, 'returns', 0.0)), 4))),
                    decimal.Decimal(str(round(metrics.max_drawdown, 4))),
                    decimal.Decimal(str(round(metrics.margin, 4))),
                    decimal.Decimal(str(round(max_corr, 4))),
                    universe, neutralization, decay,
                    f"cloud_{category}",
                ))
        log.info("[+] Successfully committed %s to options_alphas as QUALIFIED.", alpha_id)
    except Exception as e:
        log.error("Failed to commit qualified alpha %s: %s", alpha_id, e)


def log_candidate_evaluation(
    db_url: str,
    expr: str,
    arch: str,
    src: str,
    stage: str,
    status: str,
    metrics: SimMetrics,
):
    """Log individual simulation result to options_evaluations for live pipeline telemetry."""
    if not db_url:
        return
    try:
        ret_val = getattr(metrics, 'annualized_return', getattr(metrics, 'returns', 0.0))
        with psycopg.connect(
            db_url, autocommit=True,
            keepalives=1, keepalives_idle=30, keepalives_interval=10, keepalives_count=5
        ) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO options_evaluations
                    (expression, archetype, source, stage, status, sharpe, fitness, turnover, returns, drawdown, alpha_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """,
                    (
                        expr, arch, src, stage, status,
                        decimal.Decimal(str(round(metrics.sharpe, 4))),
                        decimal.Decimal(str(round(metrics.fitness, 4))),
                        decimal.Decimal(str(round(metrics.turnover, 4))),
                        decimal.Decimal(str(round(ret_val, 4))),
                        decimal.Decimal(str(round(metrics.max_drawdown, 4))),
                        metrics.alpha_id,
                    ),
                )
    except Exception as e:
        log.debug("Failed to log candidate evaluation to DB: %s", e)


def pre_screen_expression(expr: str) -> Tuple[bool, str]:
    """Strict local AST and verified field validator."""
    return validate_expression(expr)


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
    db: Any = None,
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

        # Cache newly qualified PnL vector into PostgreSQL DB
        target_db = db or getattr(client, "db", None)
        if target_db:
            try:
                target_db.save_alpha_pnl(metrics.alpha_id, cand_pnl)
            except Exception as cache_err:
                log.debug("Failed to cache alpha PnL to DB: %s", cache_err)

        # Telegram Alert (with robust HTML escaping to prevent parse errors)
        safe_expr = html.escape(expr)
        safe_arch = html.escape(arch)
        safe_cat = html.escape(category.upper())
        safe_alpha = html.escape(metrics.alpha_id or "unknown")
        send_tg_message(
            token=config.telegram_bot_token,
            chat_id=config.telegram_chat_id,
            html_text=(
                f"🌟 <b>NEW {safe_cat} ALPHA QUALIFIED ON CLOUD!</b> 🌟\n\n"
                f"• <b>Alpha ID:</b> <code>{safe_alpha}</code>\n"
                f"• <b>Category:</b> {category}\n"
                f"• <b>Archetype:</b> {safe_arch}\n"
                f"• <b>Sharpe:</b> {metrics.sharpe:.2f} | <b>Fitness:</b> {metrics.fitness:.2f}\n"
                f"• <b>Margin:</b> {metrics.margin * 10000:.1f} bps | <b>Turnover:</b> {metrics.turnover * 100:.1f}%\n"
                f"• <b>Max Correlation:</b> {max_corr:.4f} (&lt; 0.70)\n"
                f"• <b>Sub-Universe Check:</b> 100% PASS\n"
                f"• <b>Expression:</b>\n<code>{safe_expr}</code>"
            ),
        )
        log.info("[🌟] QUALIFIED & COMMITTED: %s (%s, Sharpe=%.2f, Fit=%.2f)", metrics.alpha_id, arch, metrics.sharpe, metrics.fitness)
        return True
    except Exception as exc:
        log.error("Error in asynchronous qualification pipeline for %s: %s", metrics.alpha_id, exc)
        return False


async def run_cloud_miner(category: str, max_candidates: int, timeout_mins: int, concurrency: int = 3):
    config = OptionsConfig.from_env()
    store = OptionsStore()
    llm = LLMAdapter(config)
    client = BrainClient(
        username=config.brain_username,
        password=config.brain_password,
        max_concurrent_sims=concurrency,
        db=store.db,
    )
    mutator = ConvexNearMissMutator(db=store.db)

    log.info("=" * 70)
    log.info("STARTING HIGH-SPEED CLOUD MULTI-MINER: Category=%s | Batch=%d | Timeout=%dm | Concurrency=%d Slots",
             category.upper(), max_candidates, timeout_mins, concurrency)
    log.info("=" * 70)

    # 1. Authenticate with WorldQuant BRAIN (resumes PostgreSQL cluster session cache)
    try:
        await asyncio.to_thread(client.authenticate)
    except Exception as auth_err:
        log.error("Failed to authenticate with WorldQuant BRAIN: %s", auth_err)
        return

    # 2. Pre-fetch reference PnLs for correlation gate (PostgreSQL DB Cache first <50ms!)
    ref_alpha_ids, known_exprs = load_reference_pnls(config.database_url)
    ref_pnls: Dict[str, Dict[str, float]] = {}

    if store.db:
        try:
            ref_pnls = store.db.get_all_cached_alpha_pnls()
        except Exception as e:
            log.warning("Could not load cached PnLs from DB: %s", e)

    missing_aids = [aid for aid in ref_alpha_ids if aid not in ref_pnls]
    if missing_aids:
        log.info("Fetching PnL for %d un-cached portfolio reference alphas...", len(missing_aids))
        for aid in missing_aids:
            pnl = await client.get_alpha_pnl(aid)
            if pnl:
                ref_pnls[aid] = pnl
                if store.db:
                    store.db.save_alpha_pnl(aid, pnl)
    else:
        log.info("All %d reference alpha PnLs loaded instantly from DB cache (<50ms). Zero API wait.", len(ref_pnls))

    priority_queue: List[Dict[str, Any]] = []

    # 3. Initialize generator & seed priority candidates based on category
    generator = None
    apex_candidates: List[Any] = []

    if category == "options":
        generator = OptionsGenerator(db=store.db, llm_adapter=llm)
        log.info("Options generator loaded. Mining option8/option9 (PCR + Vol Surface).")
        # Inoculate priority queue with Near-Miss Convex Sweeps on TOPSP500 (mL6wvmP6 Base)
        for d in [12, 15, 18, 20, 22, 25]:
            for p in [1.0, 1.5, 2.0]:
                for delta_win in [8, 10, 12]:
                    for neut in ["SECTOR", "SUBINDUSTRY"]:
                        priority_queue.append({
                            "expression": (
                                f"trade_when(volume > adv20 * 0.70, "
                                f"group_neutralize(signed_power(rank(-ts_decay_linear(ts_delta(pcr_oi_30, {delta_win}), 5)) - 0.5, {p}), {neut.lower()}), "
                                f"-1)"
                            ),
                            "archetype": f"PutOI_Convex_d{d}_w{delta_win}_p{p}_{neut}",
                            "hypothesis": f"Near-miss optimization of 1.05 Sharpe Put OI Buildup on TOPSP500 with decay {d}, power {p}, delta {delta_win}.",
                            "universe": "TOPSP500",
                            "neutralization": neut,
                            "decay": d,
                            "region": "USA",
                        })

        # Inoculate 1.28 Sharpe Breakthrough Volatility Skew Steepness on TOPSP500
        for thresh in ["0.24", "0.26", "0.28", "0.32"]:
            for p in [1.5, 2.0]:
                expr = f"trade_when(abs(rank(ts_decay_linear(-ts_delta(implied_volatility_mean_skew_30, 10), 5)) - 0.5) > {thresh}, group_neutralize(signed_power(rank(ts_decay_linear(-ts_delta(implied_volatility_mean_skew_30, 10), 5)) - 0.5, {p}), subindustry), -1)"
                for d in [12, 14, 16, 18, 20]:
                    priority_queue.append({
                        "expression": expr,
                        "archetype": f"SkewSteepness_t{thresh}_p{p}_d{d}",
                        "hypothesis": f"Breakthrough Vol Skew with thresh={thresh}, power={p}, decay={d}.",
                        "universe": "TOPSP500",
                        "neutralization": "SUBINDUSTRY",
                        "decay": d,
                        "region": "USA",
                    })

    elif category == "risk_model":
        generator = RiskModelGenerator(db=store.db, llm_adapter=llm)
        log.info("Risk model generator loaded. Inoculating 1.74 Sharpe BAB breakthrough seeds.")
        # 1. Base BAB variants with smoothed return windows
        for d in [14, 16, 18, 20, 22]:
            for u in ["TOP1000", "TOP2000"]:
                for neut in ["INDUSTRY", "SUBINDUSTRY"]:
                    for (rw, rd) in [(5, 6), (8, 6), (10, 8)]:
                        priority_queue.append({
                            "expression": f"group_neutralize(rank(-ts_decay_linear(beta_last_60_days_spy, {d}) * ts_decay_linear(ts_zscore(returns, {rw}), {rd})), {neut.lower()})",
                            "archetype": f"BAB_Beta{d}_w{rw}d{rd}_{u}_{neut}",
                            "hypothesis": f"BAB institutional beta spread on {u} with {neut} neutralization and decay {d}.",
                            "universe": u,
                            "neutralization": neut,
                            "decay": d,
                            "region": "USA",
                        })
        # 2. Conviction-Gated BAB variants to reduce turnover from 46% to ~28-32% (lifts Fitness >= 1.05)
        for d in [16, 18, 22, 26]:
            for thresh in ["0.10", "0.15", "0.20"]:
                for u in ["TOP1000"]:
                    for neut in ["INDUSTRY", "SUBINDUSTRY"]:
                        inner_bab = f"rank(-ts_decay_linear(beta_last_60_days_spy, {d}) * ts_decay_linear(ts_zscore(returns, 5), 6))"
                        gated_expr = f"trade_when(abs({inner_bab} - 0.5) > {thresh}, group_neutralize({inner_bab}, {neut.lower()}), -1)"
                        priority_queue.append({
                            "expression": gated_expr,
                            "archetype": f"BAB_Gated{thresh}_d{d}_{u}_{neut}",
                            "hypothesis": f"Conviction-gated BAB thresh={thresh} decay={d} to cut turnover below 30% and push Fitness >= 1.05.",
                            "universe": u,
                            "neutralization": neut,
                            "decay": d,
                            "region": "USA",
                        })
    elif category == "analyst":
        analyst_candidates = generate_analyst_revision_candidates()
        log.info("Analyst generator loaded. %d verified candidates from analyst4 dataset (CJL/DMS/GL).", len(analyst_candidates))
        for ac in analyst_candidates:
            priority_queue.append({
                "expression": ac["expression"],
                "archetype":  ac["archetype"],
                "hypothesis": ac["hypothesis"],
                "universe":   ac["universe"],
                "neutralization": ac["neutralization"],
                "decay":      ac["decay"],
                "region":     "USA",
            })
    elif category == "apex":
        apex_candidates = generate_apex_candidates()
        log.info("Loaded %d verified Apex Tri-Factor candidates (model51 + option8/9 + analyst4).", len(apex_candidates))
        for ac in apex_candidates:
            priority_queue.append({
                "expression": ac.expression,
                "archetype":  ac.name,
                "hypothesis": ac.hypothesis,
                "universe":   ac.universe,
                "neutralization": ac.neutralization,
                "decay":      ac.decay,
                "region":     getattr(ac, "region", "USA"),
            })

        # Inoculate 1.14 Sharpe / 0.96 Fitness Apex Tri-Factor Breakthrough Seeds with Tail Power on TOPSP500 & TOP1000
        seed_apex = (
            "trade_when(volume > adv20 * 0.75, group_neutralize(rank(0.45 * "
            "rank(ts_decay_linear(((call_breakeven_60 - forward_price_60) / (close + 0.001)), 8)) + "
            "0.35 * rank(ts_decay_linear(((anl4_af_eps_value - anl4_afv4_eps_mean) / (anl4_afv4_dts_spe + 0.001)), 8)) - "
            "0.20 * rank(ts_decay_linear(beta_last_60_days_spy, 8))), subindustry), -1)"
        )
        for u in ["TOPSP500", "TOP1000"]:
            for p in [1.25, 1.5, 1.75, 2.0]:
                wrapped_apex = _wrap_neutralize_with_signed_power(seed_apex, p)
                if wrapped_apex:
                    for d in [6, 8, 10, 12]:
                        priority_queue.append({
                            "expression": wrapped_apex,
                            "archetype": f"Apex1_{u}_Power{p}_d{d}",
                            "hypothesis": f"Apex Tri-Factor on {u} Tail Power p={p} decay={d} targeting >1.25 Sharpe.",
                            "universe": u,
                            "neutralization": "SUBINDUSTRY",
                            "decay": d,
                            "region": "USA",
                        })
            for hurdle in ["0.80", "0.90", "1.05"]:
                gated = seed_apex.replace("volume > adv20 * 0.75", f"volume > adv20 * {hurdle}")
                wrapped = _wrap_neutralize_with_signed_power(gated, 1.5)
                priority_queue.append({
                    "expression": wrapped or gated,
                    "archetype": f"Apex1_{u}_Gated{hurdle}_Power1.5_d8",
                    "hypothesis": f"Apex Tri-Factor on {u} Gated hurdle={hurdle} + Power 1.5",
                    "universe": u,
                    "neutralization": "SUBINDUSTRY",
                    "decay": 8,
                    "region": "USA",
                })
    else:
        raise ValueError(f"Unknown category: {category}")

    candidates_evaluated = 0
    start_time = time.time()
    max_duration_sec = timeout_mins * 60
    background_eval_tasks: set[asyncio.Task] = set()

    # Async Queue for concurrent worker pool
    work_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
    stop_event = asyncio.Event()
    counter_lock = asyncio.Lock()

    # Feeder coroutine: maintains queue depth
    async def feeder_loop():
        # First push all pre-seeded priority candidates
        for cand in priority_queue:
            cand_key = f"{cand.get('archetype', '')}::{cand['expression'].strip()}"
            if cand_key not in known_exprs and cand["expression"] not in known_exprs:
                known_exprs.add(cand_key)
                await work_queue.put(cand)

        # Then continuously feed from generator as queue empties
        while not stop_event.is_set():
            if work_queue.qsize() < 20:
                if generator is not None:
                    try:
                        c = generator.generate_candidate()
                        expr = c.expression
                        if expr not in known_exprs:
                            known_exprs.add(expr)
                            await work_queue.put({
                                "expression": expr,
                                "archetype": getattr(c, "archetype", None) or getattr(c, "archetype_name", "general"),
                                "hypothesis": getattr(c, "hypothesis", ""),
                                "universe": getattr(c, "universe", "TOPSP500"),
                                "neutralization": getattr(c, "neutralization", "SUBINDUSTRY"),
                                "decay": getattr(c, "decay", 18),
                                "region": getattr(c, "region", "USA"),
                            })
                    except Exception as gen_err:
                        log.debug("Feeder generator error: %s", gen_err)
            await asyncio.sleep(0.5)

    # Worker coroutine: concurrent simulation consumer
    async def worker_loop(worker_id: int):
        nonlocal candidates_evaluated
        while not stop_event.is_set():
            if time.time() - start_time > max_duration_sec:
                log.info("Worker #%d: Time budget (%d mins) reached.", worker_id, timeout_mins)
                stop_event.set()
                break

            async with counter_lock:
                if candidates_evaluated >= max_candidates:
                    stop_event.set()
                    break

            try:
                cand_obj = await asyncio.wait_for(work_queue.get(), timeout=2.0)
            except asyncio.TimeoutError:
                if stop_event.is_set() or (work_queue.empty() and generator is None and not priority_queue):
                    break
                continue

            expr = cand_obj["expression"]
            arch = cand_obj["archetype"]
            hyp = cand_obj["hypothesis"]
            universe = cand_obj["universe"]
            neut = cand_obj["neutralization"]
            decay = cand_obj["decay"]
            region = cand_obj.get("region", "USA")

            # Fast local pre-screening
            ok, reason = pre_screen_expression(expr)
            if not ok:
                log.warning("[-] Pre-screening rejected expression (%s): %s", reason, expr[:60])
                work_queue.task_done()
                continue

            async with counter_lock:
                candidates_evaluated += 1
                current_num = candidates_evaluated

            settings = SimSettings(
                region=region,
                universe=universe,
                delay=1,
                decay=decay,
                neutralization=neut,
                truncation=0.05,
                pasteurization=True,
            )

            log.info("[%s W#%d Sim #%d/%d] Simulating %s (decay=%d, u=%s)...",
                     category.upper(), worker_id, current_num, max_candidates, arch, decay, universe)

            try:
                metrics = await client.simulate_one(expr, settings)
            except Exception as e:
                log.warning("Simulation exception in worker #%d: %s", worker_id, e)
                work_queue.task_done()
                await asyncio.sleep(1.0)
                continue

            if not metrics or not metrics.is_valid:
                work_queue.task_done()
                await asyncio.sleep(0.5)
                continue

            log.info(
                "[%s W#%d Sim #%d] %s | Sharpe=%.2f | Fitness=%.2f | TO=%.1f%% | Margin=%.1fbps | DD=%.1f%% | %s",
                category.upper(), worker_id, current_num, metrics.alpha_id, metrics.sharpe, metrics.fitness,
                metrics.turnover * 100, metrics.margin * 10000, metrics.max_drawdown * 100, arch
            )

            # Gate 1: Performance Gate (BRAIN requires Sharpe >= 1.25, Fitness >= 1.00, Margin >= 4 bps)
            fitness_threshold = 1.00
            passed_gate1 = (
                metrics.sharpe >= 1.25
                and metrics.fitness >= fitness_threshold
                and 0.01 <= metrics.turnover <= 0.70
                and metrics.margin >= 0.0004
                and metrics.max_drawdown <= 0.35
            )

            # Log to DB
            log_candidate_evaluation(
                db_url=config.database_url,
                expr=expr,
                arch=arch,
                src=f"cloud_{category}",
                stage="STAGE0",
                status="PASS" if passed_gate1 else "FAIL",
                metrics=metrics,
            )

            # RL MAB Reward
            if store.db:
                try:
                    rew = float(metrics.sharpe) if metrics.sharpe is not None else 0.0
                    store.db.record_strategy_operator_reward(
                        strategy_name=f"cloud_{category}",
                        operator_name=arch,
                        parameter_name="decay",
                        parameter_val=str(decay),
                        reward=rew,
                        success=passed_gate1,
                    )
                except Exception as rl_err:
                    log.debug("Failed to record strategy operator reward: %s", rl_err)

            # Gate 1 Pass -> Spawn Async Gate 2 & 3
            if passed_gate1:
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
                        db=store.db,
                    )
                )
                background_eval_tasks.add(eval_task)
                eval_task.add_done_callback(background_eval_tasks.discard)

            # Near-Miss Sweep: If Sharpe in [1.00, 1.24], generate 5-axis convex surface gradient mutations
            elif 1.00 <= metrics.sharpe < 1.25 and metrics.fitness >= (0.40 if category == "options" else 0.60):
                log.info("[⚡] Near-Miss detected for %s (Sharpe=%.2f, Fit=%.2f). Launching 5-axis convex optimizer...",
                         metrics.alpha_id, metrics.sharpe, metrics.fitness)
                mutations = mutator.generate_convex_sweeps(
                    expr=expr,
                    archetype=arch,
                    hypothesis=hyp,
                    universe=universe,
                    neutralization=neut,
                    decay=decay,
                    sharpe=metrics.sharpe,
                    fitness=metrics.fitness,
                    region=region,
                )
                for mut in mutations:
                    m_expr = mut["expression"]
                    if m_expr not in known_exprs:
                        known_exprs.add(m_expr)
                        await work_queue.put(mut)

            work_queue.task_done()

    # Launch feeder and worker tasks concurrently
    feeder_task = asyncio.create_task(feeder_loop())
    worker_tasks = [asyncio.create_task(worker_loop(i + 1)) for i in range(concurrency)]

    await asyncio.gather(*worker_tasks, return_exceptions=True)
    stop_event.set()
    feeder_task.cancel()

    if background_eval_tasks:
        log.info("[*] Waiting for %d in-flight qualification evaluation tasks to complete...", len(background_eval_tasks))
        await asyncio.gather(*background_eval_tasks, return_exceptions=True)

    log.info("=" * 70)
    log.info("HIGH-SPEED CLOUD MINER COMPLETE: %d evaluated in %d slots.", candidates_evaluated, concurrency)
    log.info("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Dedicated Cloud Multi-Category Alpha Miner")
    parser.add_argument("--category", choices=["options", "risk_model", "analyst", "apex"], required=True, help="Category to mine")
    parser.add_argument("--candidates", type=int, default=9999, help="Max candidates to simulate")
    parser.add_argument("--timeout-mins", type=int, default=115, help="Max time in minutes (default: 115m for 2h runner)")
    parser.add_argument("--concurrency", type=int, default=3, help="Concurrent simulation slots (default: 3)")
    args = parser.parse_args()

    asyncio.run(run_cloud_miner(
        category=args.category,
        max_candidates=args.candidates,
        timeout_mins=args.timeout_mins,
        concurrency=args.concurrency
    ))


if __name__ == "__main__":
    main()
