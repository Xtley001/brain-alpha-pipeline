"""
Bakshi, Kapadia & Madan (2003) — Stock Return Characteristics, Skew Laws, and Differential Pricing of Individual Equity Options
Source KB: docs/kb/options/bakshi_kapadia_madan_skew_kurtosis.md

Key Institutional Empirical Findings (RFS 2003):
1. Model-Free Moment Spanning:
   - Volatility contract V(t, tau): quadratic log-return payoff spanning.
   - Cubic contract W(t, tau): cubic log-return payoff, positive weight on calls, negative weight on puts.
   - Quartic contract X(t, tau): quartic log-return payoff spanning risk-neutral kurtosis.
2. The Skew Laws:
   - Individual stock skewness decomposes into systematic market skewness and idiosyncratic skewness:
     SKEW_n = w_m * SKEW_m + w_eps * SKEW_eps.
   - Since idiosyncratic shocks are symmetric or positively skewed, individual stock skews are strictly
     less negative than index skews (SKEW_n > SKEW_m).
   - This directly explains why individual stock implied volatility smiles are flatter (beta = -0.74)
     than the steep index smile (beta = -1.61).
3. Higher risk-neutral kurtosis flattens the smile in the presence of left tails.
"""
from typing import Any, Dict, List

SOURCE_KB = "docs/kb/options/bakshi_kapadia_madan_skew_kurtosis.md"


def generate_bakshi_kapadia_madan_skew_candidates() -> List[Dict[str, Any]]:
    """
    Generate paper-grounded alpha candidates from Bakshi, Kapadia & Madan (2003).
    All expressions feature balanced parentheses, valid BRAIN operators, and 100% source_kb traceability.
    """
    catalog: List[Dict[str, Any]] = []

    universes = ["TOPSP500", "TOP500", "TOP1000", "TOP2000"]
    neut_groups = ["SUBINDUSTRY", "SECTOR", "MARKET"]
    tenors = [30, 60]
    decays = [5, 10, 20]

    # ─────────────────────────────────────────────────────────────────────────
    # 1. BKM (2003): Model-Free Risk-Neutral Skewness (SKEW)
    # Cubic contract proxy: normalized (call IV - put IV) / ATM IV (Theorem 1)
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:3]:
        for g in neut_groups:
            for t in tenors:
                for d in decays[:2]:
                    catalog.append({
                        "pillar": "MODEL_FREE_SKEW_KURTOSIS",
                        "archetype": f"BKM_Skew_Proxy_t{t}_d{d}_{u}_{g}",
                        "expression": (
                            f"trade_when(volume > adv20 * 0.80, "
                            f"group_neutralize(rank(ts_decay_linear((iv_call_{t} - iv_put_{t}) / (iv_atm_{t} + 0.001), {d})), {g.lower()}), "
                            f"-1)"
                        ),
                        "hypothesis": (
                            f"Bakshi, Kapadia & Madan (2003) Theorem 1: Model-free risk-neutral skewness from cubic "
                            f"contract option spanning. {t}d tenor, decay {d}, {u}."
                        ),
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "options",
                        "source_kb": SOURCE_KB,
                    })

    # ─────────────────────────────────────────────────────────────────────────
    # 2. BKM (2003): Model-Free Risk-Neutral Kurtosis (KURT)
    # Quartic contract proxy: (OTM call + OTM put - 2 * ATM) / ATM IV (Theorem 1)
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:3]:
        for g in ["SUBINDUSTRY", "MARKET"]:
            for t in tenors:
                catalog.append({
                    "pillar": "MODEL_FREE_SKEW_KURTOSIS",
                    "archetype": f"BKM_Kurtosis_Proxy_t{t}_{u}_{g}",
                    "expression": (
                        f"group_neutralize(rank(ts_decay_linear((iv_call_{t} + iv_put_{t} - 2 * iv_atm_{t}) / (iv_atm_{t} + 0.001), 10)), {g.lower()})"
                    ),
                    "hypothesis": (
                        f"Bakshi, Kapadia & Madan (2003) Theorem 1: Model-free risk-neutral kurtosis from quartic "
                        f"contract spanning. Captures fat-tail jump pricing. {t}d tenor, {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": 10,
                    "category": "options",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 3. BKM (2003): Kurtosis-Attenuated Skewness Slope
    # Extract 19: High kurtosis flattens the smile in the presence of negative skewness
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:3]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for t in [30, 60]:
                catalog.append({
                    "pillar": "MODEL_FREE_SKEW_KURTOSIS",
                    "archetype": f"BKM_Kurt_Adj_Skew_t{t}_{u}_{g}",
                    "expression": (
                        f"group_neutralize(rank((iv_call_{t} - iv_put_{t}) / (1.0 + 0.5 * abs(iv_put_{t} - iv_atm_{t}))), {g.lower()})"
                    ),
                    "hypothesis": (
                        f"Bakshi, Kapadia & Madan (2003): Higher kurtosis flattens the smile; scaling skewness by "
                        f"tail curvature isolates pure asymmetric downside demand. {t}d tenor, {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": 5,
                    "category": "options",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 4. BKM (2003): Skew Laws Idiosyncratic Skewness Premium
    # Theorem 3: SKEW_n = w_m SKEW_m + w_eps SKEW_eps; isolating idiosyncratic skewness
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP1000"]:
        for g in neut_groups:
            catalog.append({
                "pillar": "MODEL_FREE_SKEW_KURTOSIS",
                "archetype": f"BKM_Idio_Skew_Laws_{u}_{g}",
                "expression": (
                    f"group_neutralize(rank((iv_call_30 - iv_put_30) - 0.75 * (iv_call_60 - iv_put_60)), {g.lower()})"
                ),
                "hypothesis": (
                    f"Bakshi, Kapadia & Madan (2003) Theorem 3 (Skew Laws): Idiosyncratic skewness innovation "
                    f"orthogonalized against term structure market skewness. {u}."
                ),
                "universe": u,
                "neutralization": g,
                "decay": 10,
                "category": "options",
                "source_kb": SOURCE_KB,
            })

    # ─────────────────────────────────────────────────────────────────────────
    # 5. BKM (2003): Downside Tail Risk Compensation Strategy
    # Stocks with deeply negative risk-neutral skewness earn higher subsequent risk premia (Extract 20)
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:3]:
        for g in ["SUBINDUSTRY", "MARKET"]:
            catalog.append({
                "pillar": "MODEL_FREE_SKEW_KURTOSIS",
                "archetype": f"BKM_Crash_Risk_Premium_{u}_{g}",
                "expression": (
                    f"trade_when(volume > adv20 * 0.80, "
                    f"group_neutralize(rank(-(iv_call_30 - iv_put_30)) * rank(historical_volatility_30), {g.lower()}), "
                    f"-1)"
                ),
                "hypothesis": (
                    f"Bakshi, Kapadia & Madan (2003) Extract 20: Equities subject to extreme downside jump "
                    f"hedging demand (negative skewness x high vol) command equilibrium return premia. {u}."
                ),
                "universe": u,
                "neutralization": g,
                "decay": 10,
                "category": "options",
                "source_kb": SOURCE_KB,
            })

    # ─────────────────────────────────────────────────────────────────────────
    # 6. BKM (2003): Cross-Sectional Flatness Differential
    # Table 3: Individual smiles are flatter than index; stocks with flatter smiles outperform
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500"]:
        for g in ["SUBINDUSTRY", "MARKET"]:
            catalog.append({
                "pillar": "MODEL_FREE_SKEW_KURTOSIS",
                "archetype": f"BKM_Flatness_Differential_{u}_{g}",
                "expression": (
                    f"group_neutralize(rank(abs(iv_call_30 - iv_put_30) / (iv_atm_30 + 0.001) - "
                    f"ts_mean(abs(iv_call_30 - iv_put_30) / (iv_atm_30 + 0.001), 60)), {g.lower()})"
                ),
                "hypothesis": (
                    f"Bakshi, Kapadia & Madan (2003) Table 3: Deviations from baseline smile flatness predict "
                    f"volatility risk-neutral moment repricing. {u}."
                ),
                "universe": u,
                "neutralization": g,
                "decay": 10,
                "category": "options",
                "source_kb": SOURCE_KB,
            })

    return catalog
