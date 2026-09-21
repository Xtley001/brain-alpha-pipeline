"""Templates for Cross-Asset Implied Volatility Leading Cash Equity."""
from __future__ import annotations

from brain_options.specialist.templates import OptionCandidate


def generate_iv_lead_lag_candidates() -> list[OptionCandidate]:
    candidates: list[OptionCandidate] = []
    groups = ["subindustry", "industry", "sector"]

    for grp in groups:
        candidates.append(
            OptionCandidate(
                expression=f"group_neutralize(ts_delta(iv_atm_call_30, 5) - ts_delta(iv_atm_put_30, 5), {grp})",
                archetype_name="Call-Put IV Acceleration Divergence",
                hypothesis="Informed traders buy call options ahead of positive news, causing call IV to expand faster than put IV.",
                generation_source="template",
            )
        )
        candidates.append(
            OptionCandidate(
                expression=f"group_neutralize(group_rank(ts_decay_linear((call_volume - put_volume) / (volume + 1), 10), {grp}), {grp})",
                archetype_name="Directional Option Flow Imbalance",
                hypothesis="Net directional option volume imbalance relative to cash volume leads underlying equity price adjustment.",
                generation_source="template",
            )
        )
        candidates.append(
            OptionCandidate(
                expression=f"group_neutralize(rank(ts_regression_residuals(returns, ts_delay(ts_delta(iv_atm_call_30, 5), 2), 20)), {grp})",
                archetype_name="Residual Equity Drift from IV Lead",
                hypothesis="Cash equities lagging their options market implied volatility expansion experience sharp mean-reversion catches.",
                generation_source="template",
            )
        )
        candidates.append(
            OptionCandidate(
                expression=f"group_neutralize(ts_zscore(iv_atm_call_30 / (iv_atm_put_30 + 0.001), 60), {grp})",
                archetype_name="Relative Call IV Dominance",
                hypothesis="Elevated ratio of call IV to put IV relative to historical baseline reflects bullish institutional positioning.",
                generation_source="template",
            )
        )

    return candidates
