"""
Gleason & Lee (2002) — Analyst Forecast Revisions & Delayed Price Formation
Diether, Malloy & Scherbina (2002) — Analyst Forecast Dispersion Anomaly
Barber & Odean (2008) — Attention-Driven Retail Buying & Reversals
Loh & Stulz (2018) — Sell-Side Research More Valuable in Bad Times
Source KB: docs/kb/sentiment/gleason_lee_2002_revision.md
WorldQuant Master Recalibration: docs/kb/sentiment/worldquant_brain_sentiment_master_recalibration.md

Core Finding (Gleason & Lee 2002):
    The market under-reacts to individual analyst forecast revisions.
    Table 2: Confirming revisions produce a 1-year drift of +4.6% long / -4.8% short (9.4% L/S spread).
    Table 6: The post-revision drift is 2-3x larger for firms with low analyst coverage (+12.7% spread).
    Table 4: Revision momentum remains statistically positive after controlling for Size, BM, and Momentum.

Live Verified BRAIN Fields:
    snt1_d1_netearningsrevision: Net analyst earnings revision momentum score
    snt1_d1_dtstsespe: Analyst forecast dispersion / uncertainty standard deviation
    anl4_total_rec: Total count of analyst recommendations (coverage breadth)
    scl12_buzz: Relative social media mention volume / buzz ratio
    scl12_sentiment: Social media net sentiment score
"""
from typing import Any, Dict, List

SOURCE_KB = "docs/kb/sentiment/gleason_lee_2002_revision.md"


def generate_sentiment_p1_candidates() -> List[Dict[str, Any]]:
    """
    Gleason-Lee 2002 + DMS 2002 + Barber-Odean 2008 + Loh-Stulz 2018 generators.
    Citation: JAR 2002, Table 2, Table 4, Table 6.
    """
    catalog: List[Dict[str, Any]] = []

    universes   = ["TOP1000", "TOP500", "TOPSP500"]
    neut_groups = ["SUBINDUSTRY", "SECTOR"]
    decays      = [8, 10, 12, 15]

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 1: Gleason & Lee (2002) Revision Momentum x Mean-Reversion Interaction
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for d in decays:
                for lookback in [20, 30]:
                    catalog.append({
                        "pillar": "GL_REVISION_DRIFT",
                        "archetype": f"GL_RevDrift_d{d}_lb{lookback}_{u}_{g}",
                        "expression": (
                            f"trade_when(volume > adv20 * 0.80, "
                            f"group_neutralize("
                            f"rank(ts_decay_linear(snt1_d1_netearningsrevision, {d})) * "
                            f"rank(-ts_delta(close, 3) / (ts_std_dev(close, {lookback}) + 0.001)), "
                            f"{g.lower()}), -1)"
                        ),
                        "hypothesis": (
                            f"Gleason-Lee 2002 Table 2: Market under-reacts to net analyst earnings revisions "
                            f"(snt1_d1_netearningsrevision). Interacted with {lookback}d volatility-scaled price reversion. {u}."
                        ),
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "analyst",
                        "source_kb": SOURCE_KB,
                    })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 2: Diether-Malloy-Scherbina (2002) Dispersion Contraction Shock
    # Shrinking analyst dispersion indicates collapsing ambiguity and consensus convergence
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for d in [10, 12]:
                catalog.append({
                    "pillar": "DMS_DISPERSION_CONTRACTION",
                    "archetype": f"DMS_DispContraction_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"group_neutralize("
                        f"rank(-ts_delta(snt1_d1_dtstsespe, 10) / (ts_std_dev(snt1_d1_dtstsespe, 20) + 0.001)) * "
                        f"rank(ts_decay_linear(snt1_d1_netearningsrevision, {d})), "
                        f"{g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"DMS 2002: Contraction in analyst forecast dispersion (snt1_d1_dtstsespe) signals "
                        f"uncertainty resolution, accelerating upward price incorporation of revisions. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 3: Low-Dispersion Conviction Gate (DMS 2002 Table 4)
    # Revisions in low-dispersion stocks have significantly higher information content
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:2]:
        for g in neut_groups:
            for d in [10, 12]:
                catalog.append({
                    "pillar": "DMS_LOW_DISPERSION_GATE",
                    "archetype": f"DMS_LowDispGate_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"trade_when(rank(ts_decay_linear(snt1_d1_dtstsespe, 10)) < 0.40, "
                        f"group_neutralize("
                        f"rank(ts_decay_linear(snt1_d1_netearningsrevision, {d})) * "
                        f"rank(-ts_delta(close, 3) / (ts_std_dev(close, 20) + 0.001)), "
                        f"{g.lower()}), -1), -1)"
                    ),
                    "hypothesis": (
                        f"DMS 2002 Table 4: Net revision signal filtered by low analyst dispersion (<40th pct). "
                        f"Avoids high-disagreement noise and short-sale constraint distortion. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 4: Barber & Odean (2008) Social Buzz Reversal
    # Extreme retail attention (social buzz spike) leads to temporary buying pressure followed by reversal
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for d in [5, 8, 10]:
                catalog.append({
                    "pillar": "BO_SOCIAL_BUZZ_REVERSAL",
                    "archetype": f"BO_SocialBuzzRev_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"trade_when(rank(scl12_buzz) > 0.80, "
                        f"group_neutralize("
                        f"rank(-ts_decay_linear(scl12_sentiment, {d})) * "
                        f"rank(-ts_delta(close, 3) / (ts_std_dev(close, 20) + 0.001)), "
                        f"{g.lower()}), -1), -1)"
                    ),
                    "hypothesis": (
                        f"Barber & Odean (2008) + Da et al. (2011): Retail buzz surge (scl12_buzz > 80th pct) "
                        f"indicates speculative retail herd entry. Fade extreme bullish sentiment into mean-reversion. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "social",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 5: Low Analyst Coverage Neglected Stock Gate (Extract 5, Table 6)
    # Firms with low coverage exhibit 2-3x larger post-revision drift (+12.7% spread)
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:2]:
        for g in neut_groups:
            for d in [10, 12]:
                catalog.append({
                    "pillar": "GL_LOW_COVERAGE_GATE",
                    "archetype": f"GL_LowCoverage_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"trade_when(rank(anl4_total_rec) < 0.40, "
                        f"group_neutralize("
                        f"rank(ts_decay_linear(snt1_d1_netearningsrevision, {d})) * "
                        f"rank(-ts_delta(close, 3) / (ts_std_dev(close, 20) + 0.001)), "
                        f"{g.lower()}), -1), -1)"
                    ),
                    "hypothesis": (
                        f"Gleason-Lee 2002 Table 6: Revision signal gated on low analyst coverage (anl4_total_rec < 40th pct). "
                        f"Neglected equities incorporate sell-side revisions slowly, generating +12.7% annual drift spread. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 6: Loh & Stulz (2018) Bad Times Uncertainty Magnifier
    # During high volatility regimes, investors rely heavily on sell-side analyst revisions
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for d in [8, 10]:
                catalog.append({
                    "pillar": "LS_REGIME_ANALYST_MAGNIFIER",
                    "archetype": f"LS_RegimeAnalyst_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"trade_when(rank(ts_std_dev(returns, 20)) > 0.60, "
                        f"group_neutralize("
                        f"rank(ts_decay_linear(snt1_d1_netearningsrevision, {d})) * "
                        f"rank(-ts_delta(close, 2) / (ts_std_dev(close, 10) + 0.001)), "
                        f"{g.lower()}), -1), -1)"
                    ),
                    "hypothesis": (
                        f"Loh-Stulz 2018: In high volatility regimes, Bayesian investors increase weighting on analyst revisions. "
                        f"Revisions in elevated volatility generate substantially higher abnormal price drift. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                    "source_kb": SOURCE_KB,
                })

    return catalog


if __name__ == "__main__":
    cands = generate_sentiment_p1_candidates()
    print(f"Generated {len(cands)} Gleason-Lee Revision Speed candidates.")
    print("Sample expression:")
    print(cands[0]["expression"])
