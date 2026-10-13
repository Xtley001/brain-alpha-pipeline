"""
Ang, Hodrick, Xing & Zhang (2006) — Idiosyncratic Volatility Anomaly
Baker, Bradley & Wurgler (2011) — Low Volatility Anomaly & Benchmarks
Merton (1974) — Structural Model / Distance-to-Default
Savor & Wilson (2013) — Macroeconomic Risk & Announcement Premiums
Source KB: docs/kb/risk_models/ahxz_2006_idiovol_and_derivatives.md

Core Finding (AHXZ 2006):
    Stocks with high idiosyncratic volatility relative to the Fama-French 3-factor model
    earn abysmally low average returns (-1.16%/month FF3 alpha in top quintile, t=-5.92).
    Top-minus-bottom quintile spread is -1.31%/month (-15.7% annualized, t=-7.00).
    Table VIII: Controlling for past 12-month momentum widens the spread to -1.22%/month (t=-5.46).
    The anomaly is robust in large caps (Table VII NYSE-only spread -0.66%/mo, t=-4.85).
"""
from typing import Any, Dict, List

SOURCE_KB = "docs/kb/risk_models/ahxz_2006_idiovol_and_derivatives.md"


def generate_risk_model_p1_candidates() -> List[Dict[str, Any]]:
    """
    AHXZ 2006 + BBW 2011 + Merton 1974 + Savor-Wilson 2013 risk model generators.
    Paper-faithful constructions for the model dataset (model51/52 on BRAIN).
    Citation: JF 2006, Table VI, Table VII, Table VIII.
    """
    catalog: List[Dict[str, Any]] = []

    universes   = ["TOPSP500", "TOP500", "TOP1000", "TOP3000"]
    neut_groups = ["SUBINDUSTRY", "SECTOR", "MARKET"]
    decays      = [10, 14, 20]

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 1: Pure Idiosyncratic Volatility Anomaly (AHXZ 2006 Table VI)
    # Short high-IVOL stocks, long low-IVOL stocks.
    # Top quintile underperforms bottom quintile by -1.31%/month FF3 alpha.
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for d in decays:
                catalog.append({
                    "pillar": "AHXZ_IDIOVOL",
                    "archetype": f"AHXZ_IdioVol_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"trade_when(abs(rank(ts_decay_linear(idiosyncratic_vol_last_60_days_spy, {d})) - 0.5) > 0.25, "
                        f"group_neutralize(signed_power(rank(-ts_decay_linear(idiosyncratic_vol_last_60_days_spy, {d})), 0.5), {g.lower()}), "
                        f"-1), -1)"
                    ),
                    "hypothesis": (
                        f"AHXZ2006 Table VI: high IVOL -> low future returns (volatility puzzle). "
                        f"Short extreme IVOL stocks; 1.31%/month underperformance in top IVOL quintile. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "model",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 2: IVOL Rising Delta (Extract 13, Distress Acceleration)
    # Rapidly rising IVOL signals worsening distress and impending tail realization.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [10, 14]:
                for lookback in [21, 42]:
                    catalog.append({
                        "pillar": "AHXZ_IDIOVOL_RISING",
                        "archetype": f"AHXZ_IdioVolRise_lb{lookback}_d{d}_{u}_{g}",
                        "expression": (
                            f"trade_when(volume > adv20 * 0.80, "
                            f"trade_when(rank(ts_delta(idiosyncratic_vol_last_60_days_spy, {lookback})) > 0.70, "
                            f"group_neutralize(rank(-ts_decay_linear(ts_delta(idiosyncratic_vol_last_60_days_spy, {lookback}), {d})), {g.lower()}), "
                            f"-1), -1)"
                        ),
                        "hypothesis": (
                            f"AHXZ2006 Extract 13: rapidly rising idiosyncratic volatility signals "
                            f"distress escalation — sharper timing than level signal. {lookback}d delta, {u}."
                        ),
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "model",
                        "source_kb": SOURCE_KB,
                    })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 3: Total Realized Volatility Anomaly (BBW 2011 Table 1)
    # Benchmark-constrained institutional managers avoid high total vol stocks.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for window in [21, 63]:
                for d in [10, 14]:
                    catalog.append({
                        "pillar": "BBW_REALIZED_VOL",
                        "archetype": f"BBW_RealVol_w{window}_d{d}_{u}_{g}",
                        "expression": (
                            f"trade_when(volume > adv20 * 0.80, "
                            f"trade_when(abs(rank(ts_decay_linear(ts_std_dev(returns, {window}), {d})) - 0.5) > 0.25, "
                            f"group_neutralize(signed_power(rank(-ts_decay_linear(ts_std_dev(returns, {window}), {d})), 0.5), {g.lower()}), "
                            f"-1), -1)"
                        ),
                        "hypothesis": (
                            f"BBW2011: total realized vol anomaly — high total vol -> benchmark exclusion -> "
                            f"overpriced by momentum chasers -> negative future returns. {window}d window, {u}."
                        ),
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "model",
                        "source_kb": SOURCE_KB,
                    })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 4: Merton (1974) Distance-to-Default Proxy
    # High leverage x high realized volatility = near-default structural distress.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [20, 30]:
                catalog.append({
                    "pillar": "MERTON_DISTRESS",
                    "archetype": f"Merton_D2D_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"trade_when(rank(debt_to_equity_ratio * ts_std_dev(returns, 252)) > 0.70, "
                        f"group_neutralize(signed_power(rank(-ts_decay_linear("
                        f"1 / (debt_to_equity_ratio * ts_std_dev(returns, 252) + 0.001), {d}"
                        f")), 0.5), {g.lower()}), -1), -1)"
                    ),
                    "hypothesis": (
                        f"Merton1974: inverse D2D proxy = leverage * vol. "
                        f"High leverage * high vol = near-default = distress discount. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "model",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 5: Savor & Wilson (2013) Macro Announcement Beta
    # Stocks with high sensitivity to macro shocks earn an announcement-day premium.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [14, 20]:
                catalog.append({
                    "pillar": "SAVOR_MACRO_BETA",
                    "archetype": f"SavorWilson_MacroBeta_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"group_neutralize(signed_power(rank(ts_decay_linear("
                        f"beta_last_252_days_spy * ts_rank(ts_std_dev(returns, 5), 252), {d}"
                        f")), 0.5), {g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"Savor-Wilson2013: macro-sensitive stocks (high beta * recent high vol) "
                        f"earn announcement-day premium (+11bps on FOMC/CPI days). {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "model",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 6: BAB x IDIOVOL (Frazzini-Pedersen + AHXZ Dual Insulation)
    # Low-beta AND low-idiovol = double-anomaly capture with diversified drivers.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [10, 14]:
                catalog.append({
                    "pillar": "BAB_X_IDIOVOL",
                    "archetype": f"BAB_x_IdioVol_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"group_neutralize("
                        f"rank(-ts_decay_linear(beta_last_60_days_spy, {d})) * "
                        f"rank(-ts_decay_linear(idiosyncratic_vol_last_60_days_spy, {d})), "
                        f"{g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"FP2014 x AHXZ2006: low-beta x low-idiovol composite. "
                        f"Both anomalies reinforcing: double-anomaly capture with diversified drivers. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "model",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 7: IdioVol x 12-Month Momentum Interaction (Extract 9, Table VIII Panel B)
    # Table VIII proves: Low IdioVol + 12-Month Winner generates +1.22%/mo alpha (t=5.46).
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [10, 14]:
                catalog.append({
                    "pillar": "AHXZ_IDIOVOL_X_MOMENTUM",
                    "archetype": f"AHXZ_IdioVolMom_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"group_neutralize("
                        f"rank(-ts_decay_linear(idiosyncratic_vol_last_60_days_spy, {d})) * "
                        f"rank(ts_decay_linear(ts_delta(close, 252) / ts_delay(close, 252), 20)), "
                        f"{g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"AHXZ2006 Table VIII Panel B: Low idiovol + 12m momentum winner composite. "
                        f"Eliminates loser drag; delivers +1.22%/mo FF3 alpha (t=5.46). {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "model",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 8: Idiosyncratic Variance Purity Ratio (Extract 7 & 12, Table VI)
    # Short stocks where idiosyncratic volatility dominates total volatility.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [10, 14]:
                catalog.append({
                    "pillar": "AHXZ_IDIOVOL_PURITY_RATIO",
                    "archetype": f"AHXZ_IdioPurity_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"group_neutralize("
                        f"signed_power(rank(-ts_decay_linear("
                        f"idiosyncratic_vol_last_60_days_spy / (ts_std_dev(returns, 60) * 15.87 + 0.001), {d}"
                        f")), 0.5), {g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"AHXZ2006 Extract 12: Ratio of idiovol to total vol. High idio-purity identifies "
                        f"extreme speculative retail lottery stocks prone to severe underperformance. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "model",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 9: IdioVol Short-Term Surge Reversal (Extract 13)
    # Sudden 10-day spike in idiosyncratic volatility signals jump hazard.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [10, 14]:
                catalog.append({
                    "pillar": "AHXZ_IDIOVOL_SURGE_FADE",
                    "archetype": f"AHXZ_IdioSurgeFade_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"group_neutralize("
                        f"rank(-ts_decay_linear(ts_delta(idiosyncratic_vol_last_60_days_spy, 10), {d})), "
                        f"{g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"AHXZ2006 Extract 13: 10-day surge in idiosyncratic volatility signals sudden firm "
                        f"instability. Fading recent vol explosions captures distress drift. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "model",
                    "source_kb": SOURCE_KB,
                })

    return catalog
