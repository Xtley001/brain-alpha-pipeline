"""Formula templates for Volatility Skew & Smirk Asymmetry."""
from __future__ import annotations
from brain_options.specialist.templates import OptionCandidate

def generate_skew_candidates() -> list[OptionCandidate]:
    candidates: list[OptionCandidate] = []
    groups = ["subindustry", "sector"]

    # 1. Volatility Skew Steepness Shock
    for tenor in [20, 30]:
        for window in [5, 10]:
            for grp in groups:
                candidates.append(
                    OptionCandidate(
                        expression=f"group_neutralize(rank(-ts_delta(implied_volatility_mean_skew_{tenor}, {window})), {grp})",
                        archetype_name="Volatility Skew Steepness Shock",
                        hypothesis=f"Sudden steepening of {tenor}d skew indicates institutional downside crash hedging.",
                        generation_source="template",
                    )
                )

    # 2. Sqrt-T Normalized Skew Acceleration (Cross-book high confidence)
    for tenor in [20, 30, 60]:
        for grp in groups:
            candidates.append(
                OptionCandidate(
                    expression=f"group_neutralize(rank(-ts_delta(implied_volatility_mean_skew_{tenor} * sqrt({tenor} / 252.0), 5)), {grp})",
                    archetype_name="Sqrt-T Normalized Skew Acceleration",
                    hypothesis=f"Skew normalized by sqrt(T) at {tenor}d isolates pure crash risk without double-counting IV.",
                    generation_source="template",
                )
            )

    # 3. Xing-Zhang-Zhao Volatility Smirk Smear
    for tenor in [20, 30]:
        for grp in ["subindustry", "industry"]:
            candidates.append(
                OptionCandidate(
                    expression=f"group_neutralize(rank(-ts_decay_linear(implied_volatility_mean_skew_{tenor} * sqrt({tenor} / 252.0), 5)), {grp})",
                    archetype_name="Xing-Zhang-Zhao Smirk Smear",
                    hypothesis="Smirk steepness smoothed with linear decay directly forecasts negative earnings surprises.",
                    generation_source="template",
                )
            )

    # 4. Call-Put Implied Volatility Asymmetry / Bali-Hovakimian Spread
    for tenor in [20, 30]:
        for grp in groups:
            candidates.append(
                OptionCandidate(
                    expression=f"group_neutralize(rank(ts_decay_linear((implied_volatility_call_{tenor} - implied_volatility_put_{tenor}) / (implied_volatility_mean_{tenor} + 0.001), 5)), {grp})",
                    archetype_name="Call-Put IV Asymmetry",
                    hypothesis=f"Call IV exceeding Put IV at {tenor}d captures speculative institutional upside demand.",
                    generation_source="template",
                )
            )

    return candidates
