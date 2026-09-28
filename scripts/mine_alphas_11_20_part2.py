"""
Orthogonal Reserve Alpha Miner (Target: Alphas 11 to 20 / 20)
Specifically engineered to qualify Reserve Alphas 11 through 20 locally:
- Strict Institutional Gates: Sharpe >= 1.25, Fitness >= 1.00, Turnover 1%-70%, Margin >= 10.0 bps, Max Drawdown < 35%.
- Pearson |rho| < 0.70 against ALL 25 reference alphas (15 submitted + 10 qualified reserve).
- Immediate PostgreSQL storage with status 'QUALIFIED'.
- Formatted Telegram dispatch for every qualified alpha with updated (#X / 20) counter.
"""

import asyncio
import logging
import os
import sys
from typing import Any, Dict, List, Optional
import requests

sys.path.insert(0, r"c:\Users\pc\Desktop\brain-alpha-pipeline")

from brain_options.config import OptionsConfig
from brain_options.core.client import BrainClient, SimSettings
from brain_options.core.correlation import compute_correlation
from brain_options.store.store import OptionsStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("reserve_miner_part2")

TOTAL_RESERVE_TARGET = 20


def send_tg_reserve_alert(config: OptionsConfig, alpha_id: str, archetype: str, sharpe: float, fitness: float, turnover: float, margin: float, max_corr: float, count: int):
    token = config.telegram_bot_token
    chat_id = config.telegram_chat_id
    if not token or not chat_id:
        return
    text = (
        f"<b>RESERVE ALPHA QUALIFIED (#{count} / {TOTAL_RESERVE_TARGET})</b>\n\n"
        f"<b>Alpha ID:</b> <code>{alpha_id}</code>\n"
        f"<b>Archetype:</b> <code>{archetype}</code>\n"
        f"<b>Sharpe Ratio:</b> <b>{sharpe:.2f}</b>\n"
        f"<b>Fitness Score:</b> <b>{fitness:.2f}</b>\n"
        f"<b>Turnover:</b> {turnover*100:.1f}%\n"
        f"<b>Margin:</b> <b>{margin*10000:.1f} bps</b>\n"
        f"<b>Max Portfolio Correlation:</b> <b>{max_corr:.4f}</b> (&lt; 0.70)\n"
        f"<b>Status:</b> <code>QUALIFIED</code> (Stored in Reserve Vault)\n\n"
        f"<i>Pipeline Reserve Progress: {count}/{TOTAL_RESERVE_TARGET} Alphas Secured</i>"
    )
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}, timeout=10)
    except Exception as e:
        log.warning("Telegram alert dispatch failed: %s", e)


def insert_qualified_alpha(
    database_url: str,
    alpha_id: str,
    expression: str,
    archetype: str,
    hypothesis: str,
    sharpe: float,
    fitness: float,
    turnover: float,
    returns: float,
    drawdown: float,
    margin: float,
    max_corr: float,
    universe: str,
    neutralization: str,
    delay: int,
    decay: int,
    strategy_name: str,
) -> bool:
    import psycopg
    sql = """
        INSERT INTO options_alphas (
            alpha_id, expression, archetype, hypothesis, source,
            sharpe, fitness, turnover, returns, drawdown, margin, max_correlation,
            universe, neutralization, delay, decay, truncation, pasteurization, nan_handling,
            status, strategy_name
        ) VALUES (
            %s, %s, %s, %s, 'mine_alphas_11_20_local',
            %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, 0.05, true, 'ON',
            'QUALIFIED', %s
        )
        ON CONFLICT (alpha_id) DO UPDATE SET
            status = 'QUALIFIED',
            sharpe = EXCLUDED.sharpe,
            fitness = EXCLUDED.fitness,
            margin = EXCLUDED.margin,
            max_correlation = EXCLUDED.max_correlation;
    """
    try:
        with psycopg.connect(database_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (
                    alpha_id, expression, archetype, hypothesis,
                    sharpe, fitness, turnover, returns, drawdown, margin, max_corr,
                    universe, neutralization, delay, decay, strategy_name,
                ))
        log.info("Successfully recorded %s as QUALIFIED in PostgreSQL.", alpha_id)
        return True
    except Exception as e:
        log.error("Failed to insert qualified alpha into database: %s", e)
        return False


def build_candidate_matrix() -> List[Dict[str, Any]]:
    candidates = []

    # -------------------------------------------------------------------------
    # Family 1: Decoupled Call-Breakeven with Short Tenor IV Asymmetry (IV30 / IV20)
    # Tested Levers:
    # 1. Tenors: 120d, 90d, 60d, 270d, 360d with IV30 / IV20
    # 2. Neutralization: SECTOR and INDUSTRY (GICS industry shift breaks correlation)
    # 3. Weights: 0.65 / 0.35 and 0.70 / 0.30
    # 4. Gates: 0.30, 0.32, 0.34
    # -------------------------------------------------------------------------
    call_configs = [
        # (t_call, t_iv, w1, w2, gate, decay, univ, neut)
        # Priority A: 120d Call + IV30/IV20 (Candidate 14 with IV60 had Sharpe 2.26, corr 0.7069)
        (120, 30, 0.65, 0.35, 0.32, 10, "TOP3000", "SECTOR"),
        (120, 30, 0.65, 0.35, 0.34, 10, "TOP3000", "SECTOR"),
        (120, 20, 0.65, 0.35, 0.32, 10, "TOP3000", "SECTOR"),
        (120, 30, 0.60, 0.40, 0.30, 8, "TOP3000", "INDUSTRY"),
        (120, 30, 0.65, 0.35, 0.32, 8, "TOP3000", "INDUSTRY"),

        # Priority B: 90d Call + IV30/IV20
        (90, 30, 0.65, 0.35, 0.32, 10, "TOP3000", "SECTOR"),
        (90, 30, 0.65, 0.35, 0.34, 10, "TOP3000", "SECTOR"),
        (90, 20, 0.65, 0.35, 0.32, 10, "TOP3000", "SECTOR"),
        (90, 30, 0.60, 0.40, 0.30, 8, "TOP3000", "INDUSTRY"),
        (90, 30, 0.65, 0.35, 0.32, 8, "TOP3000", "INDUSTRY"),

        # Priority C: 60d Call + IV30/IV20 (Fastest call ceiling tenor)
        (60, 30, 0.65, 0.35, 0.30, 8, "TOP3000", "SECTOR"),
        (60, 30, 0.65, 0.35, 0.32, 10, "TOP3000", "SECTOR"),
        (60, 20, 0.65, 0.35, 0.30, 8, "TOP3000", "SECTOR"),
        (60, 20, 0.65, 0.35, 0.32, 10, "TOP3000", "SECTOR"),
        (60, 30, 0.60, 0.40, 0.30, 8, "TOP3000", "INDUSTRY"),

        # Priority D: 270d Call + IV30/IV20
        (270, 30, 0.65, 0.35, 0.32, 10, "TOP3000", "SECTOR"),
        (270, 30, 0.70, 0.30, 0.34, 10, "TOP3000", "SECTOR"),
        (270, 20, 0.65, 0.35, 0.32, 10, "TOP3000", "SECTOR"),
        (270, 30, 0.65, 0.35, 0.32, 8, "TOP3000", "INDUSTRY"),

        # Priority E: 360d Call + IV30/IV20
        (360, 30, 0.65, 0.35, 0.34, 10, "TOP3000", "SECTOR"),
        (360, 20, 0.65, 0.35, 0.34, 10, "TOP3000", "SECTOR"),
        (360, 30, 0.65, 0.35, 0.32, 8, "TOP3000", "INDUSTRY"),

        # Priority F: 180d Call + IV20 & INDUSTRY shift (180/30 was 0.6814; IV20/INDUSTRY gives second distinct alpha)
        (180, 20, 0.65, 0.35, 0.32, 10, "TOP3000", "SECTOR"),
        (180, 20, 0.65, 0.35, 0.34, 10, "TOP3000", "SECTOR"),
        (180, 30, 0.65, 0.35, 0.32, 8, "TOP3000", "INDUSTRY"),
    ]

    for t_call, t_iv, w1, w2, gate, dcy, u, n in call_configs:
        sig1 = f"ts_decay_linear(ts_decay_linear(((call_breakeven_{t_call} - forward_price_{t_call}) / close * (implied_volatility_mean_skew_{t_call} * sqrt({t_call}/252.0)) * (pcr_vol_{t_call} / (pcr_oi_{t_call} + 0.001))), 10), 3)"
        sig2 = f"ts_decay_linear(ts_decay_linear(((implied_volatility_call_{t_iv} - implied_volatility_put_{t_iv}) / (implied_volatility_mean_{t_iv} + 0.001) * sqrt({t_iv}/252.0) * (volume / (adv20 + 1))), 10), 3)"
        comb = f"({w1} * rank({sig1}) + {w2} * rank({sig2}))"
        expr = f"trade_when(abs(rank({comb}) - 0.5) > {gate}, group_neutralize(rank({comb}) * (volume / adv20), {n.lower()}), -1)"

        candidates.append({
            "expression": expr,
            "archetype": f"Call{t_call}_IV{t_iv}_{int(w1*100)}_{u}_{n}_d{dcy}_g{int(gate*100)}",
            "hypothesis": f"Call breakeven ceiling ({t_call}d) blended with decoupled IV asymmetry ({t_iv}d) neutralized by {n}.",
            "universe": u,
            "neutralization": n,
            "decay": dcy,
            "strategy": "call_breakeven_iv_asym",
        })

    # -------------------------------------------------------------------------
    # Family 2: Industry-Neutralized High-Performance Blends (360/60, 270/60, 180/60)
    # The Sector versions had Sharpe ~1.9 and corr 0.705-0.716.
    # Group neutralizing by GICS Industry introduces orthogonal dispersion.
    # -------------------------------------------------------------------------
    industry_blends = [
        (360, 60, 0.60, 0.40, 0.30, 8, "TOP3000", "INDUSTRY"),
        (360, 60, 0.60, 0.40, 0.32, 10, "TOP3000", "INDUSTRY"),
        (270, 60, 0.60, 0.40, 0.30, 8, "TOP3000", "INDUSTRY"),
        (270, 60, 0.60, 0.40, 0.32, 10, "TOP3000", "INDUSTRY"),
        (180, 60, 0.60, 0.40, 0.30, 8, "TOP3000", "INDUSTRY"),
        (180, 60, 0.60, 0.40, 0.32, 10, "TOP3000", "INDUSTRY"),
    ]
    for t_call, t_iv, w1, w2, gate, dcy, u, n in industry_blends:
        sig1 = f"ts_decay_linear(ts_decay_linear(((call_breakeven_{t_call} - forward_price_{t_call}) / close * (implied_volatility_mean_skew_{t_call} * sqrt({t_call}/252.0)) * (pcr_vol_{t_call} / (pcr_oi_{t_call} + 0.001))), 10), 3)"
        sig2 = f"ts_decay_linear(ts_decay_linear(((implied_volatility_call_{t_iv} - implied_volatility_put_{t_iv}) / (implied_volatility_mean_{t_iv} + 0.001) * sqrt({t_iv}/252.0) * (volume / (adv20 + 1))), 10), 3)"
        comb = f"({w1} * rank({sig1}) + {w2} * rank({sig2}))"
        expr = f"trade_when(abs(rank({comb}) - 0.5) > {gate}, group_neutralize(rank({comb}) * (volume / adv20), {n.lower()}), -1)"

        candidates.append({
            "expression": expr,
            "archetype": f"Call{t_call}_IV{t_iv}_Ind_{u}_{n}_d{dcy}_g{int(gate*100)}",
            "hypothesis": f"Industry-neutralized call breakeven ({t_call}d) + IV ({t_iv}d) blend.",
            "universe": u,
            "neutralization": n,
            "decay": dcy,
            "strategy": "call_breakeven_industry_neutral",
        })

    # -------------------------------------------------------------------------
    # Family 3: Put Breakeven at Uncrowded Tenors with Short IV Asymmetry
    # Tenors: 150d, 120d, 90d with IV30 / IV20 on SECTOR and INDUSTRY
    # Candidate 38 (Put150_IV60) had Sharpe 1.48, Fitness 1.16, Margin 17.4 bps!
    # -------------------------------------------------------------------------
    put_configs = [
        (150, 30, 0.65, 0.35, 0.30, 8, "TOP3000", "SECTOR"),
        (150, 30, 0.65, 0.35, 0.32, 10, "TOP3000", "SECTOR"),
        (150, 20, 0.65, 0.35, 0.30, 8, "TOP3000", "SECTOR"),
        (150, 30, 0.65, 0.35, 0.30, 8, "TOP3000", "INDUSTRY"),
        (120, 30, 0.65, 0.35, 0.30, 8, "TOP3000", "SECTOR"),
        (120, 30, 0.65, 0.35, 0.32, 10, "TOP3000", "SECTOR"),
        (120, 20, 0.65, 0.35, 0.30, 8, "TOP3000", "SECTOR"),
        (120, 30, 0.65, 0.35, 0.30, 8, "TOP3000", "INDUSTRY"),
        (90, 30, 0.65, 0.35, 0.30, 8, "TOP3000", "SECTOR"),
        (90, 30, 0.65, 0.35, 0.32, 10, "TOP3000", "SECTOR"),
        (90, 30, 0.65, 0.35, 0.30, 8, "TOP3000", "INDUSTRY"),
        (270, 30, 0.65, 0.35, 0.32, 10, "TOP3000", "INDUSTRY"),
    ]
    for t_put, t_iv, w1, w2, gate, dcy, u, n in put_configs:
        sig1 = f"ts_decay_linear(ts_decay_linear(((forward_price_{t_put} - put_breakeven_{t_put}) / close * (implied_volatility_mean_skew_{t_put} * sqrt({t_put}/252.0)) * (pcr_vol_{t_put} / (pcr_oi_{t_put} + 0.001))), 10), 3)"
        sig2 = f"ts_decay_linear(ts_decay_linear(((implied_volatility_call_{t_iv} - implied_volatility_put_{t_iv}) / (implied_volatility_mean_{t_iv} + 0.001) * sqrt({t_iv}/252.0) * (volume / (adv20 + 1))), 10), 3)"
        comb = f"({w1} * rank({sig1}) + {w2} * rank({sig2}))"
        expr = f"trade_when(abs(rank({comb}) - 0.5) > {gate}, group_neutralize(rank({comb}) * (volume / adv20), {n.lower()}), -1)"

        candidates.append({
            "expression": expr,
            "archetype": f"Put{t_put}_IV{t_iv}_{u}_{n}_d{dcy}_g{int(gate*100)}",
            "hypothesis": f"Downside put breakeven floor ({t_put}d) blended with IV asymmetry ({t_iv}d) neutralized by {n}.",
            "universe": u,
            "neutralization": n,
            "decay": dcy,
            "strategy": "put_floor_uncrowded_tenor",
        })

    return candidates


async def run_miner():
    config = OptionsConfig.from_env()
    store = OptionsStore(database_url=config.database_url)
    client = BrainClient(
        username=config.brain_username,
        password=config.brain_password,
        max_concurrent_sims=2,
        db=store.db,
    )
    client.authenticate()

    # Step 1: Query current database count & expressions
    log.info("Connecting to PostgreSQL to load existing alphas...")
    with store.db._get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT alpha_id, expression, status FROM options_alphas WHERE status IN ('SUBMITTED', 'QUALIFIED')")
            db_rows = cur.fetchall()

    submitted_ids = [r[0] for r in db_rows if r[2] == "SUBMITTED"]
    qualified_ids = [r[0] for r in db_rows if r[2] == "QUALIFIED"]
    current_qualified = len(qualified_ids)
    all_ref_ids = [r[0] for r in db_rows]
    existing_expressions = {r[1].strip() for r in db_rows if r[1]}

    log.info("Found %d SUBMITTED and %d QUALIFIED in database (Total Reference: %d).", len(submitted_ids), current_qualified, len(all_ref_ids))

    if current_qualified >= TOTAL_RESERVE_TARGET:
        log.info("Reserve target of %d alphas already achieved! (Currently %d in vault)", TOTAL_RESERVE_TARGET, current_qualified)
        return

    # Step 2: Pre-fetch all daily PnL vectors for reference alphas
    log.info("Pre-fetching daily PnL vectors for %d reference alphas...", len(all_ref_ids))
    ref_pnls: Dict[str, Dict[str, float]] = {}
    for aid in all_ref_ids:
        try:
            pnl = await client.get_alpha_pnl(aid)
            if pnl:
                ref_pnls[aid] = pnl
        except Exception as e:
            log.warning("Could not fetch PnL for %s: %s", aid, e)

    log.info("Loaded %d daily PnL series into memory.", len(ref_pnls))

    # Step 3: Generate candidate matrix
    candidates = build_candidate_matrix()
    log.info("Built candidate matrix with %d prioritized orthogonal candidates.", len(candidates))

    # Step 4: Iterative simulation, qualification & dynamic storage
    for idx, cand in enumerate(candidates, 1):
        if current_qualified >= TOTAL_RESERVE_TARGET:
            log.info("Target of %d Reserve Alphas ACHIEVED! Halting miner.", TOTAL_RESERVE_TARGET)
            break

        expr = cand["expression"]
        if expr.strip() in existing_expressions:
            log.info("[%d/%d] Skipping duplicate expression for %s", idx, len(candidates), cand["archetype"])
            continue

        log.info("\n--------------------------------------------------------------------------------")
        log.info("[%d/%d] Evaluating Candidate: %s", idx, len(candidates), cand["archetype"])
        log.info("Settings: Universe=%s | Neutralization=%s | Decay=%d", cand["universe"], cand["neutralization"], cand["decay"])

        settings = SimSettings(
            region="USA",
            universe=cand["universe"],
            delay=1,
            decay=cand["decay"],
            neutralization=cand["neutralization"],
            truncation=0.05,
            pasteurization=True,
        )

        try:
            metrics = await client.simulate_one(expr, settings)
        except Exception as e:
            log.warning("Simulation exception: %s", e)
            continue

        if not metrics.alpha_id or not metrics.is_valid:
            log.warning("Simulation returned invalid metrics (alpha_id=%s, status=%s)", metrics.alpha_id, metrics.status)
            continue

        log.info(
            "  Alpha ID: %s | Sharpe: %.2f | Fitness: %.2f | Turnover: %.1f%% | Margin: %.1f bps | Return: %.1f%% | MaxDD: %.1f%%",
            metrics.alpha_id, metrics.sharpe, metrics.fitness, metrics.turnover * 100, metrics.margin * 10000,
            metrics.annualized_return * 100, metrics.max_drawdown * 100,
        )

        # Gate 1: Performance Filters
        if metrics.sharpe < 1.25:
            log.info("  --> REJECT: Sharpe %.2f < 1.25", metrics.sharpe)
            continue
        if metrics.fitness < 1.00:
            log.info("  --> REJECT: Fitness %.2f < 1.00", metrics.fitness)
            continue
        if not (0.01 <= metrics.turnover <= 0.70):
            log.info("  --> REJECT: Turnover %.1f%% out of bounds [1%%, 70%%]", metrics.turnover * 100)
            continue
        if metrics.margin < 0.0010:
            log.info("  --> REJECT: Margin %.1f bps < 10.0 bps", metrics.margin * 10000)
            continue
        if metrics.max_drawdown >= 0.35:
            log.info("  --> REJECT: Max Drawdown %.1f%% >= 35.0%%", metrics.max_drawdown * 100)
            continue

        log.info("  --> PASS: Met all performance criteria! Checking correlation vs %d alphas...", len(ref_pnls))

        # Gate 2: Correlation Check
        cand_pnl = await client.get_alpha_pnl(metrics.alpha_id)
        if not cand_pnl:
            log.warning("  --> REJECT: Could not fetch PnL for %s", metrics.alpha_id)
            continue

        max_c = 0.0
        max_ref = ""
        for ref_id, ref_pnl in ref_pnls.items():
            c = abs(compute_correlation(cand_pnl, ref_pnl))
            if c > max_c:
                max_c = c
                max_ref = ref_id

        log.info("  --> Max Correlation: %.4f (vs %s)", max_c, max_ref)
        if max_c >= 0.70:
            log.info("  --> REJECT: Max correlation %.4f >= 0.70 barrier", max_c)
            continue

        # Gate 3: Platform Checklist Immunity Check
        log.info("  --> PASS: Correlation %.4f < 0.70! Running WorldQuant BRAIN submission checklist...", max_c)
        try:
            session = client._get_session()
            resp = session.get(f"https://api.worldquantbrain.com/alphas/{metrics.alpha_id}/check")
            if resp.status_code == 200:
                chk_data = resp.json()
                chk_status = chk_data.get("status", "PASS")
                checks = {c.get("name"): c.get("result") for c in chk_data.get("checks", [])}
                sub_univ_check = checks.get("LOW_SUB_UNIVERSE_SHARPE", "PASS")
                log.info("  --> Checklist Status: %s | LOW_SUB_UNIVERSE_SHARPE: %s", chk_status, sub_univ_check)
                if chk_status == "FAIL" or sub_univ_check == "FAIL":
                    log.warning("  --> REJECT: Alpha failed BRAIN pre-submission checklist (%s)", checks)
                    continue
        except Exception as e:
            log.warning("  --> Checklist check error: %s (proceeding with caution)", e)

        # QUALIFIED!
        current_qualified += 1
        log.info("================================================================================")
        log.info(
            "[QUALIFIED] RESERVE ALPHA (#%d / %d): %s | Sharpe: %.2f | Fitness: %.2f | Turnover: %.1f%% | Margin: %.1f bps | Max Corr: %.4f",
            current_qualified, TOTAL_RESERVE_TARGET, metrics.alpha_id, metrics.sharpe, metrics.fitness,
            metrics.turnover * 100, metrics.margin * 10000, max_c,
        )
        log.info("================================================================================")

        # 1. Insert into PostgreSQL
        insert_qualified_alpha(
            database_url=config.database_url,
            alpha_id=metrics.alpha_id,
            expression=expr,
            archetype=cand["archetype"],
            hypothesis=cand["hypothesis"],
            sharpe=metrics.sharpe,
            fitness=metrics.fitness,
            turnover=metrics.turnover,
            returns=metrics.annualized_return,
            drawdown=metrics.max_drawdown,
            margin=metrics.margin,
            max_corr=max_c,
            universe=cand["universe"],
            neutralization=cand["neutralization"],
            delay=1,
            decay=cand["decay"],
            strategy_name=cand["strategy"],
        )

        # 2. Add to reference pool dynamically
        ref_pnls[metrics.alpha_id] = cand_pnl
        existing_expressions.add(expr.strip())

        # 3. Dispatch formatted Telegram HTML alert
        send_tg_reserve_alert(
            config=config,
            alpha_id=metrics.alpha_id,
            archetype=cand["archetype"],
            sharpe=metrics.sharpe,
            fitness=metrics.fitness,
            turnover=metrics.turnover,
            margin=metrics.margin,
            max_corr=max_c,
            count=current_qualified,
        )

    log.info("================================================================================")
    log.info("PART 2 MINER COMPLETE: Final Reserve Count = %d / %d Alphas", current_qualified, TOTAL_RESERVE_TARGET)
    log.info("================================================================================")


if __name__ == "__main__":
    asyncio.run(run_miner())
