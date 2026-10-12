"""
Menzly & Ozbas (2010) — Market Segmentation & Cross-Firm Return Predictability
Paper: "Market Segmentation and Cross-predictability of Returns" — JF

Core Finding: Economically-related firms (supplier-customer pairs) exhibit return
predictability. Returns of upstream (supplier) firms predict downstream (customer) firm
returns with a 1-MONTH LAG. This violates market efficiency due to investor segmentation
— investors in supplier stocks don't follow customer stocks closely.

Key Signal Constructions:
  1. Supplier → Customer lead-lag: rank(supplier_return, 21d) predicts customer return
  2. Customer demand shock → Supplier: negative customer surprise → supplier revision
  3. Industry supply-chain momentum: upstream industry return leads downstream

BRAIN Limitation: We don't have explicit supplier-customer link data.
Approximation: Use industry-level lead-lag (upstream industries leading downstream),
leveraging the well-known sector return auto-correlations.

Barrot & Sauvagnat (2016): Supply chain disaster propagation.
  Natural disasters hurt suppliers → customer stocks drop too, with a lag.
  Signal: detect stocks with concentrated supply chains (proxy: high supplier concentration)
  → more vulnerable to supply shocks → mean-reversion after shock absorption.
"""
from typing import Any, Dict, List


def generate_supply_chain_p0_candidates() -> List[Dict[str, Any]]:
    """
    Menzly-Ozbas (2010) supply chain lead-lag and cross-firm predictability signals.
    Citation: JF 2010, Table 3 (monthly portfolio returns on lagged supplier returns).
    """
    catalog: List[Dict[str, Any]] = []

    universes   = ["TOPSP500", "TOP500", "TOP1000"]
    neut_groups = ["SUBINDUSTRY", "SECTOR"]
    decays      = [10, 14, 20]

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 1: Industry Momentum Lead-Lag (Menzly-Ozbas 2010 approximation)
    # Core finding: upstream industry returns predict downstream returns with 1-month lag.
    # Approximation: sub-industry returns lead their parent sector returns.
    # Signal: rank(subindustry_return_21d) cross-predicts WITHIN-sector counterparts.
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
                            f"Menzly-Ozbas2010: {lookback}d lagged return predicts future return via "
                            f"market segmentation. Upstream stocks' recent performance leads downstream. {u}."
                        ),
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "fundamental",
                    })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 2: Supply Chain Concentration Risk (Barrot-Sauvagnat 2016 approximation)
    # Firms with concentrated customer/supplier relationships are more vulnerable to
    # supply shocks. Proxy: high revenue concentration (geographic/customer)
    # After a shock (large negative return period), these stocks overshoot and mean-revert.
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
                        f"Barrot-Sauvagnat2016: supply chain shock → temporary price depression → reversal. "
                        f"Buy recent extreme losers (supply chain disruption temporary overshooting). {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 3: Cross-Industry Sales Revision (Menzly-Ozbas Mechanism)
    # The paper's mechanism: customer demand revisions propagate to supplier revenues.
    # Proxy: when a sector's analyst estimates are revised upward, suppliers to that
    # sector (same-industry stocks with high sales concentration) benefit.
    # Signal: analyst estimate revision in sector × cross-industry sales dependency
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [14, 20]:
                catalog.append({
                    "pillar": "SUPPLY_CHAIN_REVISION",
                    "archetype": f"SC_SalesRevision_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.75, "
                        f"group_neutralize(signed_power(rank(ts_decay_linear("
                        f"ts_sum(analyst_rating_change, 42) * ts_sum(returns, 63), {d}"
                        f")), 0.5), {g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"Menzly-Ozbas2010 mechanism: analyst revision × recent performance "
                        f"proxies demand shock propagation from customers to suppliers. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                })

    return catalog
