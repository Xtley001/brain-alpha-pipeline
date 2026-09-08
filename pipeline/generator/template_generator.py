"""
Tier-1 generator: no LLM involved, pure string substitution over the 50
seed ideas transcribed from the project's original idea list. Each seed idea's BRAIN
expression is stored as a template with `{w}`-style placeholders for the
window/lookback parameters the source doc explicitly calls out as
sweepable (e.g. "Sweep decay 2-5" -> here that's the *expression's own*
window arguments like ts_delta(close, N), not the simulation-settings
`decay` field, which pipeline/sweep/settings_sweep.py already sweeps
separately). Seed ideas with no explicit sweep range in the source doc
generate a single expression (no window variants).

This module never calls BRAIN and never uses an LLM — it's pure, fast,
and cheap, which is exactly why it's tier 1 ("the generator is never the
bottleneck"). Strategy generation is NOT limited to these 50 seed ideas:
this tier only ever produces mechanical window variants of them, while
pipeline/generator/llm_generator.py's propose_new_ideas() is explicitly
prompted to bring genuinely new, economically distinct ideas beyond
whatever is already in the pool. The two tiers exist together so cheap
volume (this file) doesn't crowd out actual novelty (the LLM tier).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SeedIdea:
    id: int
    category: str  # matches the doc's lettered sections, e.g. "A. Reversal"
    name: str
    template: str  # BRAIN expression, with {w}/{w1}/{w2} placeholders
    windows: tuple  # tuple of dicts of placeholder->value; () or single-dict tuple if not swept


# Transcribed from the project's original seed-idea list. Window ranges follow each
# idea's own "Details" line where the doc gives one (e.g. "Sweep decay 2-5"
# maps to the ts_delta window in idea #1, not the simulation decay field).
# Where the doc gives no explicit numeric sweep range, a single fixed
# expression is used (windows has exactly one entry: {}).
SEED_IDEAS: tuple = (
    # A. Reversal & Mean Reversion (Doc 1 §3.1, Doc 2 §2, Doc 4 §10)
    SeedIdea(1, "A. Reversal", "Sector-relative n-day mean reversion",
             "group_neutralize(rank(-(ts_delta(close, {w}) - group_mean(ts_delta(close, {w}), 1, sector))), sector)",
             ({"w": 1}, {"w": 2}, {"w": 3}, {"w": 5})),
    SeedIdea(2, "A. Reversal", "Z-Score mean reversion subindustry neutral",
             "group_neutralize(rank(-ts_zscore(close, {w})), subindustry)",
             ({"w": 5}, {"w": 10}, {"w": 20})),
    SeedIdea(3, "A. Reversal", "Volume-surge conditioned reversal",
             "trade_when(volume > adv20, group_neutralize(rank(-ts_delta(close, {w})), sector), -1)",
             ({"w": 1}, {"w": 2}, {"w": 3})),
    SeedIdea(4, "A. Reversal", "Volatility-regime conditioned mean reversion",
             "trade_when(ts_rank(ts_std_dev(returns, 60), 126) > 0.50, group_neutralize(rank(-ts_delta(close, {w})), subindustry), -1)",
             ({"w": 2}, {"w": 5})),
    SeedIdea(5, "A. Reversal", "Overnight gap fade with volume anomaly filter",
             "group_neutralize(rank(-(open - ts_delay(close, 1)) / (ts_delay(close, 1) + 0.001)) * rank(volume / (adv20 + 0.001)), subindustry)",
             ({},)),
    SeedIdea(6, "A. Reversal", "Intraday pressure reversion",
             "group_neutralize(rank(-((close - open) / (high - low + 0.0001))), subindustry)",
             ({},)),
    SeedIdea(7, "A. Reversal", "Volume anomaly return reversal",
             "group_neutralize(rank(-ts_rank(returns, {w}) * rank(volume / (adv20 + 0.001))), subindustry)",
             ({"w": 3}, {"w": 5}, {"w": 10})),

    # B. Momentum & Trend Following (Doc 1 §3.1, Doc 4 §10)
    SeedIdea(8, "B. Momentum", "Risk-adjusted momentum",
             "group_neutralize(rank(ts_decay_linear(returns, {w}) / (ts_std_dev(returns, {w}) + 0.0001)), sector)",
             ({"w": 20}, {"w": 60}, {"w": 126})),
    SeedIdea(9, "B. Momentum", "Decay-smoothed momentum skip-month",
             "group_neutralize(rank(ts_decay_linear(ts_delta(ts_delay(close, 21), {w}), 20)), industry)",
             ({"w": 63}, {"w": 126})),
    SeedIdea(10, "B. Momentum", "Event-gated volume momentum shock",
             "trade_when(volume > adv20, group_neutralize(rank(ts_delta(close, {w})), sector), -1)",
             ({"w": 5}, {"w": 10}, {"w": 20})),
    SeedIdea(11, "B. Momentum", "Momentum size interaction",
             "group_neutralize(rank(ts_delta(close, {w})) * rank(-cap), sector)",
             ({"w": 63}, {"w": 126})),
    SeedIdea(12, "B. Momentum", "Volatility-conditioned momentum",
             "group_neutralize(rank(ts_delta(close, {w})) * (1 / (1 + ts_std_dev(returns, 20))), sector)",
             ({"w": 63}, {"w": 126})),
    SeedIdea(13, "B. Momentum", "52-week high proximity",
             "group_neutralize(rank(close / (ts_max(high, {w}) + 0.001)), subindustry)",
             ({"w": 126}, {"w": 252})),
    SeedIdea(14, "B. Momentum", "Momentum rank stability decay",
             "group_neutralize(ts_decay_linear(rank(ts_delta(close, {w})), 10), industry)",
             ({"w": 20}, {"w": 60})),

    # C. Volume & Liquidity Microstructure (Doc 1 §3.1, Doc 4 §9)
    SeedIdea(15, "C. Volume/Liquidity", "Volume-price divergence",
             "group_neutralize(rank(ts_delta(close, {w})) * rank(-ts_delta(volume, {w})), subindustry)",
             ({"w": 5}, {"w": 10})),
    SeedIdea(16, "C. Volume/Liquidity", "Price-volume correlation anomaly",
             "group_neutralize(rank(-ts_corr(close, volume, {w})), sector)",
             ({"w": 10}, {"w": 20})),
    SeedIdea(17, "C. Volume/Liquidity", "VWAP price displacement decay",
             "group_neutralize(rank(ts_decay_linear((vwap - close) / close, {w})), subindustry)",
             ({"w": 5}, {"w": 10}, {"w": 20})),
    SeedIdea(18, "C. Volume/Liquidity", "Intraday pressure with volume surge",
             "group_neutralize(rank((close - open) / (high - low + 0.0001)) * rank(volume / (adv20 + 0.001)), subindustry)",
             ({},)),
    SeedIdea(19, "C. Volume/Liquidity", "Turnover-decline precursor signal",
             "group_neutralize(rank(-ts_delta(ts_mean(volume, {w1}), {w2})), sector)",
             ({"w1": 5, "w2": 20},)),
    SeedIdea(20, "C. Volume/Liquidity", "Amihud illiquidity proxy rank",
             "group_neutralize(rank(abs(returns) / (volume * close + 1000)), subindustry)",
             ({},)),

    # D. Multi-Factor Interactions & Non-Linear Shapes (Doc 1 §8, Doc 4 §2)
    SeedIdea(21, "D. Interactions", "Non-linear reversal power",
             "signed_power(group_neutralize(rank(-ts_delta(close, {w})), subindustry), 2)",
             ({"w": 2}, {"w": 5})),
    SeedIdea(22, "D. Interactions", "Volume rank x VWAP deviation",
             "group_neutralize(rank(ts_rank(volume, {w}) * (close - vwap) / close), industry)",
             ({"w": 10}, {"w": 20})),
    SeedIdea(23, "D. Interactions", "Small-cap momentum tilt",
             "group_neutralize(rank(ts_delta(close, {w}) / (ts_delay(close, {w}) + 0.001)) * rank(-cap), sector)",
             ({"w": 20}, {"w": 60})),
    SeedIdea(24, "D. Interactions", "Price Z-score minus volume Z-score",
             "group_neutralize(rank(ts_zscore(close, 20)) - rank(ts_zscore(volume, 20)), industry)",
             ({},)),
    SeedIdea(25, "D. Interactions", "Decay momentum with volume confirmation",
             "group_neutralize(rank(ts_decay_linear(returns, {w})) * rank(ts_decay_linear(volume / (adv20 + 0.001), {w})), sector)",
             ({"w": 5}, {"w": 10})),

    # E. Volatility & Risk (Doc 1 §5.2, Doc 4 §4)
    SeedIdea(26, "E. Volatility/Risk", "Low-volatility anomaly",
             "group_neutralize(rank(-ts_std_dev(returns, {w})), sector)",
             ({"w": 20}, {"w": 60}, {"w": 126})),
    SeedIdea(27, "E. Volatility/Risk", "Idiosyncratic volatility rank",
             "group_neutralize(rank(-ts_std_dev(returns - group_mean(returns, 1, sector), {w})), sector)",
             ({"w": 60}, {"w": 120})),
    SeedIdea(28, "E. Volatility/Risk", "Volatility term structure ratio",
             "group_neutralize(rank(-(ts_std_dev(returns, {w1}) / (ts_std_dev(returns, {w2}) + 0.0001))), sector)",
             ({"w1": 5, "w2": 60},)),
    SeedIdea(29, "E. Volatility/Risk", "VWAP displacement with low-vol filter",
             "group_neutralize(rank(close - ts_decay_linear(vwap, {w})) * rank(-ts_std_dev(returns, {w})), subindustry)",
             ({"w": 10}, {"w": 20})),
    SeedIdea(30, "E. Volatility/Risk", "Returns-volume correlation signal",
             "group_neutralize(rank(ts_corr(returns, volume, {w})), subindustry)",
             ({"w": 10}, {"w": 20})),
    SeedIdea(31, "E. Volatility/Risk", "Range rank with price trend",
             "group_neutralize(rank(-ts_rank(high - low, {w})) * rank(ts_delta(close, 5)), sector)",
             ({"w": 20}, {"w": 60})),

    # F. Cross-Sectional & Group Relative (Doc 4 §6, Doc 4 §10)
    SeedIdea(32, "F. Group/Cross-sectional", "Sector mean momentum rotation",
             "group_rank(ts_delta(group_mean(close, 1, sector), {w}), sector)",
             ({"w": 5}, {"w": 20})),
    SeedIdea(33, "F. Group/Cross-sectional", "Industry-neutral time-series rank",
             "group_neutralize(rank(ts_rank(close, {w})), industry)",
             ({"w": 10}, {"w": 20}, {"w": 60})),
    SeedIdea(34, "F. Group/Cross-sectional", "Subindustry-neutral VWAP reversal",
             "group_neutralize(rank(-ts_delta(vwap, {w})), subindustry)",
             ({"w": 3}, {"w": 5}, {"w": 10})),
    SeedIdea(35, "F. Group/Cross-sectional", "Sector-relative return with size interaction",
             "group_neutralize(rank(returns - group_mean(returns, 1, sector)) * rank(-cap), sector)",
             ({},)),
    SeedIdea(36, "F. Group/Cross-sectional", "Subindustry group Z-score decay",
             "group_zscore(ts_decay_linear(returns, {w}), subindustry)",
             ({"w": 5}, {"w": 20})),
    SeedIdea(37, "F. Group/Cross-sectional", "Dual-horizon momentum spread",
             "group_neutralize(rank(ts_delta(close, 5) - ts_delta(close, 20)), sector)",
             ({},)),
    SeedIdea(38, "F. Group/Cross-sectional", "Large-cap short-term mean reversion",
             "group_neutralize(rank(-ts_delta(close, 1)) * rank(cap), sector)",
             ({},)),
    SeedIdea(39, "F. Group/Cross-sectional", "Intraday trend decay",
             "group_neutralize(rank(ts_decay_linear(close - open, {w})), subindustry)",
             ({"w": 5}, {"w": 10})),
)


def generate_template_candidates(seed_ids: tuple | None = None) -> list[dict]:
    """Expand every (seed idea x window variant) into a concrete candidate
    dict ready for `candidates` table insertion: {expression, category,
    generation_tier}. `seed_ids` optionally restricts to a subset (e.g. for
    building within one category before moving on, per the source doc's own
    build-order advice)."""
    out = []
    for idea in SEED_IDEAS:
        if seed_ids is not None and idea.id not in seed_ids:
            continue
        for variant in idea.windows:
            expr = idea.template.format(**variant) if variant else idea.template
            out.append({
                "expression": expr,
                "category": f"{idea.category} / #{idea.id} {idea.name}",
                "generation_tier": "template",
            })
    return out
