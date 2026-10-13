"""
An, Ang, Bali & Cakici (2014) & Baker, Bradley & Wurgler (2011)
Source KB: docs/kb/risk_models/an_ang_bali_bbw_low_vol.md

Key Institutional Empirical Findings:
1. An, Ang, Bali & Cakici (2014, Journal of Finance):
   - Implied volatility innovations: Delta CVOL = CVOL_t - CVOL_{t-1}, Delta PVOL = PVOL_t - PVOL_{t-1}.
   - Sorting on Delta CVOL produces +1.38%/month (t=5.85) spread in raw returns, +1.36%/month (t=5.22) FF3 alpha.
   - Sorting on Delta PVOL produces -1.04%/month (t=-6.40) spread in raw returns, -1.06%/month (t=-6.38) FF3 alpha.
   - Spread sort (Delta PVOL - Delta CVOL) yields -1.68%/month (t=-6.77) return spread, persisting up to 6 months.
   - Reverse predictability: +1% abnormal stock return predicts +4% call IV and +2% put IV with decreasing realized vol.
2. Baker, Bradley & Wurgler (2011, Financial Analysts Journal):
   - 41-year low-risk anomaly (1968-2008): $1 invested in lowest-volatility grew to $59.55 vs $0.58 for highest-volatility.
   - Lowest-beta grew to $60.46 vs $3.77 for highest-beta.
   - Benchmarking as limit to arbitrage: institutional managers with tracking error mandates and leverage constraints
     overweight high-beta stocks, bidding up their prices and creating persistent negative alphas.
"""
from typing import Any, Dict, List

SOURCE_KB = "docs/kb/risk_models/an_ang_bali_bbw_low_vol.md"


def generate_an_ang_bali_bbw_candidates() -> List[Dict[str, Any]]:
    """
    Generate paper-grounded alpha candidates from An, Ang, Bali & Cakici (2014)
    and Baker, Bradley & Wurgler (2011).
    All expressions feature balanced parentheses, valid BRAIN operators, and 100% source_kb traceability.
    """
    catalog: List[Dict[str, Any]] = []

    universes = ["TOPSP500", "TOP500", "TOP1000", "TOP2000"]
    neut_groups = ["SUBINDUSTRY", "SECTOR", "MARKET"]
    decays = [5, 10, 20]

    # ─────────────────────────────────────────────────────────────────────────
    # 1. An, Ang, Bali & Cakici (2014): Joint Volatility Innovation Spread
    # Delta CVOL - Delta PVOL (+1.68%/month, t=6.77 in JF 2014 Table II)
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:3]:
        for g in neut_groups:
            for d in [5, 10]:
                catalog.append({
                    "pillar": "VOLATILITY_INNOVATION_SPREAD",
                    "archetype": f"AABC_Vol_Innovation_Spread_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"group_neutralize(rank(ts_decay_linear((iv_call_30 - ts_delay(iv_call_30, 22)) - (iv_put_30 - ts_delay(iv_put_30, 22)), {d})), {g.lower()}), "
                        f"-1)"
                    ),
                    "hypothesis": (
                        f"An, Ang, Bali & Cakici (2014) Table II: Spread between call and put implied volatility "
                        f"innovations captures informed options order flow (+1.68%/mo, t=6.77). Decay {d}, {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "model",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 2. AABC (2014): Call Volatility Innovation Alpha (Delta CVOL)
    # +1.38%/month (t=5.85) in raw returns, +1.36% FF3 alpha
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:2]:
        for g in neut_groups:
            for d in [5, 10]:
                catalog.append({
                    "pillar": "CALL_VOL_INNOVATION",
                    "archetype": f"AABC_Call_Vol_Innovation_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"group_neutralize(rank(ts_decay_linear(iv_call_30 - ts_delay(iv_call_30, 22), {d})), {g.lower()}), "
                        f"-1)"
                    ),
                    "hypothesis": (
                        f"An, Ang, Bali & Cakici (2014) Table III: Bullish informed call buying creates Delta CVOL "
                        f"innovations forecasting positive spot returns (+1.38%/mo, t=5.85). Decay {d}, {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "model",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 3. AABC (2014): Put Volatility Innovation Penalty (-Delta PVOL)
    # -1.04%/month (t=-6.40) in raw returns, -1.06% FF3 alpha
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:2]:
        for g in neut_groups:
            for d in [5, 10]:
                catalog.append({
                    "pillar": "PUT_VOL_INNOVATION_PENALTY",
                    "archetype": f"AABC_Put_Vol_Penalty_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"group_neutralize(rank(-ts_decay_linear(iv_put_30 - ts_delay(iv_put_30, 22), {d})), {g.lower()}), "
                        f"-1)"
                    ),
                    "hypothesis": (
                        f"An, Ang, Bali & Cakici (2014) Table III: Bearish informed put buying creates Delta PVOL "
                        f"innovations forecasting negative spot returns (-1.04%/mo, t=-6.40). Decay {d}, {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "model",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 4. Baker, Bradley & Wurgler (2011): 41-Year Low-Volatility Anomaly
    # Lowest-volatility quintile grew to $59.55 vs $0.58 for highest-volatility
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:3]:
        for g in neut_groups:
            for w in [126, 252]:
                catalog.append({
                    "pillar": "BBW_LOW_VOLATILITY_ANOMALY",
                    "archetype": f"BBW_Low_Vol_w{w}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.75, "
                        f"group_neutralize(rank(-ts_std(returns, {w})), {g.lower()}), "
                        f"-1)"
                    ),
                    "hypothesis": (
                        f"Baker, Bradley & Wurgler (2011) FAJ Figure 1: 41-year low-volatility anomaly ($59.55 vs $0.58) "
                        f"driven by benchmarking limits to arbitrage. Window {w}, {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": 20,
                    "category": "model",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 5. BBW (2011): Low-Beta Benchmark Limit to Arbitrage Alpha
    # Lowest-beta grew to $60.46 vs $3.77 for highest-beta
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:2]:
        for g in neut_groups:
            catalog.append({
                "pillar": "BBW_LOW_BETA_ARBITRAGE",
                "archetype": f"BBW_Low_Beta_Anomaly_{u}_{g}",
                "expression": (
                    f"trade_when(volume > adv20 * 0.80, "
                    f"group_neutralize(rank(-ts_covariance(returns, group_mean(returns, 1, market), 252) / (ts_variance(group_mean(returns, 1, market), 252) + 0.0001)), {g.lower()}), "
                    f"-1)"
                ),
                "hypothesis": (
                    f"Baker, Bradley & Wurgler (2011) Figure 1 Panel C: Low-beta anomaly ($60.46 vs $3.77) "
                    f"resulting from delegated institutional manager benchmarking constraints. {u}."
                ),
                "universe": u,
                "neutralization": g,
                "decay": 20,
                "category": "model",
                "source_kb": SOURCE_KB,
            })

    # ─────────────────────────────────────────────────────────────────────────
    # 6. BBW (2011) & AABC (2014): Interacting Informed Option Signal with Low Volatility
    # Long low-volatility stocks with high call innovation, short high-vol with put innovation
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:2]:
        for g in neut_groups:
            catalog.append({
                "pillar": "BBW_AABC_JOINT_INTERACTION",
                "archetype": f"BBW_AABC_Joint_Interaction_{u}_{g}",
                "expression": (
                    f"trade_when(volume > adv20 * 0.80, "
                    f"group_neutralize(rank(ts_rank((iv_call_30 - ts_delay(iv_call_30, 22)) - (iv_put_30 - ts_delay(iv_put_30, 22)), 40) - ts_rank(ts_std(returns, 126), 40)), {g.lower()}), "
                    f"-1)"
                ),
                "hypothesis": (
                    f"Baker, Bradley & Wurgler (2011) and An, Ang, Bali & Cakici (2014): Joint interaction combining "
                    f"informed option innovations with institutional low-risk premium. {u}."
                ),
                "universe": u,
                "neutralization": g,
                "decay": 20,
                "category": "model",
                "source_kb": SOURCE_KB,
            })

    # ─────────────────────────────────────────────────────────────────────────
    # 7. AABC (2014): Reverse Predictability Alpha (Uncertainty Resolution)
    # High abnormal stock return with subsequent volatility compression
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:2]:
        for g in neut_groups:
            catalog.append({
                "pillar": "AABC_UNCERTAINTY_RESOLUTION",
                "archetype": f"AABC_Uncertainty_Resolution_{u}_{g}",
                "expression": (
                    f"trade_when(volume > adv20 * 0.85, "
                    f"group_neutralize(rank(ts_rank(ts_decay_linear(returns, 22), 60) * ts_rank(-ts_std(returns, 22), 60)), {g.lower()}), "
                    f"-1)"
                ),
                "hypothesis": (
                    f"An, Ang, Bali & Cakici (2014) Section III: Informed trading resolves future cash flow uncertainty, "
                    f"causing subsequent realized volatility compression in winner stocks. {u}."
                ),
                "universe": u,
                "neutralization": g,
                "decay": 20,
                "category": "model",
                "source_kb": SOURCE_KB,
            })

    return catalog


if __name__ == "__main__":
    candidates = generate_an_ang_bali_bbw_candidates()
    print(f"Generated {len(candidates)} An-Ang-Bali-BBW alpha candidates.")
    print("Sample expression:")
    print(candidates[0]["expression"])
