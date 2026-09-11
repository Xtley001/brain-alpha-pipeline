"""
Mathematical archetypes and quantitative hypotheses for Options Alpha generation.
Each archetype represents a structural derivatives-pricing edge with proven institutional
and academic pedigree, incorporating principles from Options Master Knowledge Base (Books 1-4).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class OptionArchetype:
    name: str
    category: str
    description: str
    economic_rationale: str
    formula_template: str
    typical_horizons: list[int]
    neutralization_groups: list[str]
    is_high_confidence: bool = False


ARCHETYPES: list[OptionArchetype] = [
    OptionArchetype(
        name="Synthetic Forward Basis Spread",
        category="forward_basis",
        description="Spread between synthetic forward price from put-call parity and spot price.",
        economic_rationale="Options market synthetic forwards reflect institutional consensus drift expectations.",
        formula_template="group_neutralize(rank((forward_price_{tenor} - close) / close), {group})",
        typical_horizons=[10, 20, 30, 60, 90],
        neutralization_groups=["sector", "industry", "subindustry"],
    ),
    OptionArchetype(
        name="Forward Basis Velocity",
        category="forward_basis",
        description="Rate of change in synthetic forward basis over trailing window.",
        economic_rationale="Accelerating forward basis reveals institutional accumulation before spot breakout.",
        formula_template="group_neutralize(rank(ts_delta((forward_price_{tenor} - close) / close, {window})), {group})",
        typical_horizons=[10, 20, 30],
        neutralization_groups=["sector", "subindustry"],
    ),
    OptionArchetype(
        name="Put-Call Ratio Contrarian Reversal",
        category="pcr_flow",
        description="Normalized z-score of put-to-call volume ratio.",
        economic_rationale="Extreme spikes in put volume signal capitulation and provide high-conviction squeeze setups.",
        formula_template="group_neutralize(rank(-ts_zscore(pcr_vol_{tenor}, {window})), {group})",
        typical_horizons=[10, 20, 30],
        neutralization_groups=["sector", "industry", "subindustry"],
    ),
    OptionArchetype(
        name="PCR Volume-to-OI Flow Surge",
        category="pcr_flow",
        description="Ratio of daily put-call volume to open interest stock.",
        economic_rationale="Unusual trading velocity in puts relative to existing open interest reveals aggressive smart-money flow.",
        formula_template="group_neutralize(rank(-ts_rank(pcr_vol_{tenor} / (pcr_oi_{tenor} + 0.001), {window})), {group})",
        typical_horizons=[10, 20, 30],
        neutralization_groups=["sector", "subindustry"],
    ),
    OptionArchetype(
        name="Volatility Skew Steepness Shock",
        category="skew",
        description="Change in downside OTM put skew steepness.",
        economic_rationale="Sudden steepening of the skew indicates institutional demand for downside crash protection.",
        formula_template="group_neutralize(rank(-ts_delta(implied_volatility_mean_skew_{tenor}, {window})), {group})",
        typical_horizons=[10, 20, 30, 60],
        neutralization_groups=["sector", "subindustry"],
    ),
    OptionArchetype(
        name="Sqrt-T Normalized Skew Acceleration",
        category="skew",
        description="Downside skew steepness normalized by the square root of expiration time.",
        economic_rationale="Cross-book high confidence principle: skew mathematically decays with sqrt(T). Normalizing isolates true tail risk without double-counting volatility.",
        formula_template="group_neutralize(rank(-ts_delta(implied_volatility_mean_skew_{tenor} * sqrt({tenor} / 252.0), {window})), {group})",
        typical_horizons=[20, 30, 60],
        neutralization_groups=["sector", "subindustry"],
        is_high_confidence=True,
    ),
    OptionArchetype(
        name="Call Breakeven Hurdle Spread",
        category="breakeven",
        description="Percentage distance from spot to open-interest weighted call breakeven price.",
        economic_rationale="Demeaned distance to call breakeven reflects expected upside target priced by option writers.",
        formula_template="group_neutralize(rank((call_breakeven_{tenor} - close) / close), {group})",
        typical_horizons=[10, 20, 30, 60, 90],
        neutralization_groups=["sector", "subindustry"],
    ),
    OptionArchetype(
        name="Call Breakeven Hurdle Acceleration",
        category="breakeven",
        description="Rate of change in open-interest weighted call breakeven hurdle.",
        economic_rationale="Rapidly shifting call breakeven targets signal market makers adjusting upper strike barriers ahead of moves.",
        formula_template="group_neutralize(rank(ts_delta((call_breakeven_{tenor} - close) / close, {window})), {group})",
        typical_horizons=[20, 30, 60],
        neutralization_groups=["sector", "subindustry"],
        is_high_confidence=True,
    ),
    OptionArchetype(
        name="Liquidity-Gated Breakeven Surge",
        category="breakeven",
        description="Call breakeven hurdle filtered by volume surge condition.",
        economic_rationale="Options breakeven upside signals are most actionable when trading volume confirms active participation.",
        formula_template="trade_when(volume > adv20, group_neutralize(rank((call_breakeven_{tenor} - close) / close), {group}), -1)",
        typical_horizons=[20, 30, 60],
        neutralization_groups=["sector", "subindustry"],
    ),
    OptionArchetype(
        name="Volatility Term Structure Slope",
        category="term_structure",
        description="Ratio of front-month implied volatility to 3-month implied volatility.",
        economic_rationale="Inversion of IV term structure (front-month > 3-month) indicates temporary panic pricing that mean-reverts.",
        formula_template="group_neutralize(rank(-(implied_volatility_mean_30 / (implied_volatility_mean_90 + 0.001) - 1.0)), {group})",
        typical_horizons=[30],
        neutralization_groups=["sector", "subindustry"],
    ),
    OptionArchetype(
        name="Pairwise Forward Volatility Term Notch",
        category="term_structure",
        description="Notch between front-month and intermediate forward volatility derived from term structure variance.",
        economic_rationale="Forward volatility extracted across tenors isolates scheduled catalyst risk and event mispricing.",
        formula_template="group_neutralize(rank(-(sqrt(max(0.0001, (signed_power(implied_volatility_mean_90, 2) * 90 - signed_power(implied_volatility_mean_30, 2) * 30) / 60)) - implied_volatility_mean_30)), {group})",
        typical_horizons=[30],
        neutralization_groups=["sector", "subindustry"],
        is_high_confidence=True,
    ),
    OptionArchetype(
        name="Variance Risk Premium (IV vs RV)",
        category="term_structure",
        description="Difference between implied volatility and rolling realized volatility.",
        economic_rationale="Stocks with excessively high IV over realized volatility suffer from option overpricing, predicting subdued return drag.",
        formula_template="group_neutralize(rank(-(implied_volatility_mean_{tenor} - ts_std_dev(returns, {window}) * 15.87)), {group})",
        typical_horizons=[20, 30],
        neutralization_groups=["sector", "industry"],
    ),
    OptionArchetype(
        name="Jensen-Debiased Variance Risk Premium",
        category="term_structure",
        description="VRP adjusted for small-sample downward bias in realized volatility estimator.",
        economic_rationale="Jensen's inequality causes short-window realized volatility to systematically underestimate true volatility; debiasing eliminates false-positive VRP richness.",
        formula_template="group_neutralize(rank(-(implied_volatility_mean_{tenor} - ts_std_dev(returns, {window}) * (15.87 / 0.96))), {group})",
        typical_horizons=[20, 30],
        neutralization_groups=["sector", "subindustry"],
        is_high_confidence=True,
    ),
    OptionArchetype(
        name="Optimal Mean-Reversion Threshold Gated VRP",
        category="term_structure",
        description="Variance risk premium entry conditioned on crossing the ~0.75 SD optimal threshold.",
        economic_rationale="Institutional derivation from Sinclair (Book 1): for mean-reverting processes, entering at ~0.75 SD maximizes expected growth by balancing edge with trading opportunity count.",
        formula_template="trade_when(abs(ts_zscore(implied_volatility_mean_30 - ts_std_dev(returns, 30) * 15.87, 40)) > 0.75, group_neutralize(rank(-(implied_volatility_mean_30 - ts_std_dev(returns, 30) * 15.87)), {group}), -1)",
        typical_horizons=[30],
        neutralization_groups=["sector", "subindustry"],
        is_high_confidence=True,
    ),
]
