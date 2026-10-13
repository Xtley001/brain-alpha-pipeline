"""
Chan, Jegadeesh & Lakonishok (1996), Fink (2020), Harshita et al. (2018) & Martineau (2021)
Source KB: docs/kb/sentiment/cjl_fink_harshita_martineau_pead.md

Key Institutional Empirical Findings:
1. Chan, Jegadeesh & Lakonishok (1996, Journal of Finance):
   - Price momentum (15.4%/yr, t=4.49) and SUE earnings momentum (6.8%/yr, t=3.63) are distinct and non-redundant.
   - In two-way sorts, high SUE outperforms low SUE by 4.2% to 6.1% per year within every prior-return quintile.
   - Earnings momentum does not experience long-term reversal, reflecting permanent cash-flow news.
2. Fink (2020, Graz WP / Survey of 222 PEAD papers):
   - SUE drift averages ~4% per quarter historically and is inversely related to firm size.
   - Revenue surprises produce stronger and more durable drift than cost-cutting expense surprises (Jegadeesh & Livnat 2006).
   - Investor attention clutter (high announcement volume days) increases delayed response and subsequent drift.
3. Harshita, Singh & Yadav (2018, TEL):
   - Standardized unexpected earnings: SUE = (EPS_{t} - EPS_{t-4}) / Price.
   - Extreme decile spread (P10 - P1) equals +4.8% (t=7.80 Fama-MacBeth).
   - SUE * Value interaction is positive and strong (omega_4 = +0.07, t=3.16).
   - SUE * Beta interaction is negative (omega_2 = -0.05 to -0.15, t=-1.66 to -2.60), confirming cleaner drift in low-beta stocks.
4. Martineau (2021, Critical Finance Review):
   - Simple linear 60-day SUE drift has dissipated in mega-caps since 2006; prices reflect earnings 6x faster.
   - Surviving alpha requires conditioning on attention shocks, revenue quality, and short-horizon execution windows.
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

    universes = ["TOPSP500", "TOP500", "TOP1000", "TOP2000"]
    neut_groups = ["SUBINDUSTRY", "SECTOR", "MARKET"]
    decays = [5, 10, 20]

    # ─────────────────────────────────────────────────────────────────────────
    # 1. Chan, Jegadeesh & Lakonishok (1996): Dual Momentum (Price + SUE)
    # Composite of intermediate price momentum and fundamental operating income surprise
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:3]:
        for g in neut_groups:
            for d in [10, 20]:
                catalog.append({
                    "pillar": "CJL_DUAL_MOMENTUM",
                    "archetype": f"CJL_Dual_Momentum_{u}_{g}_d{d}",
                    "expression": (
                        f"group_neutralize("
                        f"rank(ts_decay_linear(returns, 126)) * 0.5 + "
                        f"rank(ts_delta(ebitda / (close * sharesout + 1e-4), 60)) * 0.5, "
                        f"{g.lower()})"
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
    # 2. Fink (2020) & Jegadeesh-Livnat: Revenue Surprise vs Cost Reduction Quality
    # Top-line sales expansion creates more persistent drift than operating expense cuts
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            catalog.append({
                "pillar": "FINK_REVENUE_SURPRISE_QUALITY",
                "archetype": f"Fink_Revenue_Surprise_Quality_{u}_{g}",
                "expression": (
                    f"group_neutralize("
                    f"rank(ts_delta(sales, 60) / (assets + 1e-4)) - "
                    f"rank(ts_delta(operating_expense, 60) / (assets + 1e-4)), "
                    f"{g.lower()})"
                ),
                "hypothesis": (
                    f"Fink (2020) Observation 15 & Jegadeesh & Livnat (2006): Revenue surprises provide durable signals "
                    f"of market demand expansion that generate stronger and more persistent post-earnings drift than cost cuts. {u}."
                ),
                "universe": u,
                "neutralization": g,
                "decay": 20,
                "category": "fundamental",
                "source_kb": SOURCE_KB,
            })

    # ─────────────────────────────────────────────────────────────────────────
    # 3. Harshita, Singh & Yadav (2018): Value-SUE Interaction
    # SUE interacted with high book-to-price ratio (omega_4 = +0.07, t=3.16)
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:3]:
        for g in neut_groups:
            for d in [10, 15]:
                catalog.append({
                    "pillar": "HARSHITA_VALUE_SUE_INTERACTION",
                    "archetype": f"Harshita_Value_SUE_{u}_{g}_d{d}",
                    "expression": (
                        f"group_neutralize("
                        f"rank(ts_delta(net_income / (close * sharesout + 1e-4), 60)) * "
                        f"rank(book_to_price), "
                        f"{g.lower()})"
                    ),
                    "hypothesis": (
                        f"Harshita, Singh & Yadav (2018) Table 2: The PEAD-SUE relationship is significantly magnified "
                        f"in value stocks (omega_4 = 0.07, t=3.16), creating large fundamental valuation re-ratings. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 4. Harshita, Singh & Yadav (2018): Low-Beta SUE Persistence
    # Negative interaction between market beta and SUE drift (omega_2 = -0.05 to -0.15)
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:3]:
        for g in neut_groups:
            catalog.append({
                "pillar": "HARSHITA_LOW_BETA_SUE",
                "archetype": f"Harshita_Low_Beta_SUE_{u}_{g}",
                "expression": (
                    f"group_neutralize("
                    f"rank(ts_delta(ebitda / (assets + 1e-4), 60)) * "
                    f"rank(-ts_corr(returns, group_mean(returns, 1, market), 60)), "
                    f"{g.lower()})"
                ),
                "hypothesis": (
                    f"Harshita, Singh & Yadav (2018) Table 2: Low systematic beta isolates fundamental cash flow drift "
                    f"from market beta noise (negative SUE x Beta interaction, t=-1.66 to -2.60). {u}."
                ),
                "universe": u,
                "neutralization": g,
                "decay": 20,
                "category": "analyst",
                "source_kb": SOURCE_KB,
            })

    # ─────────────────────────────────────────────────────────────────────────
    # 5. Fink (2020) & Hirshleifer: Investor Clutter & Attention Distraction
    # High volume trading day interacted with earnings surprise and volatility reduction
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:2]:
        for g in neut_groups:
            catalog.append({
                "pillar": "FINK_ATTENTION_CLUTTER_DRIFT",
                "archetype": f"Fink_Attention_Clutter_{u}_{g}",
                "expression": (
                    f"trade_when(volume > adv20 * 1.25, "
                    f"group_neutralize("
                    f"rank(ts_delta(net_income, 60) / (assets + 1e-4)) * "
                    f"ts_rank(-ts_std(returns, 20), 40), "
                    f"{g.lower()}), "
                    f"-1)"
                ),
                "hypothesis": (
                    f"Fink (2020) Observation 19 & Hirshleifer et al. (2009): Clutter and high announcement volume "
                    f"distract investors, blunting the immediate reaction and generating protracted post-earnings drift. {u}."
                ),
                "universe": u,
                "neutralization": g,
                "decay": 15,
                "category": "sentiment",
                "source_kb": SOURCE_KB,
            })

    # ─────────────────────────────────────────────────────────────────────────
    # 6. Martineau (2021): Fast Post-Earnings Discovery Acceleration
    # Capturing immediate post-earnings convergence in broad market universes
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[1:]:
        for g in neut_groups:
            for d in [3, 5]:
                catalog.append({
                    "pillar": "MARTINEAU_FAST_DRIFT_CONVERGENCE",
                    "archetype": f"Martineau_Fast_Drift_{u}_{g}_d{d}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.95, "
                        f"group_neutralize("
                        f"rank(ts_decay_linear(returns, 5)) * "
                        f"rank(ts_delta(ebitda / (close * sharesout + 1e-4), 60)), "
                        f"{g.lower()}), "
                        f"-1)"
                    ),
                    "hypothesis": (
                        f"Martineau (2021) Section 3: Modern price discovery accelerates 6x faster; capturing surviving drift "
                        f"requires short execution windows (decay 3-5 days) with volume confirmation in non-mega-cap stocks. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "sentiment",
                    "source_kb": SOURCE_KB,
                })

    return catalog


if __name__ == "__main__":
    candidates = generate_modern_pead_dynamics_candidates()
    print(f"Generated {len(candidates)} modern PEAD candidates.")
    print("Sample expression:")
    print(candidates[0]["expression"])
