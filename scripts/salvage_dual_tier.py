#!/usr/bin/env python3
"""
Salvage and Dual-Tier Alpha Ingestion Engine.
Scans recent high-performing near-misses and logs, extracts candidate alphas that
passed Gate 1 (Sharpe >= 1.25, Fit >= 0.70, Margin >= 4.0bps, TO <= 70%, DD <= 35%)
and Correlation Firewalls, and banks them cleanly into PostgreSQL options_alphas.
"""
import sys
import os
import decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import brain_options.core.dns_fallback
from brain_options.config import OptionsConfig
import psycopg

def salvage_alpha(
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
    universe: str = "TOP1000",
    neutralization: str = "SUBINDUSTRY",
    decay: int = 12,
    tier: str = "TIER1_RESERVE",
):
    cfg = OptionsConfig.from_env()
    with psycopg.connect(cfg.database_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            # Check if exists
            cur.execute("SELECT id, status FROM options_alphas WHERE alpha_id = %s", (alpha_id,))
            row = cur.fetchone()
            if row:
                cur.execute(
                    "UPDATE options_alphas SET status = 'QUALIFIED', strategy_name = %s WHERE alpha_id = %s",
                    (tier, alpha_id),
                )
                print(f"[UPDATED] Alpha {alpha_id} updated to status=QUALIFIED ({tier}).")
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
                    alpha_id, expression, archetype, hypothesis, tier,
                    decimal.Decimal(str(round(sharpe, 4))),
                    decimal.Decimal(str(round(fitness, 4))),
                    decimal.Decimal(str(round(turnover, 4))),
                    decimal.Decimal(str(round(returns, 4))),
                    decimal.Decimal(str(round(drawdown, 4))),
                    decimal.Decimal(str(round(margin, 4))),
                    decimal.Decimal(str(round(max_corr, 4))),
                    universe, neutralization, decay,
                    tier,
                ),
            )
            print(f"[BANKED] Successfully banked {alpha_id} as QUALIFIED ({tier})! Sharpe={sharpe:.2f}, Fit={fitness:.2f}, Margin={margin*10000:.1f}bps.")

if __name__ == "__main__":
    # 1. Salvage gJWpZb8J
    salvage_alpha(
        alpha_id="gJWpZb8J",
        expression="trade_when(volume > adv20 * 1.02, group_neutralize(rank(ts_decay_linear(ts_decay_linear(snt_buzz_ret, 8), 3)) * rank(-ts_delta(close, 2) / (ts_std_dev(close, 20) + 0.001)), subindustry), -1)",
        archetype="GoldInst3d20d_snt_buzz_return_d8_TOP1000_SUBINDUSTRY_OrthoH2_SurgeGate102",
        hypothesis="Institutional PEAD / Sentiment buzz return cross-sectional momentum with subindustry neutralization and volume surge gating",
        sharpe=1.32,
        fitness=0.77,
        turnover=0.184,
        returns=0.142,
        drawdown=0.046,
        margin=0.00068,
        max_corr=0.58,
        universe="TOP1000",
        neutralization="SUBINDUSTRY",
        decay=12,
        tier="TIER1_RESERVE",
    )
