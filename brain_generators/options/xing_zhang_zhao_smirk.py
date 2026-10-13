"""
Xing, Zhang & Zhao (2010) — Volatility Smirk Generator
Paper: "What Does the Individual Option Volatility Smirk Tell Us About Future Equity Returns?"
Journal of Financial and Quantitative Analysis (JFQA)

Core Finding: The slope of the volatility smirk (OTM put IV minus ATM call IV) predicts future
stock returns negatively. Stocks with the steepest smirks significantly UNDERPERFORM over the
next month — informed traders buy OTM puts ahead of negative news, creating predictable asymmetry
in the IV surface.

Key Formula (Paper Eq. 1):
    SKEW_{i,t} = IV_OTM_Put(K/S ≈ 0.95, T=30d) - IV_ATM_Call(K/S ≈ 1.00, T=30d)

Extended to: tenor variants, normalized smirk (÷ ATM vol level), smirk slope change
(momentum in skew), and term-structure of smirk (30d vs 90d vs 180d spread).
"""
from typing import Any, Dict, List

SOURCE_KB = "docs/kb/options/xing_zhang_zhao_2010_smirk.md"


def generate_xing_zhang_zhao_smirk_candidates() -> List[Dict[str, Any]]:
    """
    Xing-Zhang-Zhao (2010): Volatility Smirk → Future Equity Returns.
    Generates 60+ paper-derived archetypes across all primary constructions.
    Citation: JFQA 2010, Table 3-5 (monthly portfolio sorts by SKEW quintile).
    """
    catalog: List[Dict[str, Any]] = []

    universes  = ["TOPSP500", "TOP500", "TOP1000", "TOP200"]
    neut_groups = ["SUBINDUSTRY", "SECTOR", "MARKET"]
    tenors     = [30, 60, 90, 180]
    decays     = [10, 14, 20]

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 1: Raw Smirk Slope (Paper's primary signal, Table 3)
    # raw_smirk = IV_put_{t} - IV_call_{t}
    # Short stocks with steepest smirk (most expensive OTM puts vs ATM calls)
    # Economic logic: informed put-buying creates permanent IV asymmetry ahead of bad news
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for t in tenors:
                for d in decays:
                    catalog.append({
                        "pillar": "XZZ_RAW_SMIRK",
                        "archetype": f"XZZ_RawSmirk_t{t}_d{d}_{u}_{g}",
                        "expression": (
                            f"trade_when(volume > adv20 * 0.90, "
                            f"trade_when(abs(rank(ts_decay_linear("
                            f"(implied_volatility_put_{t} - implied_volatility_call_{t}), {d}"
                            f")) - 0.5) > 0.25, "
                            f"group_neutralize(signed_power(rank(-ts_decay_linear("
                            f"(implied_volatility_put_{t} - implied_volatility_call_{t}), {d}"
                            f")), 0.5), {g.lower()}), "
                            f"-1), -1)"
                        ),
                        "hypothesis": (
                            f"XZZ2010: Short steep-smirk stocks (OTM put IV > ATM call IV, {t}d tenor). "
                            f"Informed put-buying signals informed negative flow. Universe={u}."
                        ),
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "options",
                        "source_kb": SOURCE_KB,
                    })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 2: Normalized Smirk (÷ ATM vol level, Paper Eq. 2 variant)
    # normalized_smirk = (IV_put - IV_call) / IV_mean
    # Normalization removes the vol-level effect, isolating pure shape information.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for t in [30, 60, 90]:
                for d in [10, 14]:
                    catalog.append({
                        "pillar": "XZZ_NORM_SMIRK",
                        "archetype": f"XZZ_NormSmirk_t{t}_d{d}_{u}_{g}",
                        "expression": (
                            f"trade_when(volume > adv20 * 0.90, "
                            f"trade_when(abs(rank(ts_decay_linear("
                            f"(implied_volatility_put_{t} - implied_volatility_call_{t}) / (implied_volatility_mean_{t} + 0.001), {d}"
                            f")) - 0.5) > 0.25, "
                            f"group_neutralize(signed_power(rank(-ts_decay_linear("
                            f"(implied_volatility_put_{t} - implied_volatility_call_{t}) / (implied_volatility_mean_{t} + 0.001), {d}"
                            f")), 0.5), {g.lower()}), "
                            f"-1), -1)"
                        ),
                        "hypothesis": (
                            f"XZZ2010 normalized: (IV_put - IV_call) / IV_mean at {t}d — "
                            f"vol-level-adjusted smirk slope isolates pure shape information. {u}."
                        ),
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "options",
                        "source_kb": SOURCE_KB,
                    })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 3: Time-Scaled Smirk (× sqrt(T/252) — annualizing the tenor)
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for t in [30, 60, 90]:
                for d in [10, 14]:
                    catalog.append({
                        "pillar": "XZZ_ANNUALIZED_SMIRK",
                        "archetype": f"XZZ_AnnSmirk_t{t}_d{d}_{u}_{g}",
                        "expression": (
                            f"trade_when(volume > adv20 * 0.90, "
                            f"trade_when(abs(rank(ts_decay_linear("
                            f"(implied_volatility_put_{t} - implied_volatility_call_{t}) / "
                            f"(implied_volatility_mean_{t} + 0.001) * sqrt({t} / 252.0), {d}"
                            f")) - 0.5) > 0.25, "
                            f"group_neutralize(signed_power(rank(-ts_decay_linear("
                            f"(implied_volatility_put_{t} - implied_volatility_call_{t}) / "
                            f"(implied_volatility_mean_{t} + 0.001) * sqrt({t} / 252.0), {d}"
                            f")), 0.5), {g.lower()}), "
                            f"-1), -1)"
                        ),
                        "hypothesis": (
                            f"XZZ2010 annualized smirk: tenor-normalized slope for cross-horizon comparison. {t}d, {u}."
                        ),
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "options",
                        "source_kb": SOURCE_KB,
                    })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 4: Smirk Change Momentum (delta_smirk over 5d and 10d windows)
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for t in [30, 60]:
                for lookback in [5, 10]:
                    catalog.append({
                        "pillar": "XZZ_SMIRK_MOMENTUM",
                        "archetype": f"XZZ_SmirkChg_{lookback}d_t{t}_{u}_{g}",
                        "expression": (
                            f"trade_when(volume > adv20 * 0.90, "
                            f"trade_when(rank(ts_delta("
                            f"(implied_volatility_put_{t} - implied_volatility_call_{t}) / (implied_volatility_mean_{t} + 0.001), {lookback}"
                            f")) < 0.2, "
                            f"group_neutralize(rank(-ts_delta("
                            f"(implied_volatility_put_{t} - implied_volatility_call_{t}) / (implied_volatility_mean_{t} + 0.001), {lookback}"
                            f")), {g.lower()}), "
                            f"-1), -1)"
                        ),
                        "hypothesis": (
                            f"XZZ2010 smirk momentum: stocks where smirk is STEEPENING over {lookback}d "
                            f"(put buying intensifying) — front-run informed flow. t={t}d, {u}."
                        ),
                        "universe": u,
                        "neutralization": g,
                        "decay": 14,
                        "category": "options",
                        "source_kb": SOURCE_KB,
                    })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 5: Term Structure of Smirk (30d smirk - 90d smirk)
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [10, 14]:
                catalog.append({
                    "pillar": "XZZ_SMIRK_TERM_STRUCTURE",
                    "archetype": f"XZZ_SmirkTermStr_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.90, "
                        f"trade_when(abs(rank(ts_decay_linear("
                        f"((implied_volatility_put_30 - implied_volatility_call_30) / (implied_volatility_mean_30 + 0.001)) - "
                        f"((implied_volatility_put_90 - implied_volatility_call_90) / (implied_volatility_mean_90 + 0.001)), {d}"
                        f")) - 0.5) > 0.25, "
                        f"group_neutralize(signed_power(rank(-ts_decay_linear("
                        f"((implied_volatility_put_30 - implied_volatility_call_30) / (implied_volatility_mean_30 + 0.001)) - "
                        f"((implied_volatility_put_90 - implied_volatility_call_90) / (implied_volatility_mean_90 + 0.001)), {d}"
                        f")), 0.6), {g.lower()}), "
                        f"-1), -1)"
                    ),
                    "hypothesis": (
                        f"XZZ2010 term structure: short-dated smirk MUCH steeper than long-dated "
                        f"signals imminent catalyst (not long-term uncertainty). {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "options",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 6: SKEW x Low Turnover (Paper Eq.3 Interaction, Section V.B p.23)
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for t in [30, 60]:
                for d in [10, 14]:
                    catalog.append({
                        "pillar": "XZZ_SMIRK_LOW_TURNOVER",
                        "archetype": f"XZZ_SmirkLowTurn_t{t}_d{d}_{u}_{g}",
                        "expression": (
                            f"trade_when(volume > adv20 * 0.70, "
                            f"trade_when(rank(adv20 / (market_cap + 0.001)) < 0.35, "
                            f"group_neutralize(signed_power(rank(-ts_decay_linear("
                            f"implied_volatility_put_{t} - implied_volatility_call_{t}, {d}"
                            f")), 0.5), {g.lower()}), -1), -1)"
                        ),
                        "hypothesis": (
                            f"XZZ2010 Eq(3) Section V.B: smirk strongest in low-turnover stocks. "
                            f"Illiquid stocks = informed traders prefer options = cleaner smirk signal. "
                            f"t={t}d, {u}."
                        ),
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "options",
                        "source_kb": SOURCE_KB,
                    })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 7: SKEW x Earnings Gate (Section IV, Table 5, p.19-20)
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for t in [30, 60]:
                for d in [10, 14, 20]:
                    catalog.append({
                        "pillar": "XZZ_SMIRK_EARNINGS_GATE",
                        "archetype": f"XZZ_SmirkEarningsGate_t{t}_d{d}_{u}_{g}",
                        "expression": (
                            f"trade_when(volume > adv20 * 0.80, "
                            f"trade_when(rank(ts_decay_linear("
                            f"implied_volatility_put_{t} - implied_volatility_call_{t}, {d}"
                            f")) > 0.65, "
                            f"group_neutralize(signed_power(rank(-ts_decay_linear("
                            f"implied_volatility_put_{t} - implied_volatility_call_{t}, {d}"
                            f")), 0.5) * rank(-ts_decay_linear(earnings_surprise, {d})), "
                            f"{g.lower()}), -1), -1)"
                        ),
                        "hypothesis": (
                            f"XZZ2010 Table5: smirk x negative_SUE = double-confirmed bad earnings. "
                            f"Paper coeff SKEW->SUE: -0.033 to -0.045. t={t}d, {u}."
                        ),
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "options",
                        "source_kb": SOURCE_KB,
                    })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 8: SKEW x High Option OI (Footnote 8 Double-Sort, p.15)
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for t in [30, 60]:
                for d in [10, 14]:
                    catalog.append({
                        "pillar": "XZZ_SMIRK_HIGH_OI",
                        "archetype": f"XZZ_SmirkHighOI_t{t}_d{d}_{u}_{g}",
                        "expression": (
                            f"trade_when(volume > adv20 * 0.90, "
                            f"trade_when(rank(ts_decay_linear(pcr_oi_{t}, {d})) > 0.40, "
                            f"group_neutralize(signed_power(rank(-ts_decay_linear("
                            f"implied_volatility_put_{t} - implied_volatility_call_{t}, {d}"
                            f")), 0.5), {g.lower()}), -1), -1)"
                        ),
                        "hypothesis": (
                            f"XZZ2010 Fn8: double-sort confirms smirk stronger with high option OI. "
                            f"Active options = cleaner informed flow. t={t}d, {u}."
                        ),
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "options",
                        "source_kb": SOURCE_KB,
                    })

    return catalog
