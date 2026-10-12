"""
Cohen, Diether & Malloy (2007) — Short Supply/Demand Decomposition
Engelberg, Reed & Ringgenberg (2012) — Informed Shorts
Rapach, Ringgenberg & Zhou (2016) — Aggregate Short Interest & Market Returns
Asquith, Pathak & Ritter (2005) — Short Float & Institutional Ownership

Papers:
  1. CDM (2007): "Supply and Demand Shifts in the Shorting Market" — JF
     Key: An increase in SHORTING DEMAND → -2.98% abnormal return next month.
     Key: Changes in short interest are informative; LEVELS are not sufficient statistics.
     Signal: ΔShortInterest > 0 AND ΔLoan_Fee > 0 → DEMAND shift (private info)

  2. Engelberg-Reed-Ringgenberg (2012): "How Are Shorts Informed?" — JF
     Key: Short sellers are informed about bad earnings, analyst downgrades, and
     analyst revision-related news. Short interest SPIKES before bad earnings surprises.
     Signal: Shorts are especially informed when they TRADE AGAINST consensus.

  3. Rapach-Ringgenberg-Zhou (2016): "Short Interest and Aggregate Stock Returns" — JFE
     Key: Aggregate short interest negatively predicts market returns.
     But at the STOCK level: high short interest ratio (SI/shares outstanding) predicts
     negative stock-level returns cross-sectionally with t-stat > 4.

  4. Asquith-Pathak-Ritter (2005): "Short Interest, Institutional Ownership, and Stock Returns" — JFE
     Key: The short interest anomaly is concentrated in stocks where:
          - Short interest is HIGH (demand constrained by supply)
          - Institutional ownership is LOW (little lendable supply)
     Combined: High SI + Low Inst_Own = maximal short-sale constraint → most overpriced
"""
from typing import Any, Dict, List


def generate_short_interest_p0_candidates() -> List[Dict[str, Any]]:
    """
    4 P0 short interest papers → paper-faithful signal constructions.
    Citation: CDM JF 2007, ERR JF 2012, RRZ JFE 2016, APR JFE 2005.
    """
    catalog: List[Dict[str, Any]] = []

    universes   = ["TOPSP500", "TOP500", "TOP1000", "TOP3000"]
    neut_groups = ["SUBINDUSTRY", "SECTOR", "MARKET"]
    decays      = [10, 14, 20]

    # ─────────────────────────────────────────────────────────────────────────
    # CDM (2007) SIGNAL 1: Short Interest Level (Rapach-Ringgenberg-Zhou)
    # shares_sold_short / shares_outstanding = short interest ratio (SIR)
    # High SIR → -2.98% next month abnormal return (CDM) / t>4 (RRZ)
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
                        f"CDM2007/RRZ2016: high short_interest_ratio predicts negative returns. "
                        f"-2.98%/month (CDM). Gated on top 30% SI only (noise reduction for low-SI stocks). {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "short_interest",
                })

    # ─────────────────────────────────────────────────────────────────────────
    # CDM (2007) SIGNAL 2: Change in Short Interest (Demand Shift Signal)
    # CDM: LEVELS not sufficient statistic. CHANGES are informative.
    # ΔShortInterest > 0 (rising demand) → negative future return
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
                            f"CDM2007: ΔShortInterest over {lookback}d is the demand shift signal. "
                            f"Rising SI = informed shorters entering position. "
                            f"Gated on extreme demand shifts (rank > 0.65). {u}."
                        ),
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "short_interest",
                    })

    # ─────────────────────────────────────────────────────────────────────────
    # ENGELBERG-REED-RINGGENBERG (2012): Informed Shorts
    # Key finding: Short sellers are INFORMED about negative analyst events.
    # Signal: Short interest spikes in the 20 days BEFORE a bad earnings surprise.
    # Combined signal: high short interest + negative earnings revision
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
                        f"ERR2012: informed shorts trade against consensus BEFORE bad earnings. "
                        f"ΔShortInterest × negative earnings_surprise = double-confirmed informed flow. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "short_interest",
                })

    # ─────────────────────────────────────────────────────────────────────────
    # ASQUITH-PATHAK-RITTER (2005): Short Float × Institutional Ownership
    # APR: anomaly concentrated where SI is HIGH AND institutional ownership is LOW.
    # Low institutional ownership = limited lendable supply = maximal constraint.
    # Combined signal: rank(-SI_ratio) × rank(-Inst_Own) → highest overpricing
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
                        f"Low inst_own = constrained lending supply = maximal overpricing signal. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "short_interest",
                })

    # ─────────────────────────────────────────────────────────────────────────
    # DAYS-TO-COVER: Short Interest / Average Daily Volume
    # DTC = shares_short / avg_volume_20d  — liquidity-adjusted short constraint
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
                        f"Illiquid shorts are more constrained and more overpriced. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "short_interest",
                })

    return catalog
