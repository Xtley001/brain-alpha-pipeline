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
            expr = f"group_neutralize(rank(ts_decay_linear(-ts_delta(implied_volatility_mean_skew_{tenor}, {window}), 5)), subindustry)"
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
            expr = f"group_neutralize(rank(ts_decay_linear(-ts_delta(implied_volatility_mean_skew_{tenor} * {sqrt_t}, {window}), 5)), subindustry)"
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
            expr = f"group_neutralize(rank(ts_decay_linear(ts_delta((call_breakeven_{tenor} - close) / close, {window}), 5)), subindustry)"
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

    # 15. Parkinson Extreme-Value Volatility Premium
    for tenor in [20, 30, 60]:
        for grp in ["subindustry", "sector"]:
            candidates.append(
                OptionCandidate(
                    expression=f"group_neutralize(rank(ts_decay_linear(-(implied_volatility_mean_{tenor} / (parkinson_volatility_{tenor} + 0.001) - 1.0), 5)), {grp})",
                    archetype_name="Parkinson Extreme-Value Volatility Premium",
                    hypothesis=f"Fade overpriced {tenor}d IV against Parkinson extreme-value intraday realized volatility demeaned by {grp}.",
                    generation_source="template",
                )
            )

    # 16. Call-Put Implied Volatility Asymmetry
    for tenor in [20, 30, 60]:
        for grp in ["subindustry", "sector"]:
            candidates.append(
                OptionCandidate(
                    expression=f"group_neutralize(rank(ts_decay_linear((implied_volatility_call_{tenor} - implied_volatility_put_{tenor}) / (implied_volatility_mean_{tenor} + 0.001), 5)), {grp})",
                    archetype_name="Call-Put Implied Volatility Asymmetry",
                    hypothesis=f"Directional flow divergence between {tenor}d call and put IV demeaned by {grp}.",
                    generation_source="template",
                )
            )

    # 17. Liquidity-Gated Breakeven Acceleration
    for tenor in [20, 30, 60]:
        for win in [3, 5]:
            candidates.append(
                OptionCandidate(
                    expression=f"trade_when(volume > adv20, group_neutralize(rank(ts_decay_linear(ts_delta((call_breakeven_{tenor} - close) / close, {win}), 5)), subindustry), -1)",
                    archetype_name="Liquidity-Gated Breakeven Acceleration",
                    hypothesis=f"Acceleration in {tenor}d call breakeven hurdle rate over {win}d conditioned on liquid trading volume.",
                    generation_source="template",
                )
            )

    # 18. Pan-Poteshman Informed Option Flow (Journal of Finance 2006)
    for tenor in [20, 30]:
        candidates.append(
            OptionCandidate(
                expression=f"trade_when(volume > adv20, group_neutralize(rank(-ts_decay_linear(pcr_vol_{tenor} / (pcr_oi_{tenor} + 0.001), 5)), subindustry), -1)",
                archetype_name="Pan-Poteshman Informed Option Flow",
                hypothesis=f"Pan & Poteshman (2006): Informed buyer-initiated option flow velocity at {tenor}d tenor leads next-day equity returns under volume confirmation.",
                generation_source="template",
            )
        )

    # 19. Xing-Zhang-Zhao Volatility Smirk Smear (JFQA 2010)
    for tenor in [20, 30, 60]:
        candidates.append(
            OptionCandidate(
                expression=f"group_neutralize(rank(-ts_decay_linear(implied_volatility_mean_skew_{tenor} * sqrt({tenor} / 252.0), 5)), subindustry)",
                archetype_name="Xing-Zhang-Zhao Volatility Smirk Smear",
                hypothesis=f"Xing, Zhang, & Zhao (2010): Square-root-time normalized smirk steepness at {tenor}d tenor isolates downside jump-to-default risk.",
                generation_source="template",
            )
        )

    # 20. Bali-Hovakimian Volatility Spread PC3 (Management Science 2009)
    for tenor in [20, 30, 60]:
        candidates.append(
            OptionCandidate(
                expression=f"group_neutralize(rank(ts_decay_linear((implied_volatility_call_{tenor} - implied_volatility_put_{tenor}) / (implied_volatility_mean_{tenor} + 0.001), 5)), subindustry)",
                archetype_name="Bali-Hovakimian Volatility Spread PC3",
                hypothesis=f"Bali & Hovakimian (2009): Call IV minus Put IV spread at {tenor}d tenor predicts underlying cross-sectional price direction.",
                generation_source="template",
            )
        )

    # 21. Carr-Wu Quadratic Variance Risk Premium (RFS 2009)
    for tenor in [20, 30]:
        candidates.append(
            OptionCandidate(
                expression=f"group_neutralize(rank(-(signed_power(implied_volatility_mean_{tenor}, 2) - signed_power(ts_std_dev(returns, {tenor}), 2) * 252)), subindustry)",
                archetype_name="Carr-Wu Quadratic Variance Risk Premium",
                hypothesis=f"Carr & Wu (2009): Quadratic variance swap rate minus realized variance at {tenor}d tenor isolates true volatility risk premium.",
                generation_source="template",
            )
        )

    # 22. Tulchinsky Winsorized Robust Breakeven (Finding Alphas Ch. 12)
    for tenor in [20, 30, 60]:
        candidates.append(
            OptionCandidate(
                expression=f"trade_when(volume > adv20, group_neutralize(rank(ts_decay_linear((call_breakeven_{tenor} - close) / close, 5)), subindustry), -1)",
                archetype_name="Tulchinsky Winsorized Robust Breakeven",
                hypothesis=f"Tulchinsky et al. (2019): Robust linear decay smoothed call breakeven distance with volume gating eliminates quote noise in WebSim.",
                generation_source="template",
            )
        )

    # 23. Givoly-Lakonishok Analyst Revision Momentum (JAE 1979)
    for win in [30, 60, 90]:
        for grp in ["subindustry", "sector"]:
            candidates.append(
                OptionCandidate(
                    expression=f"group_neutralize(rank(ts_decay_linear((est_eps - ts_delay(est_eps, {win})) / (abs(ts_delay(est_eps, {win})) + 0.01), 10)), {grp})",
                    archetype_name="Analyst Revision Momentum",
                    hypothesis=f"Givoly & Lakonishok (1979): Sticky analyst forecast revisions over {win}d drift forward over multi-month horizons demeaned by {grp}.",
                    generation_source="template",
                )
            )

    # 24. Diether-Malloy-Scherbina Forecast Dispersion Fade (JF 2002)
    for grp in ["subindustry", "sector"]:
        candidates.append(
            OptionCandidate(
                expression=f"group_neutralize(rank(-ts_decay_linear(std_dev_eps_est / (abs(est_eps) + 0.01), 10)), {grp})",
                archetype_name="Analyst Dispersion Fade",
                hypothesis=f"Diether, Malloy, & Scherbina (2002): High analyst forecast dispersion signals market overoptimism under short-sale constraints; fade high disagreement names.",
                generation_source="template",
            )
        )

    # 25. Fabozzi Price Target Implied Upside Momentum (Wiley 2010)
    for grp in ["subindustry", "sector"]:
        candidates.append(
            OptionCandidate(
                expression=f"trade_when(ts_delta(close, 10) > 0, group_neutralize(rank(ts_decay_linear((target_price - close) / close, 10)), {grp}), -1)",
                archetype_name="Price Target Implied Upside",
                hypothesis=f"Fabozzi et al. (2010): Consensus price target upside conditioned on positive 10d trailing price velocity prevents value traps.",
                generation_source="template",
            )
        )

    # 26. Cohen-Diether-Malloy Short Demand Borrow Surge (JF 2007)
    for grp in ["subindustry", "sector"]:
        candidates.append(
            OptionCandidate(
                expression=f"group_neutralize(rank(-ts_decay_linear(borrow_fee * (short_interest / (float_shares + 0.001)), 10)), {grp})",
                archetype_name="Short Demand Borrow Surge",
                hypothesis=f"Cohen, Diether, & Malloy (2007): Rising institutional borrow fees combined with high short interest isolates informed bearish demand.",
                generation_source="template",
            )
        )

    # 27. Rapach-Ringgenberg-Zhou De-Trended Short Interest Z-Score (JFE 2016)
    for grp in ["subindustry", "sector"]:
        candidates.append(
            OptionCandidate(
                expression=f"group_neutralize(rank(-ts_zscore(short_interest / (float_shares + 0.001), 252)), {grp})",
                archetype_name="De-Trended Short Interest Z-Score",
                hypothesis=f"Rapach, Ringgenberg, & Zhou (2016): De-trended 252d short interest Z-score measures abnormal institutional positioning.",
                generation_source="template",
            )
        )

    # 28. Asquith-Staley Days-to-Cover Short Squeeze Breakout (JFE 2005 / Staley 1997)
    for grp in ["subindustry", "sector"]:
        candidates.append(
            OptionCandidate(
                expression=f"trade_when((close > ts_mean(close, 20)) & (days_to_cover > 5.0), group_neutralize(rank(days_to_cover * ts_delta(close, 5)), {grp}), -1)",
                archetype_name="Days-to-Cover Short Squeeze Breakout",
                hypothesis=f"Asquith et al. (2005) & Staley (1997): Squeeze breakout trigger on heavily shorted stocks with high days-to-cover and positive momentum.",
                generation_source="template",
            )
        )

    # 29. Volatility Smirk vs Borrow Fee Confluence Hybrid (MPRA 42566)
    for grp in ["subindustry", "sector"]:
        candidates.append(
            OptionCandidate(
                expression=f"group_neutralize(rank(-ts_decay_linear((implied_volatility_mean_skew_30 * sqrt(30 / 252.0)) * (borrow_fee + 1.0), 5)), {grp})",
                archetype_name="Volatility Smirk Borrow Fee Hybrid",
                hypothesis=f"Cross-Asset Confluence: Confluence of steep downside OTM put skew and high institutional borrow fee maximizes conviction of downside collapse.",
                generation_source="template",
            )
        )

    # 30. Analyst Revision vs Volatility Skew Divergence Hybrid
    for grp in ["subindustry", "sector"]:
        candidates.append(
            OptionCandidate(
                expression=f"group_neutralize(rank(ts_decay_linear((target_price - close) / close - (implied_volatility_mean_skew_30 * sqrt(30 / 252.0)), 10)), {grp})",
                archetype_name="Revision vs Skew Divergence Hybrid",
                hypothesis=f"Cross-Asset Divergence: Exploits misalignments between optimistic sell-side price target expectations and derivatives downside hedging.",
                generation_source="template",
            )
        )

    return candidates

