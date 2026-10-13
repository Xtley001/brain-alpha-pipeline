"""
Bali & Hovakimian (2009) — Volatility Spreads & Expected Stock Returns
Delisle, Lee & Mauck (2011) — The Dynamic Relation Between Short Sellers, Option Traders, and Aggregate Returns
Source KB: docs/kb/options/bali_hovakimian_delisle_vol_spreads.md

Key Institutional Empirical Findings:
1. Bali & Hovakimian (2009, Management Science):
   - PC3 (Call-Put Implied Volatility Spread CVol - PVol, corr = 0.937) generates +1.1% to +1.4% per month
     abnormal return (t > 3.0 to 3.7). High CVol - PVol reflects upward informed demand / limits to short arbitrage.
   - PC2 (Realized - Implied Volatility Spread RVol - IVol, corr = 0.896) strongly and negatively predicts
     cross-sectional returns (-50 to -90 bps/mo, t = -2.0 to -2.8), proxying for Merton ICAPM volatility innovations.
2. Delisle, Lee & Mauck (2011, JBF):
   - Option trading and short selling are dynamic complements driven by delta-hedging market makers.
   - Option traders are forward-looking informed; short sellers are backward-looking momentum followers.
   - Option-to-Stock Volume Ratio (O/S) and Call/Put open interest lead future equity returns and short interest.
"""
from typing import Any, Dict, List

SOURCE_KB = "docs/kb/options/bali_hovakimian_delisle_vol_spreads.md"


def generate_bali_hovakimian_vol_spread_candidates() -> List[Dict[str, Any]]:
    """
    Generate paper-grounded alpha candidates from Bali-Hovakimian (2009) and Delisle et al. (2011).
    All expressions feature balanced parentheses, valid BRAIN operators, and 100% source_kb traceability.
    """
    catalog: List[Dict[str, Any]] = []

    universes = ["TOPSP500", "TOP500", "TOP1000", "TOP2000"]
    neut_groups = ["SUBINDUSTRY", "SECTOR", "MARKET"]
    tenors = [30, 60]
    decays = [5, 10, 20]

    # ─────────────────────────────────────────────────────────────────────────
    # 1. BALI & HOVAKIMIAN (2009): Call-Put Implied Volatility Spread (PC3)
    # Long high CVol - PVol, short low CVol - PVol (+1.1% to +1.4%/mo, t > 3.0)
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:3]:
        for g in neut_groups:
            for t in tenors:
                for d in decays[:2]:
                    catalog.append({
                        "pillar": "OPTIONS_VOL_SPREAD",
                        "archetype": f"Bali_CP_Spread_t{t}_d{d}_{u}_{g}",
                        "expression": (
                            f"trade_when(volume > adv20 * 0.80, "
                            f"group_neutralize(rank(ts_decay_linear(iv_call_{t} - iv_put_{t}, {d})), {g.lower()}), "
                            f"-1)"
                        ),
                        "hypothesis": (
                            f"Bali & Hovakimian (2009): High call-put IV spread indicates upward informed demand. "
                            f"1.1-1.4% monthly spread (t>3.0). {t}d tenor, decay {d}, {u}."
                        ),
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "options",
                        "source_kb": SOURCE_KB,
                    })

    # ─────────────────────────────────────────────────────────────────────────
    # 2. BALI & HOVAKIMIAN (2009): Normalized Volatility Spread (Spread / ATM IV)
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "MARKET"]:
            for t in [30, 60]:
                catalog.append({
                    "pillar": "OPTIONS_VOL_SPREAD",
                    "archetype": f"Bali_Norm_Spread_t{t}_{u}_{g}",
                    "expression": (
                        f"group_neutralize(rank((iv_call_{t} - iv_put_{t}) / (iv_atm_{t} + 0.001)), {g.lower()})"
                    ),
                    "hypothesis": (
                        f"Bali & Hovakimian (2009): Normalized call-put skew tilt scaled by ATM volatility level. "
                        f"{t}d tenor, {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": 5,
                    "category": "options",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 3. BALI & HOVAKIMIAN (2009): Realized - Implied Volatility Spread (PC2)
    # High RVol - IVol -> Volatility shock / deterioration in investment opportunities -> Lower return
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:3]:
        for g in neut_groups:
            for t in tenors:
                catalog.append({
                    "pillar": "OPTIONS_VOL_SPREAD",
                    "archetype": f"Bali_RVol_IVol_Shock_t{t}_{u}_{g}",
                    "expression": (
                        f"group_neutralize(rank(-(historical_volatility_{t} - iv_atm_{t})), {g.lower()})"
                    ),
                    "hypothesis": (
                        f"Bali & Hovakimian (2009) PC2: Realized-Implied vol spread negatively predicts returns. "
                        f"-50 to -90 bps/mo (t=-2.0 to -2.8). Volatility innovation hedging. {t}d tenor, {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": 10,
                    "category": "options",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 4. DELISLE, LEE & MAUCK (2011): Option-to-Stock Volume Ratio (O/S)
    # Informed leverage-seeking option volume leads stock returns
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:3]:
        for g in ["SUBINDUSTRY", "MARKET"]:
            for d in [5, 10]:
                catalog.append({
                    "pillar": "OPTIONS_VOL_SPREAD",
                    "archetype": f"Delisle_OS_Ratio_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.75, "
                        f"group_neutralize(rank(ts_decay_linear(option_volume * 100 / (volume + 1), {d})), {g.lower()}), "
                        f"-1)"
                    ),
                    "hypothesis": (
                        f"Delisle et al. (2011): Dollar option volume to stock volume (O/S) leads aggregate equity "
                        f"returns; option traders possess forward-looking private information. Decay {d}, {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "options",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 5. DELISLE, LEE & MAUCK (2011): Call vs Put Open Interest Growth Differential
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP1000"]:
        for g in neut_groups:
            catalog.append({
                "pillar": "OPTIONS_VOL_SPREAD",
                "archetype": f"Delisle_OI_Differential_{u}_{g}",
                "expression": (
                    f"group_neutralize(rank(ts_delta(call_open_interest, 10) - ts_delta(put_open_interest, 10)), {g.lower()})"
                ),
                "hypothesis": (
                    f"Delisle et al. (2011): Dynamic shifts in call vs put open interest capture forward-looking "
                    f"contract positioning relative to backward-looking short interest. {u}."
                ),
                "universe": u,
                "neutralization": g,
                "decay": 10,
                "category": "options",
                "source_kb": SOURCE_KB,
            })

    # ─────────────────────────────────────────────────────────────────────────
    # 6. INTERACTION: Bali Call-Put Spread Conditioned on Short Borrow Constraints
    # Interacting informed option skew with backward-looking short positioning
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:2]:
        for g in ["SUBINDUSTRY", "MARKET"]:
            for t in [30, 60]:
                catalog.append({
                    "pillar": "OPTIONS_VOL_SPREAD",
                    "archetype": f"Bali_Delisle_Informed_Short_Squeeze_t{t}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"group_neutralize(signed_power(rank(iv_call_{t} - iv_put_{t}), 0.5) * "
                        f"(1.0 - rank(short_interest / (float_shares + 1))), {g.lower()}), "
                        f"-1)"
                    ),
                    "hypothesis": (
                        f"Bali (2009) & Delisle (2011) Interaction: Bullish call-put spread when short sellers "
                        f"are heavily crowded creates powerful asymmetric return continuation. {t}d tenor, {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": 10,
                    "category": "options",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 7. INTERACTION: Volatility Innovation Spread interacted with O/S Volume Ratio
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            catalog.append({
                "pillar": "OPTIONS_VOL_SPREAD",
                "archetype": f"Bali_Delisle_Vol_Shock_OS_Filter_{u}_{g}",
                "expression": (
                    f"group_neutralize(rank(-(historical_volatility_30 - iv_atm_30)) * "
                    f"rank(option_volume * 100 / (volume + 1)), {g.lower()})"
                ),
                "hypothesis": (
                    f"Bali (2009) PC2 volatility shock hedge combined with Delisle (2011) informed option "
                    f"volume confirmation. {u}."
                ),
                "universe": u,
                "neutralization": g,
                "decay": 10,
                "category": "options",
                "source_kb": SOURCE_KB,
            })

    return catalog
