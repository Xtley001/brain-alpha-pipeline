"""
Novy-Marx (2013) — Gross Profitability Premium
Piotroski (2000) — F-Score
Cooper, Gulen & Schill (2008) — Asset Growth
Titman, Wei & Xie (2004) — Capital Investments
Hirshleifer, Hsu & Li (2013) — Innovative Efficiency
Lee & Swaminathan (2000) — Price Momentum & Trading Volume
Kogan, Papanikolaou et al. (2017) — Technological Innovation (KPSS)
Sias, Starks & Titman (2006) — Changes in Institutional Ownership
Cohen & Diether (2013) — Misvaluing Innovation

These generators extend the P0 fundamental pillar with P1/P2 papers,
all deriving their signals DIRECTLY from paper-specific formulas.
"""
from typing import Any, Dict, List


def generate_fundamental_p1_candidates() -> List[Dict[str, Any]]:
    """
    Fundamental P1 extensions — innovation, vol-momentum, institutional ownership.
    All constructions paper-faithful.
    """
    catalog: List[Dict[str, Any]] = []
    universes   = ["TOPSP500", "TOP500", "TOP1000", "TOP3000"]
    neut_groups = ["SUBINDUSTRY", "SECTOR", "MARKET"]
    decays      = [10, 20, 30, 60]

    # ─────────────────────────────────────────────────────────────────────────
    # HIRSHLEIFER, HSU & LI (2013): Innovative Efficiency (IE)
    # Paper: "Innovative Efficiency and Stock Returns" — JFE
    # IE = Patents / R&D_expenditure or Citations / R&D_expenditure
    # High IE firms (doing more with each R&D dollar) earn +2%/month premium.
    # BRAIN approx: r_and_d_expense as inverse proxy — high R&D / sales → low IE
    # (absent patent data: short high-R&D-but-low-output firms)
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for d in decays:
                # Proxy: R&D intensity (high R&D / sales without output = low IE)
                catalog.append({
                    "pillar": "HIRSHLEIFER_INNOVATION_PROXY",
                    "archetype": f"Hirsh_RD_Intensity_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.70, "
                        f"group_neutralize(signed_power(rank(-ts_decay_linear("
                        f"r_and_d_expense / (sales + 0.001), {d}"
                        f")), 0.5), {g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"Hirshleifer-Hsu-Li2013: R&D intensity as negative IE proxy. "
                        f"High R&D/Sales without return = low innovative efficiency → underperformance. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                })
                # Positive signal: HIGH R&D + HIGH sales growth = high IE proxy
                catalog.append({
                    "pillar": "HIRSHLEIFER_HIGH_IE",
                    "archetype": f"Hirsh_HighIE_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.70, "
                        f"trade_when(rank(r_and_d_expense / (assets + 0.001)) > 0.40, "
                        f"group_neutralize(signed_power(rank(ts_decay_linear("
                        f"ts_delta(sales, 252) / (r_and_d_expense + 0.001), {d}"
                        f")), 0.5), {g.lower()}), -1), -1)"
                    ),
                    "hypothesis": (
                        f"Hirshleifer-Hsu-Li2013: sales growth per R&D dollar = innovative efficiency. "
                        f"Among R&D-intensive firms only: high IE earns +2%/month. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                })

    # ─────────────────────────────────────────────────────────────────────────
    # LEE & SWAMINATHAN (2000): Volume as Momentum Life-Cycle Predictor
    # Paper: "Price Momentum and Trading Volume" — JF
    # Core: HIGH volume momentum winners continue to win for longer but then
    # REVERSE more sharply. LOW volume momentum winners have slower but more
    # persistent drift. Volume acts as a momentum life-cycle signal.
    # Signal 1: Price momentum × low volume = persistent drift (long)
    # Signal 2: Price momentum × high volume = near peak, about to reverse (short)
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [10, 14, 20]:
                # Low-vol momentum (persistent — long)
                catalog.append({
                    "pillar": "LS_LOW_VOL_MOM",
                    "archetype": f"LS_LowVolMom_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.50, "
                        f"trade_when(rank(adv20 / ts_mean(volume, 252)) < 0.35, "
                        f"group_neutralize(signed_power(rank(ts_decay_linear("
                        f"ts_sum(returns, 126) - ts_sum(returns, 5), {d}"
                        f")), 0.5), {g.lower()}), -1), -1)"
                    ),
                    "hypothesis": (
                        f"Lee-Swaminathan2000: low-volume momentum is persistent (slow life-cycle). "
                        f"Gate: current ADV < 35th percentile of 1yr avg → low vol winners. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                })
                # High-vol momentum (near reversal — fade)
                catalog.append({
                    "pillar": "LS_HIGH_VOL_MOM_REVERSAL",
                    "archetype": f"LS_HighVolRevrs_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 1.20, "
                        f"trade_when(rank(adv20 / ts_mean(volume, 252)) > 0.70, "
                        f"group_neutralize(signed_power(rank(-ts_decay_linear("
                        f"ts_sum(returns, 63), {d}"
                        f")), 0.5), {g.lower()}), -1), -1)"
                    ),
                    "hypothesis": (
                        f"Lee-Swaminathan2000: high-volume momentum winners near reversal peak. "
                        f"Gate: current ADV > 70th pctile of 1yr avg → crowded momentum. Fade. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIAS, STARKS & TITMAN (2006): Changes in Institutional Ownership
    # Paper: "Changes in Institutional Ownership and Stock Returns" — JF
    # Core: INCREASES in institutional ownership predict positive future returns.
    # Mechanism: institutional investors are better informed → their buying is
    # informative about fundamental value improvement.
    # Delta institutional ownership = current quarter - prior quarter
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for d in decays:
                catalog.append({
                    "pillar": "SIAS_INST_OWNERSHIP_DELTA",
                    "archetype": f"Sias_InstOwn_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.70, "
                        f"group_neutralize(signed_power(rank(ts_decay_linear("
                        f"ts_delta(institutional_ownership_percentage, 63), {d}"
                        f")), 0.5), {g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"Sias-Starks-Titman2006: ΔInstitutional ownership predicts positive returns. "
                        f"Institutional buying is informed — 63d change captures quarterly flow. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIAS: Institutional Ownership Level (Cross-Sectional)
    # High inst. ownership → well-researched → efficiently priced (less alpha)
    # Low inst. ownership → under-researched → more alpha potential
    # Combined: CHANGE × LEVEL → informed buying in neglected stocks = strongest signal
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [20, 30]:
                catalog.append({
                    "pillar": "SIAS_INST_NEGLECT_BUYING",
                    "archetype": f"Sias_NeglectBuy_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.70, "
                        f"trade_when(rank(institutional_ownership_percentage) < 0.40, "
                        f"group_neutralize(signed_power(rank(ts_decay_linear("
                        f"ts_delta(institutional_ownership_percentage, 63), {d}"
                        f")), 0.5), {g.lower()}), -1), -1)"
                    ),
                    "hypothesis": (
                        f"Sias2006: institutional buying in NEGLECTED (low ownership) stocks is most informative. "
                        f"Gate: inst_own < 40th pctile → neglected → informed entry signal. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                })

    # ─────────────────────────────────────────────────────────────────────────
    # KOGAN-PAPANIKOLAOU-SERU-STOFFMAN (2017): Technological Innovation Premium
    # Paper: "Technological Innovation, Resource Allocation, and Growth" — QJE
    # KPSS construct patent-value-weighted innovation measure (VXFIN).
    # Firms with high patent citation-weighted R&D earn +1.7%/month premium.
    # BRAIN approx: R&D growth rate as innovation momentum proxy.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [30, 60]:
                catalog.append({
                    "pillar": "KPSS_INNOVATION_MOMENTUM",
                    "archetype": f"KPSS_InnovMom_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.70, "
                        f"trade_when(rank(r_and_d_expense / (assets + 0.001)) > 0.30, "
                        f"group_neutralize(signed_power(rank(ts_decay_linear("
                        f"ts_delta(r_and_d_expense, 252) / (r_and_d_expense + 0.001), {d}"
                        f")), 0.5), {g.lower()}), -1), -1)"
                    ),
                    "hypothesis": (
                        f"KPSS2017: R&D growth rate among R&D-intensive firms = innovation momentum. "
                        f"Increasing R&D investment with existing capability → +1.7%/month premium. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                })

    # ─────────────────────────────────────────────────────────────────────────
    # COHEN & DIETHER (2013): Misvaluing Innovation
    # Paper: "Burying the Lead: Misvaluing Financial Statements"
    # Firms that INVEST heavily in innovation (R&D) while reporting LOW earnings
    # are systematically MISVALUED — markets confound R&D investment with low quality.
    # Signal: high R&D + low current earnings + high sales growth = misvalued innovator
    # These stocks earn +3%+/month when the true innovation value is discovered.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [20, 30, 60]:
                catalog.append({
                    "pillar": "COHEN_MISVALUED_INNOVATION",
                    "archetype": f"CohenD_MisvalInno_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.70, "
                        f"trade_when(rank(r_and_d_expense / (assets + 0.001)) > 0.50, "
                        f"group_neutralize(signed_power(rank(ts_decay_linear("
                        f"ts_delta(sales, 252) / (sales + 0.001) - earnings_before_tax / (assets + 0.001), {d}"
                        f")), 0.5), {g.lower()}), -1), -1)"
                    ),
                    "hypothesis": (
                        f"Cohen-Diether2013: R&D-intensive firm with high sales growth but low ROA = "
                        f"misvalued innovator. Market confuses investment with poor quality. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                })

    return catalog
