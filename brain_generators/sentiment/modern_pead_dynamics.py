"""
Chan, Jegadeesh & Lakonishok (1996), Fink (2020), Harshita et al. (2018) & Martineau (2021)
Modern PEAD Microstructure, Revenue Surprises & Attention Frictions
Source KB: docs/kb/sentiment/cjl_fink_harshita_martineau_pead.md
WorldQuant Master Recalibration: docs/kb/sentiment/worldquant_brain_sentiment_master_recalibration.md

Key Institutional Empirical Findings:
1. Chan, Jegadeesh & Lakonishok (1996, Journal of Finance):
   - Price momentum and SUE earnings momentum are distinct and non-redundant.
   - In two-way sorts, high SUE outperforms low SUE by 4.2% to 6.1% per year within every prior-return quintile.
2. Fink (2020, Graz WP / Survey of 222 PEAD papers):
   - Revenue surprises produce stronger and more durable drift than cost-cutting expense surprises (Jegadeesh & Livnat 2006).
   - Investor attention clutter (high announcement volume days) increases delayed response and subsequent drift.
3. Harshita, Singh & Yadav (2018, TEL):
   - Extreme decile spread (P10 - P1) equals +4.8% (t=7.80 Fama-MacBeth).
   - Low-beta stocks experience less speculative noise and more persistent drift.
4. Martineau (2021, Critical Finance Review):
   - Simple linear 60-day SUE drift has dissipated in mega-caps; prices reflect earnings 6x faster.
   - Surviving alpha requires short-horizon execution windows, attention shocks, and revenue quality.

Live Verified BRAIN Fields:
    snt1_d1_earningssurprise: Standardized Unexpected Earnings (SUE)
    rp_css_revenue: RavenPack composite sentiment score for revenue news
    rp_css_earnings: RavenPack composite sentiment score for earnings news
    snt1_d1_netearningsrevision: Net analyst earnings revision momentum score
    snt1_d1_dtstsespe: Analyst forecast dispersion / disagreement standard deviation
"""
from typing import Any, Dict, List

SOURCE_KB = "docs/kb/sentiment/cjl_fink_harshita_martineau_pead.md"


def generate_modern_pead_dynamics_candidates() -> List[Dict[str, Any]]:
    """
    Generate paper-grounded alpha candidates from Chan, Jegadeesh & Lakonishok (1996),
    Fink (2020), Harshita et al. (2018), and Martineau (2021).
    All expressions feature balanced parentheses, valid BRAIN operators, and 100% source_kb traceability.
    """
    catalog: List[Dict[str, Any]] = []

    universes   = ["TOP1000", "TOP500", "TOPSP500"]
    neut_groups = ["SUBINDUSTRY", "SECTOR"]
    decays      = [5, 8, 10, 12]

    # ─────────────────────────────────────────────────────────────────────────
    # 1. Chan, Jegadeesh & Lakonishok (1996): Dual Momentum (Price + SUE)
    # Composite of intermediate price momentum and fundamental SUE surprise
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for d in [10, 12]:
                catalog.append({
                    "pillar": "CJL_DUAL_MOMENTUM",
                    "archetype": f"CJL_DualMomentum_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"group_neutralize("
                        f"rank(ts_decay_linear(snt1_d1_earningssurprise, {d})) * "
                        f"rank(ts_decay_linear(returns, 126) - ts_decay_linear(returns, 5)), "
                        f"{g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"Chan, Jegadeesh & Lakonishok (1996) Table III: Price momentum and earnings surprise momentum (SUE) "
                        f"are distinct, mutually reinforcing anomalies (+4.2% to +6.1% spread, t=3.63). {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 2. Fink (2020) & Jegadeesh-Livnat: Revenue Surprise Quality vs Earnings Tone
    # Top-line revenue sentiment creates more persistent drift than cost cuts
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for d in [8, 10, 12]:
                catalog.append({
                    "pillar": "FINK_REVENUE_QUALITY_SPREAD",
                    "archetype": f"Fink_RevQualitySpread_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"group_neutralize("
                        f"rank(ts_decay_linear(rp_css_revenue, {d}) - ts_decay_linear(rp_css_earnings, {d})) * "
                        f"rank(-ts_delta(close, 3) / (ts_std_dev(close, 20) + 0.001)), "
                        f"{g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"Fink (2020) Obs. 15 & Jegadeesh & Livnat (2006): Revenue sentiment spread (rp_css_revenue - rp_css_earnings) "
                        f"isolates top-line commercial demand expansion, generating superior post-announcement drift. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "news",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 3. Harshita, Singh & Yadav (2018): Low-Beta SUE Persistence
    # Negative interaction between market volatility / beta and SUE drift
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for d in [10, 12]:
                catalog.append({
                    "pillar": "HARSHITA_LOW_VOL_SUE",
                    "archetype": f"Harshita_LowVolSUE_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"group_neutralize("
                        f"rank(ts_decay_linear(snt1_d1_earningssurprise, {d})) * "
                        f"rank(-ts_std_dev(returns, 20)) * "
                        f"rank(-ts_delta(close, 3) / (ts_std_dev(close, 20) + 0.001)), "
                        f"{g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"Harshita et al. (2018) Table 2: Low-volatility / low-beta stocks have less speculative noise, "
                        f"allowing fundamental earnings drift to compound cleanly without abrupt whipsaws. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 4. Fink (2020) & Hirshleifer: Investor Clutter & Attention Distraction
    # High volume trading day interacted with earnings surprise and volatility reduction
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for d in [10, 12]:
                catalog.append({
                    "pillar": "FINK_ATTENTION_CLUTTER_DRIFT",
                    "archetype": f"Fink_AttentionClutter_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 1.20, "
                        f"group_neutralize("
                        f"rank(volume / (adv20 + 1)) * "
                        f"rank(ts_decay_linear(snt1_d1_earningssurprise, {d})) * "
                        f"rank(-ts_delta(close, 3) / (ts_std_dev(close, 20) + 0.001)), "
                        f"{g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"Fink (2020) Observation 19 & Hirshleifer et al. (2009): Clutter and high announcement volume "
                        f"distract investors, blunting the immediate reaction and generating protracted post-earnings drift. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 5. Martineau (2021): Fast Post-Earnings Discovery Acceleration
    # Capturing immediate short-horizon drift (decay 5 days) with volume execution filter
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for d in [5, 8]:
                catalog.append({
                    "pillar": "MARTINEAU_FAST_DRIFT_CONVERGENCE",
                    "archetype": f"Martineau_FastDrift_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.85, "
                        f"group_neutralize("
                        f"rank(ts_decay_linear(snt1_d1_earningssurprise, {d})) * "
                        f"rank(-ts_delta(close, 2) / (ts_std_dev(close, 10) + 0.001)), "
                        f"{g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"Martineau (2021) Section 3: Modern price discovery accelerates rapidly; capturing surviving drift "
                        f"requires short execution windows (decay 5-8 days) with volume confirmation. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                    "source_kb": SOURCE_KB,
                })

    return catalog


if __name__ == "__main__":
    candidates = generate_modern_pead_dynamics_candidates()
    print(f"Generated {len(candidates)} modern PEAD candidates.")
    print("Sample expression:")
    print(candidates[0]["expression"])
