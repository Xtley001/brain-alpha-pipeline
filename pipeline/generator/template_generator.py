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
    SeedIdea(1, "A. Reversal", "Classic 1-day reversal",
              "group_neutralize(rank(-ts_delta(close, {w})), sector)",
              ({"w": 2}, {"w": 3}, {"w": 4}, {"w": 5})),
    SeedIdea(2, "A. Reversal", "3-day reversal",
              "group_neutralize(rank(-ts_delta(close, {w})), industry)",
              ({"w": 3}, {"w": 4}, {"w": 5})),
    SeedIdea(3, "A. Reversal", "Gap-fade",
              "rank(-(open - ts_delay(close,1)) / ts_delay(close,1))",
              ({},)),
    SeedIdea(4, "A. Reversal", "Volume-weighted reversal",
              "rank(-ts_delta(close,1) * min(volume / ts_mean(volume, {w}), 5))",
              ({"w": 20},)),
    SeedIdea(5, "A. Reversal", "Intraday-range-filtered reversal",
              "rank(rank(-ts_delta(close,1)) * rank((high-low)/ts_mean(high-low,{w})))",
              ({"w": 20},)),
    SeedIdea(6, "A. Reversal", "Sector-relative reversal",
              "rank(-(ts_delta(close,1) - group_mean(ts_delta(close,1), 1, sector)))",
              ({},)),
    SeedIdea(7, "A. Reversal", "Reversal with earnings-announcement exclusion",
              "rank(-ts_delta(close,1)) * (1 - is_earnings_window)",
              ({},)),
    SeedIdea(8, "B. Momentum", "6-month momentum, skip-month",
              "rank(ts_delta(ts_delay(close,21), {w}))",
              ({"w": 105},)),
    SeedIdea(9, "B. Momentum", "12-month momentum, skip-month",
              "rank(ts_delta(ts_delay(close,21), {w}))",
              ({"w": 231},)),
    SeedIdea(10, "B. Momentum", "Momentum acceleration",
              "rank(ts_delta(rank(ts_delta(close,{w1})), {w2}))",
              ({"w1": 63, "w2": 21},)),
    SeedIdea(11, "B. Momentum", "Momentum x size interaction",
              "rank(rank(ts_delta(close,{w})) * rank(-market_cap))",
              ({"w": 126},)),
    SeedIdea(12, "B. Momentum", "Volatility-regime-conditioned momentum",
              "rank(ts_delta(close,{w})) * (1 / (1 + ts_std(ts_delta(close,1), 20)))",
              ({"w": 126},)),
    SeedIdea(13, "B. Momentum", "52-week high proximity",
              "rank(close / ts_max(close, {w}))",
              ({"w": 252},)),
    SeedIdea(14, "B. Momentum", "Momentum rank stability",
              "ts_mean(rank(ts_delta(close,{w})), 10)",
              ({"w": 126},)),
    SeedIdea(15, "C. Volume/Liquidity", "Volume-anomaly-weighted price signal",
              "rank(ts_delta(close,1) * min(volume / ts_mean(volume,{w}), 5))",
              ({"w": 20},)),
    SeedIdea(16, "C. Volume/Liquidity", "Amihud illiquidity premium",
              "rank(abs(ts_delta(close,1)) / (volume * close))",
              ({},)),
    SeedIdea(17, "C. Volume/Liquidity", "Turnover-decline precursor signal",
              "rank(-ts_delta(ts_mean(volume,{w1}), {w2}))",
              ({"w1": 10, "w2": 20},)),
    SeedIdea(18, "C. Volume/Liquidity", "Volume-price divergence",
              "rank(rank(ts_delta(close,{w})) * rank(-ts_delta(volume,{w})))",
              ({"w": 5},)),
    SeedIdea(19, "C. Volume/Liquidity", "Dollar-volume rank (diagnostic feature)",
              "rank(volume * close)",
              ({},)),
    SeedIdea(20, "C. Volume/Liquidity", "Bid-ask-proxy spread compression signal",
              "rank(-((high-low)/close) / ts_mean((high-low)/close, {w}))",
              ({"w": 20},)),
    SeedIdea(21, "D. Fundamental/Valuation", "Sector-relative valuation z-score",
              "group_neutralize(rank(-pe_ratio), sector)",
              ({},)),
    SeedIdea(22, "D. Fundamental/Valuation", "Quality-filtered value",
              "rank(-pe_ratio) * rank(roe)",
              ({},)),
    SeedIdea(23, "D. Fundamental/Valuation", "EV/EBITDA cross-sectional rank",
              "group_neutralize(rank(-ev_ebitda), industry)",
              ({},)),
    SeedIdea(24, "D. Fundamental/Valuation", "Free-cash-flow yield",
              "group_neutralize(rank(free_cash_flow / market_cap), sector)",
              ({},)),
    SeedIdea(25, "D. Fundamental/Valuation", "Book-to-market with size interaction",
              "rank(rank(book_value/market_cap) * rank(-market_cap))",
              ({},)),
    SeedIdea(26, "D. Fundamental/Valuation", "Earnings-quality-adjusted valuation",
              "rank(-pe_ratio) - rank(accruals / total_assets)",
              ({},)),
    SeedIdea(27, "E. Analyst Estimates", "Estimate revision momentum",
              "rank(ts_delta(eps_estimate, {w}))",
              ({"w": 10}, {"w": 15}, {"w": 21})),
    SeedIdea(28, "E. Analyst Estimates", "Post-earnings-announcement drift (PEAD)",
              "rank(earnings_surprise) * decay_linear(1, {w})",
              ({"w": 20}, {"w": 40}, {"w": 60})),
    SeedIdea(29, "E. Analyst Estimates", "Estimate dispersion (analyst disagreement)",
              "rank(-ts_std(eps_estimate, {w}))",
              ({"w": 60},)),
    SeedIdea(30, "E. Analyst Estimates", "Revision breadth signal",
              "rank((num_upgrades - num_downgrades) / num_analysts)",
              ({},)),
    SeedIdea(31, "E. Analyst Estimates", "Guidance-implied surprise proxy",
              "rank(abs(ts_delta(close,1)) - ts_mean(abs(ts_delta(close,1)), {w}))",
              ({"w": 60},)),
    SeedIdea(32, "F. Volatility/Risk", "Low-volatility anomaly",
              "group_neutralize(rank(-ts_std(ts_delta(close,1), {w})), sector)",
              ({"w": 60},)),
    SeedIdea(33, "F. Volatility/Risk", "Idiosyncratic volatility",
              "rank(-ts_std(residual_return, {w}))",
              ({"w": 60},)),
    SeedIdea(34, "F. Volatility/Risk", "Volatility term structure",
              "rank(-(ts_std(ts_delta(close,1),{w1}) / ts_std(ts_delta(close,1),{w2})))",
              ({"w1": 5, "w2": 60},)),
    SeedIdea(35, "F. Volatility/Risk", "Skewness-based signal",
              "rank(-ts_skewness(ts_delta(close,1), {w}))",
              ({"w": 60},)),
    SeedIdea(36, "F. Volatility/Risk", "Beta-neutral market-timing overlay",
              "rank(ts_delta(close,126)) / cross_sectional_dispersion(returns, universe)",
              ({},)),
    SeedIdea(37, "G. Seasonality", "Turn-of-month effect",
              "rank(close) * is_turn_of_month",
              ({},)),
    SeedIdea(38, "G. Seasonality", "Day-of-week effect",
              "rank(-ts_delta(close,1)) * day_of_week_flag",
              ({},)),
    SeedIdea(39, "G. Seasonality", "January/quarter-end reversal",
              "rank(-ts_delta(close,1)) * calendar_window_flag",
              ({},)),
    SeedIdea(40, "G. Seasonality", "Pre-holiday drift",
              "rank(close) * is_pre_holiday",
              ({},)),
    SeedIdea(41, "H. Group/Cross-sectional", "Sector rotation signal",
              "group_rank(ts_delta(group_mean(close, 1, sector), {w}), sector)",
              ({"w": 21},)),
    SeedIdea(42, "H. Group/Cross-sectional", "Industry-relative earnings growth",
              "group_neutralize(rank(earnings_growth), industry)",
              ({},)),
    SeedIdea(43, "H. Group/Cross-sectional", "Peer-relative price-to-growth (PEG-style) rank",
              "group_neutralize(rank(-pe_ratio / max(earnings_growth, 0.01)), sector)",
              ({},)),
    SeedIdea(44, "H. Group/Cross-sectional", "Country-relative signal wrapper",
              "group_neutralize(rank(ts_delta(close,{w})), country)",
              ({"w": 126},)),
    # Section I (45-50) are ML-combiner ideas: conceptual, not single BRAIN
    # expressions (per the source doc itself). They are intentionally not
    # template-generated here; pipeline/generator/llm_generator.py's
    # reasoning tier is the right place to build rank-average / ridge /
    # GBM combiners once ~15-20 individually validated signals exist,
    # per the project's build order.
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
