"""
Pan & Poteshman (2006) — Informed Put-Call Volume Ratio
Garleanu, Pedersen & Poteshman (2009) — Demand-Based Option Pricing
Bali & Hovakimian (2009) — Volatility Spreads & Expected Stock Returns
Bakshi, Kapadia & Madan (2003) — Model-Free Skew & Kurtosis Laws
Source KB: docs/kb/options/pan_poteshman_2006_pcr_informed.md

Core Finding (Pan & Poteshman 2006):
    Open-buy put-call ratio (PCR) constructed from customer order flow strongly predicts
    future underlying equity returns.
    Table 4: Next-day slope coefficient = -59.31 bps (t-stat = -32.82).
    Controlling for turnover, spread, and 5-day short-term reversal retains a -55.62 bps slope (t = -31.56).
    Stocks with low PCR (bullish open-buy calls) outperform high PCR (bearish open-buy puts)
    by >40 bps on day t+1 and >100 bps over week t+1.
"""
from typing import Any, Dict, List

SOURCE_KB = "docs/kb/options/pan_poteshman_2006_pcr_informed.md"


def generate_pan_poteshman_pcr_candidates() -> List[Dict[str, Any]]:
    """
    Pan & Poteshman (2006) + Garleanu-Pedersen (2009) + Bali-Hovakimian (2009) + BKM (2003).
    Citation: JF 2006, Table 4, Table 5, Table 6.
    """
    catalog: List[Dict[str, Any]] = []

    universes   = ["TOPSP500", "TOP500", "TOP1000", "TOP200"]
    neut_groups = ["SUBINDUSTRY", "SECTOR", "MARKET"]
    tenors      = [30, 60, 90]
    decays      = [5, 10, 14]

    # ─────────────────────────────────────────────────────────────────────────
    # PAN & POTESHMAN (2006): Informed Put-Call Ratio (Extract 3 & 5, Table 4)
    # PCR = put_vol / (put_vol + call_vol)
    # Low PCR -> bullish informed flow; high PCR -> bearish informed flow.
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for t in tenors:
                for d in decays:
                    catalog.append({
                        "pillar": "PCR_INFORMED",
                        "archetype": f"PCR_Pan_t{t}_d{d}_{u}_{g}",
                        "expression": (
                            f"trade_when(volume > adv20 * 0.85, "
                            f"trade_when(abs(rank(ts_decay_linear(pcr_vol_{t}, {d})) - 0.5) > 0.20, "
                            f"group_neutralize(signed_power(rank(-ts_decay_linear(pcr_vol_{t}, {d})), 0.5), {g.lower()}), "
                            f"-1), -1)"
                        ),
                        "hypothesis": (
                            f"Pan-Poteshman2006 Table 4: low PCR = bullish informed flow; high PCR = bearish. "
                            f"-59bps next-day slope (t=-32.82). {t}d tenor, {u}."
                        ),
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "options",
                        "source_kb": SOURCE_KB,
                    })

    # ─────────────────────────────────────────────────────────────────────────
    # PAN & POTESHMAN: PCR x Volume-to-OI Surge (Extract 7)
    # Volume surge relative to existing open interest isolates new opening flow.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for t in [30, 60]:
                for d in [5, 10]:
                    catalog.append({
                        "pillar": "PCR_URGENCY_AMPLIFIED",
                        "archetype": f"PCR_Urgency_t{t}_d{d}_{u}_{g}",
                        "expression": (
                            f"trade_when(volume > adv20 * 0.85, "
                            f"trade_when(rank(ts_decay_linear(pcr_vol_{t} / (pcr_oi_{t} + 0.001), {d})) < 0.25, "
                            f"group_neutralize(rank(-ts_decay_linear(pcr_vol_{t}, {d})), {g.lower()}), "
                            f"-1), -1)"
                        ),
                        "hypothesis": (
                            f"Pan-Poteshman2006 + GPP2009: informed urgency gate — "
                            f"bullish PCR (low) AND high volume/OI ratio = urgent private opening info. {u}."
                        ),
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "options",
                        "source_kb": SOURCE_KB,
                    })

    # ─────────────────────────────────────────────────────────────────────────
    # GARLEANU-PEDERSEN-POTESHMAN (2009): Open Interest Demand Pressure
    # OI surge vs quiet underlying -> inventory build -> IV elevated -> mean-revert
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for t in [30, 60]:
                for d in [5, 10, 14]:
                    catalog.append({
                        "pillar": "GPP_DEMAND_PRESSURE",
                        "archetype": f"GPP_OI_Pressure_t{t}_d{d}_{u}_{g}",
                        "expression": (
                            f"trade_when(volume > adv20 * 0.85, "
                            f"trade_when(abs(rank(ts_decay_linear("
                            f"ts_delta(pcr_oi_{t}, 5) / (ts_std_dev(returns, 20) + 0.001), {d}"
                            f")) - 0.5) > 0.25, "
                            f"group_neutralize(signed_power(rank(-ts_decay_linear("
                            f"ts_delta(pcr_oi_{t}, 5) / (ts_std_dev(returns, 20) + 0.001), {d}"
                            f")), 0.5), {g.lower()}), -1), -1)"
                        ),
                        "hypothesis": (
                            f"GPP2009: Delta OI / realized_vol -> inventory pressure signal. "
                            f"OI surge in quiet market = demand-driven IV premium -> mean-revert. {u}."
                        ),
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "options",
                        "source_kb": SOURCE_KB,
                    })

    # ─────────────────────────────────────────────────────────────────────────
    # BALI & HOVAKIMIAN (2009): Volatility Spread Principal Components
    # PC2: Realized Vol Spread = IV - RV (Variance Risk Premium component)
    # PC3: Call IV - Put IV spread -> directional expectations signal
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for t in tenors:
                for d in [10, 14]:
                    # PC2: Realized-Implied Vol Spread (VRP)
                    catalog.append({
                        "pillar": "BH_VRP_SPREAD",
                        "archetype": f"BH_VRP_t{t}_d{d}_{u}_{g}",
                        "expression": (
                            f"trade_when(volume > adv20 * 0.85, "
                            f"trade_when(abs(rank(ts_decay_linear("
                            f"implied_volatility_mean_{t} - ts_std_dev(returns, 20) * 15.87, {d}"
                            f")) - 0.5) > 0.25, "
                            f"group_neutralize(signed_power(rank(-ts_decay_linear("
                            f"implied_volatility_mean_{t} - ts_std_dev(returns, 20) * 15.87, {d}"
                            f")), 0.5), {g.lower()}), -1), -1)"
                        ),
                        "hypothesis": (
                            f"Bali-Hovakimian2009 PC2: IV - RV spread (VRP). "
                            f"High IV vs realized vol -> IV is expensive -> revert to fair value -> negative. {u}."
                        ),
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "options",
                        "source_kb": SOURCE_KB,
                    })

                    # PC3: Call-Put IV Spread (directional expectations)
                    catalog.append({
                        "pillar": "BH_CALL_PUT_SPREAD",
                        "archetype": f"BH_CPSpread_t{t}_d{d}_{u}_{g}",
                        "expression": (
                            f"trade_when(volume > adv20 * 0.85, "
                            f"trade_when(abs(rank(ts_decay_linear("
                            f"(implied_volatility_call_{t} - implied_volatility_put_{t}) / (implied_volatility_mean_{t} + 0.001), {d}"
                            f")) - 0.5) > 0.25, "
                            f"group_neutralize(signed_power(rank(ts_decay_linear("
                            f"(implied_volatility_call_{t} - implied_volatility_put_{t}) / (implied_volatility_mean_{t} + 0.001), {d}"
                            f")), 0.5), {g.lower()}), -1), -1)"
                        ),
                        "hypothesis": (
                            f"Bali-Hovakimian2009 PC3: Call IV > Put IV = bullish directional tilt in IV surface. "
                            f"Opposite sign to XZZ smirk — isolates directional expectations only. {u}."
                        ),
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "options",
                        "source_kb": SOURCE_KB,
                    })

    # ─────────────────────────────────────────────────────────────────────────
    # BAKSHI-KAPADIA-MADAN (2003): Risk-Neutral Skewness Proxy
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for t in [30, 60, 90]:
                for d in [10, 14]:
                    catalog.append({
                        "pillar": "BKM_RNSKEW",
                        "archetype": f"BKM_RNSkew_t{t}_d{d}_{u}_{g}",
                        "expression": (
                            f"trade_when(volume > adv20 * 0.85, "
                            f"trade_when(abs(rank(ts_decay_linear("
                            f"(implied_volatility_put_{t} - implied_volatility_call_{t}) / "
                            f"(implied_volatility_mean_{t} + 0.001) * (1 + ts_std_dev(returns, 60) * 2), {d}"
                            f")) - 0.5) > 0.25, "
                            f"group_neutralize(signed_power(rank(-ts_decay_linear("
                            f"(implied_volatility_put_{t} - implied_volatility_call_{t}) / "
                            f"(implied_volatility_mean_{t} + 0.001) * (1 + ts_std_dev(returns, 60) * 2), {d}"
                            f")), 0.5), {g.lower()}), -1), -1)"
                        ),
                        "hypothesis": (
                            f"BKM2003: Risk-neutral skew proxy — smirk * vol-level scaling. "
                            f"High RNSK = expensive downside protection = negative return predictor. {u}."
                        ),
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "options",
                        "source_kb": SOURCE_KB,
                    })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 6: PCR x Short-Term Price Reversal (Extract 5 & 12, Table 4)
    # Table 4 proves PCR slope remains -55.62 bps (t=-31.56) controlling for reversal.
    # Bullish call buying into short-term dip produces maximum rebound.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [5, 10]:
                catalog.append({
                    "pillar": "PCR_X_REVERSAL",
                    "archetype": f"PCR_Reversal_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.85, "
                        f"group_neutralize("
                        f"rank(-ts_decay_linear(pcr_vol_30, {d})) * "
                        f"rank(-ts_decay_linear(ts_delta(close, 5), 5)), "
                        f"{g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"Pan-Poteshman2006 Table 4: Low PCR + recent 5-day price pullback. "
                        f"Informed accumulation into dip; -55.62bps slope with reversal control (t=-31.56). {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "options",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 7: Multi-Tenor PCR Term Spread Urgency (Extract 10)
    # Tactical 30d informed flow exceeding structural 90d hedging flow.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [5, 10]:
                catalog.append({
                    "pillar": "PCR_TERM_SPREAD_URGENCY",
                    "archetype": f"PCR_TermSpread_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.85, "
                        f"group_neutralize("
                        f"signed_power(rank(-ts_decay_linear(pcr_vol_30 - pcr_vol_90, {d})), 0.5), "
                        f"{g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"Pan-Poteshman2006 Extract 10: Term structure of PCR (30d vs 90d). "
                        f"Short-dated PCR surge isolates near-term private event information over hedging. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "options",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 8: High Turnover Surge Gated PCR (Extract 5 & 13, Table 4)
    # High equity turnover confirms active institutional reallocation.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [5, 10]:
                catalog.append({
                    "pillar": "PCR_TURNOVER_SURGE",
                    "archetype": f"PCR_TurnoverSurge_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 1.25, "
                        f"group_neutralize("
                        f"signed_power(rank(-ts_decay_linear(pcr_vol_30, {d})), 0.5), "
                        f"{g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"Pan-Poteshman2006 Table 4 turnover interaction: PCR signal gated on volume > 1.25 ADV. "
                        f"High volume confirms institutional participation over retail noise. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "options",
                    "source_kb": SOURCE_KB,
                })

    return catalog
