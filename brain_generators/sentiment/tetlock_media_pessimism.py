"""
Tetlock (2007) — Media Pessimism & Fast Return Reversal
Da, Engelberg & Gao (2011) — In Search of Attention & Retail Buzz
Baker & Wurgler (2006) — Investor Sentiment Regime Cross-Section
Jegadeesh & Livnat (2006) — Top-Line Revenue News Sentiment
Source KB: docs/kb/sentiment/tetlock_da_kothari_givoly_media_sentiment.md
WorldQuant Master Recalibration: docs/kb/sentiment/worldquant_brain_sentiment_master_recalibration.md

Core Institutional Empirical Findings:
1. Tetlock (2007, Journal of Finance):
   - High media pessimism depresses next-day returns by -8.1 basis points (t=3.94).
   - This price depression reverses by +6.8 basis points over trading days t+2 to t+5.
   - Extreme media pessimism shocks predict surges in trading volume.
2. Da, Engelberg & Gao (2011, Journal of Finance):
   - Spikes in retail attention / search volume create short-term buying pressure followed by price reversal.
3. Jegadeesh & Livnat (2006) / Fink (2020):
   - Top-line revenue surprises drive more persistent and durable drift than cost-cutting noise.

Live Verified BRAIN Fields:
    rp_css_earnings: RavenPack composite sentiment score for earnings news
    rp_css_revenue: RavenPack composite sentiment score for revenue news
    rp_css_dividends: RavenPack composite sentiment score for dividend announcements
    rp_css_credit: RavenPack composite sentiment score for credit/debt news
    scl12_sentiment: Social media net sentiment score
    scl12_buzz: Relative social media mention volume / buzz ratio
"""
from typing import Any, Dict, List

SOURCE_KB = "docs/kb/sentiment/tetlock_da_kothari_givoly_media_sentiment.md"


def generate_sentiment_p2_candidates() -> List[Dict[str, Any]]:
    """
    Generate paper-grounded alpha candidates from Tetlock (2007), Da et al. (2011),
    Baker & Wurgler (2006), and Jegadeesh & Livnat (2006).
    All expressions feature balanced parentheses, valid BRAIN operators, and 100% source_kb traceability.
    """
    catalog: List[Dict[str, Any]] = []

    universes   = ["TOP1000", "TOP500", "TOPSP500"]
    neut_groups = ["SUBINDUSTRY", "SECTOR"]
    decays      = [5, 8, 10, 12]

    # ─────────────────────────────────────────────────────────────────────────
    # 1. Tetlock (2007): Media Pessimism Mean-Reversion
    # Fade sudden negative spikes in RavenPack composite earnings sentiment
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for d in [5, 8]:
                catalog.append({
                    "pillar": "TETLOCK_MEDIA_PESSIMISM_REVERSAL",
                    "archetype": f"Tetlock_MediaPessimismRev_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"group_neutralize("
                        f"rank(-ts_delta(rp_css_earnings, 3)) * "
                        f"rank(-ts_delta(close, 3) / (ts_std_dev(close, 20) + 0.001)), "
                        f"{g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"Tetlock 2007 Table 1: Sudden spikes in media pessimism (drop in rp_css_earnings) "
                        f"cause temporary price depression that systematically reverses over trading days t+2 to t+5. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "news",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 2. Jegadeesh & Livnat (2006): Top-Line Revenue News Drift
    # Revenue sentiment generates more persistent cash-flow expansion signals than cost cuts
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for d in [10, 12]:
                catalog.append({
                    "pillar": "JEGADEESH_REVENUE_SENTIMENT_DRIFT",
                    "archetype": f"Jegadeesh_RevSentimentDrift_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"group_neutralize("
                        f"rank(ts_decay_linear(rp_css_revenue, {d})) * "
                        f"rank(-ts_delta(close, 3) / (ts_std_dev(close, 20) + 0.001)), "
                        f"{g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"Jegadeesh & Livnat (2006) + Fink (2020) Obs. 15: RavenPack revenue sentiment (rp_css_revenue) "
                        f"captures durable product demand expansion, driving persistent post-announcement drift. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "news",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 3. Revenue Tone vs Earnings Tone Divergence (Quality SUE)
    # Long firms where revenue news tone exceeds headline earnings tone (demand growth)
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for d in [8, 10]:
                catalog.append({
                    "pillar": "REVENUE_EARNINGS_TONE_DIVERGENCE",
                    "archetype": f"RevEarningsToneDiverge_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"group_neutralize("
                        f"rank(ts_decay_linear(rp_css_revenue, {d}) - ts_decay_linear(rp_css_earnings, {d})) * "
                        f"rank(-ts_delta(close, 3) / (ts_std_dev(close, 20) + 0.001)), "
                        f"{g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"Fink (2020) Obs. 15: Positive spread between revenue sentiment (rp_css_revenue) and earnings sentiment "
                        f"(rp_css_earnings) isolates genuine organic top-line expansion from temporary cost-cutting. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "news",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 4. Da, Engelberg & Gao (2011): Retail Attention Shock & Contrarian Reversal
    # Extreme social media buzz without fundamental justification predicts reversal
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for d in [5, 8]:
                catalog.append({
                    "pillar": "DEG_RETAIL_BUZZ_REVERSAL",
                    "archetype": f"DEG_RetailBuzzRev_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"trade_when(rank(scl12_buzz) > 0.80, "
                        f"group_neutralize("
                        f"rank(-ts_decay_linear(scl12_sentiment, {d})) * "
                        f"rank(-ts_delta(close, 3) / (ts_std_dev(close, 20) + 0.001)), "
                        f"{g.lower()}), -1), -1)"
                    ),
                    "hypothesis": (
                        f"Da, Engelberg & Gao (2011) Table 4: Extreme social buzz surges (scl12_buzz > 80th pct) indicate retail "
                        f"speculative exuberance. Fade sentiment extremes to capture two-week price reversal. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "social",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 5. RavenPack Dividend & Credit News Conviction
    # Machine-readable sentiment from capital structure news (dividends, credit)
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for d in [10, 12]:
                catalog.append({
                    "pillar": "RP_CAPITAL_STRUCTURE_TONE",
                    "archetype": f"RPCapitalTone_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"group_neutralize("
                        f"rank(ts_decay_linear(rp_css_dividends, {d})) * "
                        f"rank(ts_decay_linear(rp_css_credit, {d})) * "
                        f"rank(-ts_delta(close, 3) / (ts_std_dev(close, 20) + 0.001)), "
                        f"{g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"Merton (1974) + Baker & Wurgler (2006): Positive tone across both dividend (rp_css_dividends) and "
                        f"credit news (rp_css_credit) signals fundamental solvency and financial distress mitigation. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "news",
                    "source_kb": SOURCE_KB,
                })

    return catalog


if __name__ == "__main__":
    candidates = generate_sentiment_p2_candidates()
    print(f"Generated {len(candidates)} Tetlock / Da / Jegadeesh sentiment candidates.")
    print("Sample expression:")
    print(candidates[0]["expression"])
