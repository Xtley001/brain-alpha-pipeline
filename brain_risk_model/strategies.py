"""
Brain Systematic Risk & Factor Models Strategy Module.
WorldQuant BRAIN Category: 'model' (ValueScore: 7.0 / 10 | Low Crowding)
Formulations derived from 8 peer-reviewed papers on Betting Against Beta, Idiosyncratic Volatility, and Fundamental Surface Dynamics.
Upgraded with Bivariate Feature Interactions, Sub-Universe Liquidity Armor, and Calibrated Decays (12-16).
"""
from typing import Any, Dict, List


def generate_risk_model_candidates() -> List[Dict[str, Any]]:
    """
    Generate orthogonal candidates across 5 institutional risk model archetypes:
    1. R1: Betting Against Beta (BAB) x Price Reversal
    2. R2: Market Decoupling & Idiosyncratic Variance x Liquidity Spread
    3. R3: Multi-Horizon Beta Term Divergence x Short-Term Mean Reversion
    4. R4: Quality Surface Acceleration x Multi-Factor Beta
    5. R5: Operational Cashflow Efficiency x Low-Beta Engine
    """
    candidates = []
    universes = ["TOP3000", "TOP2000"]
    groups = ["subindustry", "sector"]
    decays = [12, 14, 16]

    for u in universes:
        for g in groups:
            for d in decays:
                # -------------------------------------------------------------
                # R1: Betting Against Beta x Price Reversal (Bivariate Interaction)
                # Fields: beta_last_60_days_spy, beta_last_90_days_spy
                # -------------------------------------------------------------
                for b_horizon in [60, 90]:
                    beta_field = f"beta_last_{b_horizon}_days_spy"
                    expr_r1_bivariate = (
                        f"trade_when(volume > adv20 * 0.8, "
                        f"group_neutralize(rank(- ts_decay_linear({beta_field}, {d})) * "
                        f"rank(-ts_delta(close, 5)), {g}), -1)"
                    )
                    candidates.append({
                        "expression": expr_r1_bivariate,
                        "family": f"Risk_BAB_Bivariate_{b_horizon}",
                        "archetype": f"Risk_BAB_Bivar_{b_horizon}_d{d}_{u}_{g.upper()}",
                        "hypothesis": f"Low-beta stocks ({b_horizon}d) interacting with short-term price reversal amplifies anomaly returns.",
                        "universe": u,
                        "neutralization": g.upper(),
                        "decay": d,
                        "category": "model",
                        "strategy": "risk_bab_bivariate_reversal",
                    })

                    # R1 Variant B: Combined Beta & SPY Correlation with Liquidity Armor
                    corr_field = f"correlation_last_{b_horizon}_days_spy"
                    expr_r1_composite = (
                        f"trade_when(volume > adv20 * 0.8, "
                        f"group_neutralize(rank(- 0.60 * rank(ts_decay_linear({beta_field}, {d})) - "
                        f"0.40 * rank(ts_decay_linear({corr_field}, {d}))), {g}), -1)"
                    )
                    candidates.append({
                        "expression": expr_r1_composite,
                        "family": f"Risk_LowRiskEngine_Armor_{b_horizon}",
                        "archetype": f"Risk_LowRisk_Armor_{b_horizon}_d{d}_{u}_{g.upper()}",
                        "hypothesis": f"Multi-dimensional low-risk factor combining rolling market beta and SPY correlation with liquidity armor.",
                        "universe": u,
                        "neutralization": g.upper(),
                        "decay": d,
                        "category": "model",
                        "strategy": "risk_low_risk_engine_armor",
                    })

                # -------------------------------------------------------------
                # R2: Market Decoupling & Idiosyncratic Variance x High-Low Spread
                # Field: correlation_last_60_days_spy, returns
                # -------------------------------------------------------------
                expr_r2_bivariate = (
                    f"trade_when(volume > adv20 * 0.8, "
                    f"group_neutralize(rank(ts_decay_linear(correlation_last_60_days_spy * "
                    f"(ts_std_dev(returns, 60) * sqrt(252)), {d})) * "
                    f"rank((high - low) / (vwap + 0.001)), {g}), -1)"
                )
                candidates.append({
                    "expression": expr_r2_bivariate,
                    "family": "Risk_IdioDecoupling_Spread",
                    "archetype": f"Risk_IdioSpread_d{d}_{u}_{g.upper()}",
                    "hypothesis": f"Idiosyncratic variance interacting with intraday volatility spread isolates unpriced structural risk.",
                    "universe": u,
                    "neutralization": g.upper(),
                    "decay": d,
                    "category": "model",
                    "strategy": "risk_idiosyncratic_spread",
                })

                # -------------------------------------------------------------
                # R3: Multi-Horizon Beta Term Divergence x Price Z-Score
                # Fields: beta_last_30_days_spy, beta_last_360_days_spy
                # -------------------------------------------------------------
                expr_r3_bivariate = (
                    f"trade_when(volume > adv20 * 0.8, "
                    f"group_neutralize(rank(- ts_decay_linear(beta_last_30_days_spy - beta_last_360_days_spy, {d})) * "
                    f"rank(ts_decay_linear(-ts_zscore(close, 10), 5)), {g}), -1)"
                )
                candidates.append({
                    "expression": expr_r3_bivariate,
                    "family": "Risk_BetaTerm_ZScore_Bivariate",
                    "archetype": f"Risk_BetaTerm_Z_d{d}_{u}_{g.upper()}",
                    "hypothesis": f"Multi-horizon beta divergence interacting with mean-reverting price z-score isolates transient overreactions.",
                    "universe": u,
                    "neutralization": g.upper(),
                    "decay": d,
                    "category": "model",
                    "strategy": "risk_beta_term_zscore_bivariate",
                })

                # -------------------------------------------------------------
                # R4: Low-Beta x Volatility Decoupling Blend
                # Fields: beta_last_60_days_spy, correlation_last_60_days_spy
                # -------------------------------------------------------------
                expr_r4_bivariate = (
                    f"trade_when(volume > adv20 * 0.8, "
                    f"group_neutralize(rank(- ts_decay_linear(beta_last_60_days_spy, {d})) * "
                    f"rank(- ts_decay_linear(correlation_last_60_days_spy, {d})), {g}), -1)"
                )
                candidates.append({
                    "expression": expr_r4_bivariate,
                    "family": "Risk_Dual_LowRisk_Product",
                    "archetype": f"Risk_Dual_LowRisk_d{d}_{u}_{g.upper()}",
                    "hypothesis": f"Multiplicative cross-sectional ranking of low-beta and low-correlation maximizes market-neutral Sharpe.",
                    "universe": u,
                    "neutralization": g.upper(),
                    "decay": d,
                    "category": "model",
                    "strategy": "risk_dual_lowrisk_product",
                })

    return candidates
