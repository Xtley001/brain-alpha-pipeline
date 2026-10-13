"""
Asquith, Mikhail & Au (2005), Loh & Stulz (2018) & Floropoulos (2018) — Price Target Dominance & Uncertainty Regimes
Source KB: docs/kb/sentiment/asquith_loh_stulz_floropoulos_analysts.md
WorldQuant Master Recalibration: docs/kb/sentiment/worldquant_brain_sentiment_master_recalibration.md

Key Institutional Empirical Findings:
1. Asquith, Mikhail & Au (2005, Journal of Financial Economics):
   - Price target revisions (Delta Target / Price) have a larger and more statistically significant market reaction than earnings forecast revisions.
   - Including price targets dramatically increases regression fit and partially subsumes earnings forecasts.
   - Market response is heavily asymmetric: downgrades receive the most scrutiny and generate massive negative alpha, while upgrades are discounted.
   - Price targets achieve ~54% accuracy within 12 months; extreme optimism (>50%) is inversely related to achieving target.
2. Loh & Stulz (2018, Journal of Finance):
   - In bad times (crises, high market volatility), the 2-day abnormal price impact of analyst revisions is substantially larger.
   - Bayesian mechanism: macro uncertainty increases, private signal precision falls, so rational investors put higher weight on sell-side analyst signals.
   - Harder-to-value firms (high idiosyncratic risk) experience the largest increase in analyst research reliance.
3. Floropoulos (2018):
   - Concordant multi-horizon revisions double post-announcement drift.

Live Verified BRAIN Fields:
    snt1_d1_nettargetpercent: Net analyst price target percentage upside from current stock price
    rp_css_ptg: RavenPack composite sentiment score for price target announcements
    rp_ess_ptg: RavenPack event sentiment score for price target releases
    snt1_d1_netearningsrevision: Net analyst earnings revision momentum score
    implied_volatility_call_30, implied_volatility_put_30: Options cross-market conviction
"""
from typing import Any, Dict, List

SOURCE_KB = "docs/kb/sentiment/asquith_loh_stulz_floropoulos_analysts.md"


def generate_asquith_loh_stulz_analyst_candidates() -> List[Dict[str, Any]]:
    """
    Generate paper-grounded alpha candidates from Asquith, Mikhail & Au (2005),
    Loh & Stulz (2018), and Floropoulos (2018).
    All expressions feature balanced parentheses, valid BRAIN operators, and 100% source_kb traceability.
    """
    catalog: List[Dict[str, Any]] = []

    universes   = ["TOP1000", "TOP500", "TOPSP500"]
    neut_groups = ["SUBINDUSTRY", "SECTOR"]
    decays      = [8, 10, 12, 15]

    # ─────────────────────────────────────────────────────────────────────────
    # 1. Asquith, Mikhail & Au (2005): Target Price Implied Return with Optimism Truncation
    # High implied target return with penalty on extreme optimism (> 50% upside)
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for d in decays:
                catalog.append({
                    "pillar": "ASQUITH_TARGET_OPTIMISM_TRUNCATION",
                    "archetype": f"Asquith_TargetOptimism_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"trade_when(snt1_d1_nettargetpercent < 0.50, "
                        f"group_neutralize("
                        f"rank(ts_decay_linear(snt1_d1_nettargetpercent, {d})) * "
                        f"rank(-ts_delta(close, 3) / (ts_std_dev(close, 20) + 0.001)), "
                        f"{g.lower()}), -1), -1)"
                    ),
                    "hypothesis": (
                        f"Asquith, Mikhail & Au (2005) Section 4: Analyst price target implied upside (snt1_d1_nettargetpercent) "
                        f"provides superior price discovery, but extreme optimism (>50% upside) is penalized due to bias. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 2. Asquith, Mikhail & Au (2005): RavenPack Price Target NLP Sentiment Tone
    # Machine-readable NLP tone of price target changes captures qualitative justification
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for d in [8, 10, 12]:
                catalog.append({
                    "pillar": "ASQUITH_RP_TARGET_TONE",
                    "archetype": f"Asquith_RPTargetTone_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"group_neutralize("
                        f"rank(ts_decay_linear(rp_css_ptg, {d})) * "
                        f"rank(-ts_delta(close, 3) / (ts_std_dev(close, 20) + 0.001)), "
                        f"{g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"Asquith et al. (2005) Extract 2: Report justification text and price target sentiment (rp_css_ptg) "
                        f"captures qualitative analyst rationale and generates multi-week drift. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 3. Asquith Downgrade Asymmetry Drift
    # Severe negative drift following sell-side downgrades
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for d in [10, 12]:
                catalog.append({
                    "pillar": "ASQUITH_DOWNGRADE_ASYMMETRY",
                    "archetype": f"Asquith_DowngradeAsym_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"group_neutralize("
                        f"rank(-ts_delta(snt1_d1_netearningsrevision, 10)) * "
                        f"rank(-returns), "
                        f"{g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"Asquith, Mikhail & Au (2005) Section 3: Downgrades receive the most scrutiny from institutional investors, "
                        f"driving persistent negative abnormal drift that is rarely reversed. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 4. Target Upside x Options Volatility Smirk Interaction
    # Cross-market options informed order flow confirms analyst target conviction
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for d in [10, 12]:
                catalog.append({
                    "pillar": "ASQUITH_TARGET_X_VOL_SMIRK",
                    "archetype": f"Asquith_TargetxVolSmirk_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"group_neutralize("
                        f"rank(ts_decay_linear((implied_volatility_call_30 - implied_volatility_put_30) / (implied_volatility_mean_30 + 0.001), 10)) * "
                        f"rank(ts_decay_linear(snt1_d1_nettargetpercent, {d})) * "
                        f"rank(-ts_delta(close, 3) / (ts_std_dev(close, 20) + 0.001)), "
                        f"{g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"Asquith (2005) + Xing-Zhang-Zhao (2010): Price target upside confirmed by options implied volatility smirk. "
                        f"Institutional call accumulation validates analyst price target feasibility. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 5. Loh & Stulz (2018): Hard-to-Value Firm Revision Interaction
    # Sell-side output impact surges most for firms with high idiosyncratic uncertainty
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for d in [10, 12]:
                catalog.append({
                    "pillar": "LOH_STULZ_HARD_TO_VALUE",
                    "archetype": f"Loh_Stulz_HardToValue_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"group_neutralize("
                        f"rank(ts_decay_linear(snt1_d1_netearningsrevision, {d})) * "
                        f"rank(ts_std_dev(returns, 60)) * "
                        f"rank(-ts_delta(close, 3) / (ts_std_dev(close, 20) + 0.001)), "
                        f"{g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"Loh & Stulz (2018) Table 5: Harder-to-value firms with elevated idiosyncratic volatility experience "
                        f"the largest increase in sell-side analyst reliance and abnormal price impact. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                    "source_kb": SOURCE_KB,
                })

    return catalog


if __name__ == "__main__":
    candidates = generate_asquith_loh_stulz_analyst_candidates()
    print(f"Generated {len(candidates)} Asquith-Loh-Stulz analyst candidates.")
    print("Sample expression:")
    print(candidates[0]["expression"])
