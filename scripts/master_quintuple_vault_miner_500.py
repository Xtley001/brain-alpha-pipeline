#!/usr/bin/env python3
"""
Master Quintuple-Vault Autonomous Multi-Dataset Alpha Miner & Qualifier (500 Quota).
Deploys across 5 Orthogonal Institutional Pillars:
  - Vault 1: Options Volatility Surface & Convexity (100 Target)
  - Vault 2: Sentiment, PEAD & Revision Dynamics (100 Target)
  - Vault 3: Systematic Factor & Risk Models (100 Target)
  - Vault 4: Short Interest & Securities Lending Dynamics (100 Target)
  - Vault 5: Fundamental Quality, Profitability & Capital Discipline (100 Target)

Safety & Governance:
  - 100% Zero Auto-Submissions to BRAIN (Banked to PostgreSQL options_alphas as QUALIFIED)
  - Pairwise correlation |rho| <= 0.62 vs all 23 submitted production baselines
  - Platform /check 100% PASS requirement
  - Auto-reauthenticating session recovery with cluster caching
"""
from __future__ import annotations

import asyncio
import datetime
import decimal
import html
import logging
import math
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional, Set, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.makedirs("logs", exist_ok=True)

try:
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
except Exception:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/omni_vault_miner.log", mode="a", encoding="utf-8"),
    ],
)
log = logging.getLogger("quintuple_vault_miner")

import psycopg
import requests
from dotenv import load_dotenv

load_dotenv()

from brain_options.config import OptionsConfig
from brain_options.core.client import BrainClient, SimMetrics, SimSettings
from brain_options.core.correlation import compute_correlation
from brain_options.store.store import OptionsStore

# ── Legacy skeleton generators (kept for backward compat) ──────────────────
from brain_generators.options.smirk_surface import generate_options_vault_candidates
from brain_generators.sentiment.pead_revision import generate_sentiment_vault_candidates
from brain_generators.risk_models.betting_against_beta import generate_risk_model_vault_candidates
from brain_generators.short_interest.lending_dynamics import generate_short_interest_vault_candidates
from brain_generators.fundamental.quality_profitability import generate_fundamental_vault_candidates

# ── P0/P1/P2: Paper-faithful generators (90 research materials — full extraction) ──
# Options
from brain_generators.options.xing_zhang_zhao_smirk import generate_xing_zhang_zhao_smirk_candidates
from brain_generators.options.pan_poteshman_pcr_informed import generate_pan_poteshman_pcr_candidates
from brain_generators.options.carr_wu_vrp import generate_options_vrp_surface_candidates
from brain_generators.options.bali_hovakimian_vol_spread import generate_bali_hovakimian_vol_spread_candidates
from brain_generators.options.garleanu_pedersen_demand import generate_garleanu_pedersen_demand_candidates
from brain_generators.options.bakshi_kapadia_madan_skew import generate_bakshi_kapadia_madan_skew_candidates
from brain_generators.options.ni_pearson_pinning import generate_ni_pearson_pinning_candidates
from brain_generators.options.bollerslev_vrp_dynamics import generate_bollerslev_vrp_dynamics_candidates
from brain_generators.options.institutional_surface_treatise import generate_institutional_surface_treatise_candidates
# Sentiment
from brain_generators.sentiment.bernard_thomas_sue import generate_bernard_thomas_sue_candidates
from brain_generators.sentiment.gleason_lee_revision_speed import generate_sentiment_p1_candidates
from brain_generators.sentiment.tetlock_media_pessimism import generate_sentiment_p2_candidates
# Risk Models
from brain_generators.risk_models.frazzini_pedersen_bab_exact import generate_frazzini_pedersen_bab_candidates
from brain_generators.risk_models.ang_idiovol_anomaly import generate_risk_model_p1_candidates
from brain_generators.risk_models.risk_model_p2_vpin_fomc import generate_risk_model_p2_candidates
from brain_generators.risk_models.an_ang_bali_bbw_anomaly import generate_an_ang_bali_bbw_candidates
# Short Interest + Insider
from brain_generators.short_interest.short_interest_p0_combined import generate_short_interest_p0_candidates
from brain_generators.short_interest.short_interest_p1_insider import generate_short_interest_p1_candidates
# Fundamental + Innovation
from brain_generators.fundamental.fundamental_p0_combined import generate_fundamental_p0_candidates
from brain_generators.fundamental.fundamental_p1_innovation import generate_fundamental_p1_candidates
from brain_generators.fundamental.kakushadze_101_direct import generate_kakushadze_framework_candidates
# Supply Chain
from brain_generators.supply_chain.menzly_ozbas_lead_lag import generate_supply_chain_p0_candidates
from brain_generators.supply_chain.production_network_p1_shocks import generate_production_network_p1_candidates


def send_tg_message(token: str, chat_id: str, html_text: str):
    if not token or not chat_id:
        return
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": html_text, "parse_mode": "HTML"},
            timeout=10,
        )
        if r.status_code == 200:
            log.info("Telegram notification sent.")
            return
        plain_text = re.sub(r"<[^>]+>", "", html_text)
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": plain_text},
            timeout=10,
        )
    except Exception as exc:
        log.warning("Telegram notification failed: %s", exc)


def load_reference_alphas(db_url: str) -> Tuple[List[str], Dict[str, Dict[str, Any]]]:
    """Loads all submitted production alphas and reserve qualified alphas."""
    prod_alphas: List[str] = []
    reserve_meta: Dict[str, Dict[str, Any]] = {}

    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT alpha_id FROM options_alphas WHERE status = 'SUBMITTED' AND alpha_id IS NOT NULL"
                )
                for r in cur.fetchall():
                    if r[0] and r[0] not in prod_alphas:
                        prod_alphas.append(r[0])

                cur.execute(
                    "SELECT alpha_id, COALESCE(sharpe, 0.0), COALESCE(fitness, 0.0), COALESCE(margin, 0.0) "
                    "FROM options_alphas WHERE status = 'QUALIFIED' AND alpha_id IS NOT NULL"
                )
                for r in cur.fetchall():
                    aid = r[0]
                    if aid and aid not in prod_alphas:
                        reserve_meta[aid] = {
                            "sharpe": float(r[1]),
                            "fitness": float(r[2]),
                            "margin": float(r[3]),
                        }
    except Exception as exc:
        log.warning("Could not fetch reference alpha IDs from DB: %s", exc)

    hardcoded = [
        "rKOa6qa9", "YPboG01w", "XgbOoJjx", "e7bWxz7E", "ZYbNORZx", "mLmQjlzE",
        "P02K7eYK", "Xgbv1A80", "levEYpmx", "YPb81N2v", "E5pNpQlm", "N176Geqp",
        "gJQWL7aK", "Grdg2Njo", "xA3872wq", "3qXLMqg0", "0mX0kG86", "RRbnn8xe",
        "blbZ9Wkp", "KPNd6Ovl", "gJbAP76e"
    ]
    for h in hardcoded:
        if h not in prod_alphas:
            prod_alphas.append(h)

    return prod_alphas, reserve_meta


async def verify_checklist_passes(session: Any, alpha_id: str) -> Tuple[bool, str]:
    """Verifies 100% PASS on platform /check with backoff."""
    chk_url = f"https://api.worldquantbrain.com/alphas/{alpha_id}/check"
    for attempt in range(15):
        try:
            if hasattr(session, "retry"):
                resp = await asyncio.wait_for(session.retry("GET", chk_url, max_tries=5), timeout=25.0)
            else:
                resp = session.get(chk_url, timeout=15)
        except Exception:
            await asyncio.sleep(2.0)
            continue

        if resp is not None and resp.status_code == 200:
            text = resp.text.strip() if hasattr(resp, "text") and resp.text else ""
            if not text:
                await asyncio.sleep(2.0)
                continue
            try:
                data = resp.json()
            except Exception:
                await asyncio.sleep(2.0)
                continue

            is_data = data.get("is", {}) if isinstance(data.get("is"), dict) else {}
            checks = is_data.get("checks", []) or data.get("checks", [])
            if checks:
                failures = []
                for c in checks:
                    res = c.get("result", "")
                    name = c.get("name", "Unknown")
                    val = c.get("value", "")
                    lim = c.get("limit", "")
                    if res in ("FAIL", "ERROR"):
                        failures.append(f"{name} ({val} vs {lim})")
                if failures:
                    return False, f"Checklist FAIL: {', '.join(failures)}"
                return True, "Checklist 100% PASS"
        await asyncio.sleep(3.0)
    return False, "Checklist timed out"


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
    strategy_name: str,
):
    try:
        ret_val = getattr(metrics, "annualized_return", getattr(metrics, "returns", 0.0))
        with psycopg.connect(db_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM options_alphas WHERE alpha_id = %s AND status = 'QUALIFIED'",
                    (alpha_id,)
                )
                if cur.fetchone():
                    log.info("[!] Alpha %s already exists in options_alphas.", alpha_id)
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
                    );
                """
                cur.execute(
                    sql,
                    (
                        alpha_id, expression, archetype, hypothesis, strategy_name,
                        decimal.Decimal(str(round(metrics.sharpe, 4))),
                        decimal.Decimal(str(round(metrics.fitness, 4))),
                        decimal.Decimal(str(round(metrics.turnover, 4))),
                        decimal.Decimal(str(round(ret_val, 4))),
                        decimal.Decimal(str(round(metrics.max_drawdown, 4))),
                        decimal.Decimal(str(round(metrics.margin, 4))),
                        decimal.Decimal(str(round(max_corr, 4))),
                        universe, neutralization, decay,
                        strategy_name,
                    ),
                )
        log.info("🎉 [VAULT COMMIT] Stored %s as QUALIFIED in options_alphas (Sharpe=%.2f, Margin=%.1fbps, rho=%.2f, Strategy=%s).",
                 alpha_id, metrics.sharpe, metrics.margin * 10000, max_corr, strategy_name)
    except Exception as e:
        log.error("Failed to commit alpha %s: %s", alpha_id, e)


def commit_collision_challenger(
    db_url: str,
    alpha_id: str,
    expression: str,
    archetype: str,
    incumbent_id: str,
    metrics: SimMetrics,
    max_corr: float,
    universe: str,
    neutralization: str,
    decay: int,
    strategy_name: str,
):
    try:
        ret_val = getattr(metrics, "annualized_return", getattr(metrics, "returns", 0.0))
        with psycopg.connect(db_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                sql = """
                    INSERT INTO options_alphas (
                        alpha_id, expression, archetype, hypothesis, source,
                        sharpe, fitness, turnover, returns, drawdown, margin,
                        max_correlation, universe, neutralization, delay, decay,
                        truncation, pasteurization, nan_handling, status,
                        created_at, strategy_name, incumbent_id
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, 1, %s,
                        0.05, 'ON', 'OFF', 'REJECTED_COLLISION',
                        NOW(), %s, %s
                    );
                """
                cur.execute(
                    sql,
                    (
                        alpha_id, expression, archetype, "Collision Challenger", strategy_name,
                        decimal.Decimal(str(round(metrics.sharpe, 4))),
                        decimal.Decimal(str(round(metrics.fitness, 4))),
                        decimal.Decimal(str(round(metrics.turnover, 4))),
                        decimal.Decimal(str(round(ret_val, 4))),
                        decimal.Decimal(str(round(metrics.max_drawdown, 4))),
                        decimal.Decimal(str(round(metrics.margin, 4))),
                        decimal.Decimal(str(round(max_corr, 4))),
                        universe, neutralization, decay,
                        strategy_name, incumbent_id,
                    ),
                )
    except Exception:
        pass


def get_current_qualified_count(db_url: str) -> int:
    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM options_alphas WHERE status = 'QUALIFIED';")
                return cur.fetchone()[0]
    except Exception:
        return 0


def build_quintuple_vault_matrix() -> List[Dict[str, Any]]:
    """
    FULL 90-paper extraction vault. All 14 paper-faithful generator modules.
    Pillars:
      Options:        XZZ Smirk | PCR Informed | Carr-Wu VRP | legacy
      Sentiment:      SUE/PEAD | Revisions | Media/Attention | legacy
      Risk Models:    BAB | AHXZ Idiovol | VPIN/FOMC | legacy
      Short Interest: CDM/ERR/APR | Insider/Lending | legacy
      Fundamental:    GPA/F-Score/AG | Innovation | Kakushadze 101 | legacy
      Supply Chain:   Menzly-Ozbas | Barrot
    """
    # ── Legacy skeletons (backward compat) ─────────────────────────────────
    options_legacy    = generate_options_vault_candidates()
    sentiment_legacy  = generate_sentiment_vault_candidates()
    risk_legacy       = generate_risk_model_vault_candidates()
    short_legacy      = generate_short_interest_vault_candidates()
    fund_legacy       = generate_fundamental_vault_candidates()

    # ── Options pillar (3 modules) ──────────────────────────────────────────
    options_xzz  = generate_xing_zhang_zhao_smirk_candidates()
    options_pcr  = generate_pan_poteshman_pcr_candidates()
    options_vrp  = generate_options_vrp_surface_candidates()
    options_bali = generate_bali_hovakimian_vol_spread_candidates()
    options_gpp  = generate_garleanu_pedersen_demand_candidates()
    options_bkm  = generate_bakshi_kapadia_madan_skew_candidates()
    options_npp  = generate_ni_pearson_pinning_candidates()
    options_btz  = generate_bollerslev_vrp_dynamics_candidates()
    options_treatise = generate_institutional_surface_treatise_candidates()

    # ── Sentiment pillar (3 modules) ────────────────────────────────────────
    sentiment_sue  = generate_bernard_thomas_sue_candidates()
    sentiment_rev  = generate_sentiment_p1_candidates()
    sentiment_med  = generate_sentiment_p2_candidates()

    # ── Risk model pillar (4 modules) ───────────────────────────────────────
    risk_bab    = generate_frazzini_pedersen_bab_candidates()
    risk_ivol   = generate_risk_model_p1_candidates()
    risk_vpin   = generate_risk_model_p2_candidates()
    risk_aabc   = generate_an_ang_bali_bbw_candidates()

    # ── Short interest + insider pillar (2 modules) ─────────────────────────
    short_p0    = generate_short_interest_p0_candidates()
    short_p1    = generate_short_interest_p1_candidates()

    # ── Fundamental + Innovation + Supply Chain (4 modules) ─────────────────
    fund_p0     = generate_fundamental_p0_candidates()
    fund_p1     = generate_fundamental_p1_candidates()
    fund_kak    = generate_kakushadze_framework_candidates()
    sc_p0       = generate_supply_chain_p0_candidates()
    sc_p1       = generate_production_network_p1_candidates()

    # ── Merge per pillar ────────────────────────────────────────────────────
    options_cands   = options_xzz + options_pcr + options_vrp + options_bali + options_gpp + options_bkm + options_npp + options_btz + options_treatise + options_legacy
    sentiment_cands = sentiment_sue + sentiment_rev + sentiment_med + sentiment_legacy
    risk_cands      = risk_bab + risk_ivol + risk_vpin + risk_aabc + risk_legacy
    short_cands     = short_p0 + short_p1 + short_legacy
    fund_cands      = fund_p0 + fund_p1 + fund_kak + sc_p0 + sc_p1 + fund_legacy

    total = len(options_cands)+len(sentiment_cands)+len(risk_cands)+len(short_cands)+len(fund_cands)
    log.info(
        "FULL 90-PAPER VAULT — Opt=%d | Sent=%d | Risk=%d | SI=%d | Fund+SC=%d | TOTAL=%d",
        len(options_cands), len(sentiment_cands), len(risk_cands),
        len(short_cands), len(fund_cands), total
    )

    # Interleave round-robin across all 5 verticals for balanced slot usage
    interleaved: List[Dict[str, Any]] = []
    max_len = max(len(options_cands), len(sentiment_cands), len(risk_cands), len(short_cands), len(fund_cands))
    for i in range(max_len):
        if i < len(options_cands):
            interleaved.append(options_cands[i])
        if i < len(sentiment_cands):
            interleaved.append(sentiment_cands[i])
        if i < len(risk_cands):
            interleaved.append(risk_cands[i])
        if i < len(short_cands):
            interleaved.append(short_cands[i])
        if i < len(fund_cands):
            interleaved.append(fund_cands[i])

    return interleaved


async def run_quintuple_vault_miner():
    config = OptionsConfig.from_env()
    store = OptionsStore()

    client = BrainClient(
        username=config.brain_username,
        password=config.brain_password,
        max_concurrent_sims=4,
        db=store.db,
    )

    log.info("=" * 80)
    log.info("MASTER QUINTUPLE-VAULT AUTONOMOUS ALPHA MINER LAUNCHED")
    log.info("TARGET: 500 QUALIFIED ALPHAS (100 per dataset vertical)")
    log.info("PILLARS: Options | Sentiment | Risk Models | Short Interest | Fundamentals")
    log.info("PARALLEL WORKERS: 4 Simulation Slots with Session Auto-Recovery")
    log.info("=" * 80)

    auth_success = False
    for attempt in range(20):
        try:
            await asyncio.to_thread(client.authenticate)
            auth_success = True
            log.info("Successfully authenticated with WorldQuant BRAIN.")
            break
        except Exception as auth_err:
            log.warning("[WIFI-BACKOFF] Authentication attempt %d failed: %s. Retrying in 10s...", attempt + 1, auth_err)
            await asyncio.sleep(10.0)

    if not auth_success:
        log.error("Fatal: Could not authenticate after 20 attempts.")
        return

    prod_alpha_ids, reserve_meta = load_reference_alphas(config.database_url)
    ref_pnls: Dict[str, Dict[str, float]] = {}
    all_refs = list(prod_alpha_ids) + list(reserve_meta.keys())
    log.info("Pre-fetching PnL vectors for %d reference alphas...", len(all_refs))

    for aid in all_refs:
        try:
            pnl = await client.get_alpha_pnl(aid)
            if pnl:
                ref_pnls[aid] = pnl
        except Exception:
            pass
    log.info("Loaded %d reference PnL vectors into correlation firewall.", len(ref_pnls))

    candidates = build_quintuple_vault_matrix()
    target_count = 500
    current_qualified = get_current_qualified_count(config.database_url)
    log.info("Enqueued %d candidates across all 5 vaults. Current Qualified: %d / %d",
             len(candidates), current_qualified, target_count)

    queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
    for c in candidates:
        queue.put_nowait(c)

    lock = asyncio.Lock()
    eval_count = 0
    PROD_FIREWALL = 0.62

    async def worker(worker_id: int):
        nonlocal eval_count, current_qualified

        while not queue.empty() and current_qualified < target_count:
            cand = await queue.get()
            expr = cand["expression"]
            arch = cand["archetype"]
            hyp = cand["hypothesis"]
            universe = cand["universe"]
            neut = cand["neutralization"]
            decay = cand["decay"]
            cat = cand.get("category", "options")
            strategy_name = f"vault_{cat}"

            async with lock:
                eval_count += 1
                curr_eval = eval_count
                curr_qual = current_qualified

            log.info("[Worker %d | #%d | Qual: %d/%d] Simulating %s (cat=%s, u=%s, neut=%s, d=%d)...",
                     worker_id, curr_eval, curr_qual, target_count, arch, cat, universe, neut, decay)

            settings = SimSettings(
                region="USA",
                universe=universe,
                delay=1,
                decay=decay,
                neutralization=neut,
                truncation=0.05,
                pasteurization=True,
            )

            metrics = None
            for net_attempt in range(5):
                try:
                    metrics = await client.simulate_one(expr, settings)
                    if metrics is not None:
                        break
                except Exception as net_err:
                    log.warning("[Worker %d | WIFI-RETRY %d] Network error: %s. Sleeping 5s...",
                                worker_id, net_attempt + 1, net_err)
                    await asyncio.sleep(5.0)

            if metrics is None:
                log.warning("[Worker %d] Simulation returned None for %s; skipping.", worker_id, arch)
                queue.task_done()
                continue

            log.info("[Worker %d] %s | Sharpe=%.2f | Fit=%.2f | TO=%.1f%% | Margin=%.1fbps | DD=%.1f%% | %s",
                     worker_id, metrics.alpha_id, metrics.sharpe, metrics.fitness,
                     metrics.turnover * 100, metrics.margin * 10000, metrics.max_drawdown * 100, arch)

            # Gate 1: Performance Gate (Sharpe >= 1.25, Fitness >= 0.70, TO <= 70%, Margin >= 4bps)
            passed_gate1 = (
                metrics.sharpe >= 1.25
                and metrics.fitness >= 0.70
                and 0.01 <= metrics.turnover <= 0.70
                and (metrics.margin * 10000) >= 4.0
                and metrics.max_drawdown <= 0.35
            )

            if not passed_gate1:
                queue.task_done()
                continue

            # Fetch PnL Vector with Wi-Fi retry
            cand_pnl = {}
            for pnl_try in range(4):
                try:
                    cand_pnl = await client.get_alpha_pnl(metrics.alpha_id)
                    if cand_pnl and len(cand_pnl) >= 30:
                        break
                except Exception:
                    await asyncio.sleep(3.0)

            if not cand_pnl or len(cand_pnl) < 30:
                log.warning("[Worker %d] Could not fetch PnL for %s; skipping.", worker_id, metrics.alpha_id)
                queue.task_done()
                continue

            # Gate 2: Correlation Firewall (|rho| <= 0.62 vs Production)
            max_prod_corr = 0.0
            worst_prod = ""
            for p_id in prod_alpha_ids:
                if p_id in ref_pnls:
                    c = abs(compute_correlation(cand_pnl, ref_pnls[p_id]))
                    if c > max_prod_corr:
                        max_prod_corr = c
                        worst_prod = p_id

            if max_prod_corr > PROD_FIREWALL:
                log.info("[Worker %d] REJECTED_PROD_FIREWALL: %s vs %s (rho=%.4f > %.2f).",
                         worker_id, arch, worst_prod, max_prod_corr, PROD_FIREWALL)
                commit_collision_challenger(
                    db_url=config.database_url,
                    alpha_id=metrics.alpha_id,
                    expression=expr,
                    archetype=arch,
                    incumbent_id=worst_prod,
                    metrics=metrics,
                    max_corr=max_prod_corr,
                    universe=universe,
                    neutralization=neut,
                    decay=decay,
                    strategy_name=strategy_name,
                )
                queue.task_done()
                continue

            # Gate 3: Correlation Firewall vs Reserve (|rho| <= 0.65)
            max_res_corr = 0.0
            worst_res = ""
            for r_id in list(reserve_meta.keys()):
                if r_id in ref_pnls:
                    c = abs(compute_correlation(cand_pnl, ref_pnls[r_id]))
                    if c > max_res_corr:
                        max_res_corr = c
                        worst_res = r_id

            if max_res_corr > 0.65:
                log.info("[Worker %d] REJECTED_RESERVE_COLLISION: %s vs %s (rho=%.4f > 0.65).",
                         worker_id, arch, worst_res, max_res_corr)
                commit_collision_challenger(
                    db_url=config.database_url,
                    alpha_id=metrics.alpha_id,
                    expression=expr,
                    archetype=arch,
                    incumbent_id=worst_res,
                    metrics=metrics,
                    max_corr=max_res_corr,
                    universe=universe,
                    neutralization=neut,
                    decay=decay,
                    strategy_name=strategy_name,
                )
                queue.task_done()
                continue

            # Gate 4: Platform Checklist (/alphas/{id}/check)
            log.info("[*] Verifying platform checklist for %s...", metrics.alpha_id)
            chk_ok, chk_msg = await verify_checklist_passes(client._session, metrics.alpha_id)
            if not chk_ok:
                log.warning("[Worker %d] REJECTED_CHECKLIST: %s (%s).", worker_id, metrics.alpha_id, chk_msg)
                queue.task_done()
                continue

            # ALL GATES PASSED! Commit to PostgreSQL
            async with lock:
                current_qualified += 1
                ref_pnls[metrics.alpha_id] = cand_pnl
                reserve_meta[metrics.alpha_id] = {
                    "sharpe": metrics.sharpe,
                    "fitness": metrics.fitness,
                    "margin": metrics.margin,
                }

                commit_qualified_alpha(
                    db_url=config.database_url,
                    alpha_id=metrics.alpha_id,
                    expression=expr,
                    archetype=arch,
                    hypothesis=hyp,
                    metrics=metrics,
                    max_corr=max(max_prod_corr, max_res_corr),
                    universe=universe,
                    neutralization=neut,
                    decay=decay,
                    strategy_name=strategy_name,
                )

                safe_expr = html.escape(expr)
                safe_alpha = html.escape(metrics.alpha_id)
                safe_arch = html.escape(arch)

                send_tg_message(
                    token=config.telegram_bot_token,
                    chat_id=config.telegram_chat_id,
                    html_text=(
                        f"🌟 <b>NEW QUALIFIED ALPHA BANKED!</b> ({current_qualified}/{target_count})\n\n"
                        f"• <b>ID:</b> <code>{safe_alpha}</code>\n"
                        f"• <b>Pillar:</b> <b>{cat.upper()}</b>\n"
                        f"• <b>Archetype:</b> {safe_arch}\n"
                        f"• <b>Sharpe:</b> <b>{metrics.sharpe:.2f}</b>  |  <b>Fitness:</b> <b>{metrics.fitness:.2f}</b>\n"
                        f"• <b>Margin:</b> {metrics.margin * 10000:.1f} bps  |  <b>Turnover:</b> {metrics.turnover * 100:.1f}%\n"
                        f"• <b>Drawdown:</b> {metrics.max_drawdown * 100:.1f}%  |  <b>Universe:</b> {universe}\n"
                        f"• <b>Max Corr:</b> {max(max_prod_corr, max_res_corr):.2f}\n"
                        f"• <b>Expression:</b>\n<code>{safe_expr}</code>\n\n"
                        f"<i>Safely banked into PostgreSQL options_alphas (Zero Auto-Submissions).</i>"
                    ),
                )

            queue.task_done()

    workers = [asyncio.create_task(worker(i + 1)) for i in range(4)]
    await asyncio.gather(*workers)

    log.info("=" * 80)
    log.info("QUINTUPLE-VAULT MINING SESSION COMPLETED: %d / %d QUALIFIED BANKED.", current_qualified, target_count)
    log.info("=" * 80)


if __name__ == "__main__":
    try:
        asyncio.run(run_quintuple_vault_miner())
    except KeyboardInterrupt:
        log.info("Mining interrupted by user.")
    except Exception as e:
        log.error("Fatal error in quintuple-vault miner: %s", e)
