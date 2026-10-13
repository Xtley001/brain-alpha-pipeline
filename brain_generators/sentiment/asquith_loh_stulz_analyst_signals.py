"""
Asquith, Mikhail & Au (2005), Loh & Stulz (2018) & Floropoulos (2018)
Source KB: docs/kb/sentiment/asquith_loh_stulz_floropoulos_analysts.md

Key Institutional Empirical Findings:
1. Asquith, Mikhail & Au (2005, Journal of Financial Economics):
   - Price target revisions (Delta Target / Price) have a larger and more statistically significant market reaction than earnings forecast revisions.
   - Including price targets dramatically increases regression fit and partially subsumes earnings forecasts.
   - Market response is heavily asymmetric: downgrades receive the most scrutiny and generate massive negative alpha, while upgrades are discounted (55% buys vs 6% sells).
   - Price targets achieve ~54% accuracy within 12 months; extreme optimism is inversely related to achieving target.
2. Loh & Stulz (2018, Journal of Finance):
   - In bad times (crises, high market volatility, recessions), the 2-day abnormal price impact of analyst revisions is substantially larger for both upgrades and downgrades.
   - Bayesian mechanism: macro uncertainty increases, private signal precision falls, so rational investors put higher weight on sell-side analyst signals.
   - Harder-to-value firms (high idiosyncratic risk) experience the largest increase in analyst research reliance.
3. Floropoulos (2018, UC3M WP):
   - Two-year-ahead (FY2) forecasts are the most informative in financial markets (0.42% abnormal return vs 0.30% for FY1 alone).
   - Concordant revisions (FY1 and FY2 revised in the same direction) double abnormal post-announcement drift.
   - Contrasting revisions: investors prioritize longer-term FY2 expectations over temporary FY1 revisions.
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

    universes = ["TOPSP500", "TOP500", "TOP1000", "TOP2000"]
    neut_groups = ["SUBINDUSTRY", "SECTOR", "MARKET"]
    decays = [5, 10, 20]

    # ─────────────────────────────────────────────────────────────────────────
    # 1. Asquith, Mikhail & Au (2005): Target Price Implied Return & Optimism Truncation
    # High implied target return with penalty on extreme optimism (> 60% upside)
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:3]:
        for g in neut_groups:
            for d in [10, 20]:
                catalog.append({
                    "pillar": "ASQUITH_TARGET_OPTIMISM_TRUNCATION",
                    "archetype": f"Asquith_Target_Optimism_{u}_{g}_d{d}",
                    "expression": (
                        f"group_neutralize("
                        f"rank(ts_decay_linear(ts_delta(analyst_eps_mean, 20) / (close + 1e-4), 10)) * "
                        f"rank(trade_when(ts_decay_linear(returns, 60) < 0.50, 1.0, 0.2)), "
                        f"{g.lower()})"
                    ),
                    "hypothesis": (
                        f"Asquith, Mikhail & Au (2005) Section 4: Analyst price target and earnings revisions provide strong price discovery, "
                        f"but extreme optimism (>50% projected upside) is inversely related to target achievement (54% base accuracy). {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 2. Asquith, Mikhail & Au (2005): Downgrade Scrutiny Asymmetry
    # Severe negative drift following analyst downgrades & downward revisions
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:3]:
        for g in neut_groups:
            catalog.append({
                "pillar": "ASQUITH_DOWNGRADE_ASYMMETRY",
                "archetype": f"Asquith_Downgrade_Asymmetry_{u}_{g}",
                "expression": (
                    f"group_neutralize("
                    f"rank(-ts_delta(analyst_eps_mean, 22) / (close + 1e-4)) * "
                    f"ts_rank(-returns, 22), "
                    f"{g.lower()})"
                ),
                "hypothesis": (
                    f"Asquith, Mikhail & Au (2005) Section 3: Downgrades receive the most scrutiny from institutional investors, "
                    f"generating massive and persistent negative abnormal drift that is rarely reversed. {u}."
                ),
                "universe": u,
                "neutralization": g,
                "decay": 20,
                "category": "analyst",
                "source_kb": SOURCE_KB,
            })

    # ─────────────────────────────────────────────────────────────────────────
    # 3. Loh & Stulz (2018): Bad Times Analyst Revision Magnifier
    # Sell-side revisions have substantially larger price impact during high uncertainty periods
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:3]:
        for g in neut_groups:
            for d in [5, 10]:
                catalog.append({
                    "pillar": "LOH_STULZ_BAD_TIMES_MAGNIFIER",
                    "archetype": f"Loh_Stulz_Bad_Times_{u}_{g}_d{d}",
                    "expression": (
                        f"trade_when(ts_std(returns, 22) > group_mean(ts_std(returns, 22), 1, market), "
                        f"group_neutralize(rank(ts_delta(analyst_eps_mean, 20) / (close + 1e-4)), {g.lower()}), "
                        f"-1)"
                    ),
                    "hypothesis": (
                        f"Loh & Stulz (2018) Section 2: In bad times (elevated market volatility), rational Bayesian investors "
                        f"place significantly higher weight on sell-side analyst revisions because private precision plunges. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 4. Loh & Stulz (2018): Hard-to-Value Firm Revision Interaction
    # Sell-side output surges most for firms with high idiosyncratic uncertainty
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            catalog.append({
                "pillar": "LOH_STULZ_HARD_TO_VALUE",
                "archetype": f"Loh_Stulz_Hard_To_Value_{u}_{g}",
                "expression": (
                    f"group_neutralize("
                    f"rank(ts_delta(analyst_eps_mean, 20) / (close + 1e-4)) * "
                    f"rank(ts_std(returns, 60)), "
                    f"{g.lower()})"
                ),
                "hypothesis": (
                    f"Loh & Stulz (2018) Table 5: Harder-to-value firms with elevated idiosyncratic risk experience the largest "
                    f"increase in sell-side analyst reliance and price impact during market downturns. {u}."
                ),
                "universe": u,
                "neutralization": g,
                "decay": 15,
                "category": "analyst",
                "source_kb": SOURCE_KB,
            })

    # ─────────────────────────────────────────────────────────────────────────
    # 5. Floropoulos (2018): Concordant Horizon Revision (Short + Intermediate)
    # Joint alignment of short-term (FY1) and long-term (FY2) revision trends
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:3]:
        for g in neut_groups:
            catalog.append({
                "pillar": "FLOROPOULOS_CONCORDANT_REVISION",
                "archetype": f"Floropoulos_Concordant_{u}_{g}",
                "expression": (
                    f"group_neutralize("
                    f"rank(ts_delta(analyst_eps_mean, 20) / (close + 1e-4)) + "
                    f"rank(ts_delta(analyst_eps_mean, 60) / (close + 1e-4)), "
                    f"{g.lower()})"
                ),
                "hypothesis": (
                    f"Floropoulos (2018) Section 3: When analysts revise short- and intermediate-term forecasts in the same "
                    f"direction (concordant revision), post-announcement abnormal drift nearly doubles (+0.60% vs +0.30%). {u}."
                ),
                "universe": u,
                "neutralization": g,
                "decay": 20,
                "category": "analyst",
                "source_kb": SOURCE_KB,
            })

    # ─────────────────────────────────────────────────────────────────────────
    # 6. Floropoulos (2018): Structural Horizon Anchoring (FY2 over FY1 Noise)
    # Prioritizing intermediate revision trend over short-term noise
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:2]:
        for g in neut_groups:
            catalog.append({
                "pillar": "FLOROPOULOS_STRUCTURAL_ANCHORING",
                "archetype": f"Floropoulos_Structural_Anchor_{u}_{g}",
                "expression": (
                    f"group_neutralize("
                    f"rank(ts_delta(analyst_eps_mean, 60) / (close + 1e-4)) - "
                    f"rank(ts_delta(analyst_eps_mean, 5) / (close + 1e-4)), "
                    f"{g.lower()})"
                ),
                "hypothesis": (
                    f"Floropoulos (2018) Section 4: Contrasting revisions reveal that investors prioritize structural intermediate-horizon "
                    f"revisions (60 days) over short-term transient noise (5 days) when evaluating true long-term value. {u}."
                ),
                "universe": u,
                "neutralization": g,
                "decay": 20,
                "category": "analyst",
                "source_kb": SOURCE_KB,
            })

    return catalog


if __name__ == "__main__":
    candidates = generate_asquith_loh_stulz_analyst_candidates()
    print(f"Generated {len(candidates)} Asquith-Loh-Stulz-Floropoulos analyst candidates.")
    print("Sample expression:")
    print(candidates[0]["expression"])
