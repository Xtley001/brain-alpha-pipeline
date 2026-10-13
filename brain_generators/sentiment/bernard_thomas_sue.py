"""
Bernard & Thomas (1990) + Chan, Jegadeesh & Lakonishok (1996) — SUE & PEAD Generators
Papers:
  1. Bernard & Thomas (1990): "Evidence That Stock Prices Do Not Fully Reflect the
     Implications of Current Earnings for Future Earnings" — JAE 13(4): 305-340
  2. Chan, Jegadeesh & Lakonishok (1996): "Momentum Strategies" — JF 51(5): 1681-1713
Source KB: docs/kb/sentiment/bernard_thomas_1990_pead_sue.md

Core Finding (BT 1990):
    Stock prices systematically under-react to quarterly earnings surprises.
    The post-announcement drift persists for up to 3 quarters (~60-90 trading days).
    Autocorrelation structure from Table 1:
        Lag 1: +0.34 (100% of 37 industries positive)
        Lag 2: +0.19 (100% of 37 industries positive)
        Lag 3: +0.06 (95% of industries positive)
        Lag 4: -0.24 (100% of industries negative reversal!)
    Table 5 Regression (Eq 9):
        AR = 5.38 * SUE_{t-1} + 1.46 * SUE_{t-2} + 0.53 * SUE_{t-3} - 1.56 * SUE_{t-4}
    Estimated abnormal return: 18% annualized in the first quarter post-announcement.
"""
from typing import Any, Dict, List

SOURCE_KB = "docs/kb/sentiment/bernard_thomas_1990_pead_sue.md"


def generate_bernard_thomas_sue_candidates() -> List[Dict[str, Any]]:
    """
    Bernard & Thomas (1990) / Chan-Jegadeesh-Lakonishok (1996):
    Standardized Unexpected Earnings (SUE), PEAD persistence, and seasonal autocorrelation models.
    Citation: JAE 1990, Table 1, Table 2, Table 5.
    """
    catalog: List[Dict[str, Any]] = []

    universes   = ["TOPSP500", "TOP500", "TOP1000", "TOP3000"]
    neut_groups = ["SUBINDUSTRY", "SECTOR", "MARKET"]
    decays      = [10, 14, 20, 30]

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 1: Pure SUE — Standardized Unexpected Earnings (Extract 4 & 7, Table 5)
    # SUE = (Q_t - Q_{t-4} - delta) / sigma(UE)
    # BRAIN equivalent: earnings_surprise smoothed with linear decay
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for d in decays:
                catalog.append({
                    "pillar": "PEAD_SUE",
                    "archetype": f"PEAD_SUE_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"trade_when(abs(rank(ts_decay_linear(earnings_surprise, {d})) - 0.5) > 0.20, "
                        f"group_neutralize(signed_power(rank(ts_decay_linear(earnings_surprise, {d})), 0.5), {g.lower()}), "
                        f"-1), -1)"
                    ),
                    "hypothesis": (
                        f"BT1990 Table 2: Post-earnings-announcement drift on earnings_surprise (SUE proxy). "
                        f"Market under-reacts to earnings: drift persists for 60+ trading days. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 2: SUE x Price Momentum (Extract 12, CJL 1996 Sec. III)
    # Dual confirmation: positive earnings surprise + positive intermediate price momentum.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [14, 20]:
                catalog.append({
                    "pillar": "PEAD_DUAL_CONFIRM",
                    "archetype": f"PEAD_DualConfirm_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"group_neutralize("
                        f"rank(ts_decay_linear(earnings_surprise, {d})) * "
                        f"rank(ts_sum(returns, 126) - ts_sum(returns, 5)), "
                        f"{g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"CJL1996: Dual confirmation — positive earnings surprise + positive 6m price momentum. "
                        f"Both independently predict; combined signal strongest. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 3: Analyst Revision Momentum (CJL 1996 Sec. III.B)
    # Revisions systematically continue upward after positive earnings releases.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [14, 20, 30]:
                catalog.append({
                    "pillar": "PEAD_REVISION_MOMENTUM",
                    "archetype": f"PEAD_RevMom_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"group_neutralize(signed_power(rank(ts_decay_linear(ts_sum(analyst_rating_change, 63), {d})), 0.5), "
                        f"{g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"CJL1996: 3-month cumulative analyst rating revision momentum — "
                        f"analysts systematically revise upward after positive earnings. Drift up to 6m. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 4: PEAD Persistence Delayed to Next Quarter (Extract 2 & 6, Table 2)
    # A large fraction of drift is delayed until quarter t+1's announcement.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [5, 10]:
                catalog.append({
                    "pillar": "PEAD_NEXT_QUARTER_DRIFT",
                    "archetype": f"PEAD_NextQ_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"trade_when(abs(rank(ts_decay_linear(ts_delay(earnings_surprise, 63), {d})) - 0.5) > 0.20, "
                        f"group_neutralize(rank(ts_decay_linear(ts_delay(earnings_surprise, 63), {d})), {g.lower()}), "
                        f"-1), -1)"
                    ),
                    "hypothesis": (
                        f"BT1990 Table 2: 25-30% of PEAD is delayed until NEXT quarter announcement window. "
                        f"Use 63-day lagged earnings surprise to position before subsequent release. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 5: SUE x Low Analyst Dispersion Gate (Extract 13, DMS 2002 Link)
    # High-consensus surprises have cleaner, higher-information drift.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [14, 20]:
                catalog.append({
                    "pillar": "PEAD_LOW_DISPERSION_GATE",
                    "archetype": f"PEAD_LowDisp_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"trade_when(rank(analyst_estimate_dispersion) < 0.30, "
                        f"group_neutralize(signed_power(rank(ts_decay_linear(earnings_surprise, {d})), 0.5), {g.lower()}), "
                        f"-1), -1)"
                    ),
                    "hypothesis": (
                        f"BT1990 + DMS2002: PEAD signal gated on low analyst dispersion. "
                        f"High-consensus earnings surprises have cleaner PEAD; high-dispersion stocks confound. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 6: Autoregressive Multi-Lag SUE Momentum (Extract 3 & 7, Table 5 Eq 9)
    # Paper Eq. (9) regression: 5.38*SUE_t + 1.46*SUE_{t-63} - 1.56*SUE_{t-252}
    # Weights directly mirror the empirical autocorrelation coefficients of earnings!
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [14, 20]:
                catalog.append({
                    "pillar": "PEAD_AUTOREGRESSIVE_LAGS",
                    "archetype": f"PEAD_AutoregressiveLags_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"group_neutralize("
                        f"rank(ts_decay_linear(0.70 * earnings_surprise + 0.30 * ts_delay(earnings_surprise, 63), {d})), "
                        f"{g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"BT1990 Table 5 Eq (9): Autoregressive SUE composite reflecting lags 1 and 2 autocorrelation. "
                        f"Positively combines current surprise with prior quarter surprise. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 7: SUE x Immediate Price Jump Confirmation (Extract 12, Table 2)
    # Requires immediate 5-day price confirmation: eliminates value traps where positive
    # headline surprise hides deteriorations in revenue or guidance.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [14, 20]:
                catalog.append({
                    "pillar": "PEAD_PRICE_CONFIRMATION",
                    "archetype": f"PEAD_PriceConfirm_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"group_neutralize("
                        f"rank(ts_decay_linear(earnings_surprise, {d})) * "
                        f"rank(ts_decay_linear(ts_delta(close, 5), 5)), "
                        f"{g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"BT1990 Table 2: SUE confirmed by positive 5-day post-announcement price return. "
                        f"Filters out guidance cuts and headline accounting artifacts. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 8: SUE x Announcement Volume Surge Gate (Extract 11)
    # Institutional reallocation after earnings manifests in heavy volume (> 1.25 ADV).
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [14, 20]:
                catalog.append({
                    "pillar": "PEAD_VOLUME_SURGE",
                    "archetype": f"PEAD_VolSurge_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 1.25, "
                        f"group_neutralize("
                        f"signed_power(rank(ts_decay_linear(earnings_surprise, {d})), 0.5), "
                        f"{g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"BT1990 Extract 11: PEAD gated on institutional volume surge (>1.25 ADV20). "
                        f"High volume confirms institutional buying rather than retail noise. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 9: Lag-4 Seasonal Mean-Reversion Hedge (Extract 3 & 7, Table 1 & Table 5)
    # Table 1: Lag-4 autocorrelation is -0.24 across all 37 industries.
    # Fading extreme positive surprises from 4 quarters ago (252 trading days)
    # harvests the systematic seasonal mean-reversion.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [14, 20]:
                catalog.append({
                    "pillar": "PEAD_SEASONAL_LAG4_REVERSAL",
                    "archetype": f"PEAD_Lag4Reversal_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"group_neutralize("
                        f"rank(-ts_decay_linear(ts_delay(earnings_surprise, 252), {d})), "
                        f"{g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"BT1990 Table 1 & 5: Lag-4 autocorrelation is -0.24 across all 37 industries. "
                        f"Fading extreme positive surprises from 1 year prior harvests seasonal mean-reversion. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                    "source_kb": SOURCE_KB,
                })

    return catalog
