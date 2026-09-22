"""
Deterministic seed template generator for Options Alpha candidates.
Generates fully valid Fast Expression candidates across the quantitative archetypes,
incorporating cross-book high-confidence formulas from Master Books 1-4.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional
from brain_options.specialist.archetypes import ARCHETYPES, OptionArchetype


@dataclass(frozen=True)
class OptionCandidate:
    expression: str
    archetype_name: str
    hypothesis: str
    generation_source: str  # "template" or "llm_reasoning" or "llm_mechanical" or "decorrelator"
    n_variants_tried: int = 1
    base_alpha_id: Optional[str] = None
    corr_partner_alpha_id: Optional[str] = None
    decorrelation_attempts: int = 0


def with_liquidity_gate(inner_expr: str, threshold_mult: float = 1.0) -> str:
    """Wraps any alpha expression in a volume-confirmation gate."""
    cond = f"volume > {threshold_mult} * adv20" if threshold_mult != 1.0 else "volume > adv20"
    return f"trade_when({cond}, {inner_expr}, -1)"


def with_regime_gate(inner_expr: str, regime_field: str, window: int = 60) -> str:
    """Wraps any alpha expression in a field-vs-own-trend regime gate."""
    return f"trade_when({regime_field} > ts_mean({regime_field}, {window}), {inner_expr}, -1)"


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

    # 23. Givoly-Lakonishok Analyst Revision Momentum (JAE 1979) - Multi-Speed Dispersal
    # Fast: win=15, decay=5 | Medium: win=30, decay=10 | Slow: win=60, decay=20
    for win, dcy in [(15, 5), (30, 10), (60, 20)]:
        for grp in ["subindustry", "sector"]:
            candidates.append(
                OptionCandidate(
                    expression=f"group_neutralize(rank(ts_decay_linear((est_eps - ts_delay(est_eps, {win})) / (abs(ts_delay(est_eps, {win})) + 0.01), {dcy})), {grp})",
                    archetype_name="Analyst Revision Momentum",
                    hypothesis=f"Givoly & Lakonishok (1979): Sluggish analyst EPS forecast revisions over {win}d drift forward with decay={dcy} demeaned by {grp}.",
                    generation_source="template",
                )
            )

    # 24. Sales & Revenue Revision Momentum - Multi-Speed Dispersal
    for win, dcy in [(15, 5), (30, 10), (60, 20)]:
        for grp in ["subindustry", "sector"]:
            candidates.append(
                OptionCandidate(
                    expression=f"group_neutralize(rank(ts_decay_linear((est_sales - ts_delay(est_sales, {win})) / (abs(ts_delay(est_sales, {win})) + 0.01), {dcy})), {grp})",
                    archetype_name="Sales Revision Momentum",
                    hypothesis=f"Consensus sales revision drift over {win}d with decay={dcy} captures top-line demand momentum demeaned by {grp}.",
                    generation_source="template",
                )
            )

    # 25. Diether-Malloy-Scherbina Forecast Dispersion Fade (JF 2002) - Multi-Speed Dispersal
    for win, dcy in [(20, 5), (60, 10), (120, 20)]:
        for grp in ["subindustry", "sector"]:
            candidates.append(
                OptionCandidate(
                    expression=f"group_neutralize(rank(-ts_decay_linear(ts_zscore(std_dev_eps_est / (abs(est_eps) + 0.01), {win}), {dcy})), {grp})",
                    archetype_name="Analyst Dispersion Fade",
                    hypothesis=f"Diether, Malloy, & Scherbina (2002): High analyst forecast dispersion over {win}d signals market overoptimism; fade high disagreement with decay={dcy}.",
                    generation_source="template",
                )
            )

    # 26. Bernard-Thomas PEAD Revision vs Price Momentum Gap
    for grp in ["subindustry", "sector"]:
        candidates.append(
            OptionCandidate(
                expression=f"group_neutralize(rank(ts_decay_linear(((est_eps - ts_delay(est_eps, 30)) / (abs(ts_delay(est_eps, 30)) + 0.01)) - (ts_delta(close, 30) / (ts_delay(close, 30) + 0.001)), 10)), {grp})",
                archetype_name="PEAD Revision Price Lag",
                hypothesis=f"Bernard & Thomas (1989): Gap between 30d EPS revision surge and sluggish 30d realized stock return isolates unpriced post-earnings drift demeaned by {grp}.",
                generation_source="template",
            )
        )

    # 27. Fabozzi Price Target Implied Upside Momentum (Wiley 2010) - Multi-Speed Gated
    for mom_win, dcy in [(5, 5), (10, 10), (20, 20)]:
        for grp in ["subindustry", "sector"]:
            candidates.append(
                OptionCandidate(
                    expression=f"trade_when(ts_delta(close, {mom_win}) > 0, group_neutralize(rank(ts_decay_linear((target_price - close) / close, {dcy})), {grp}), -1)",
                    archetype_name="Price Target Implied Upside",
                    hypothesis=f"Fabozzi et al. (2010): Consensus price target upside conditioned on positive {mom_win}d price velocity eliminates value traps (decay={dcy}).",
                    generation_source="template",
                )
            )

    # 28. Cohen-Diether-Malloy Short Demand Borrow Surge (JF 2007) - Multi-Speed Dispersal
    for dcy in [5, 10, 20]:
        for grp in ["subindustry", "sector"]:
            candidates.append(
                OptionCandidate(
                    expression=f"group_neutralize(rank(-ts_decay_linear(borrow_fee * (short_interest / (float_shares + 0.001)), {dcy})), {grp})",
                    archetype_name="Short Demand Borrow Surge",
                    hypothesis=f"Cohen, Diether, & Malloy (2007): Elevated institutional borrow cost and high short interest isolate informed shorting with decay={dcy}.",
                    generation_source="template",
                )
            )

    # 29. Borrow Fee Acceleration Spike
    for dcy in [5, 10]:
        for grp in ["subindustry", "sector"]:
            candidates.append(
                OptionCandidate(
                    expression=f"group_neutralize(rank(-ts_decay_linear(ts_delta(borrow_fee, 5) * (short_interest / (float_shares + 0.001)), {dcy})), {grp})",
                    archetype_name="Borrow Fee Acceleration Spike",
                    hypothesis=f"Sudden 5-day spike in institutional borrow fee multiplied by short interest scale isolates imminent borrow squeeze or collapse with decay={dcy}.",
                    generation_source="template",
                )
            )

    # 30. Rapach-Ringgenberg-Zhou De-Trended Short Interest Z-Score (JFE 2016) - Multi-Speed
    for win, dcy in [(126, 10), (252, 20)]:
        for grp in ["subindustry", "sector"]:
            candidates.append(
                OptionCandidate(
                    expression=f"group_neutralize(rank(-ts_decay_linear(ts_zscore(short_interest / (float_shares + 0.001), {win}), {dcy})), {grp})",
                    archetype_name="De-Trended Short Interest Z-Score",
                    hypothesis=f"Rapach, Ringgenberg, & Zhou (2016): De-trended {win}d short interest Z-score measures abnormal institutional positioning with decay={dcy}.",
                    generation_source="template",
                )
            )

    # 31. Asquith-Staley Days-to-Cover Short Squeeze Breakout (JFE 2005 / Staley 1997) - Multi-Speed
    for dtc_thresh, mom_win, dcy in [(4.0, 5, 5), (6.0, 10, 10), (8.0, 20, 20)]:
        for grp in ["subindustry", "sector"]:
            candidates.append(
                OptionCandidate(
                    expression=f"trade_when((close > ts_mean(close, {mom_win * 2})) & (days_to_cover > {dtc_thresh}), group_neutralize(rank(ts_decay_linear(days_to_cover * ts_delta(close, {mom_win}), {dcy})), {grp}), -1)",
                    archetype_name="Days-to-Cover Short Squeeze Breakout",
                    hypothesis=f"Asquith et al. (2005) & Staley (1997): Squeeze breakout on heavily shorted stocks with DTC > {dtc_thresh} and {mom_win}d positive momentum.",
                    generation_source="template",
                )
            )

    # 32. Short Loan Utilization Velocity
    for grp in ["subindustry", "sector"]:
        candidates.append(
            OptionCandidate(
                expression=f"group_neutralize(rank(-ts_decay_linear(ts_delta(short_interest / (float_shares + 0.001), 5), 5)), {grp})",
                archetype_name="Short Loan Utilization Velocity",
                hypothesis=f"5-day rate of change in short interest relative to float captures rapid institutional accumulation of bearish positions.",
                generation_source="template",
            )
        )

    # 33. Volatility Smirk vs Borrow Fee Confluence Hybrid (MPRA 42566) - Multi-Speed
    for tenor, dcy in [(20, 5), (30, 10), (60, 20)]:
        sqrt_t = round(math.sqrt(tenor / 252.0), 4)
        for grp in ["subindustry", "sector"]:
            candidates.append(
                OptionCandidate(
                    expression=f"group_neutralize(rank(-ts_decay_linear((implied_volatility_mean_skew_{tenor} * {sqrt_t}) * (borrow_fee + 1.0), {dcy})), {grp})",
                    archetype_name="Volatility Smirk Borrow Fee Hybrid",
                    hypothesis=f"Cross-Asset Confluence: Confluence of steep {tenor}d downside OTM put skew and high borrow fee maximizes conviction with decay={dcy}.",
                    generation_source="template",
                )
            )

    # 34. PCR Flow vs Borrow Fee Confluence Hybrid - Multi-Speed
    for tenor, dcy in [(10, 5), (20, 10), (30, 20)]:
        for grp in ["subindustry", "sector"]:
            candidates.append(
                OptionCandidate(
                    expression=f"group_neutralize(rank(-ts_decay_linear((pcr_vol_{tenor} / (pcr_oi_{tenor} + 0.001)) * (borrow_fee + 1.0), {dcy})), {grp})",
                    archetype_name="PCR Borrow Fee Confluence Hybrid",
                    hypothesis=f"Surging {tenor}d put/call volume ratio paired with elevated borrow cost flags coordinated institutional exit (decay={dcy}).",
                    generation_source="template",
                )
            )

    # 35. Analyst Revision vs Volatility Skew Divergence Hybrid - Multi-Speed
    for tenor, dcy in [(20, 5), (30, 10), (60, 20)]:
        sqrt_t = round(math.sqrt(tenor / 252.0), 4)
        for grp in ["subindustry", "sector"]:
            candidates.append(
                OptionCandidate(
                    expression=f"group_neutralize(rank(ts_decay_linear((target_price - close) / close - (implied_volatility_mean_skew_{tenor} * {sqrt_t}), {dcy})), {grp})",
                    archetype_name="Revision vs Skew Divergence Hybrid",
                    hypothesis=f"Cross-Asset Divergence: Exploits misalignments between optimistic price target expectations and {tenor}d downside hedging (decay={dcy}).",
                    generation_source="template",
                )
            )

    # 36. Price Target Upside vs Call Breakeven Hurdle Confluence
    for tenor, dcy in [(20, 5), (30, 10)]:
        for grp in ["subindustry", "sector"]:
            candidates.append(
                OptionCandidate(
                    expression=f"group_neutralize(rank(ts_decay_linear(((target_price - close) / close) + ((call_breakeven_{tenor} - close) / close), {dcy})), {grp})",
                    archetype_name="Target Price Breakeven Confluence",
                    hypothesis=f"Combined signal of consensus analyst price target upside and {tenor}d option call breakeven hurdle rate confirms upside repricing.",
                    generation_source="template",
                )
            )

    # 37. Short Squeeze Gated by Call Option Velocity
    for tenor in [20, 30]:
        for grp in ["subindustry", "sector"]:
            candidates.append(
                OptionCandidate(
                    expression=f"trade_when((days_to_cover > 5.0) & (ts_delta(close, 5) > 0), group_neutralize(rank(ts_decay_linear(ts_delta((call_breakeven_{tenor} - close) / close, 5), 5)), {grp}), -1)",
                    archetype_name="Short Squeeze Call Hurdle Acceleration",
                    hypothesis=f"Short squeeze trigger: Heavily shorted stocks (DTC > 5) experiencing upward shifts in {tenor}d call breakeven hurdle rate.",
                    generation_source="template",
                )
            )

    return candidates

