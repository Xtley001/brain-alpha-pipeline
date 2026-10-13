"""
Edmans, García & Norli (2007) & Silver, Bazarova & Raseta (2022)
Source KB: docs/kb/sentiment/edmans_silver_bazarova_behavioral_expectations.md

Key Institutional Empirical Findings:
1. Edmans, García & Norli (2007, Journal of Finance):
   - Exogenous mood shocks (international sports match losses) cause economically massive and statistically significant next-day stock market declines (-38 bps for World Cup elimination, t=-3.73).
   - Marked loss aversion / negative mood asymmetry: victories produce zero market reaction, but losses cause sharp drops.
   - The loss effect is substantially stronger in small-cap and retail-held stocks, where sentiment pricing pressure is highest.
   - The drop represents pure non-fundamental sentiment distortion that predictably mean-reverts over subsequent multi-day windows.
2. Silver, Bazarova & Raseta (2022, SSRN):
   - Multicomponent expectations model: agents alternate between bounded rational fundamentalists and imitative trend-following herders.
   - Non-linear transition function: when distance |Price - Intrinsic Value| exceeds threshold bands, fundamentalist mean reversion asserts dominance.
   - Stochastic resonance (SR): exogenous noise spikes facilitate signal detection, accelerating the discovery of mispriced fundamental assets.
"""
from typing import Any, Dict, List

SOURCE_KB = "docs/kb/sentiment/edmans_silver_bazarova_behavioral_expectations.md"


def generate_edmans_silver_mood_candidates() -> List[Dict[str, Any]]:
    """
    Generate paper-grounded alpha candidates from Edmans, García & Norli (2007)
    and Silver, Bazarova & Raseta (2022).
    All expressions feature balanced parentheses, valid BRAIN operators, and 100% source_kb traceability.
    """
    catalog: List[Dict[str, Any]] = []

    universes = ["TOPSP500", "TOP500", "TOP1000", "TOP2000"]
    neut_groups = ["SUBINDUSTRY", "SECTOR", "MARKET"]
    decays = [5, 10, 20]

    # ─────────────────────────────────────────────────────────────────────────
    # 1. Edmans, García & Norli (2007): Exogenous Sentiment Overshoot Reversion
    # Sharp short-term sentiment declines (-38 bps loss effect) reverting to mean
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:3]:
        for g in neut_groups:
            for d in [5, 10]:
                catalog.append({
                    "pillar": "EDMANS_EXOGENOUS_MOOD_REVERSION",
                    "archetype": f"Edmans_Mood_Reversion_{u}_{g}_d{d}",
                    "expression": (
                        f"trade_when(volume > adv20 * 1.1, "
                        f"group_neutralize("
                        f"rank(-ts_decay_linear(returns, 3)) * "
                        f"ts_rank(-ts_std(returns, 10), 30), "
                        f"{g.lower()}), "
                        f"-1)"
                    ),
                    "hypothesis": (
                        f"Edmans, García & Norli (2007) Section 4: Exogenous negative sentiment shocks produce sharp, non-fundamental "
                        f"drawdowns (-38 bps next day, t=-3.73) that systematically mean-revert as emotional overreaction clears. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "sentiment",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 2. Edmans, García & Norli (2007): Small-Cap Sentiment Asymmetry
    # Small-cap stocks with solid fundamentals experiencing emotional drawdown
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[1:]:
        for g in neut_groups:
            catalog.append({
                "pillar": "EDMANS_SMALL_STOCK_SENTIMENT",
                "archetype": f"Edmans_Small_Sentiment_{u}_{g}",
                "expression": (
                    f"group_neutralize("
                    f"rank(-(close * sharesout)) * "
                    f"rank(-ts_decay_linear(returns, 5)) * "
                    f"rank(ebitda / (assets + 1e-4)), "
                    f"{g.lower()})"
                ),
                "hypothesis": (
                    f"Edmans, García & Norli (2007) Section 5: Small-cap stocks suffer disproportionately large sentiment drops "
                    f"due to retail holder dominance; firms with strong cash flow profitability provide asymmetric rebound alpha. {u}."
                ),
                "universe": u,
                "neutralization": g,
                "decay": 15,
                "category": "sentiment",
                "source_kb": SOURCE_KB,
            })

    # ─────────────────────────────────────────────────────────────────────────
    # 3. Silver, Bazarova & Raseta (2022): Fundamental Distance Transition
    # Non-linear distance between price and intrinsic operating value
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:3]:
        for g in neut_groups:
            for d in [10, 20]:
                catalog.append({
                    "pillar": "SILVER_FUNDAMENTAL_DISTANCE_TRANSITION",
                    "archetype": f"Silver_Fundamental_Distance_{u}_{g}_d{d}",
                    "expression": (
                        f"group_neutralize("
                        f"rank(abs(close / (ebitda / (sharesout + 1e-4) + 1e-4) - "
                        f"ts_mean(close / (ebitda / (sharesout + 1e-4) + 1e-4), 252))) * "
                        f"rank(ebitda / (close * sharesout + 1e-4)), "
                        f"{g.lower()})"
                    ),
                    "hypothesis": (
                        f"Silver, Bazarova & Raseta (2022) Section 2.1: As price distance from fundamental value expands, "
                        f"bounded rational heuristics overwhelm imitative herding, accelerating mean reversion to intrinsic valuation. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 4. Silver, Bazarova & Raseta (2022): Stochastic Resonance Noise Filter
    # Volatility spikes triggering rapid signal detection in deep value stocks
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:3]:
        for g in neut_groups:
            catalog.append({
                "pillar": "SILVER_STOCHASTIC_RESONANCE_NOISE",
                "archetype": f"Silver_Stochastic_Resonance_{u}_{g}",
                "expression": (
                    f"trade_when(ts_std(returns, 10) > group_mean(ts_std(returns, 10), 1, market), "
                    f"group_neutralize(rank(book_to_price) * rank(ts_decay_linear(returns, 5)), {g.lower()}), "
                    f"-1)"
                ),
                "hypothesis": (
                    f"Silver, Bazarova & Raseta (2022) Section 2.2: Stochastic resonance enables background volatility to push "
                    f"sub-threshold fundamental value signals across cognitive barriers, amplifying signal-to-noise ratio in value stocks. {u}."
                ),
                "universe": u,
                "neutralization": g,
                "decay": 10,
                "category": "sentiment",
                "source_kb": SOURCE_KB,
            })

    # ─────────────────────────────────────────────────────────────────────────
    # 5. Silver, Bazarova & Raseta (2022): Herding Exhaustion Reversal
    # Deceleration of trend persistence anchored by cash flow yield
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:2]:
        for g in neut_groups:
            catalog.append({
                "pillar": "SILVER_HERDING_EXHAUSTION",
                "archetype": f"Silver_Herding_Exhaustion_{u}_{g}",
                "expression": (
                    f"group_neutralize("
                    f"rank(-ts_delta(ts_rank(returns, 60), 5)) * "
                    f"rank(ebitda / (close * sharesout + 1e-4)), "
                    f"{g.lower()})"
                ),
                "hypothesis": (
                    f"Silver, Bazarova & Raseta (2022) Section 2.1.2: Imitative momentum cascades suffer sudden trend exhaustion; "
                    f"stocks with high cash flow yields recover first as fundamentalist processing reasserts market control. {u}."
                ),
                "universe": u,
                "neutralization": g,
                "decay": 20,
                "category": "sentiment",
                "source_kb": SOURCE_KB,
            })

    return catalog


if __name__ == "__main__":
    candidates = generate_edmans_silver_mood_candidates()
    print(f"Generated {len(candidates)} Edmans-Silver mood & expectation candidates.")
    print("Sample expression:")
    print(candidates[0]["expression"])
