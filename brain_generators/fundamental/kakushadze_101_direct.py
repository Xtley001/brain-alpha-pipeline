"""
Kakushadze (2016) — 101 Formulaic Alphas (WorldQuant)
Tulchinsky et al. — Finding Alphas (WorldQuant Book)
Grinold & Kahn — Active Portfolio Management
Lopez de Prado — Advances in Financial Machine Learning

Papers: These are FRAMEWORK papers — they define the operator vocabulary,
construction rules, and evaluation criteria for BRAIN alphas.

This generator extracts the highest-yield DIRECT EXPRESSIONS from Kakushadze's 101
formulaic alphas and maps them to BRAIN operators, plus key constructions from the
WorldQuant book (Tulchinsky) around neutralization and dataset usage.
"""
from typing import Any, Dict, List

SOURCE_KB = "docs/kb/frameworks/kakushadze_101_alphas.md"


def generate_kakushadze_framework_candidates() -> List[Dict[str, Any]]:
    """
    Kakushadze 101 Formulaic Alphas + Tulchinsky/Grinold-Kahn framework signals.
    Direct operator-level translations to BRAIN with source_kb links.
    """
    catalog: List[Dict[str, Any]] = []

    universes   = ["TOPSP500", "TOP500", "TOP1000"]
    neut_groups = ["SUBINDUSTRY", "SECTOR", "MARKET"]
    decays      = [5, 10, 14]

    # ─────────────────────────────────────────────────────────────────────────
    # KAKUSHADZE ALPHA #1: Volume-Price Correlation Reversal
    # (-1 * correlation(rank(ts_delta(log(volume), 2)), rank(((close - low) - (high - close)) / (high - low + 0.0001) * volume), 6))
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for d in decays:
                catalog.append({
                    "pillar": "K101_ALPHA1_VOL_PRICE_CORR",
                    "archetype": f"K101_A1_d{d}_{u}_{g}",
                    "expression": (
                        f"group_neutralize("
                        f"-1 * rank(correlation("
                        f"rank(ts_delta(log(volume + 0.001), 2)), "
                        f"rank(((close - low) - (high - close)) / (high - low + 0.0001) * volume), 6"
                        f")), {g.lower()})"
                    ),
                    "hypothesis": (
                        f"Kakushadze101 Alpha#1: inverse of 6-day correlation between ranked volume delta "
                        f"and ranked money-flow-adjusted volume. Captures microstructure reversal. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # KAKUSHADZE ALPHA #6: Open-Volume Anti-Correlation
    # (-1 * correlation(open, volume, 10))
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            catalog.append({
                "pillar": "K101_ALPHA6_OPEN_VOL",
                "archetype": f"K101_A6_{u}_{g}",
                "expression": (
                    f"group_neutralize(-1 * rank(correlation(open, volume, 10)), {g.lower()})"
                ),
                "hypothesis": (
                    f"Kakushadze101 Alpha#6: inverse 10-day correlation of open with volume. "
                    f"Captures opening price / volume activity divergence. {u}."
                ),
                "universe": u,
                "neutralization": g,
                "decay": 5,
                "category": "fundamental",
                "source_kb": SOURCE_KB,
            })

    # ─────────────────────────────────────────────────────────────────────────
    # KAKUSHADZE ALPHA #22: High-Volume Volatility Signal
    # (-1 * ts_delta(correlation(high, volume, 5), 5)) * rank(ts_std_dev(close, 20))
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            catalog.append({
                "pillar": "K101_ALPHA22_HIGH_VOL",
                "archetype": f"K101_A22_{u}_{g}",
                "expression": (
                    f"group_neutralize("
                    f"-1 * ts_delta(correlation(high, volume, 5), 5) * rank(ts_std_dev(close, 20)), "
                    f"{g.lower()})"
                ),
                "hypothesis": (
                    f"Kakushadze101 Alpha#22: rate-of-change of high-price/volume 5d correlation "
                    f"× 20d close volatility. Captures breakout exhaustion pattern. {u}."
                ),
                "universe": u,
                "neutralization": g,
                "decay": 5,
                "category": "fundamental",
                "source_kb": SOURCE_KB,
            })

    # ─────────────────────────────────────────────────────────────────────────
    # KAKUSHADZE ALPHA #101: Daily Range Signal
    # (close - open) / (high - low + 0.001)
    # Normalized daily close vs open; position within daily range.
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for d in decays:
                catalog.append({
                    "pillar": "K101_ALPHA101_RANGE",
                    "archetype": f"K101_A101_d{d}_{u}_{g}",
                    "expression": (
                        f"group_neutralize(signed_power(rank(ts_decay_linear("
                        f"(close - open) / (high - low + 0.001), {d}"
                        f")), 0.5), {g.lower()})"
                    ),
                    "hypothesis": (
                        f"Kakushadze101 Alpha#101: (close-open)/(high-low) = position within daily range. "
                        f"Consistent upper-range closing = momentum; lower-range = exhaustion. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # KAKUSHADZE ALPHA #30: Sign Reversal Momentum
    # Based on consecutive-day sign patterns of returns and overnight gaps.
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            catalog.append({
                "pillar": "K101_ALPHA30_SIGN",
                "archetype": f"K101_A30_{u}_{g}",
                "expression": (
                    f"trade_when(volume > adv20 * 0.60, "
                    f"group_neutralize("
                    f"rank(1.0 - sign(sign(close - ts_delay(close, 1)) + sign(ts_delay(close, 1) - ts_delay(close, 2)))) * "
                    f"(1.0 - rank(volume / adv20)), {g.lower()}), -1)"
                ),
                "hypothesis": (
                    f"Kakushadze101 Alpha#30: triple-day sign pattern × low volume weight. "
                    f"Stocks with consistent down-sign + below-ADV volume → low conviction sell = reversal. {u}."
                ),
                "universe": u,
                "neutralization": g,
                "decay": 5,
                "category": "fundamental",
                "source_kb": SOURCE_KB,
            })

    # ─────────────────────────────────────────────────────────────────────────
    # TULCHINSKY (WorldQuant Finding Alphas): Momentum Universe Neutralization
    # Key insight: neutralizing by subindustry dramatically improves IC stability.
    # Also: cross-sectional momentum within universe (not raw price momentum).
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500"]:
        for window in [21, 63, 126]:
            for d in [10, 14]:
                catalog.append({
                    "pillar": "TULCHINSKY_CS_MOMENTUM",
                    "archetype": f"Tulch_CSMom_{window}d_d{d}_{u}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.70, "
                        f"group_neutralize(signed_power(rank(ts_sum(returns, {window}) - ts_sum(returns, 5)), 0.5), subindustry), "
                        f"-1)"
                    ),
                    "hypothesis": (
                        f"Tulchinsky (Finding Alphas): cross-sectional momentum over {window}d "
                        f"with 5d return reversal excluded. Industry-neutralized with rank(). {u}."
                    ),
                    "universe": u,
                    "neutralization": "SUBINDUSTRY",
                    "decay": d,
                    "category": "fundamental",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # GRINOLD & KAHN: IC-Based Signal Decay (Active Portfolio Management)
    # G&K: optimal alpha decay follows the IC decay curve of the raw signal.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500"]:
        for gk_decay in [30, 45, 60, 90]:
            catalog.append({
                "pillar": "GK_OPTIMAL_DECAY",
                "archetype": f"GK_EarnSurp_gkd{gk_decay}_{u}",
                "expression": (
                    f"trade_when(volume > adv20 * 0.80, "
                    f"group_neutralize(signed_power(rank(ts_decay_linear(earnings_surprise, {gk_decay})), 0.5), subindustry), "
                    f"-1)"
                ),
                "hypothesis": (
                    f"Grinold-Kahn: IC-optimal decay of {gk_decay} days for quarterly earnings surprise signal. "
                    f"G&K Fig 7.1: IC for fundamental signals decays to 50% at ~60d. {u}."
                ),
                "universe": u,
                "neutralization": "SUBINDUSTRY",
                "decay": gk_decay,
                "category": "analyst",
                "source_kb": SOURCE_KB,
            })

    return catalog
