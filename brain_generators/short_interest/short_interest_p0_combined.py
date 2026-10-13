"""
Cohen, Diether & Malloy (2007) — Short Supply/Demand Decomposition
Engelberg, Reed & Ringgenberg (2012) — Informed Shorts
Rapach, Ringgenberg & Zhou (2016) — Aggregate Short Interest & Market Returns
Asquith, Pathak & Ritter (2005) — Short Float & Institutional Ownership

Papers & Empirical Benchmarks:
  1. CDM (2007): "Supply and Demand Shifts in the Shorting Market" — JF
     - Key finding: An outward shift in shorting demand (DOUT: Fee↑ and Quantity↑) predicts
       -2.98% abnormal return next month (t = -3.96, Table III).
     - Table IV: Large shifts (joint Fee and Quantity outliers) yield -4.48% (t = 2.32).
     - Table VIII: Concentration in small-cap stocks (ME_small * DOUT = -6.31% total).
     - Identifying strategy: Changes in short interest isolate demand shifts from supply contractions.
  2. ERR (2012): "How Are Shorts Informed?" — JF
     - Short interest accumulates 20+ days prior to negative earnings surprises and analyst downgrades.
     - Strongest when betting against bullish consensus.
  3. RRZ (2016): "Short Interest and Aggregate Stock Returns" — JFE
     - Cross-sectional short_interest_ratio predicts individual stock returns with t-stat > 4.
  4. APR (2005): "Short Interest, Institutional Ownership, and Stock Returns" — JFE
     - Anomaly concentrated in high short interest + low institutional ownership (constrained lendable supply).
"""
from typing import Any, Dict, List

SOURCE_KB = "docs/kb/short_interest/cohen_diether_malloy_2007_shorting.md"


def generate_short_interest_p0_candidates() -> List[Dict[str, Any]]:
    """
    4 P0 short interest papers -> institutional-grade signal constructions.
    Citation: CDM JF 2007, ERR JF 2012, RRZ JFE 2016, APR JFE 2005.
    """
    catalog: List[Dict[str, Any]] = []

    universes   = ["TOPSP500", "TOP500", "TOP1000", "TOP3000"]
    neut_groups = ["SUBINDUSTRY", "SECTOR", "MARKET"]
    decays      = [10, 14, 20]

    # ─────────────────────────────────────────────────────────────────────────
    # CDM (2007) SIGNAL 1: Short Interest Level (Rapach-Ringgenberg-Zhou)
    # shares_sold_short / shares_outstanding = short interest ratio (SIR)
    # High SIR -> -2.98% next month abnormal return (CDM) / t>4 (RRZ)
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for d in decays:
                catalog.append({
                    "pillar": "SI_LEVEL",
                    "archetype": f"SI_Level_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"trade_when(rank(ts_decay_linear(short_interest_ratio, {d})) > 0.70, "
                        f"group_neutralize(signed_power(rank(-ts_decay_linear(short_interest_ratio, {d})), 0.5), {g.lower()}), "
                        f"-1), -1)"
                    ),
                    "hypothesis": (
                        f"CDM2007/RRZ2016: high short_interest_ratio predicts negative returns (-2.98%/mo). "
                        f"Gated on top 30% SI only (noise reduction for low-SI stocks). {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "short_interest",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # CDM (2007) SIGNAL 2: Change in Short Interest (Demand Shift Signal)
    # CDM: LEVELS not sufficient statistic. CHANGES isolate demand shifts.
    # ΔShortInterest > 0 (rising demand) -> negative future return (-2.98%, t=-3.96)
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for d in [10, 14, 20]:
                for lookback in [10, 21, 42]:
                    catalog.append({
                        "pillar": "SI_DELTA_DEMAND",
                        "archetype": f"SI_Delta_lb{lookback}_d{d}_{u}_{g}",
                        "expression": (
                            f"trade_when(volume > adv20 * 0.80, "
                            f"trade_when(rank(ts_delta(short_interest_ratio, {lookback})) > 0.65, "
                            f"group_neutralize(rank(-ts_decay_linear(ts_delta(short_interest_ratio, {lookback}), {d})), {g.lower()}), "
                            f"-1), -1)"
                        ),
                        "hypothesis": (
                            f"CDM2007: ΔShortInterest over {lookback}d is the demand shift signal (Table III, t=-3.96). "
                            f"Rising SI = informed shorters entering position. Gated on top 35% demand changes. {u}."
                        ),
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "short_interest",
                        "source_kb": SOURCE_KB,
                    })

    # ─────────────────────────────────────────────────────────────────────────
    # ENGELBERG-REED-RINGGENBERG (2012): Informed Shorts
    # Short sellers trade 20+ days BEFORE negative earnings surprise.
    # Combined signal: high short interest delta + negative earnings surprise
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [10, 14]:
                catalog.append({
                    "pillar": "SI_INFORMED_SHORTS",
                    "archetype": f"SI_Informed_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"trade_when(rank(ts_delta(short_interest_ratio, 21)) > 0.65, "
                        f"group_neutralize("
                        f"rank(-ts_decay_linear(ts_delta(short_interest_ratio, 21), {d})) * "
                        f"rank(-ts_decay_linear(earnings_surprise, {d})), "
                        f"{g.lower()}), -1), -1)"
                    ),
                    "hypothesis": (
                        f"ERR2012: informed shorts trade against consensus before bad earnings. "
                        f"ΔShortInterest × negative earnings_surprise = dual-confirmed informed flow. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "short_interest",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # ASQUITH-PATHAK-RITTER (2005): Short Float × Institutional Ownership
    # APR: anomaly concentrated where SI is HIGH AND institutional ownership is LOW.
    # Low institutional ownership = limited lendable supply = maximal constraint (-2.15%/mo).
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [14, 20]:
                catalog.append({
                    "pillar": "SI_FLOAT_INST_OWNERSHIP",
                    "archetype": f"SI_FloatInst_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"trade_when(rank(short_interest_ratio) > 0.60, "
                        f"group_neutralize("
                        f"rank(-ts_decay_linear(short_interest_ratio, {d})) * "
                        f"rank(-ts_decay_linear(institutional_ownership_percentage, {d})), "
                        f"{g.lower()}), -1), -1)"
                    ),
                    "hypothesis": (
                        f"APR2005: short anomaly strongest when high SI + low institutional ownership. "
                        f"Low inst_own = constrained lending supply = maximal overpricing (-2.15%/mo). {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "short_interest",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # DAYS-TO-COVER: Short Interest / Average Daily Volume
    # DTC = shares_short / avg_volume_20d — liquidity-adjusted short constraint
    # Higher DTC = harder to cover = more locked-in short position = more overpriced
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [10, 14]:
                catalog.append({
                    "pillar": "SI_DAYS_TO_COVER",
                    "archetype": f"SI_DTC_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"trade_when(rank(short_interest_ratio / (adv20 + 0.001)) > 0.65, "
                        f"group_neutralize(signed_power(rank(-ts_decay_linear("
                        f"short_interest_ratio / (adv20 + 0.001), {d}"
                        f")), 0.5), {g.lower()}), -1), -1)"
                    ),
                    "hypothesis": (
                        f"CDM2007/APR2005: days-to-cover = SI/ADV. "
                        f"Illiquid shorts face higher recall costs and greater overpricing. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "short_interest",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # CDM (2007) SIGNAL 6: Large Shift Outliers (Table IV, -4.48%, t=2.32)
    # Extreme outward demand shifts (top 15% delta SI) with power concavity
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [10, 14]:
                catalog.append({
                    "pillar": "SI_LARGE_SHIFT_OUTLIER",
                    "archetype": f"SI_LargeShift_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"trade_when(rank(ts_delta(short_interest_ratio, 21)) > 0.85, "
                        f"group_neutralize(signed_power(rank(-ts_decay_linear(ts_delta(short_interest_ratio, 21), {d})), 0.5), {g.lower()}), "
                        f"-1), -1)"
                    ),
                    "hypothesis": (
                        f"CDM2007 Table IV: large demand shifts (top 15% ΔSI) produce -4.48% abnormal return (t=2.32). "
                        f"Strongest conviction institutional short bets. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "short_interest",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # CDM (2007) SIGNAL 7: Short Demand Shift × Short-Term Reversal Control (Table III Model 1)
    # Interaction between short demand surge and prior 5-day price reversal
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [10, 14]:
                catalog.append({
                    "pillar": "SI_REVERSAL_INTERACTION",
                    "archetype": f"SI_ReversalCtrl_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"trade_when(rank(ts_delta(short_interest_ratio, 21)) > 0.65, "
                        f"group_neutralize("
                        f"rank(-ts_decay_linear(ts_delta(short_interest_ratio, 21), {d})) * "
                        f"rank(-ts_decay_linear(returns, 5)), "
                        f"{g.lower()}), -1), -1)"
                    ),
                    "hypothesis": (
                        f"CDM2007 Table III Model 1: shorting demand shift combined with short-term price reversal r_-1. "
                        f"Controlling for mean-reversion amplifies pure informed short alpha. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "short_interest",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # CDM (2007) SIGNAL 8: Small-Cap Concentrated Demand Shift (Table VIII, -6.31%)
    # Outward demand shifts concentrated in lower market capitalization firms
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOP1000", "TOP3000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [10, 14]:
                catalog.append({
                    "pillar": "SI_SMALL_CAP_CONCENTRATED",
                    "archetype": f"SI_SmallCap_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"trade_when(rank(-cap) > 0.60, "
                        f"trade_when(rank(ts_delta(short_interest_ratio, 21)) > 0.65, "
                        f"group_neutralize(rank(-ts_decay_linear(ts_delta(short_interest_ratio, 21), {d})), {g.lower()}), "
                        f"-1), -1), -1)"
                    ),
                    "hypothesis": (
                        f"CDM2007 Table VIII: DOUT effect strongly concentrated in small-cap stocks (ME_small * DOUT = -6.31% total). "
                        f"Private information advantages are highest in low-coverage small caps. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "short_interest",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # CDM (2007) SIGNAL 9: Normalized Volatility Demand Surge (Table VII)
    # ΔSI scaled by rolling short interest volatility (ts_std_dev) to remove baseline noise
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [10, 14]:
                catalog.append({
                    "pillar": "SI_VOLATILITY_SURGE_GATE",
                    "archetype": f"SI_VolSurge_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"trade_when(rank(ts_delta(short_interest_ratio, 21) / (ts_std_dev(short_interest_ratio, 63) + 0.0001)) > 0.70, "
                        f"group_neutralize(rank(-ts_decay_linear(short_interest_ratio, {d})), {g.lower()}), "
                        f"-1), -1)"
                    ),
                    "hypothesis": (
                        f"CDM2007 Table VII: demand shifts exceeding 1 std dev of historical SI volatility filter out "
                        f"dividend arbitrage / passive noise and isolate true information spikes. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "short_interest",
                    "source_kb": SOURCE_KB,
                })

    return catalog
