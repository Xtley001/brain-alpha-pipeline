"""
Brain Systematic Risk & Factor Models Strategy Module.
WorldQuant BRAIN Category: 'model' (ValueScore: 7.0 / 10 | Low Crowding)
Formulations derived from 8 peer-reviewed papers on Betting Against Beta, Idiosyncratic Volatility, and Fundamental Surface Dynamics.
"""
from typing import Any, Dict, List


def generate_risk_model_candidates() -> List[Dict[str, Any]]:
    """
    Generate orthogonal candidates across 5 institutional risk model archetypes:
    1. R1: Betting Against Beta (BAB - Frazzini & Pedersen 2014)
    2. R2: Market Decoupling & Idiosyncratic Volatility (Ang et al. 2006)
    3. R3: Multi-Horizon Beta Term Divergence (Black 1972)
    4. R4: Quality Surface Acceleration Derivative (Piotroski 2000)
    5. R5: Operational Cashflow Efficiency & Profitability (Novy-Marx 2013)
    """
    candidates = []
    universes = ["TOP3000", "TOP2000"]
    groups = ["subindustry", "sector"]
    decays = [10, 12, 15]

    for u in universes:
        for g in groups:
            for d in decays:
                # -------------------------------------------------------------
                # R1: Betting Against Beta (Frazzini & Pedersen 2014)
                # Fields: beta_last_60_days_spy, beta_last_90_days_spy
                # -------------------------------------------------------------
                for b_horizon in [60, 90]:
                    beta_field = f"beta_last_{b_horizon}_days_spy"
                    expr_r1a = f"group_neutralize(rank(- ts_decay_linear({beta_field}, {d})), {g})"
                    candidates.append({
                        "expression": expr_r1a,
                        "family": f"Risk_BAB_{b_horizon}",
                        "archetype": f"Risk_BAB_{b_horizon}_d{d}_{u}_{g.upper()}",
                        "hypothesis": f"Leverage-constrained investors overpay for high-beta stocks. Going long low-beta ({b_horizon}d) captures structural risk premium.",
                        "universe": u,
                        "neutralization": g.upper(),
                        "decay": d,
                        "category": "model",
                        "strategy": "risk_betting_against_beta",
                    })

                    # R1 Variant B: Combined Beta & Market Correlation (Baker, Bradley, & Wurgler 2011)
                    corr_field = f"correlation_last_{b_horizon}_days_spy"
                    expr_r1b = (
                        f"group_neutralize(rank(- 0.60 * rank(ts_decay_linear({beta_field}, {d})) - "
                        f"0.40 * rank(ts_decay_linear({corr_field}, {d}))), {g})"
                    )
                    candidates.append({
                        "expression": expr_r1b,
                        "family": f"Risk_LowRiskEngine_{b_horizon}",
                        "archetype": f"Risk_LowRisk_{b_horizon}_d{d}_{u}_{g.upper()}",
                        "hypothesis": f"Multi-dimensional low-risk factor combining rolling market beta and SPY correlation ({b_horizon}d).",
                        "universe": u,
                        "neutralization": g.upper(),
                        "decay": d,
                        "category": "model",
                        "strategy": "risk_low_risk_engine",
                    })

                # -------------------------------------------------------------
                # R2: Market Decoupling & Idiosyncratic Variance (Ang et al. 2006)
                # Field: correlation_last_60_days_spy, returns
                # -------------------------------------------------------------
                expr_r2a = (
                    f"group_neutralize(rank(ts_decay_linear(correlation_last_60_days_spy * "
                    f"(ts_std_dev(returns, 60) * sqrt(252)), {d})), {g})"
                )
                candidates.append({
                    "expression": expr_r2a,
                    "family": "Risk_IdioDecoupling",
                    "archetype": f"Risk_IdioDecouple_d{d}_{u}_{g.upper()}",
                    "hypothesis": f"Decomposing market correlation from total realized variance isolates idiosyncratic risk discount.",
                    "universe": u,
                    "neutralization": g.upper(),
                    "decay": d,
                    "category": "model",
                    "strategy": "risk_idiosyncratic_decoupling",
                })

                # -------------------------------------------------------------
                # R3: Multi-Horizon Beta Term Divergence (Black 1972)
                # Fields: beta_last_30_days_spy, beta_last_360_days_spy
                # -------------------------------------------------------------
                expr_r3a = (
                    f"group_neutralize(rank(- ts_decay_linear(beta_last_30_days_spy - beta_last_360_days_spy, {d})), {g})"
                )
                candidates.append({
                    "expression": expr_r3a,
                    "family": "Risk_BetaTermDivergence",
                    "archetype": f"Risk_BetaTermDiv_d{d}_{u}_{g.upper()}",
                    "hypothesis": f"Transient spikes in short-term beta (30d) relative to long-term structural beta (360d) systematically mean-revert.",
                    "universe": u,
                    "neutralization": g.upper(),
                    "decay": d,
                    "category": "model",
                    "strategy": "risk_beta_term_divergence",
                })

                # -------------------------------------------------------------
                # R4: Quality Surface Acceleration Derivative (Piotroski 2000)
                # Fields: fscore_surface_accel, fscore_bfl_quality
                # -------------------------------------------------------------
                expr_r4a = (
                    f"group_neutralize(rank(0.60 * rank(ts_decay_linear(fscore_surface_accel, {d})) + "
                    f"0.40 * rank(ts_decay_linear(fscore_bfl_quality, {d}))), {g})"
                )
                candidates.append({
                    "expression": expr_r4a,
                    "family": "Risk_SurfaceAcceleration",
                    "archetype": f"Risk_SurfaceAccel_d{d}_{u}_{g.upper()}",
                    "hypothesis": f"Acceleration derivative of fundamental multi-factor quality surface identifies inflection points in corporate balance-sheet strength.",
                    "universe": u,
                    "neutralization": g.upper(),
                    "decay": d,
                    "category": "model",
                    "strategy": "risk_quality_surface_acceleration",
                })

                # -------------------------------------------------------------
                # R5: Operational Cashflow Efficiency & Profitability (Novy-Marx 2013)
                # Fields: fscore_bfl_profitability, cashflow_efficiency_rank_derivative
                # -------------------------------------------------------------
                expr_r5a = (
                    f"group_neutralize(rank(0.50 * rank(ts_decay_linear(fscore_bfl_profitability, {d})) + "
                    f"0.50 * rank(ts_decay_linear(cashflow_efficiency_rank_derivative, {d}))), {g})"
                )
                candidates.append({
                    "expression": expr_r5a,
                    "family": "Risk_CashflowEfficiency",
                    "archetype": f"Risk_CashflowEff_d{d}_{u}_{g.upper()}",
                    "hypothesis": f"Gross profitability composite blended with operational cashflow efficiency derivative (Novy-Marx 2013).",
                    "universe": u,
                    "neutralization": g.upper(),
                    "decay": d,
                    "category": "model",
                    "strategy": "risk_cashflow_profitability",
                })

    return candidates
