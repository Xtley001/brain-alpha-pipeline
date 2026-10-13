"""
Ni, Pearson & Poteshman (2005) & Michael, Cucuringu & Howison (2020)
Source KB: docs/kb/options/ni_pearson_pinning_cucuringu_flow.md

Key Institutional Empirical Findings:
1. Ni, Pearson & Poteshman (2005, JFE):
   - Expiration date strike price clustering (z = 8.15): closing prices cluster at strike prices on expiration Fridays.
   - Return deviation lower bound: average return altered by >= 16.5 bps per expiration ($9.1B market cap shift).
   - Avellaneda & Lipkin (2003) Delta-Hedge Restoring Force:
     dDelta/dt approx N'(d1) * ln(S/K) / (2 * sigma * (T-t)^(3/2)).
     When market makers are net long options, hedging exerts a mean-reverting stabilizing force pulling S -> K.
   - Price manipulation by written option holders: stock is actively pinned slightly OTM to prevent exercise liabilities.
2. Michael, Cucuringu & Howison (2020, Oxford):
   - Normalized Option Volume Imbalance (OVI):
     OVI = (V_Up - V_Down) / (V_Up + V_Down) in [-1, 1], where V_Up = CallBuy + PutSell, V_Down = CallSell + PutBuy.
   - Strongest overnight return predictability (CL -> tmOP) stems from Market Maker and Customer OVI (SR 3.5 - 4.4).
   - Put option volume carries significantly higher informational content than call option volume.
   - High-IV option contracts carry the vast majority of directional predictive power.
"""
from typing import Any, Dict, List

SOURCE_KB = "docs/kb/options/ni_pearson_pinning_cucuringu_flow.md"


def generate_ni_pearson_pinning_candidates() -> List[Dict[str, Any]]:
    """
    Generate paper-grounded alpha candidates from Ni, Pearson & Poteshman (2005)
    and Michael, Cucuringu & Howison (2020).
    All expressions feature balanced parentheses, valid BRAIN operators, and 100% source_kb traceability.
    """
    catalog: List[Dict[str, Any]] = []

    universes = ["TOPSP500", "TOP500", "TOP1000", "TOP2000"]
    neut_groups = ["SUBINDUSTRY", "SECTOR", "MARKET"]
    decays = [3, 5, 10]

    # ─────────────────────────────────────────────────────────────────────────
    # 1. Ni, Pearson & Poteshman (2005): Strike Pinning Restoring Force
    # Avellaneda-Lipkin (2003) restoring force pulling price towards strike
    # Strike approximation on $5.0 grid: round(close / 5.0) * 5.0
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:3]:
        for g in neut_groups:
            for d in [3, 5]:
                catalog.append({
                    "pillar": "STRIKE_PINNING_RESTORING_FORCE",
                    "archetype": f"NPP_Strike_Restoring_Force_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"group_neutralize(rank(ts_decay_linear(-(close - round(close / 5.0) * 5.0) / (close * (ts_std(returns, 20) + 0.001)), {d})), {g.lower()}), "
                        f"-1)"
                    ),
                    "hypothesis": (
                        f"Ni, Pearson & Poteshman (2005) / Avellaneda & Lipkin (2003): Market-maker delta rebalancing "
                        f"exerts restoring force pulling price towards nearest strike. Decay {d}, {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "options",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 2. NPP (2005): Expiration Return Variance Compression
    # Close-to-strike stocks experience suppressed volatility and return truncation
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:2]:
        for g in neut_groups:
            for w in [5, 10]:
                catalog.append({
                    "pillar": "EXPIRATION_VOL_COMPRESSION",
                    "archetype": f"NPP_Vol_Compression_w{w}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.75, "
                        f"group_neutralize(rank(-ts_std(returns, {w}) * (1.0 - abs(close - round(close / 5.0) * 5.0) / (close + 0.001))), {g.lower()}), "
                        f"-1)"
                    ),
                    "hypothesis": (
                        f"Ni, Pearson & Poteshman (2005): Return compression near strike prices due to market-maker "
                        f"pinning and hedging constraints. Window {w}, {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": 5,
                    "category": "options",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 3. Michael, Cucuringu & Howison (2020): Normalized Option Volume Imbalance (OVI)
    # Directional option volume imbalance: (opt_vol_call - opt_vol_put) / (opt_vol_call + opt_vol_put)
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:3]:
        for g in neut_groups:
            for d in decays:
                catalog.append({
                    "pillar": "OPTION_VOLUME_IMBALANCE",
                    "archetype": f"MCH_OVI_Directional_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"group_neutralize(rank(ts_decay_linear((opt_vol_call - opt_vol_put) / (opt_vol_call + opt_vol_put + 0.001), {d})), {g.lower()}), "
                        f"-1)"
                    ),
                    "hypothesis": (
                        f"Michael, Cucuringu & Howison (2020) Equation 1: Normalized Option Volume Imbalance predicts "
                        f"directional equity price movements. Decay {d}, {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "options",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 4. MCH (2020): Put Informational Dominance Imbalance (PIDI)
    # Informational content of put volume exceeds calls; downside positioning predictive
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:2]:
        for g in neut_groups:
            for d in [3, 5]:
                catalog.append({
                    "pillar": "PUT_INFORMATIONAL_DOMINANCE",
                    "archetype": f"MCH_Put_Dominance_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"group_neutralize(rank(-ts_decay_linear(opt_vol_put / (opt_vol_call + opt_vol_put + 0.001), {d})), {g.lower()}), "
                        f"-1)"
                    ),
                    "hypothesis": (
                        f"Michael, Cucuringu & Howison (2020) Section 6: Put option volume carries higher informational "
                        f"content than calls for directional forecasting. Decay {d}, {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "options",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 5. MCH (2020): High-IV Option Volume Interaction
    # OVI predictability concentrated in high implied volatility contracts
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:2]:
        for g in neut_groups:
            for d in [5, 10]:
                catalog.append({
                    "pillar": "HIGH_IV_OVI_INTERACTION",
                    "archetype": f"MCH_High_IV_OVI_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"group_neutralize(rank(ts_rank(iv_atm_30, 40) * ts_decay_linear((opt_vol_call - opt_vol_put) / (opt_vol_call + opt_vol_put + 0.001), {d})), {g.lower()}), "
                        f"-1)"
                    ),
                    "hypothesis": (
                        f"Michael, Cucuringu & Howison (2020) Section 6: Directional predictability concentrated in high-IV "
                        f"option contracts. Decay {d}, {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "options",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 6. MCH (2020): Overnight Return Predictability from Option Flow
    # Predicting overnight gap follow-through conditioned on OVI
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:2]:
        for g in neut_groups:
            for d in [3, 5]:
                catalog.append({
                    "pillar": "OVI_OVERNIGHT_GAP",
                    "archetype": f"MCH_OVI_Overnight_Gap_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"group_neutralize(rank(ts_decay_linear((open / ts_delay(close, 1) - 1.0) * ((opt_vol_call - opt_vol_put) / (opt_vol_call + opt_vol_put + 0.001)), {d})), {g.lower()}), "
                        f"-1)"
                    ),
                    "hypothesis": (
                        f"Michael, Cucuringu & Howison (2020) Section 4: Overnight excess returns (CL -> tmOP) predicted "
                        f"by directional option volume flow. Decay {d}, {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "options",
                    "source_kb": SOURCE_KB,
                })

    return catalog


if __name__ == "__main__":
    candidates = generate_ni_pearson_pinning_candidates()
    print(f"Generated {len(candidates)} Ni-Pearson-Michael-Cucuringu alpha candidates.")
    print("Sample expression:")
    print(candidates[0]["expression"])
