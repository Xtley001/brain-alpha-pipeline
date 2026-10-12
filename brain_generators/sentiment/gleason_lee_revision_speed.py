"""
Gleason & Lee (2002) — Analyst Forecast Revisions & Delayed Price Formation
Diether, Malloy & Scherbina (2002) — Analyst Forecast Dispersion Anomaly
Barber & Odean (2008) — Attention-Driven Retail Buying
Loh & Stulz (2018) — Sell-Side Research More Valuable in Bad Times

Papers:
  1. Gleason & Lee (2002): "Analyst Forecast Revisions and Market Price Discovery" — AR
     Core: Market UNDER-REACTS to analyst forecast revisions. The price response to a
     revision is systematically delayed. Key cross-sectional determinants of the delay:
       - Analyst herding → LESS informative (market over-discounts herding revisions)
       - Celebrity analysts → MORE informative (market under-discounts their revisions)
       - Revision timing relative to consensus formation
     Formula: revision_informativeness = (estimate_i - prior_mean) / prior_std
              stocks with high |z-score revision| from non-herding analysts → biggest drift

  2. Diether-Malloy-Scherbina (2002): "Differences of Opinion and Cross-Section of Returns" — JF
     Core: Stocks with HIGH analyst earnings forecast DISPERSION earn LOWER future returns.
     Miller (1977) theory: in the presence of short-sale constraints, pessimistic investors
     can't short → prices reflect optimistic views → overpricing → negative returns.
     Dispersion measured as std of analyst EPS estimates / |mean EPS estimate|.
     Effect concentrated in: small stocks, recent losers, high-short-interest stocks.

  3. Barber & Odean (2008): "All That Glitters: The Effect of Attention and News on
     the Buying Behavior of Individual and Institutional Investors" — RFS
     Core: Retail investors are net BUYERS of attention-grabbing stocks (news events,
     high abnormal volume, extreme-return stocks). This attention-driven buying creates
     temporary price pressure → prices OVERSHOOT → subsequent REVERSAL.
     Signal: abnormal volume spike + news event + recent large return → fade the attention

  4. Loh & Stulz (2018): "Is Sell-Side Research More Valuable in Bad Times?" — JF
     Core: Analyst revisions have LARGER price impact during bad times (high uncertainty).
     In bad times: analyst errors fall, revisions are more accurate, impact is +50% larger.
     Signal: weight analyst revision signal by market-uncertainty regime (VIX proxy)
"""
from typing import Any, Dict, List


def generate_sentiment_p1_candidates() -> List[Dict[str, Any]]:
    """
    Gleason-Lee 2002 + DMS 2002 + Barber-Odean 2008 + Loh-Stulz 2018 generators.
    Paper-faithful constructions for sentiment/analyst dataset.
    """
    catalog: List[Dict[str, Any]] = []

    universes   = ["TOPSP500", "TOP500", "TOP1000", "TOP3000"]
    neut_groups = ["SUBINDUSTRY", "SECTOR", "MARKET"]
    decays      = [10, 14, 20, 30]

    # ─────────────────────────────────────────────────────────────────────────
    # GLEASON & LEE (2002): Analyst Revision Speed Signal
    # Market under-reacts to revisions → buy (sell) stocks where analysts just revised
    # their estimates significantly upward (downward).
    # BRAIN: analyst_rating_change captures direction; ts_zscore for magnitude.
    # Key: Gleason-Lee find the effect is STRONGER for non-herding revisions.
    # Proxy for non-herding: large revision vs. current consensus (high |z-score|)
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
                        f"Gleason-Lee2002: market under-reacts to analyst rating changes. "
                        f"Buy (sell) stocks with recent large upward (downward) revisions. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                })

    # ─────────────────────────────────────────────────────────────────────────
    # GLEASON & LEE: Cumulative Revision Momentum (6-month)
    # Paper finds that revision effects ACCUMULATE over 6 months — not just 1 event.
    # Cumulative sum of revisions = persistent informational flow signal.
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
                    })

    # ─────────────────────────────────────────────────────────────────────────
    # DIETHER-MALLOY-SCHERBINA (2002): Dispersion → Short Signal
    # High forecast dispersion among analysts → pessimists can't short → overpricing.
    # Short high-dispersion stocks: -1.06%/month underperformance (Table 1).
    # Effect strongest among: small stocks, recent losers, high-short-interest.
    # BRAIN: analyst_estimate_dispersion (std of analyst forecasts / |mean forecast|)
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
                        f"DMS2002: high analyst forecast dispersion → short-sale constraint mispricing. "
                        f"Pessimists can't short → prices reflect optimists → overpriced → short. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                })

    # ─────────────────────────────────────────────────────────────────────────
    # DMS: Dispersion × Recent Loser Gate (Paper Table 4)
    # Paper: dispersion effect is concentrated in RECENT LOSERS (momentum × dispersion).
    # Gate: high dispersion AND poor 6-month price performance → most overpriced.
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
                })

    # ─────────────────────────────────────────────────────────────────────────
    # BARBER & ODEAN (2008): Attention-Driven Price Pressure → Reversal
    # Retail investors buy attention-grabbing stocks → temporary price overshoot.
    # High abnormal volume + news day + extreme recent return → fade the attention spike.
    # BRAIN: volume / adv20 (abnormal volume), returns (recent extreme), analyst coverage
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
                            f"Barber-Odean2008: attention-driven retail buying → price overshoot → reversal. "
                            f"Gate on abnormal vol spike >1.5x ADV AND extreme {attn_window}d return → fade. {u}."
                        ),
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "analyst",
                    })

    # ─────────────────────────────────────────────────────────────────────────
    # LOH & STULZ (2018): Regime-Conditional Analyst Signal
    # In BAD TIMES (high uncertainty) → analyst revisions carry 50% MORE weight.
    # Signal: analyst_rating_change × realized vol (regime proxy).
    # High vol regime → weight analyst revisions more heavily.
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
                        f"Weight revision by realized vol rank → stress-amplified analyst signal. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                })

    # ─────────────────────────────────────────────────────────────────────────
    # CROSS-SIGNAL: Revision + Dispersion Divergence
    # Most powerful configuration: analyst is upgrading (positive revision) BUT
    # consensus dispersion is HIGH → contrarian — the upgrading analyst is going
    # against the pessimistic crowd. This is the "courageous non-herding" signal.
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
                        f"Analyst upgrading against pessimistic consensus → largest delayed drift. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                })

    return catalog
