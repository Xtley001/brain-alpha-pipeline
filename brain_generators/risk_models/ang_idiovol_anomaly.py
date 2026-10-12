"""
Ang, Hodrick, Xing & Zhang (2006) — Idiosyncratic Volatility Anomaly
Baker, Bradley & Wurgler (2011) — Low Volatility Anomaly & Benchmarks
Merton (1974) — Structural Model / Distance-to-Default
Savor & Wilson (2013) — Macroeconomic Risk & Announcement Premiums

Papers:
  1. AHXZ (2006): "The Cross-Section of Volatility and Expected Returns" — JF
     Core: Stocks with HIGH idiosyncratic volatility (IVOL) earn LOWER future returns.
     This is the "volatility puzzle" — it violates standard CAPM predictions.
     IVOL = std of daily residual returns from FF3 model over past 21 trading days.
     Top-quintile IVOL stocks underperform bottom-quintile by 1.06%/month (Table 1).
     BRAIN: idiosyncratic_vol_last_60_days_spy (best proxy, different period but same concept)

  2. Baker-Bradley-Wurgler (2011): "Benchmarks as Limits to Arbitrage" — FAJ
     Core: Explains AHXZ anomaly. Institutional investors benchmarked to indices AVOID
     high-tracking-error low-beta stocks, even if they're attractive. This creates a
     systematic mispricing: high-vol stocks are overpriced, low-vol are underpriced.
     Signal: low-vol universe construction + exposure to benchmark-driven mispricing.

  3. Merton (1974): "On the Pricing of Corporate Debt" — JF
     Core: Equity = call option on firm assets. As asset value falls toward debt face value,
     default probability rises. Distance-to-default (D2D):
       D2D = (ln(V/D) + (μ - σ²/2)T) / (σ√T)
     BRAIN approximation: leverage (debt/equity) × vol proxy → credit-adjusted beta signal
     High-leverage + high-vol stocks → near-default → negative future returns (distress risk)

  4. Savor & Wilson (2013): "How Much Do Investors Care About Macroeconomic Risk?" — JFE
     Core: Pre-announcement drift and announcement-day premium in macro event windows.
     Stocks with HIGH beta to macro announcements (FOMC, CPI, NFP) earn higher returns.
     In particular, macro-beta stocks earn +11bps on announcement days vs flat on other days.
     BRAIN approx: stocks with high realized correlation to market in volatile windows
     (capturing sensitivity to macro shocks).
"""
from typing import Any, Dict, List


def generate_risk_model_p1_candidates() -> List[Dict[str, Any]]:
    """
    AHXZ 2006 + BBW 2011 + Merton 1974 + Savor-Wilson 2013 risk model generators.
    Paper-faithful constructions for the model dataset (model51/52 on BRAIN).
    """
    catalog: List[Dict[str, Any]] = []

    universes   = ["TOPSP500", "TOP500", "TOP1000", "TOP3000"]
    neut_groups = ["SUBINDUSTRY", "SECTOR", "MARKET"]
    decays      = [10, 14, 20]

    # ─────────────────────────────────────────────────────────────────────────
    # AHXZ (2006): Pure Idiosyncratic Volatility Anomaly
    # IVOL = std(daily residuals from FF3, past 21d)
    # Short high-IVOL stocks, long low-IVOL stocks.
    # BRAIN: idiosyncratic_vol_last_60_days_spy is the best available field.
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
                        f"AHXZ2006: high IVOL → low future returns (volatility puzzle). "
                        f"Short extreme IVOL stocks; 1.06%/month underperformance in top IVOL quintile. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "model",
                })

    # ─────────────────────────────────────────────────────────────────────────
    # AHXZ VARIANT: IVOL Change (Rising IVOL = distress escalation)
    # If IVOL is RISING (not just high), it signals ongoing deterioration.
    # Delta IVOL over 21 days is an even sharper timing signal than level.
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
                            f"AHXZ2006 extension: rapidly RISING idiosyncratic volatility signals "
                            f"distress escalation — sharper timing than level signal. {lookback}d delta, {u}."
                        ),
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "model",
                    })

    # ─────────────────────────────────────────────────────────────────────────
    # AHXZ / BBW: Total Realized Volatility (alternative to idiovol)
    # Some signal comes from TOTAL vol (not just idiosyncratic), especially in
    # smaller caps where systematic and idiosyncratic risk blur.
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
                            f"BBW2011: total realized vol anomaly — high total vol → benchmark exclusion → "
                            f"overpriced by momentum chasers → negative future returns. {window}d window, {u}."
                        ),
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "model",
                    })

    # ─────────────────────────────────────────────────────────────────────────
    # MERTON (1974): Distance-to-Default Proxy
    # D2D = (V/D ratio) / (asset vol) — hard to compute exactly in BRAIN.
    # Best approximation: leverage × realized vol → credit-adjusted downside risk
    # High leverage × high vol = near default = negative future returns (distress risk)
    # BRAIN fields: debt_to_equity (leverage), ts_std_dev(returns, 252) (vol)
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
                        f"Merton1974: inverse D2D proxy = leverage × vol. "
                        f"High leverage × high vol = near-default = distress premium (negative future returns). {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "model",
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SAVOR & WILSON (2013): Macro Announcement Premium
    # Stocks with high beta to announcement-day returns earn a premium.
    # Proxy: rolling beta to macro-event windows (high VIX days ≈ macro event days)
    # Signal: beta computed on days with ts_std_dev(market_returns, 1) > 1.5%
    # Approximation: correlation of stock returns with market during high-vol days
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
                        f"Savor-Wilson2013: macro-sensitive stocks (high beta × recent high vol) "
                        f"earn announcement-day premium (+11bps on FOMC/CPI days). {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "model",
                })

    # ─────────────────────────────────────────────────────────────────────────
    # CROSS-SIGNAL: BAB × IDIOVOL (Frazzini-Pedersen + AHXZ combined)
    # FP2014 footnote 2: BAB holds CONTROLLING for AHXZ idiovol.
    # Combined signal: low-beta AND low-idiovol = double-insulated from anomaly risks.
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
                        f"FP2014 × AHXZ2006: low-beta × low-idiovol composite. "
                        f"Both anomalies reinforcing: double-anomaly capture with diversified drivers. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "model",
                })

    return catalog
