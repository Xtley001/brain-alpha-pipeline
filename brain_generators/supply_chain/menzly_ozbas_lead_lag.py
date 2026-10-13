"""
Menzly & Ozbas (2010) — Market Segmentation & Cross-Firm Return Predictability
Paper: "Market Segmentation and Cross-predictability of Returns" — JF
Barrot & Sauvagnat (2016) — Input Specificity and Shock Propagation — QJE

Core Findings & Empirical Benchmarks:
  1. Menzly & Ozbas (2010):
     - Economically linked industries cross-predict returns with a 1-month lag (21d to 42d).
     - Table V: Self-financing trading strategy on lagged supplier returns yields +7.3%/yr (Sharpe 0.660).
     - Table V: Customer returns strategy yields +7.0%/yr (Sharpe 0.520). Composite yields +8.7%/yr (Sharpe 0.658).
     - Table VI: Fama-French 4-factor alpha = +0.50% to +0.60%/month (t = 2.61 to 3.42).
     - Table II/III: Cross-predictability is 10x stronger among low analyst coverage / low institutional ownership stocks.
  2. Barrot & Sauvagnat (2016):
     - Supply chain shock propagation creates temporary pricing dislocation and subsequent mean-reversion.
"""
from typing import Any, Dict, List

SOURCE_KB = "docs/kb/supply_chain/menzly_ozbas_2010_lead_lag.md"


def generate_supply_chain_p0_candidates() -> List[Dict[str, Any]]:
    """
    Menzly-Ozbas (2010) supply chain lead-lag and cross-firm predictability signals.
    Citation: JF 2010, Table II, V, VI.
    """
    catalog: List[Dict[str, Any]] = []

    universes   = ["TOPSP500", "TOP500", "TOP1000"]
    neut_groups = ["SUBINDUSTRY", "SECTOR"]
    decays      = [10, 14, 20]

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 1: Industry Momentum Lead-Lag (Menzly-Ozbas 2010 Table V)
    # 21d and 42d lagged returns predict subsequent returns across related segments.
    # Group-neutralized within sector/subindustry to extract cross-sectional lead-lag.
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for d in decays:
                for lookback in [21, 42]:
                    catalog.append({
                        "pillar": "SUPPLY_CHAIN_LEAD_LAG",
                        "archetype": f"SC_LeadLag_lb{lookback}_d{d}_{u}_{g}",
                        "expression": (
                            f"trade_when(volume > adv20 * 0.75, "
                            f"group_neutralize(signed_power(rank(ts_decay_linear("
                            f"ts_delay(ts_sum(returns, {lookback}), 5), {d}"
                            f")), 0.5), {g.lower()}), -1)"
                        ),
                        "hypothesis": (
                            f"Menzly-Ozbas2010 Table V: {lookback}d lagged return predicts future return (+7.3%/yr spread). "
                            f"Cross-industry gradual information diffusion over 1-month horizon. {u}."
                        ),
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "fundamental",
                        "source_kb": SOURCE_KB,
                    })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 2: Low-Coverage / Low-Information Amplification (Table II & III)
    # Cross-predictability is 10x stronger in lower-capitalization / low-coverage firms.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [10, 14]:
                catalog.append({
                    "pillar": "SUPPLY_CHAIN_LOW_COVERAGE",
                    "archetype": f"SC_LowCov_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.75, "
                        f"trade_when(rank(cap) < 0.40, "
                        f"group_neutralize(signed_power(rank(ts_decay_linear("
                        f"ts_delay(ts_sum(returns, 21), 5), {d}"
                        f")), 0.5), {g.lower()}), -1), -1)"
                    ),
                    "hypothesis": (
                        f"Menzly-Ozbas2010 Table II/III: lead-lag slope is 0.380 (t=5.89) in low-information firms vs "
                        f"0.027 in high-coverage firms. Gating on lower market cap isolates the information friction. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 3: Supply Chain Concentration Shock Reversal (Barrot-Sauvagnat 2016)
    # Temporary supply shock overshoot -> mean-reversion over 21 days
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [10, 14]:
                catalog.append({
                    "pillar": "SUPPLY_CHAIN_SHOCK_REVERSAL",
                    "archetype": f"SC_ShockReversal_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.75, "
                        f"trade_when(rank(ts_sum(returns, 21)) < 0.15, "
                        f"group_neutralize(rank(-ts_decay_linear(ts_sum(returns, 21), {d})), {g.lower()}), "
                        f"-1), -1)"
                    ),
                    "hypothesis": (
                        f"Barrot-Sauvagnat2016: supply chain disruption causes temporary overshooting. "
                        f"Buy extreme 21d losers following supply shock absorption. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 4: Fundamental Demand Shock Propagation (Earnings Surprise × Lagged Momentum)
    # Customer earnings revisions propagate to supplier valuation over 42 days
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [14, 20]:
                catalog.append({
                    "pillar": "SUPPLY_CHAIN_REVISION",
                    "archetype": f"SC_EarnSurpLag_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.75, "
                        f"group_neutralize(signed_power(rank(ts_decay_linear("
                        f"earnings_surprise * ts_delay(ts_sum(returns, 21), 5), {d}"
                        f")), 0.5), {g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"Menzly-Ozbas2010 mechanism: earnings surprise interaction with lagged production return "
                        f"captures customer demand shocks propagating into supplier cash flows. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 5: Pure Factor-Neutral Lead-Lag Spread (Table VI, Alpha = +0.60%/mo)
    # Lagged 5-day delayed return minus contemporaneous 5-day return
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [10, 14]:
                catalog.append({
                    "pillar": "SUPPLY_CHAIN_PURE_LEAD_LAG",
                    "archetype": f"SC_PureLeadLag_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.75, "
                        f"group_neutralize("
                        f"rank(ts_decay_linear(ts_delay(returns, 5), {d})) - "
                        f"rank(ts_decay_linear(returns, {d})), "
                        f"{g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"Menzly-Ozbas2010 Table VI: pure lead-lag differential (lagged return - current return). "
                        f"Captures unpriced information spillover net of contemporaneous momentum. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                    "source_kb": SOURCE_KB,
                })

    return catalog
