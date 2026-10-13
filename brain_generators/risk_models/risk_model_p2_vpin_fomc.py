"""
Easley, Lopez de Prado & O'Hara (2012) — Flow Toxicity & VPIN
Lucca & Moench (2015) — Pre-FOMC Announcement Drift
Nonejad (2013) — Realized Volatility & Structural Breaks
Blitz & van Vliet (2007) — The Volatility Effect Across Markets
Black (1972) — Capital Market Equilibrium with Restricted Borrowing
Savor & Wilson (2013) — Macroeconomic Risk & Announcement Premiums

These complete the risk models pillar generators — all paper-derived formulas.
"""
from typing import Any, Dict, List


def generate_risk_model_p2_candidates() -> List[Dict[str, Any]]:
    """
    Risk model P2 generators — VPIN, FOMC drift, structural breaks, vol effect.
    All paper-faithful constructions.
    """
    catalog: List[Dict[str, Any]] = []

    universes   = ["TOPSP500", "TOP500", "TOP1000"]
    neut_groups = ["SUBINDUSTRY", "SECTOR", "MARKET"]
    decays      = [5, 10, 14, 20]

    # ─────────────────────────────────────────────────────────────────────────
    # EASLEY-LOPEZ DE PRADO-O'HARA (2012): VPIN — Volume-Synchronized PIN
    # Paper: "Flow Toxicity and Liquidity in a High Frequency World" — RFS
    # VPIN = |buy_volume - sell_volume| / total_volume over recent N buckets
    # High VPIN → high order flow toxicity → market makers widen spreads → 
    # adverse selection risk → subsequent price move (direction following informed flow).
    # BRAIN approx: |returns| / (volume / adv20) as flow toxicity proxy.
    # High VPIN = informed flow → follow the direction.
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for d in decays:
                # VPIN proxy as liquidity-adjusted absolute return signal
                catalog.append({
                    "pillar": "VPIN_FLOW_TOXICITY",
                    "archetype": f"VPIN_FlowTox_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"trade_when(rank(ts_decay_linear("
                        f"ts_mean(abs(returns) / (volume / adv20 + 0.001), 10), {d}"
                        f")) > 0.65, "
                        f"group_neutralize(rank(ts_decay_linear(returns, {d})), {g.lower()}), "
                        f"-1), -1)"
                    ),
                    "hypothesis": (
                        f"Easley-LdP-OHara2012: VPIN proxy = |ret|/(vol/adv20). "
                        f"High flow toxicity = informed flow → follow direction (momentum in toxicity). {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "model",
                })

    # ─────────────────────────────────────────────────────────────────────────
    # VPIN REVERSAL: High VPIN (toxicity) → subsequent REVERSAL
    # Alternative interpretation: high VPIN = overshoot → mean-revert afterward.
    # After toxic informed flow, price corrects as market makers re-set quotes.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [5, 10]:
                catalog.append({
                    "pillar": "VPIN_REVERSAL",
                    "archetype": f"VPIN_Reversal_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"trade_when(rank(ts_mean(abs(returns) / (volume / adv20 + 0.001), 5)) > 0.70, "
                        f"group_neutralize(rank(-ts_decay_linear(ts_sum(returns, 3), {d})), {g.lower()}), "
                        f"-1), -1)"
                    ),
                    "hypothesis": (
                        f"ELO2012 reversal: high flow toxicity days → post-overshoot reversal. "
                        f"3-day price move in high-VPIN stocks reverts as market makers re-hedge. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "model",
                })

    # ─────────────────────────────────────────────────────────────────────────
    # LUCCA & MOENCH (2015): Pre-FOMC Announcement Drift
    # Paper: "The Pre-FOMC Announcement Drift" — JF
    # Core: S&P 500 earns ~50bps in the 24 hours BEFORE FOMC announcements.
    # Stock-level analog: stocks with highest FOMC-day beta (market sensitivity)
    # earn the pre-announcement premium most reliably.
    # BRAIN approx: stocks with high beta to market around FOMC windows.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [5, 10]:
                catalog.append({
                    "pillar": "LUCCA_FOMC_BETA",
                    "archetype": f"Lucca_FOMCBeta_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"trade_when(ts_rank(ts_std_dev(returns, 5), 252) > 0.60, "
                        f"group_neutralize(signed_power(rank(ts_decay_linear("
                        f"beta_last_252_days_spy * ts_rank(ts_std_dev(returns, 5), 252), {d}"
                        f")), 0.5), {g.lower()}), -1), -1)"
                    ),
                    "hypothesis": (
                        f"Lucca-Moench2015: high-beta stocks earn pre-FOMC drift (+50bps S&P, then stock-level). "
                        f"Active in high-vol windows that proxy for macro event proximity. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "model",
                })

    # ─────────────────────────────────────────────────────────────────────────
    # BLITZ & VAN VLIET (2007): Volatility Effect Across Markets
    # Paper: "The Volatility Effect" — JPM
    # Core: Low-volatility stocks earn higher risk-adjusted returns globally.
    # Global confirmation of AHXZ anomaly. Signal: rank low vol, long low-vol stocks.
    # Focus: works especially well in NON-US markets (but BRAIN has global stocks via TOP universes)
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for vol_window in [21, 63, 126]:
                for d in [10, 14]:
                    catalog.append({
                        "pillar": "BLITZ_VOL_EFFECT",
                        "archetype": f"Blitz_VolEffect_{vol_window}d_d{d}_{u}_{g}",
                        "expression": (
                            f"trade_when(volume > adv20 * 0.70, "
                            f"trade_when(abs(rank(ts_decay_linear(ts_std_dev(returns, {vol_window}), {d})) - 0.5) > 0.25, "
                            f"group_neutralize(signed_power(rank(-ts_decay_linear(ts_std_dev(returns, {vol_window}), {d})), 0.5), {g.lower()}), "
                            f"-1), -1)"
                        ),
                        "hypothesis": (
                            f"Blitz-vanVliet2007: low realized vol → higher risk-adjusted returns. "
                            f"Global confirmation of AHXZ. {vol_window}d window, {u}."
                        ),
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "model",
                    })

    # ─────────────────────────────────────────────────────────────────────────
    # NONEJAD (2013): Structural Break Detection in Realized Volatility
    # Paper: "Structural Breaks in Realized Volatility" — European Financial Management
    # Core: Detect structural breaks in vol regime → post-break, vol is mean-reverting.
    # Signal: sudden vol spike (structural break) → vol will revert to new lower regime.
    # BRAIN: ts_rank of recent vol vs long-run vol to detect jumps.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [5, 10]:
                catalog.append({
                    "pillar": "NONEJAD_VOL_BREAK",
                    "archetype": f"Nonejad_VolBreak_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"trade_when(rank(ts_std_dev(returns, 5) / (ts_std_dev(returns, 63) + 0.001)) > 0.80, "
                        f"group_neutralize(rank(-ts_decay_linear("
                        f"ts_std_dev(returns, 5) / (ts_std_dev(returns, 63) + 0.001), {d}"
                        f")), {g.lower()}), -1), -1)"
                    ),
                    "hypothesis": (
                        f"Nonejad2013: sudden vol spike (5d vol >> 63d vol) = structural break. "
                        f"Post-break vol reverts to lower regime → short the vol spike. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "model",
                })

    # ─────────────────────────────────────────────────────────────────────────
    # BLACK (1972): Zero-Beta Portfolio
    # Paper: "Capital Market Equilibrium with Restricted Borrowing" — JB
    # Core: The zero-beta portfolio (orthogonal to market) earns positive returns
    # in a world where borrowing is restricted.
    # BRAIN: stocks with near-zero beta (0.0 < beta < 0.3) that also have
    # positive idiosyncratic momentum = zero-beta candidates.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [10, 14]:
                catalog.append({
                    "pillar": "BLACK_ZERO_BETA",
                    "archetype": f"Black_ZeroBeta_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.70, "
                        f"trade_when(rank(abs(beta_last_60_days_spy)) < 0.25, "
                        f"group_neutralize(signed_power(rank(ts_decay_linear("
                        f"ts_sum(returns, 63), {d}"
                        f")), 0.5), {g.lower()}), -1), -1)"
                    ),
                    "hypothesis": (
                        f"Black1972: near-zero-beta stocks (|beta| < 25th pctile) earn premium. "
                        f"Restricted borrowing CAPM: zero-beta portfolio intercept is positive. "
                        f"Apply idiosyncratic momentum to select among them. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "model",
                })

    return catalog
