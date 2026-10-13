"""
Tetlock (2007) — Giving Content to Investor Sentiment (Media Pessimism)
Da, Engelberg & Gao (2011) — In Search of Attention
Baker & Wurgler (2006) — Investor Sentiment Index
Barber & Odean (2008) — Attention and News (cross-market)
Kothari, So & Verdi (2016) — Analysts Forecasts in Asset Pricing

Papers:
  1. Tetlock (2007): "Giving Content to Investor Sentiment" — JF
     Core: High media PESSIMISM (fraction of negative words in WSJ column) predicts
     downward pressure on the market and subsequent MEAN REVERSION.
     Individual stock level: negative abnormal media coverage → temporary price depression
     → mean reversal over next 2 weeks.
     BRAIN approx: news_sentiment score (if available), or volume spike on negative days.

  2. Da, Engelberg & Gao (2011): "In Search of Attention" — JF
     Core: Google search volume (ASVI) for a stock's ticker predicts SHORT-TERM returns.
     Increase in ASVI → retail attention → temporary buying pressure → REVERSAL in ~2 weeks.
     BRAIN approx: abnormal volume surge on no-news days as search-attention proxy.

  3. Baker & Wurgler (2006): "Investor Sentiment and the Cross-Section of Stock Returns" — JF
     Core: When sentiment is HIGH → subsequent low returns for hard-to-value stocks
     (small, high vol, unprofitable, high growth, no dividends).
     When sentiment is LOW → subsequent high returns for same stocks.
     BRAIN: volatility regime as sentiment proxy (high VIX = low sentiment).

  4. Kothari, So & Verdi (2016): "Analysts as Intermediaries" — JFE
     Core: When analyst COVERAGE increases for a stock, it provides POSITIVE return.
     Analyst coverage = reduces information asymmetry → improves market efficiency → re-rating.
     Also: analyst ACCURACY differences across time predict who to follow.
"""
from typing import Any, Dict, List


SOURCE_KB = "docs/kb/sentiment/tetlock_da_kothari_givoly_media_sentiment.md"


def generate_sentiment_p2_candidates() -> List[Dict[str, Any]]:
    """
    Media sentiment, search attention, Baker-Wurgler, and analyst coverage generators.
    All paper-faithful constructions.
    """
    catalog: List[Dict[str, Any]] = []

    universes   = ["TOPSP500", "TOP500", "TOP1000", "TOP3000"]
    neut_groups = ["SUBINDUSTRY", "SECTOR", "MARKET"]
    decays      = [5, 10, 14, 20]

    # ─────────────────────────────────────────────────────────────────────────
    # TETLOCK (2007): Media Pessimism → Temporary Price Depression → Reversal
    # Negative media sentiment creates selling pressure → overshoot → mean-revert.
    # BRAIN: news_sentiment (if available), else use volume spike on negative-return days
    # as proxy for negative media attention.
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for d in [5, 10]:
                # Proxy: abnormal volume + negative return = negative media attention day
                catalog.append({
                    "pillar": "TETLOCK_MEDIA_REVERSAL",
                    "archetype": f"Tetlock_MediaRev_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 1.30, "
                        f"trade_when(rank(ts_sum(volume / adv20, 3)) > 0.80, "
                        f"trade_when(returns < 0, "
                        f"group_neutralize(rank(-ts_decay_linear(returns, {d})), {g.lower()}), "
                        f"-1), -1), -1)"
                    ),
                    "hypothesis": (
                        f"Tetlock2007: high abnormal volume + negative return = negative media day. "
                        f"Temporary price depression → mean-revert over 2 weeks. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # DA, ENGELBERG & GAO (2011): Search Attention → Short-Term Reversal
    # ASVI = abnormal search volume index. High ASVI → retail attention → buying pressure → reversal.
    # BRAIN proxy: adv20 spike relative to 1yr vol norm = retail-attention-driven surge.
    # If volume spikes MUCH more than price, it suggests retail attention (not institutional).
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [5, 10]:
                catalog.append({
                    "pillar": "DEG_SEARCH_ATTENTION_REV",
                    "archetype": f"DEG_SearchAttn_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(rank(volume / adv20) > 0.85, "
                        f"trade_when(rank(abs(returns)) < 0.40, "
                        f"group_neutralize(rank(-ts_decay_linear(ts_sum(volume / adv20, 5), {d})), {g.lower()}), "
                        f"-1), -1)"
                    ),
                    "hypothesis": (
                        f"Da-Engelberg-Gao2011: high volume with small price move = search/retail attention. "
                        f"ASVI proxy: volume spike on quiet-return day = retail entry → 2-week reversal. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # BAKER & WURGLER (2006): Sentiment Regime × Hard-to-Value Stocks
    # High vol regime (proxy for low sentiment) → hard-to-value stocks OUTPERFORM.
    # Hard-to-value: small, high vol, no dividends, high growth.
    # Signal: in high-vol regime, LONG high-idiovol stocks (normally short them!).
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOP1000", "TOP3000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [10, 14]:
                # Regime-conditional: high vol market = low sentiment = buy spec stocks
                catalog.append({
                    "pillar": "BW_SENTIMENT_LOW_REGIME",
                    "archetype": f"BW_LowSentiment_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(ts_rank(ts_std_dev(returns, 21), 252) > 0.70, "
                        f"trade_when(volume > adv20 * 0.70, "
                        f"group_neutralize(signed_power(rank(ts_decay_linear("
                        f"idiosyncratic_vol_last_60_days_spy, {d}"
                        f")), 0.5), {g.lower()}), -1), -1)"
                    ),
                    "hypothesis": (
                        f"Baker-Wurgler2006: in low-sentiment (high-vol) regime, hard-to-value stocks "
                        f"(high idiovol) are UNDERPRICED and outperform. Contrarian to AHXZ in low-sentiment. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # KOTHARI-SO-VERDI (2016): Analyst Coverage Expansion → Re-Rating
    # When analyst count INCREASES for a stock, market re-prices with reduced
    # information asymmetry → positive returns. Most pronounced in small/neglected stocks.
    # BRAIN: analyst_count changes (or analyst_coverage field)
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for d in decays:
                catalog.append({
                    "pillar": "KSV_ANALYST_COVERAGE",
                    "archetype": f"KSV_Coverage_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.70, "
                        f"group_neutralize(signed_power(rank(ts_decay_linear("
                        f"ts_delta(analyst_count, 63), {d}"
                        f")), 0.5), {g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"Kothari-So-Verdi2016: increasing analyst coverage → reduced info asymmetry "
                        f"→ positive re-rating. 63d change in analyst count. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # GIVOLY & LAKONISHOK (1979): Analyst Forecast Revision Direction (early paper)
    # One of the first papers to show analyst revisions predict returns.
    # Simple but powerful: cumulative revision signal over 3 months predicts 6m drift.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for window in [21, 42, 63]:
                for d in [10, 14, 20]:
                    catalog.append({
                        "pillar": "GIVOLY_REVISION_DIRECTION",
                        "archetype": f"Givoly_Rev_{window}d_d{d}_{u}_{g}",
                        "expression": (
                            f"trade_when(volume > adv20 * 0.70, "
                            f"group_neutralize(signed_power(rank(ts_decay_linear("
                            f"ts_sum(analyst_rating_change, {window}), {d}"
                            f")), 0.5), {g.lower()}), -1)"
                        ),
                        "hypothesis": (
                            f"Givoly-Lakonishok1979: {window}d cumulative analyst revision. "
                            f"One of the first revision-drift papers. Persistent effect over 6m. {u}."
                        ),
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "analyst",
                        "source_kb": SOURCE_KB,
                    })

    return catalog
