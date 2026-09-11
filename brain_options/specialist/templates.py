"""
Deterministic seed template generator for Options Alpha candidates.
Generates fully valid Fast Expression candidates across the quantitative archetypes,
incorporating cross-book high-confidence formulas from Master Books 1-4.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List
from brain_options.specialist.archetypes import ARCHETYPES, OptionArchetype


@dataclass(frozen=True)
class OptionCandidate:
    expression: str
    archetype_name: str
    hypothesis: str
    generation_source: str  # "template" or "llm_reasoning" or "llm_mechanical"


def generate_template_candidates() -> list[OptionCandidate]:
    candidates: list[OptionCandidate] = []

    # 1. Forward Basis Spread across tenors and groups
    for tenor in [10, 20, 30, 60, 90]:
        for grp in ["sector", "subindustry"]:
            expr = f"group_neutralize(rank((forward_price_{tenor} - close) / close), {grp})"
            candidates.append(
                OptionCandidate(
                    expression=expr,
                    archetype_name="Forward Basis Spread",
                    hypothesis=f"Synthetic forward basis at {tenor}d tenor demeaned by {grp} predicts drift.",
                    generation_source="template",
                )
            )

    # 2. Forward Basis Velocity
    for tenor in [20, 30]:
        for window in [3, 5, 10]:
            expr = f"group_neutralize(rank(ts_delta((forward_price_{tenor} - close) / close, {window})), sector)"
            candidates.append(
                OptionCandidate(
                    expression=expr,
                    archetype_name="Forward Basis Velocity",
                    hypothesis=f"Acceleration in {tenor}d forward basis over {window} days indicates institutional front-running.",
                    generation_source="template",
                )
            )

    # 3. Put-Call Ratio Contrarian Reversal
    for tenor in [10, 20, 30]:
        for window in [20, 40, 60]:
            for grp in ["sector", "subindustry"]:
                expr = f"group_neutralize(rank(-ts_zscore(pcr_vol_{tenor}, {window})), {grp})"
                candidates.append(
                    OptionCandidate(
                        expression=expr,
                        archetype_name="Put-Call Ratio Contrarian Reversal",
                        hypothesis=f"Contrarian fade of extreme {tenor}d put-call volume ratio spikes over {window}d window.",
                        generation_source="template",
                    )
                )

    # 4. PCR Flow to Open Interest Surge
    for tenor in [20, 30]:
        for window in [5, 10, 20]:
            expr = f"group_neutralize(rank(-ts_rank(pcr_vol_{tenor} / (pcr_oi_{tenor} + 0.001), {window})), subindustry)"
            candidates.append(
                OptionCandidate(
                    expression=expr,
                    archetype_name="PCR Volume-to-OI Flow Surge",
                    hypothesis=f"Surge in {tenor}d put volume relative to open interest over {window}d flags aggressive positioning.",
                    generation_source="template",
                )
            )

    # 5. Volatility Skew Acceleration
    for tenor in [20, 30, 60]:
        for window in [3, 5, 10]:
            expr = f"group_neutralize(rank(-ts_delta(implied_volatility_mean_skew_{tenor}, {window})), sector)"
            candidates.append(
                OptionCandidate(
                    expression=expr,
                    archetype_name="Volatility Skew Steepness Shock",
                    hypothesis=f"Sudden softening of {tenor}d downside put skew over {window}d signals tail-risk subsiding.",
                    generation_source="template",
                )
            )

    # 6. Sqrt-T Normalized Skew Acceleration (Cross-Book High Confidence #1: Book 2 & Book 3)
    for tenor in [20, 30, 60]:
        sqrt_t = round(math.sqrt(tenor / 252.0), 4)
        for window in [3, 5]:
            expr = f"group_neutralize(rank(-ts_delta(implied_volatility_mean_skew_{tenor} * {sqrt_t}, {window})), subindustry)"
            candidates.append(
                OptionCandidate(
                    expression=expr,
                    archetype_name="Sqrt-T Normalized Skew Acceleration",
                    hypothesis=f"Decay-normalized sqrt(T) downside skew shift at {tenor}d over {window}d isolates pure tail repricing.",
                    generation_source="template",
                )
            )

    # 7. Call Breakeven Hurdle Spread
    for tenor in [10, 20, 30, 60]:
        for grp in ["sector", "subindustry"]:
            expr = f"group_neutralize(rank((call_breakeven_{tenor} - close) / close), {grp})"
            candidates.append(
                OptionCandidate(
                    expression=expr,
                    archetype_name="Call Breakeven Hurdle Spread",
                    hypothesis=f"OI-weighted call breakeven hurdle rate at {tenor}d tenor demeaned by {grp}.",
                    generation_source="template",
                )
            )

    # 8. Call Breakeven Hurdle Acceleration
    for tenor in [20, 30]:
        for window in [3, 5]:
            expr = f"group_neutralize(rank(ts_delta((call_breakeven_{tenor} - close) / close, {window})), subindustry)"
            candidates.append(
                OptionCandidate(
                    expression=expr,
                    archetype_name="Call Breakeven Hurdle Acceleration",
                    hypothesis=f"Acceleration in {tenor}d call breakeven hurdle rate over {window}d signals target price repricing.",
                    generation_source="template",
                )
            )

    # 9. Liquidity-Gated Breakeven Surge
    for tenor in [20, 30]:
        expr = f"trade_when(volume > adv20, group_neutralize(rank((call_breakeven_{tenor} - close) / close), sector), -1)"
        candidates.append(
            OptionCandidate(
                expression=expr,
                archetype_name="Liquidity-Gated Breakeven Surge",
                hypothesis=f"Trade {tenor}d call breakeven upside only when trading volume exceeds 20-day average.",
                generation_source="template",
            )
        )

    # 10. Volatility Term Structure Slope
    candidates.append(
        OptionCandidate(
            expression="group_neutralize(rank(-(implied_volatility_mean_30 / (implied_volatility_mean_90 + 0.001) - 1.0)), sector)",
            archetype_name="Volatility Term Structure Slope",
            hypothesis="Fade extreme inversion between 30d and 90d implied volatility term structure.",
            generation_source="template",
        )
    )

    # 11. Pairwise Forward Volatility Term Notch (Cross-Book High Confidence #8: Books 1, 2, 4)
    # Forward var = (IV90^2 * 90 - IV30^2 * 30) / 60
    candidates.append(
        OptionCandidate(
            expression="group_neutralize(rank(-(sqrt(max(0.0001, (signed_power(implied_volatility_mean_90, 2) * 90 - signed_power(implied_volatility_mean_30, 2) * 30) / 60)) - implied_volatility_mean_30)), sector)",
            archetype_name="Pairwise Forward Volatility Term Notch",
            hypothesis="Forward volatility notch between 30d and 90d isolates mispriced scheduled event variance.",
            generation_source="template",
        )
    )

    # 12. Variance Risk Premium (IV vs RV)
    for tenor, win in [(20, 20), (30, 30)]:
        expr = f"group_neutralize(rank(-(implied_volatility_mean_{tenor} - ts_std_dev(returns, {win}) * 15.87)), sector)"
        candidates.append(
            OptionCandidate(
                expression=expr,
                archetype_name="Variance Risk Premium (IV vs RV)",
                hypothesis=f"Short over-priced implied variance when {tenor}d IV exceeds {win}d rolling realized volatility.",
                generation_source="template",
            )
        )

    # 13. Jensen-Debiased Variance Risk Premium (Books 1 & 3: b(20) ~ 0.96 bias correction)
    candidates.append(
        OptionCandidate(
            expression="group_neutralize(rank(-(implied_volatility_mean_20 - ts_std_dev(returns, 20) * 16.53)), subindustry)",
            archetype_name="Jensen-Debiased Variance Risk Premium",
            hypothesis="Variance risk premium with Jensen-debiased realized volatility (15.87 / 0.96 = 16.53) prevents spurious richness.",
            generation_source="template",
        )
    )

    # 14. Optimal Mean-Reversion Threshold Gated VRP (Sinclair Book 1: 0.75 SD optimal entry)
    candidates.append(
        OptionCandidate(
            expression="trade_when(abs(ts_zscore(implied_volatility_mean_30 - ts_std_dev(returns, 30) * 15.87, 40)) > 0.75, group_neutralize(rank(-(implied_volatility_mean_30 - ts_std_dev(returns, 30) * 15.87)), sector), -1)",
            archetype_name="Optimal Mean-Reversion Threshold Gated VRP",
            hypothesis="Condition VRP entry on crossing the 0.75 SD optimal mean-reversion threshold to maximize long-term growth.",
            generation_source="template",
        )
    )

    return candidates
