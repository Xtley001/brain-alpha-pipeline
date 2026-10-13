"""
Bernard & Thomas (1990) + Chan, Jegadeesh & Lakonishok (1996) — SUE & PEAD Generators
Papers:
  1. Bernard & Thomas (1990): "Evidence That Stock Prices Do Not Fully Reflect the
     Implications of Current Earnings for Future Earnings" — JAE 13(4): 305-340
  2. Chan, Jegadeesh & Lakonishok (1996): "Momentum Strategies" — JF 51(5): 1681-1713
Source KB: docs/kb/sentiment/bernard_thomas_1990_pead_sue.md
WorldQuant Master Recalibration: docs/kb/sentiment/worldquant_brain_sentiment_master_recalibration.md

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

Live Verified BRAIN Fields:
    snt1_d1_earningssurprise: Standardized Unexpected Earnings (SUE), verified in DB (ID 58gVPJln, Sharpe 1.63)
    snt1_d1_netearningsrevision: Net analyst earnings revision momentum (ID 1YZvdAqJ, Sharpe 1.34)
    snt1_d1_dtstsespe: Analyst forecast dispersion / disagreement standard deviation
    rp_css_earnings: RavenPack composite sentiment score for earnings releases
"""
from typing import Any, Dict, List

SOURCE_KB = "docs/kb/sentiment/bernard_thomas_1990_pead_sue.md"


def generate_bernard_thomas_sue_candidates() -> List[Dict[str, Any]]:
    """
    Bernard & Thomas (1990) / Chan-Jegadeesh-Lakonishok (1996):
    Standardized Unexpected Earnings (SUE), PEAD persistence, double-decay smoothing,
    and RavenPack news dual-confirmation models.
    Citation: JAE 1990, Table 1, Table 2, Table 5.
    """
    catalog: List[Dict[str, Any]] = []

    universes   = ["TOP1000", "TOP500", "TOPSP500"]
    neut_groups = ["SUBINDUSTRY", "SECTOR"]
    decays      = [8, 10, 12, 15]

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 1: Double-Decayed SUE x Reversion Momentum (Production Proven: Sharpe 1.63, ID 58gVPJln)
    # SUE smoothed with double linear decay and interacted with price mean-reversion
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for d in decays:
                for lookback in [20, 30, 40]:
                    catalog.append({
                        "pillar": "PEAD_SUE_DOUBLE_DECAY",
                        "archetype": f"PEAD_SUE_DoubleDecay_d{d}_lb{lookback}_{u}_{g}",
                        "expression": (
                            f"trade_when(volume > adv20 * 0.80, "
                            f"group_neutralize("
                            f"rank(ts_decay_linear(ts_decay_linear(snt1_d1_earningssurprise, {d}), 3)) * "
                            f"rank(-ts_delta(close, 3) / (ts_std_dev(close, {lookback}) + 0.001)), "
                            f"{g.lower()}), -1)"
                        ),
                        "hypothesis": (
                            f"BT1990 Table 2 & 5: Double linear decay on snt1_d1_earningssurprise (SUE) "
                            f"interacted with short-term return reversion normalized by {lookback}d volatility. {u}."
                        ),
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "analyst",
                        "source_kb": SOURCE_KB,
                    })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 2: SUE x RavenPack News Tone Dual Confirmation
    # Fundamental earnings surprise confirmed by machine-readable news sentiment
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for d in [10, 12]:
                catalog.append({
                    "pillar": "PEAD_DUAL_NEWS_CONFIRM",
                    "archetype": f"PEAD_DualNewsConfirm_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"group_neutralize("
                        f"rank(ts_decay_linear(snt1_d1_earningssurprise, {d})) * "
                        f"rank(ts_decay_linear(rp_css_earnings, 5)) * "
                        f"rank(-ts_delta(close, 3) / (ts_std_dev(close, 20) + 0.001)), "
                        f"{g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"CJL1996 + Tulchinsky Ch. 22: Dual confirmation between snt1_d1_earningssurprise and "
                        f"RavenPack rp_css_earnings sentiment. Eliminates accounting noise via NLP tone. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 3: SUE x Net Analyst Revision Momentum (Production Proven: Sharpe 1.34, ID 1YZvdAqJ)
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for d in [10, 12, 15]:
                catalog.append({
                    "pillar": "PEAD_SUE_X_REVISION",
                    "archetype": f"PEAD_SUExRev_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"group_neutralize("
                        f"rank(ts_decay_linear(snt1_d1_earningssurprise, {d})) * "
                        f"rank(ts_decay_linear(snt1_d1_netearningsrevision, {d})) * "
                        f"rank(-ts_delta(close, 3) / (ts_std_dev(close, 20) + 0.001)), "
                        f"{g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"CJL1996 Sec. III: SUE reinforced by net consensus earnings revisions (snt1_d1_netearningsrevision). "
                        f"Analysts revise upward following positive surprises, extending PEAD drift. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 4: PEAD Volume Surge Reallocation Gate (Extract 11)
    # Institutional reallocation after earnings manifests in heavy volume (> 1.20 ADV)
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for d in [10, 12]:
                catalog.append({
                    "pillar": "PEAD_VOLUME_SURGE",
                    "archetype": f"PEAD_VolSurge_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"group_neutralize("
                        f"rank(volume / (adv20 + 1)) * "
                        f"rank(ts_decay_linear(snt1_d1_earningssurprise, {d})) * "
                        f"rank(-ts_delta(close, 3) / (ts_std_dev(close, 20) + 0.001)), "
                        f"{g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"BT1990 Extract 11: PEAD weighted by institutional volume surge (volume / adv20). "
                        f"Heavy volume confirms institutional conviction behind earnings surprise. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 5: SUE x Low Analyst Dispersion Gate (Extract 13, DMS 2002 Link)
    # High-consensus surprises have cleaner, higher-information drift
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:2]:
        for g in neut_groups:
            for d in [10, 12]:
                catalog.append({
                    "pillar": "PEAD_LOW_DISPERSION_GATE",
                    "archetype": f"PEAD_LowDisp_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"trade_when(rank(ts_decay_linear(snt1_d1_dtstsespe, 10)) < 0.40, "
                        f"group_neutralize("
                        f"rank(ts_decay_linear(snt1_d1_earningssurprise, {d})) * "
                        f"rank(-ts_delta(close, 3) / (ts_std_dev(close, 20) + 0.001)), "
                        f"{g.lower()}), -1), -1)"
                    ),
                    "hypothesis": (
                        f"BT1990 + DMS2002: SUE signal gated on low analyst dispersion (snt1_d1_dtstsespe < 40th pct). "
                        f"High-consensus earnings surprises produce cleaner, lower-drawdown PEAD. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 6: Autoregressive Multi-Lag SUE Composite (Extract 3 & 7, Table 5 Eq 9)
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for d in [10, 14]:
                catalog.append({
                    "pillar": "PEAD_AUTOREGRESSIVE_LAGS",
                    "archetype": f"PEAD_AutoregressiveLags_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"group_neutralize("
                        f"rank(ts_decay_linear(0.70 * snt1_d1_earningssurprise + 0.30 * ts_delay(snt1_d1_earningssurprise, 63), {d})) * "
                        f"rank(-ts_delta(close, 3) / (ts_std_dev(close, 20) + 0.001)), "
                        f"{g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"BT1990 Table 5 Eq (9): Autoregressive SUE composite reflecting lags 1 and 2 autocorrelation (+0.34, +0.19). "
                        f"Combines current earnings surprise with prior quarter surprise. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 7: SUE x Implied Volatility Smirk Interaction (Production Proven: ID 88PAROJo)
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for d in [10, 12]:
                catalog.append({
                    "pillar": "PEAD_SUE_X_VOL_SMIRK",
                    "archetype": f"PEAD_SUExVolSmirk_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"group_neutralize("
                        f"rank(ts_decay_linear((implied_volatility_call_30 - implied_volatility_put_30) / (implied_volatility_mean_30 + 0.001), 10)) * "
                        f"rank(ts_decay_linear(snt1_d1_earningssurprise, {d})) * "
                        f"rank(-ts_delta(close, 3) / (ts_std_dev(close, 20) + 0.001)), "
                        f"{g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"BT1990 + Xing-Zhang-Zhao (2010): Earnings surprise confirmed by call-put implied volatility smirk. "
                        f"Informed options flow validates institutional conviction in PEAD continuation. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                    "source_kb": SOURCE_KB,
                })

    return catalog


if __name__ == "__main__":
    cands = generate_bernard_thomas_sue_candidates()
    print(f"Generated {len(cands)} Bernard & Thomas SUE candidates.")
    print("Sample expression:")
    print(cands[0]["expression"])
