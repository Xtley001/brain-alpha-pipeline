"""
Options Volatility Surface & Derivatives Strategy Generator.
Derived from: Xing, Zhang, Zhao (2010), Pan & Poteshman (2006), Carr & Wu (2009).
"""
from typing import Any, Dict, List

KB_XZZ = "docs/kb/options/xing_zhang_zhao_2010_smirk.md"
KB_PP = "docs/kb/options/pan_poteshman_2006_pcr_informed.md"
KB_CW = "docs/kb/options/carr_wu_2009_vrp.md"


def generate_options_vault_candidates() -> List[Dict[str, Any]]:
    """Generates 100+ highly diversified options surface and convexity candidates."""
    catalog: List[Dict[str, Any]] = []

    universes = ["TOPSP500", "TOP500", "TOP1000", "TOP200"]
    neut_groups = ["SUBINDUSTRY", "SECTOR"]
    tenors = [60, 90, 120, 150, 180, 270, 360]
    decays = [10, 14, 18]

    # 1. Tail-Power Volatility Smirk (Xing-Zhang-Zhao 2010)
    for u in universes:
        for g in neut_groups:
            for t in tenors:
                for d in decays:
                    catalog.append({
                        "pillar": "OPT_SMIRK_TAIL",
                        "archetype": f"Opt_Smirk_Tail_t{t}_d{d}_{u}_{g}",
                        "expression": (
                            f"trade_when(volume > adv20 * 0.90, "
                            f"trade_when(abs(rank(ts_decay_linear((implied_volatility_put_{t} - implied_volatility_call_{t}) / (implied_volatility_mean_{t} + 0.001) * sqrt({t}/252.0), {d})) - 0.5) > 0.25, "
                            f"group_neutralize(signed_power(rank(- ts_decay_linear(ts_decay_linear((implied_volatility_put_{t} - implied_volatility_call_{t}) / (implied_volatility_mean_{t} + 0.001) * sqrt({t}/252.0), {d}), 5)), 0.5), {g.lower()}), "
                            f"-1), -1)"
                        ),
                        "hypothesis": f"XZZ2010 normalized {t}d smirk with RL tail filter ({u}).",
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "options",
                        "source_kb": KB_XZZ,
                    })

    # 2. Call Breakeven Convexity Expansion (Carr & Wu 2009 / Sinclair 2014)
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in neut_groups:
            for t in [60, 90, 120, 180]:
                for d in [10, 14, 18]:
                    catalog.append({
                        "pillar": "OPT_BREAKEVEN_CONVEX",
                        "archetype": f"Opt_CallBreakeven_t{t}_d{d}_{u}_{g}",
                        "expression": (
                            f"trade_when(volume > adv20 * 0.90, "
                            f"trade_when(abs(rank(ts_decay_linear((call_breakeven_{t} - forward_price_{t}) / (close + 0.001), {d})) - 0.5) > 0.25, "
                            f"group_neutralize(signed_power(rank(ts_decay_linear(ts_decay_linear((call_breakeven_{t} - forward_price_{t}) / (close + 0.001), {d}), 4)), 0.6), {g.lower()}), "
                            f"-1), -1)"
                        ),
                        "hypothesis": f"Carr-Wu2009 call breakeven convexity premium ({t}d) on {u}.",
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "options",
                        "source_kb": KB_CW,
                    })

    # 3. Put-Call Ratio Surge (Pan & Poteshman 2006)
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in neut_groups:
            for t in [30, 60, 90, 180]:
                for d in [8, 12, 16]:
                    catalog.append({
                        "pillar": "OPT_PCR_SURGE",
                        "archetype": f"Opt_PCR_Surge_t{t}_d{d}_{u}_{g}",
                        "expression": (
                            f"trade_when(volume > adv20 * 0.85, "
                            f"trade_when(abs(rank(ts_decay_linear(pcr_vol_{t} / (pcr_oi_{t} + 0.001), {d})) - 0.5) > 0.25, "
                            f"group_neutralize(rank(- ts_decay_linear(pcr_vol_{t} / (pcr_oi_{t} + 0.001), {d})), {g.lower()}), "
                            f"-1), -1)"
                        ),
                        "hypothesis": f"Pan-Poteshman2006 PCR volume-to-OI acceleration ({t}d) on {u}.",
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "options",
                        "source_kb": KB_PP,
                    })

    return catalog
