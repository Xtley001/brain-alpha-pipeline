"""
Pan & Poteshman (2006) — Informed Put-Call Volume Ratio
Garleanu, Pedersen & Poteshman (2009) — Demand-Based Option Pricing
Bali & Hovakimian (2009) — Volatility Spreads & Expected Stock Returns
Bakshi, Kapadia & Madan (2003) — Model-Free Skew & Kurtosis Laws

Papers:
  1. Pan & Poteshman (2006): "The Information in Option Volume for Future Stock Prices" — RFS
     Core: Open-buy PCR (put vol / (put+call vol)) from PUBLIC CUSTOMER orders predicts
     next-day returns. Low PCR → bullish informed flow → +40bps next day.
     PCR = Put_Open_Buy_Vol / (Put_Open_Buy_Vol + Call_Open_Buy_Vol)
     BRAIN field: pcr_vol_{tenor}, pcr_oi_{tenor}

  2. Garleanu-Pedersen-Poteshman (2009): "Demand-Based Option Pricing" — RFS
     Core: End-user demand pressure forces market makers to warehouse un-hedgeable
     jump/vol risk → option prices deviate from Black-Scholes by a demand-pressure term.
     Key insight: when OI surges anomalously against quiet underlying price, market makers
     are accumulating inventory → IV premium → mean-revert as inventory clears.
     BRAIN: ts_delta(open_interest, 5) / (volume + 0.001) → inventory pressure signal

  3. Bali & Hovakimian (2009): "Volatility Spreads and Expected Stock Returns" — Management Science
     Core: 3 principal components of volatility:
       PC1: Level (realized vol) — unrelated to returns cross-sectionally
       PC2: RV−IV spread (variance risk premium) → POSITIVE return predictor
       PC3: Call IV − Put IV spread → POSITIVE return predictor (contrarian to skew)
     Note: PC3 sign is OPPOSITE to XZZ smirk (different regime/sorting methodology)

  4. Bakshi-Kapadia-Madan (2003): "Stock Return Characteristics, Skew Laws, and the
     Differential Pricing of Individual Equity Options" — RFS
     Core: Model-free risk-neutral moments derived from entire option chain:
       RNSK = E^Q[r³] / E^Q[r²]^(3/2)  ← risk-neutral skewness
       RNKURT = E^Q[r⁴] / E^Q[r²]²     ← risk-neutral kurtosis
     High RNSK (right-skewed distribution) → negative future returns (overpriced upside)
     High RNKURT (fat tails) → negative future returns
     BRAIN: implied_vol_skew (proxy for RNSK), implied_vol_kurtosis if available
"""
from typing import Any, Dict, List


def generate_pan_poteshman_pcr_candidates() -> List[Dict[str, Any]]:
    """Pan & Poteshman (2006) + Garleanu-Pedersen (2009) + Bali-Hovakimian (2009) + BKM (2003)."""
    catalog: List[Dict[str, Any]] = []

    universes   = ["TOPSP500", "TOP500", "TOP1000", "TOP200"]
    neut_groups = ["SUBINDUSTRY", "SECTOR", "MARKET"]
    tenors      = [30, 60, 90]
    decays      = [5, 10, 14]

    # ─────────────────────────────────────────────────────────────────────────
    # PAN & POTESHMAN (2006): Informed Put-Call Ratio
    # PCR = put_vol / (put_vol + call_vol) — from OPEN-BUY orders only (informed)
    # Low PCR → bullish → next-day +40bps abnormal return
    # BRAIN: pcr_vol_{tenor} is the best proxy (not decomposed by order type)
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
                            f"Pan-Poteshman2006: low PCR = bullish informed flow; high PCR = bearish. "
                            f"+40bps next day from informed open-buy customers. {t}d tenor, {u}."
                        ),
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "options",
                    })

    # ─────────────────────────────────────────────────────────────────────────
    # PAN & POTESHMAN: PCR × Volume-to-OI Surge (Garleanu cross-reference)
    # When PCR is low (bullish) AND volume/OI is unusually high (informed urgency),
    # the signal is amplified — urgency implies higher private information content.
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
                            f"bullish PCR (low) AND high volume/OI ratio = urgent private info. {u}."
                        ),
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "options",
                    })

    # ─────────────────────────────────────────────────────────────────────────
    # GARLEANU-PEDERSEN-POTESHMAN (2009): Open Interest Demand Pressure
    # Demand pressure from end-users forces dealer IV premium.
    # OI surge vs quiet underlying → inventory build → IV elevated → mean-revert
    # Signal: delta_OI / underlying_price_vol → IV inventory pressure
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
                            f"GPP2009: ΔOI / realized_vol → inventory pressure signal. "
                            f"OI surge in quiet market = demand-driven IV premium → mean-revert. {u}."
                        ),
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "options",
                    })

    # ─────────────────────────────────────────────────────────────────────────
    # BALI & HOVAKIMIAN (2009): Volatility Spread Principal Components
    # PC2: Realized Vol Spread = IV - RV (Variance Risk Premium component)
    #      High IV-RV spread → stock has large VRP → positive future return predictor
    # PC3: Call IV - Put IV spread → directional expectations signal
    #      High Call IV vs Put IV → bullish expectations → positive future returns
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
                            f"High IV vs realized vol → IV is 'expensive' → revert to fair value → negative. {u}."
                        ),
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "options",
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
                    })

    # ─────────────────────────────────────────────────────────────────────────
    # BAKSHI-KAPADIA-MADAN (2003): Risk-Neutral Skewness Proxy
    # Full RNSK requires entire option chain integration (not directly available).
    # Best BRAIN proxy: implied_vol_skew field if available, else smirk slope × tenor weight.
    # High RNSK (expensive calls vs puts on the right tail) → negative future returns.
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
                            f"BKM2003: Risk-neutral skew proxy — smirk × vol-level scaling. "
                            f"High RNSK = expensive downside protection = negative return predictor. {u}."
                        ),
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "options",
                    })

    return catalog
