"""
Deterministic seed template generator for Options Alpha candidates.
Generates fully valid Fast Expression candidates across the quantitative archetypes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List
from brain_options.specialist.archetypes import ARCHETYPES, OptionArchetype


@dataclass(frozen=True)
class OptionCandidate:
    expression: str
    archetype_name: str
    hypothesis: str
    generation_source: str  # "template" or "llm"


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

    # 6. Call Breakeven Hurdle Spread
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

    # 7. Liquidity-Gated Breakeven Surge
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

    # 8. Volatility Term Structure Slope
    candidates.append(
        OptionCandidate(
            expression="group_neutralize(rank(-(implied_volatility_mean_30 / (implied_volatility_mean_90 + 0.001) - 1.0)), sector)",
            archetype_name="Volatility Term Structure Slope",
            hypothesis="Fade extreme inversion between 30d and 90d implied volatility term structure.",
            generation_source="template",
        )
    )

    # 9. Variance Risk Premium
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

    return candidates
