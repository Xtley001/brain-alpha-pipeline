"""
Carr & Wu (2009) — Variance Risk Premiums (Individual Stocks)
Bollerslev, Tauchen & Zhou (2009) — VRP & Expected Equity Returns
An, Ang, Bali & Cakici (2014) — Joint Cross-Section: Options Surface + Equity Returns
Cucuringu (2020) — Open Interest Imbalance & Return Predictability
Source KB: docs/kb/options/carr_wu_2009_vrp.md

Core Finding (Carr & Wu 2009):
    Variance Risk Premium: VRP = RV - SW = RV - IV² (consistently negative across assets).
    Investors pay an insurance premium to hedge volatility spikes.
    Table 3: Information ratio of selling variance swap is 0.85 to 0.98 on equity indices,
    and consistently negative across individual equities (t-stats exceeding -3 to -6).
    Stocks with wide positive IV - RV spread have overpriced options -> mean-revert.
"""
from typing import Any, Dict, List

SOURCE_KB = "docs/kb/options/carr_wu_2009_vrp.md"


def generate_options_vrp_surface_candidates() -> List[Dict[str, Any]]:
    """
    Carr-Wu 2009 VRP + BTZ 2009 + An-Ang 2014 joint surface + Cucuringu 2020 OI imbalance.
    Citation: RFS 2009, Table 2, Table 3, Table 4.
    """
    catalog: List[Dict[str, Any]] = []

    universes   = ["TOPSP500", "TOP500", "TOP1000", "TOP200"]
    neut_groups = ["SUBINDUSTRY", "SECTOR", "MARKET"]
    tenors      = [30, 60, 90]
    decays      = [5, 10, 14]

    # ─────────────────────────────────────────────────────────────────────────
    # CARR & WU (2009): Individual Stock Variance Risk Premium (Extract 3 & 4)
    # VRP = IV² - RV²
    # Large negative VRP -> overpriced options insurance -> negative returns.
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
                            f"Carr-Wu2009 Table 3: VRP = IV² - RV² at {t}d. "
                            f"Overpriced volatility insurance predicts subsequent equity underperformance. {u}."
                        ),
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "options",
                        "source_kb": SOURCE_KB,
                    })

    # ─────────────────────────────────────────────────────────────────────────
    # BTZ (2009): VRP Mean-Reversion Signal (regime-filtered)
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
                            f"BTZ2009: VRP at 1yr high signals macro fear premium -> positive returns ahead. "
                            f"Only trade when VRP is in top 35% of its 1-year range. {t}d, {u}."
                        ),
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "options",
                        "source_kb": SOURCE_KB,
                    })

    # ─────────────────────────────────────────────────────────────────────────
    # AN-ANG-BALI-CAKICI (2014): Joint IV x IVOL Signal (Table 5)
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
                        "source_kb": SOURCE_KB,
                    })

    # ─────────────────────────────────────────────────────────────────────────
    # CUCURINGU (2020): Open Interest Imbalance
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
                            f"High call OI vs put OI = net bullish positioning -> positive 1-week return. {t}d, {u}."
                        ),
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "options",
                        "source_kb": SOURCE_KB,
                    })

    # ─────────────────────────────────────────────────────────────────────────
    # CUCURINGU: OI Imbalance Change (Flow-of-Funds signal)
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
                        "source_kb": SOURCE_KB,
                    })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 6: Log VRP Ratio (Extract 3 & 5, Table 3 Panel B)
    # Table 3: ln(RV / SW) standardizes across high and low volatility stocks.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [10, 14]:
                catalog.append({
                    "pillar": "CW_LOG_VRP_RATIO",
                    "archetype": f"CW_LogVRP_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.85, "
                        f"group_neutralize("
                        f"signed_power(rank(-ts_decay_linear("
                        f"log((implied_volatility_mean_30 + 0.001) / (ts_std_dev(returns, 20) * 15.87 + 0.001)), {d}"
                        f")), 0.5), {g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"Carr-Wu2009 Table 3 Panel B: log VRP ratio ln(IV/RV). "
                        f"Standardizes variance risk premium across stock volatility regimes. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "options",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 7: Multi-Tenor VRP Term Spread (Extract 7)
    # Near-term headline panic creates wider 30d VRP than 90d VRP.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [10, 14]:
                catalog.append({
                    "pillar": "CW_VRP_TERM_SPREAD",
                    "archetype": f"CW_VRPTermSpread_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.85, "
                        f"group_neutralize("
                        f"rank(-ts_decay_linear("
                        f"(implied_volatility_mean_30 - ts_std_dev(returns, 20) * 15.87) - "
                        f"(implied_volatility_mean_90 - ts_std_dev(returns, 60) * 15.87), {d}"
                        f")), {g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"Carr-Wu2009 Extract 7: VRP term spread (30d vs 90d). "
                        f"Excessive near-term options premium mean-reverts back to term structure normal. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "options",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 8: VRP Gated on Realized Volatility Regime (Extract 9)
    # VRP is widest during market pullbacks and elevated volatility.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [10, 14]:
                catalog.append({
                    "pillar": "CW_VRP_VOL_REGIME_GATE",
                    "archetype": f"CW_VRPVolGate_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.85, "
                        f"trade_when(ts_rank(ts_std_dev(returns, 20), 252) > 0.50, "
                        f"group_neutralize("
                        f"signed_power(rank(-ts_decay_linear("
                        f"implied_volatility_mean_30 - ts_std_dev(returns, 20) * 15.87, {d}"
                        f")), 0.5), {g.lower()}), -1), -1)"
                    ),
                    "hypothesis": (
                        f"Carr-Wu2009 Extract 9: VRP active only when historical volatility is in upper half of annual range. "
                        f"Harvests maximum options mispricing during elevated risk premium regimes. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "options",
                    "source_kb": SOURCE_KB,
                })

    return catalog
