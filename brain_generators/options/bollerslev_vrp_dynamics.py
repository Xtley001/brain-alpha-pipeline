"""
Carr & Madan (2001) & Bollerslev, Tauchen & Zhou (2009)
Source KB: docs/kb/options/carr_madan_bollerslev_vrp.md

Key Institutional Empirical Findings:
1. Carr & Madan (2001, Risk Books):
   - Static replication theorem: arbitrary claim spanned by bonds, forwards, and continuum of OTM options.
   - For log contract f(F) = ln(F/F0), f''(K) = -1/K^2.
   - Realized variance replication: pure volatility exposure synthesized by dynamic delta-hedging (2/F)
     plus static inverse-strike-squared option basket w(K) = 2/K^2.
2. Bollerslev, Tauchen & Zhou (2009, RFS):
   - Variance Risk Premium: VRP = IV^2 - RV^2 (model-free implied variance minus 5-minute realized variance).
   - In general equilibrium with Epstein-Zin recursive utility, VRP isolates the volatility-of-volatility factor q_t.
   - Return predictability peaks at intermediate quarterly horizon (3 months): t = 2.86, R^2 = 6.82%.
   - Bivariate regression combining VRP + P/E ratio: t(VRP) = 3.43, t(P/E) = -2.42, adjusted R^2 > 10%.
   - Volatility form (sqrt(IV) - sqrt(RV)) also yields significant predictive power (t = 2.75, R^2 = 6.51%).
"""
from typing import Any, Dict, List

SOURCE_KB = "docs/kb/options/carr_madan_bollerslev_vrp.md"


def generate_bollerslev_vrp_dynamics_candidates() -> List[Dict[str, Any]]:
    """
    Generate paper-grounded alpha candidates from Carr & Madan (2001) and Bollerslev, Tauchen & Zhou (2009).
    All expressions feature balanced parentheses, valid BRAIN operators, and 100% source_kb traceability.
    """
    catalog: List[Dict[str, Any]] = []

    universes = ["TOPSP500", "TOP500", "TOP1000", "TOP2000"]
    neut_groups = ["SUBINDUSTRY", "SECTOR", "MARKET"]
    horizons = [20, 40, 60]  # 60d corresponds to the optimal quarterly horizon in BTZ (2009)

    # ─────────────────────────────────────────────────────────────────────────
    # 1. Bollerslev, Tauchen & Zhou (2009): Model-Free Variance Risk Premium (VRP)
    # VRP = IV^2 - RV^2, isolating the volatility-of-volatility risk factor q_t
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:3]:
        for g in neut_groups:
            for h in [20, 60]:
                catalog.append({
                    "pillar": "VARIANCE_RISK_PREMIUM_BTZ",
                    "archetype": f"BTZ_VRP_Direct_h{h}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"group_neutralize(rank(ts_decay_linear((iv_atm_30^2) - ts_mean(returns^2, 22) * 252.0, {h})), {g.lower()}), "
                        f"-1)"
                    ),
                    "hypothesis": (
                        f"Bollerslev, Tauchen & Zhou (2009) Equation 22: Variance Risk Premium (IV^2 - RV^2) "
                        f"isolating volatility-of-volatility q_t. Horizon {h}d, {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": h,
                    "category": "options",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 2. BTZ (2009): Volatility Risk Premium Form (sqrt(IV) - sqrt(RV))
    # Standard deviation formulation (t = 2.75, R^2 = 6.51% in BTZ Table 4)
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:2]:
        for g in neut_groups:
            for h in [20, 60]:
                catalog.append({
                    "pillar": "VOLATILITY_RISK_PREMIUM_STD",
                    "archetype": f"BTZ_Vol_Spread_Std_h{h}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.75, "
                        f"group_neutralize(rank(ts_decay_linear(iv_atm_30 - ts_std(returns, 22) * sqrt(252.0), {h})), {g.lower()}), "
                        f"-1)"
                    ),
                    "hypothesis": (
                        f"Bollerslev, Tauchen & Zhou (2009) Section 4.2.2: Volatility Risk Premium (IV - RV_std) "
                        f"predicts intermediate equity returns. Horizon {h}d, {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": h,
                    "category": "options",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 3. BTZ (2009): Bivariate VRP & Valuation Interaction (VRP + P/E)
    # Jointly spanning short-term economic uncertainty risk (VRP) and long-run growth (P/E)
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:3]:
        for g in neut_groups:
            catalog.append({
                "pillar": "VRP_VALUATION_BIVARIATE",
                "archetype": f"BTZ_VRP_PE_Joint_{u}_{g}",
                "expression": (
                    f"trade_when(volume > adv20 * 0.80, "
                    f"group_neutralize(rank(ts_rank((iv_atm_30^2) - ts_mean(returns^2, 22) * 252.0, 60) - ts_rank(close / (earnings_per_share + 0.001), 120)), {g.lower()}), "
                    f"-1)"
                ),
                "hypothesis": (
                    f"Bollerslev, Tauchen & Zhou (2009) Table 4: Bivariate regression combining VRP and P/E ratio "
                    f"maximizes quarterly predictive R^2 (>10%, t=3.43). {u}."
                ),
                "universe": u,
                "neutralization": g,
                "decay": 60,
                "category": "options",
                "source_kb": SOURCE_KB,
            })

    # ─────────────────────────────────────────────────────────────────────────
    # 4. BTZ (2009): Expected Variance Risk Premium (EVRP with HAR-RV proxy)
    # Forward-looking EVRP = IV^2 - E[RV], weighting short- and medium-term realized components
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:2]:
        for g in neut_groups:
            for d in [10, 20]:
                catalog.append({
                    "pillar": "EXPECTED_VRP_HAR_PROXY",
                    "archetype": f"BTZ_EVRP_HAR_Proxy_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"group_neutralize(rank(ts_decay_linear((iv_atm_30^2) - (0.30 * ts_mean(returns^2, 5) * 252.0 + 0.70 * ts_mean(returns^2, 22) * 252.0), {d})), {g.lower()}), "
                        f"-1)"
                    ),
                    "hypothesis": (
                        f"Bollerslev, Tauchen & Zhou (2009) Section 4.2.3: Expected VRP utilizing HAR-RV multi-component "
                        f"realized volatility forecast. Decay {d}, {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "options",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 5. Carr & Madan (2001): Model-Free Variance Swap Curvature Spanning
    # Inverse strike-squared curvature proxy: (iv_call + iv_put - 2*iv_atm) / iv_atm
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:3]:
        for g in neut_groups:
            for d in [5, 15]:
                catalog.append({
                    "pillar": "CARR_MADAN_CURVATURE_SPANNING",
                    "archetype": f"Carr_Madan_Curvature_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"group_neutralize(rank(ts_decay_linear((iv_call_30 + iv_put_30 - 2.0 * iv_atm_30) / (iv_atm_30 + 0.001), {d})), {g.lower()}), "
                        f"-1)"
                    ),
                    "hypothesis": (
                        f"Carr & Madan (2001) Section II-A: Model-free static replication curvature spanned by "
                        f"OTM option basket with 2/K^2 weights. Decay {d}, {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "options",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 6. Carr & Madan (2001): Term-Structure Slope of Replicated Variance
    # Forward variance slope (60d vs 30d model-free variance)
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:2]:
        for g in neut_groups:
            catalog.append({
                "pillar": "CARR_MADAN_TERM_VARIANCE",
                "archetype": f"Carr_Madan_Forward_Variance_Slope_{u}_{g}",
                "expression": (
                    f"trade_when(volume > adv20 * 0.80, "
                    f"group_neutralize(rank(ts_decay_linear((iv_atm_60^2 - iv_atm_30^2) / (iv_atm_30^2 + 0.001), 10)), {g.lower()}), "
                    f"-1)"
                ),
                "hypothesis": (
                    f"Carr & Madan (2001) Section III: Forward variance curve slope across replicated option "
                    f"maturities as an autonomous volatility predictor. {u}."
                ),
                "universe": u,
                "neutralization": g,
                "decay": 10,
                "category": "options",
                "source_kb": SOURCE_KB,
            })

    # ─────────────────────────────────────────────────────────────────────────
    # 7. BTZ (2009): Quarterly Cumulative Horizon VRP Predictor
    # Capturing the 3-month peak persistence documented in BTZ Figure 1 & Figure 3
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:2]:
        for g in neut_groups:
            catalog.append({
                "pillar": "BTZ_QUARTERLY_MOMENTUM_VRP",
                "archetype": f"BTZ_Quarterly_VRP_Accum_{u}_{g}",
                "expression": (
                    f"trade_when(volume > adv20 * 0.85, "
                    f"group_neutralize(rank(ts_mean((iv_atm_30^2) - ts_mean(returns^2, 22) * 252.0, 60) / (ts_std((iv_atm_30^2) - ts_mean(returns^2, 22) * 252.0, 60) + 0.001)), {g.lower()}), "
                    f"-1)"
                ),
                "hypothesis": (
                    f"Bollerslev, Tauchen & Zhou (2009) Section 4.1: Information ratio of quarterly accumulated "
                    f"Variance Risk Premium driving multi-period return predictability. {u}."
                ),
                "universe": u,
                "neutralization": g,
                "decay": 60,
                "category": "options",
                "source_kb": SOURCE_KB,
            })

    return catalog


if __name__ == "__main__":
    candidates = generate_bollerslev_vrp_dynamics_candidates()
    print(f"Generated {len(candidates)} Carr-Madan-Bollerslev VRP alpha candidates.")
    print("Sample expression:")
    print(candidates[0]["expression"])
