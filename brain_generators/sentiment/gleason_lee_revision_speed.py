"""
Gleason & Lee (2002) — Analyst Forecast Revisions & Delayed Price Formation
Diether, Malloy & Scherbina (2002) — Analyst Forecast Dispersion Anomaly
Barber & Odean (2008) — Attention-Driven Retail Buying
Loh & Stulz (2018) — Sell-Side Research More Valuable in Bad Times
Source KB: docs/kb/sentiment/gleason_lee_2002_revision.md

Core Finding (Gleason & Lee 2002):
    The market under-reacts to individual analyst forecast revisions.
    Table 2: Confirming revisions (revision above prior estimate AND above consensus)
    produce a 1-year drift of +4.6% long / -4.8% short (9.4% L/S spread).
    Table 6: The post-revision drift is 2-3x larger for firms with low analyst coverage (+12.7% spread)
    because information is incorporated into prices much more slowly.
    Table 4: Revision momentum remains statistically positive after controlling for Size, BM, and Momentum.
"""
from typing import Any, Dict, List

SOURCE_KB = "docs/kb/sentiment/gleason_lee_2002_revision.md"


def generate_sentiment_p1_candidates() -> List[Dict[str, Any]]:
    """
    Gleason-Lee 2002 + DMS 2002 + Barber-Odean 2008 + Loh-Stulz 2018 generators.
    Citation: JAR 2002, Table 2, Table 4, Table 6.
    """
    catalog: List[Dict[str, Any]] = []

    universes   = ["TOPSP500", "TOP500", "TOP1000", "TOP3000"]
    neut_groups = ["SUBINDUSTRY", "SECTOR", "MARKET"]
    decays      = [10, 14, 20, 30]

    # ─────────────────────────────────────────────────────────────────────────
    # GLEASON & LEE (2002): Analyst Revision Speed Signal (Extract 3 & 4, Table 2)
    # Market under-reacts to revisions -> buy/sell stocks with large upward/downward revisions.
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for d in decays:
                catalog.append({
                    "pillar": "GL_REVISION_DRIFT",
                    "archetype": f"GL_RevDrift_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"trade_when(abs(rank(ts_decay_linear(analyst_rating_change, {d})) - 0.5) > 0.20, "
                        f"group_neutralize(signed_power(rank(ts_decay_linear(analyst_rating_change, {d})), 0.5), {g.lower()}), "
                        f"-1), -1)"
                    ),
                    "hypothesis": (
                        f"Gleason-Lee2002 Table 2: market under-reacts to analyst rating changes. "
                        f"Buy (sell) stocks with recent large upward (downward) revisions. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # GLEASON & LEE: Cumulative Revision Momentum (6-month)
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for cumul_window in [42, 63, 126]:
                for d in [10, 14, 20]:
                    catalog.append({
                        "pillar": "GL_CUMULATIVE_REVISION",
                        "archetype": f"GL_CumRev_{cumul_window}d_d{d}_{u}_{g}",
                        "expression": (
                            f"trade_when(volume > adv20 * 0.80, "
                            f"group_neutralize(signed_power(rank(ts_decay_linear("
                            f"ts_sum(analyst_rating_change, {cumul_window}), {d}"
                            f")), 0.5), {g.lower()}), -1)"
                        ),
                        "hypothesis": (
                            f"Gleason-Lee2002: {cumul_window}d cumulative revision signal. "
                            f"Sustained analyst upgrade/downgrade flow persists for 6 months. {u}."
                        ),
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "analyst",
                        "source_kb": SOURCE_KB,
                    })

    # ─────────────────────────────────────────────────────────────────────────
    # DIETHER-MALLOY-SCHERBINA (2002): Dispersion -> Short Signal
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for d in decays:
                catalog.append({
                    "pillar": "DMS_DISPERSION",
                    "archetype": f"DMS_Dispersion_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.75, "
                        f"trade_when(rank(ts_decay_linear(analyst_estimate_dispersion, {d})) > 0.65, "
                        f"group_neutralize(signed_power(rank(-ts_decay_linear(analyst_estimate_dispersion, {d})), 0.5), {g.lower()}), "
                        f"-1), -1)"
                    ),
                    "hypothesis": (
                        f"DMS2002: high analyst forecast dispersion -> short-sale constraint mispricing. "
                        f"Pessimists can't short -> prices reflect optimists -> overpriced -> short. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # DMS: Dispersion x Recent Loser Gate (Paper Table 4)
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [10, 14]:
                catalog.append({
                    "pillar": "DMS_DISPERSION_LOSER",
                    "archetype": f"DMS_DispLoser_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.75, "
                        f"trade_when(rank(analyst_estimate_dispersion) > 0.65, "
                        f"trade_when(rank(ts_sum(returns, 126)) < 0.35, "
                        f"group_neutralize(rank(-ts_decay_linear(analyst_estimate_dispersion, {d})), {g.lower()}), "
                        f"-1), -1), -1)"
                    ),
                    "hypothesis": (
                        f"DMS2002 Table 4: dispersion effect concentrated in recent losers. "
                        f"High dispersion + poor 6m return = maximum overpricing due to short constraints. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # BARBER & ODEAN (2008): Attention-Driven Price Pressure -> Reversal
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [5, 10]:
                for attn_window in [1, 3, 5]:
                    catalog.append({
                        "pillar": "BO_ATTENTION_REVERSAL",
                        "archetype": f"BO_AttnRev_{attn_window}d_d{d}_{u}_{g}",
                        "expression": (
                            f"trade_when(volume > adv20 * 1.50, "
                            f"trade_when(rank(ts_sum(volume / adv20, {attn_window})) > 0.80, "
                            f"group_neutralize(rank(-ts_decay_linear(ts_sum(returns, {attn_window}), {d})), {g.lower()}), "
                            f"-1), -1)"
                        ),
                        "hypothesis": (
                            f"Barber-Odean2008: attention-driven retail buying -> price overshoot -> reversal. "
                            f"Gate on abnormal vol spike >1.5x ADV AND extreme {attn_window}d return -> fade. {u}."
                        ),
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "analyst",
                        "source_kb": SOURCE_KB,
                    })

    # ─────────────────────────────────────────────────────────────────────────
    # LOH & STULZ (2018): Regime-Conditional Analyst Signal
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [10, 14, 20]:
                catalog.append({
                    "pillar": "LS_REGIME_ANALYST",
                    "archetype": f"LS_RegimeAnalyst_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"group_neutralize(signed_power(rank(ts_decay_linear("
                        f"analyst_rating_change * ts_rank(ts_std_dev(returns, 21), 252), {d}"
                        f")), 0.5), {g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"Loh-Stulz2018: analyst revisions have +50% impact in high-uncertainty regimes. "
                        f"Weight revision by realized vol rank -> stress-amplified analyst signal. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # CROSS-SIGNAL: Revision + Dispersion Divergence
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [10, 14]:
                catalog.append({
                    "pillar": "GL_DMS_DIVERGENCE",
                    "archetype": f"GL_DMS_Diverge_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"trade_when(rank(analyst_estimate_dispersion) > 0.50, "
                        f"group_neutralize(signed_power(rank(ts_decay_linear(analyst_rating_change, {d})), 0.5), {g.lower()}), "
                        f"-1), -1)"
                    ),
                    "hypothesis": (
                        f"GL2002 + DMS2002: courageous non-herding analyst revision in high-dispersion stock. "
                        f"Analyst upgrading against pessimistic consensus -> largest delayed drift. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 8: Low Analyst Coverage Revision Gate (Extract 5, Table 6)
    # Table 6 proves firms with low analyst coverage have 2-3x larger drift (+12.7% spread)!
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [14, 20]:
                catalog.append({
                    "pillar": "GL_LOW_COVERAGE_GATE",
                    "archetype": f"GL_LowCoverage_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"trade_when(rank(analyst_count) < 0.40, "
                        f"group_neutralize(signed_power(rank(ts_decay_linear(analyst_rating_change, {d})), 0.5), {g.lower()}), "
                        f"-1), -1)"
                    ),
                    "hypothesis": (
                        f"Gleason-Lee2002 Table 6: Revision signal gated on low analyst coverage (<40th pct). "
                        f"Neglected stocks incorporate news slowly, generating +12.7% annual drift spread. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 9: Confirming Revision x Price Momentum Confirmation (Extract 7 & 8, Table 4)
    # Revisions confirming 6-month intermediate price momentum eliminate value traps.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [14, 20]:
                catalog.append({
                    "pillar": "GL_REVISION_X_MOMENTUM",
                    "archetype": f"GL_RevMom_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"group_neutralize("
                        f"rank(ts_decay_linear(analyst_rating_change, {d})) * "
                        f"rank(ts_decay_linear(ts_delta(close, 126), 20)), "
                        f"{g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"Gleason-Lee2002 Table 4 Model 2: Upward revision confirming 6-month price momentum. "
                        f"Double confirmation eliminates structural value traps and maximizes drift persistence. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                    "source_kb": SOURCE_KB,
                })

    return catalog
