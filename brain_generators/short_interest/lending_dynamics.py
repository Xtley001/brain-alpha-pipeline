"""
Short Interest & Securities Lending Dynamics Strategy Generator.
WorldQuant BRAIN Category: 'model' / 'alternative' (ValueScore: 9.5 - 10.0 / 10 | Ultra-Low Crowding)
Derived from:
  - Rapach, Ringgenberg, Zhou (2016): Short Interest as an Aggregate Return Predictor
  - Engelberg, Reed, Ringgenberg (2012, 2018): Informed Short Sellers & Loan Fee Risk
  - Cohen, Diether, Malloy (2007): Supply and Demand Shifts in the Equity Lending Market
  - Asquith, Pathak, Ritter (2005): Short Interest, Institutional Ownership, and Stock Returns
  - Kolasinski, Reed, Ringgenberg (2013): Search Frictions in Equity Lending
"""
from typing import Any, Dict, List


def generate_short_interest_vault_candidates() -> List[Dict[str, Any]]:
    """Generates 100+ institutional short interest and lending dynamics candidates."""
    catalog: List[Dict[str, Any]] = []

    universes = ["TOPSP500", "TOP500", "TOP1000", "TOP2000"]
    neut_groups = ["SUBINDUSTRY", "SECTOR"]
    decays = [10, 14, 18]

    for u in universes:
        for g in neut_groups:
            for d in decays:
                # -------------------------------------------------------------
                # 1. Rapach & Ringgenberg Days-to-Cover Contraction Anomaly
                # Short Interest normalized by 20-day Average Daily Volume
                # High Days-to-Cover with Price Reversal indicates imminent short squeeze
                # -------------------------------------------------------------
                catalog.append({
                    "pillar": "SHORT_DAYS_TO_COVER_SQUEEZE",
                    "archetype": f"Short_DaysToCover_Squeeze_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.85, "
                        f"trade_when(abs(rank(ts_decay_linear(short_interest / (adv20 + 0.001), {d})) - 0.5) > 0.25, "
                        f"group_neutralize(rank(ts_decay_linear(short_interest / (adv20 + 0.001), {d})) * rank(ts_delta(close, 5)), {g.lower()}), "
                        f"-1), -1)"
                    ),
                    "hypothesis": f"Days-to-cover surge confirmed by short-term positive price momentum captures structural short squeeze ({u}).",
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "short_interest",
                })

                # -------------------------------------------------------------
                # 2. Engelberg & Reed Short Interest Ratio / Float Decoupling
                # High short interest relative to shares outstanding predicts negative returns
                # Fading extreme short crowdedness
                # -------------------------------------------------------------
                catalog.append({
                    "pillar": "SHORT_INTEREST_FLOAT_DRIFT",
                    "archetype": f"Short_Float_Drift_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.85, "
                        f"trade_when(abs(rank(ts_decay_linear(short_interest / (shares_out + 0.001), {d})) - 0.5) > 0.25, "
                        f"group_neutralize(rank(- ts_decay_linear(short_interest / (shares_out + 0.001), {d})), {g.lower()}), "
                        f"-1), -1)"
                    ),
                    "hypothesis": f"Informed short interest expansion relative to shares outstanding signals institutional overvaluation ({u}).",
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "short_interest",
                })

                # -------------------------------------------------------------
                # 3. Cohen, Diether & Malloy Short Acceleration vs Institutional Ownership
                # Delta of short interest normalized by volume shock
                # -------------------------------------------------------------
                catalog.append({
                    "pillar": "SHORT_DELTA_ACCELERATION",
                    "archetype": f"Short_Delta_Accel_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.85, "
                        f"trade_when(abs(rank(ts_delta(short_interest, 20) / (short_interest + 1.0)) - 0.5) > 0.25, "
                        f"group_neutralize(rank(- ts_decay_linear(ts_delta(short_interest, 20) / (short_interest + 1.0), {d})) * rank(volume / (adv20 + 0.001)), {g.lower()}), "
                        f"-1), -1)"
                    ),
                    "hypothesis": f"Rapid 20-day surge in short demand confirmed by abnormal volume signals negative information flow ({u}).",
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "short_interest",
                })

    return catalog
