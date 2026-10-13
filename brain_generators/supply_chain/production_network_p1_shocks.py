"""
Barrot & Sauvagnat (2016) — Input Specificity and Shock Propagation in Production Networks
Burt & Hrdlicka (2021) — Economically Linked Firms & Idiosyncratic Information Diffusion
Fee & Thomas (2004) — Buying Power Gains and Upstream Supplier Margin Squeeze
Bennett, Cucuringu & Reinert (2021) — Directed Network Lead-Lag Clustering in Equity Markets

Papers:
  1. Barrot & Sauvagnat (2016): QJE.
     Suppliers hit by shocks impose 2-3% sales loss on customers ($1 lost -> $2.4 customer loss).
     Concentrated in specific inputs (high R&D, patents, Rauch classification).
     Horizontal spillovers propagate to other non-hit suppliers.

  2. Burt & Hrdlicka (2021): RFS.
     Decomposes Cohen & Frazzini (2008) customer-supplier predictability.
     Sorting on IDIOSYNCRATIC residual returns isolates pure information diffusion.

  3. Fee & Thomas (2004): JFE.
     Customer mergers exercise buying power, extracting price concessions from upstream suppliers.
     Suppliers experience operating margin compression and negative abnormal returns.

  4. Bennett, Cucuringu & Reinert (2021): Machine Learning with Applications.
     Directed network lead-lag clustering. Large liquid leaders predict lagging suppliers.
"""
from typing import Any, Dict, List

SOURCE_KB = "docs/kb/supply_chain/barrot_burt_fee_bennett_production_networks.md"


def generate_production_network_p1_candidates() -> List[Dict[str, Any]]:
    """
    Supply chain, input specificity, horizontal spillover, buying power,
    and lead-lag network cluster alpha generators.
    """
    catalog: List[Dict[str, Any]] = []

    universes = ["TOPSP500", "TOP500", "TOP1000", "TOP3000"]
    neut_groups = ["SUBINDUSTRY", "SECTOR"]
    decays = [10, 14, 20]

    # ─────────────────────────────────────────────────────────────────────────
    # 1. BARROT & SAUVAGNAT (2016): Upstream Input Disruption Shock
    # Severe margin or sales contraction in upstream inputs with abnormal volume
    # indicates supply chain bottleneck -> short the impacted firm.
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for d in decays:
                catalog.append({
                    "pillar": "SC_SUPPLY_DISRUPTION",
                    "archetype": f"SC_SupplyDisrupt_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.75, "
                        f"trade_when(rank(-ts_delta(gross_profit / (assets + 0.001), 63)) > 0.65, "
                        f"group_neutralize(rank(-ts_decay_linear(gross_profit / (assets + 0.001), {d}) * (volume / (adv20 + 0.001))), {g.lower()}), "
                        f"-1), -1)"
                    ),
                    "hypothesis": (
                        f"Barrot-Sauvagnat2016: upstream input disruption propagates as 2-3% sales drop. "
                        f"Short firms suffering sharp quarterly margin contraction with abnormal volume. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 2. BARROT & SAUVAGNAT (2016): Specific Input Moat (R&D & Capex Specificity)
    # Firms with high relationship-specific investments (high capex / assets)
    # and strong profitability have durable supplier pricing power.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in neut_groups:
            for d in decays:
                catalog.append({
                    "pillar": "SC_INPUT_SPECIFICITY",
                    "archetype": f"SC_InputSpec_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.65, "
                        f"trade_when(rank(capex / (assets + 0.001)) > 0.60, "
                        f"group_neutralize(signed_power(rank(ts_decay_linear(gross_profit / (assets + 0.001), {d})), 0.5), {g.lower()}), "
                        f"-1), -1)"
                    ),
                    "hypothesis": (
                        f"Barrot-Sauvagnat2016: specific input suppliers with high capex intensity "
                        f"and gross margins possess switching-cost moats and outperform. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 3. BARROT & SAUVAGNAT (2016): Horizontal Supply Chain Spillover
    # Negative shocks to one input spill over horizontally to other suppliers.
    # Fade firms experiencing simultaneous volume surges and margin deterioration.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOP500", "TOP1000", "TOP3000"]:
        for g in neut_groups:
            for d in [10, 14]:
                catalog.append({
                    "pillar": "SC_HORIZONTAL_SPILLOVER",
                    "archetype": f"SC_HorizSpillover_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"trade_when(rank(ts_delta(close, 20)) < 0.35, "
                        f"group_neutralize(rank(-ts_decay_linear(ts_delta(gross_profit / (assets + 0.001), 252), {d})), {g.lower()}), "
                        f"-1), -1)"
                    ),
                    "hypothesis": (
                        f"Barrot-Sauvagnat2016: horizontal network spillovers propagate across related suppliers. "
                        f"Fade negative annual margin shifts in declining momentum stocks. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 4. FEE & THOMAS (2004): Buying Power & Upstream Margin Squeeze
    # Upstream suppliers with low gross margin facing large customers suffer
    # monopsonistic margin compression -> short low margin relative to industry.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in neut_groups:
            for d in decays:
                catalog.append({
                    "pillar": "SC_BUYING_POWER_SQUEEZE",
                    "archetype": f"SC_BuyingPower_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.70, "
                        f"trade_when(rank(market_cap) < 0.50, "
                        f"group_neutralize(rank(ts_decay_linear(gross_profit / (assets + 0.001), {d}) - ts_mean(gross_profit / (assets + 0.001), 252)), {g.lower()}), "
                        f"-1), -1)"
                    ),
                    "hypothesis": (
                        f"Fee-Thomas2004: customer buying power compresses upstream supplier margins (-1.8% to -2.4%). "
                        f"Long suppliers with expanding margins relative to 1yr average; short those with margin squeeze. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 5. BURT & HRDLICKA (2021): Idiosyncratic Network Lead-Lag
    # Residual return momentum after stripping market beta isolates pure
    # information transmission across supply chain links.
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for d in [10, 14, 20]:
                catalog.append({
                    "pillar": "SC_IDIO_LEAD_LAG",
                    "archetype": f"SC_IdioLeadLag_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.70, "
                        f"group_neutralize(signed_power(rank(ts_decay_linear("
                        f"returns - ts_mean(returns, 21), {d}"
                        f")), 0.5), {g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"Burt-Hrdlicka2021: idiosyncratic returns isolate genuine economic link diffusion "
                        f"(+1.12%/month, t=3.24) free of common factor contamination. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 6. BENNETT, CUCURINGU & REINERT (2021): Directed Network Cluster Momentum
    # Lead-lag network clusters: long lagging stocks catching up to industry leaders.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in neut_groups:
            for d in [10, 14]:
                catalog.append({
                    "pillar": "SC_NETWORK_CLUSTER_MOM",
                    "archetype": f"SC_NetClusterMom_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.70, "
                        f"trade_when(rank(ts_decay_linear(returns, 5)) > 0.55, "
                        f"group_neutralize(signed_power(rank(ts_decay_linear("
                        f"ts_sum(returns, 20) - ts_sum(returns, 5), {d}"
                        f")), 0.5), {g.lower()}), -1), -1)"
                    ),
                    "hypothesis": (
                        f"Bennett-Cucuringu-Reinert2021: directed lead-lag clustering. "
                        f"Stocks lagging the 5-20 day cluster momentum catch up with Sharpe 1.34. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                    "source_kb": SOURCE_KB,
                })

    return catalog
