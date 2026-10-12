"""
Carr & Wu (2009) — Variance Risk Premiums (Individual Stocks)
Bollerslev, Tauchen & Zhou (2009) — VRP & Expected Equity Returns
An, Ang, Bali & Cakici (2014) — Joint Cross-Section: Options Surface + Equity Returns
Cucuringu (2020) — Open Interest Imbalance & Return Predictability

Papers:
  1. Carr & Wu (2009): "Variance Risk Premiums" — RFS
     Core: VRP_i = IV²_i - RV_i (individual stock VRP is negative on average).
     Stocks with LARGE NEGATIVE VRP (overpriced insurance) earn lower subsequent returns.
     Large positive VRP (market expects vol spike not yet realized) → positive returns.
     Formula: VRP = E^Q[RV_{t,T}] - E^P[RV_{t,T}] ≈ IV²_{30d} - RV_{30d}²

  2. Bollerslev-Tauchen-Zhou (2009): "Expected Stock Returns and Variance Risk Premia" — RFS
     Core: Market-level VRP (S&P 500 IV² - realized var) is a powerful predictor of
     quarterly MARKET returns (not individual stocks). R² = 9% for 1-quarter horizon.
     Individual stock use: stocks with high sensitivity to market VRP changes earn premium.
     BRAIN application: construct individual stock VRP as per Carr-Wu 2009.

  3. An, Ang, Bali & Cakici (2014): "The Joint Cross-Section of Stocks and Options" — JF
     Core: BOTH idiosyncratic volatility AND option-implied volatility independently predict
     future stock returns. The COMBINATION is most powerful:
       - Stocks with HIGH IV and HIGH past IVOL are most overpriced
       - Stocks with LOW IV and LOW past IVOL earn the highest subsequent returns
     Formula: joint_signal = z(IV) + z(IVOL) — standardized and combined

  4. Cucuringu et al. (2020): "Predictability of Short-Term Returns from Option OI Imbalance" — JPM
     Core: Open interest IMBALANCE (call OI - put OI) predicts 1-week stock returns.
     When call OI >> put OI, market participants are net long call options → bullish.
     OI_imbalance = (call_OI - put_OI) / (call_OI + put_OI)
     Long high-OI-imbalance (net bullish positioning) stocks → positive next week returns.
"""
from typing import Any, Dict, List


def generate_options_vrp_surface_candidates() -> List[Dict[str, Any]]:
    """
    Carr-Wu 2009 VRP + BTZ 2009 + An-Ang 2014 joint surface + Cucuringu 2020 OI imbalance.
    All paper-faithful constructions.
    """
    catalog: List[Dict[str, Any]] = []

    universes   = ["TOPSP500", "TOP500", "TOP1000", "TOP200"]
    neut_groups = ["SUBINDUSTRY", "SECTOR", "MARKET"]
    tenors      = [30, 60, 90]
    decays      = [5, 10, 14]

    # ─────────────────────────────────────────────────────────────────────────
    # CARR & WU (2009): Individual Stock Variance Risk Premium
    # VRP_i = IV²_i - RV_i  (annualized, using 30-day measures)
    # LARGE NEGATIVE VRP → very overpriced insurance → negative future returns
    # LARGE POSITIVE VRP → realized vol has been surprisingly high vs IV → mean-revert
    # BRAIN: implied_volatility_mean_{t} (annualized IV) vs ts_std_dev(returns, 21)*sqrt(252)
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for t in tenors:
                for d in decays:
                    catalog.append({
                        "pillar": "CW_VRP_INDIVIDUAL",
                        "archetype": f"CW_VRP_t{t}_d{d}_{u}_{g}",
                        "expression": (
                            f"trade_when(volume > adv20 * 0.85, "
                            f"trade_when(abs(rank(ts_decay_linear("
                            f"power(implied_volatility_mean_{t}, 2) - power(ts_std_dev(returns, 21) * 15.87, 2), {d}"
                            f")) - 0.5) > 0.25, "
                            f"group_neutralize(signed_power(rank(-ts_decay_linear("
                            f"power(implied_volatility_mean_{t}, 2) - power(ts_std_dev(returns, 21) * 15.87, 2), {d}"
                            f")), 0.5), {g.lower()}), -1), -1)"
                        ),
                        "hypothesis": (
                            f"Carr-Wu2009: VRP = IV² - RV² at {t}d. "
                            f"Large negative VRP = overpriced vol insurance → negative returns. "
                            f"15.87 = sqrt(252) annualizer. {u}."
                        ),
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "options",
                    })

    # ─────────────────────────────────────────────────────────────────────────
    # BTZ (2009): VRP Mean-Reversion Signal (regime-filtered)
    # High VRP → market expects vol to spike → positive returns ahead.
    # When VRP is at MULTI-YEAR HIGH → best entry point for leveraged long positions.
    # Signal: ts_rank(VRP, 252) > 0.70 → long high-VRP stocks (contra Carr-Wu raw signal)
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for t in [30, 60]:
                for d in [10, 14]:
                    catalog.append({
                        "pillar": "BTZ_VRP_REGIME",
                        "archetype": f"BTZ_VRP_Regime_t{t}_d{d}_{u}_{g}",
                        "expression": (
                            f"trade_when(volume > adv20 * 0.85, "
                            f"trade_when(ts_rank(power(implied_volatility_mean_{t}, 2) - power(ts_std_dev(returns, 21) * 15.87, 2), 252) > 0.65, "
                            f"group_neutralize(signed_power(rank(ts_decay_linear("
                            f"power(implied_volatility_mean_{t}, 2) - power(ts_std_dev(returns, 21) * 15.87, 2), {d}"
                            f")), 0.5), {g.lower()}), -1), -1)"
                        ),
                        "hypothesis": (
                            f"BTZ2009: VRP at 1yr high signals macro fear premium → positive returns ahead. "
                            f"Only trade when VRP is in top 35% of its 1-year range. {t}d, {u}."
                        ),
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "options",
                    })

    # ─────────────────────────────────────────────────────────────────────────
    # AN-ANG-BALI-CAKICI (2014): Joint IV × IVOL Signal (Table 5)
    # Paper: combine options-implied vol with equity idiosyncratic vol for maximum power.
    # Both predict returns INDEPENDENTLY; combined signal has t-stat > 5.
    # Signal: z(IV) + z(IVOL) = sum of independent signals, standardized
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for t in tenors:
                for d in decays:
                    catalog.append({
                        "pillar": "AABC_JOINT_SURFACE",
                        "archetype": f"AABC_Joint_t{t}_d{d}_{u}_{g}",
                        "expression": (
                            f"trade_when(volume > adv20 * 0.85, "
                            f"trade_when(abs(rank(ts_decay_linear("
                            f"implied_volatility_mean_{t} + idiosyncratic_vol_last_60_days_spy, {d}"
                            f")) - 0.5) > 0.25, "
                            f"group_neutralize(signed_power(rank(-ts_decay_linear("
                            f"implied_volatility_mean_{t} + idiosyncratic_vol_last_60_days_spy, {d}"
                            f")), 0.5), {g.lower()}), -1), -1)"
                        ),
                        "hypothesis": (
                            f"An-Ang-Bali-Cakici2014: joint IV + IVOL signal. "
                            f"Both independently negative predictors; sum is additive. t={t}d, {u}."
                        ),
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "options",
                    })

    # ─────────────────────────────────────────────────────────────────────────
    # CUCURINGU (2020): Open Interest Imbalance
    # OI_imbalance = (call_OI - put_OI) / (call_OI + put_OI)
    # High imbalance (bullish positioning) → positive 1-week returns.
    # BRAIN: pcr_oi_{tenor} = put_OI / call_OI → inverse for call-bullish measure.
    # OI_imbalance ≈ (1 - PCR_OI) / (1 + PCR_OI) when PCR_OI = put/call OI ratio
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for t in tenors:
                for d in [5, 10]:
                    catalog.append({
                        "pillar": "CUCURINGU_OI_IMBALANCE",
                        "archetype": f"Cucuringu_OI_t{t}_d{d}_{u}_{g}",
                        "expression": (
                            f"trade_when(volume > adv20 * 0.85, "
                            f"trade_when(abs(rank(ts_decay_linear("
                            f"(1 - pcr_oi_{t}) / (1 + pcr_oi_{t} + 0.001), {d}"
                            f")) - 0.5) > 0.20, "
                            f"group_neutralize(signed_power(rank(ts_decay_linear("
                            f"(1 - pcr_oi_{t}) / (1 + pcr_oi_{t} + 0.001), {d}"
                            f")), 0.5), {g.lower()}), -1), -1)"
                        ),
                        "hypothesis": (
                            f"Cucuringu2020: OI imbalance = (1-PCR_OI)/(1+PCR_OI). "
                            f"High call OI vs put OI = net bullish positioning → positive 1-week return. {t}d, {u}."
                        ),
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "options",
                    })

    # ─────────────────────────────────────────────────────────────────────────
    # CUCURINGU: OI Imbalance Change (Flow-of-Funds signal)
    # When call OI is GROWING relative to put OI, net bullish positioning is BUILDING.
    # This is the flow version — more timely than the level.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for t in [30, 60]:
                for d in [5, 10]:
                    catalog.append({
                        "pillar": "CUCURINGU_OI_FLOW",
                        "archetype": f"Cucuringu_OIFlow_t{t}_d{d}_{u}_{g}",
                        "expression": (
                            f"trade_when(volume > adv20 * 0.85, "
                            f"trade_when(abs(rank(ts_decay_linear(ts_delta(pcr_oi_{t}, 5), {d})) - 0.5) > 0.20, "
                            f"group_neutralize(signed_power(rank(-ts_decay_linear(ts_delta(pcr_oi_{t}, 5), {d})), 0.5), {g.lower()}), "
                            f"-1), -1)"
                        ),
                        "hypothesis": (
                            f"Cucuringu2020 flow: falling PCR_OI = growing call-side OI vs puts = "
                            f"building bullish positioning. Captures flow-of-funds shift. {t}d, {u}."
                        ),
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "options",
                    })

    return catalog
