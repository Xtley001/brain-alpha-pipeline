"""
Convex Near-Miss Mutator & Multi-Armed Bandit Surface Optimizer.
When an alpha candidate scores 1.00 <= Sharpe < 1.25 (e.g. mL6wvmP6 at 1.05 Sharpe or Apex1 at 1.14 Sharpe),
this module systematically explores the local convex parameter surface across 5 axes:
1. Decay Gradient Perturbation (temporal holding shift)
2. Tail Power Concentration (signed_power tail amplification with balanced AST)
3. Large-Cap Universe Restriction (TOPSP500 sub-universe Sharpe stabilizer)
4. Neutralization Tier Swap (SUBINDUSTRY <-> SECTOR)
5. Liquidity & Conviction Gating (trade_when volume hurdles and conviction thresholds)
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

log = logging.getLogger("brain_options.convex_mutator")


def _wrap_neutralize_with_signed_power(expr: str, power: float = 1.5) -> Optional[str]:
    """Wraps the inner expression of group_neutralize(..., group) in signed_power(inner - 0.5, power)."""
    idx = expr.find("group_neutralize(")
    if idx == -1:
        return None
    start = idx + len("group_neutralize(")
    depth = 0
    comma_pos = -1
    for i in range(start, len(expr)):
        char = expr[i]
        if char == "(":
            depth += 1
        elif char == ")":
            if depth == 0:
                break
            depth -= 1
        elif char == "," and depth == 0:
            comma_pos = i
            break
    if comma_pos != -1:
        inner_arg = expr[start:comma_pos].strip()
        rest = expr[comma_pos:]
        wrapped = f"signed_power({inner_arg} - 0.5, {power})"
        return expr[:start] + wrapped + rest
    return None


class ConvexNearMissMutator:
    """Systematic local gradient and parameter optimizer for high-potential near-miss alphas."""

    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def generate_convex_sweeps(
        self,
        expr: str,
        archetype: str,
        hypothesis: str,
        universe: str,
        neutralization: str,
        decay: int,
        sharpe: float,
        fitness: float,
        region: str = "USA",
    ) -> List[Dict[str, Any]]:
        """
        Generates micro-sweeps along the 5 convex parameter axes to push Sharpe >= 1.25.
        """
        mutations: List[Dict[str, Any]] = []

        log.info(
            "[⚡ CONVEX MUTATOR] Optimizing near-miss: %s (Sharpe=%.2f, Fit=%.2f) on %s",
            archetype, sharpe, fitness, universe
        )

        # ── Axis 1: Decay Gradient Shifts (±2, ±5, +8) ──
        decay_shifts = [-4, -2, 3, 6, 9]
        for shift in decay_shifts:
            new_d = max(5, min(35, decay + shift))
            if new_d != decay:
                mutations.append({
                    "expression": expr,
                    "archetype": f"{archetype}_d{new_d}",
                    "hypothesis": f"{hypothesis} [Convex Decay Sweep d={new_d}]",
                    "universe": "TOPSP500" if universe != "TOPSP500" else universe,
                    "neutralization": neutralization,
                    "decay": new_d,
                    "region": region,
                    "mutation_axis": "decay",
                })

        # ── Axis 2: Power Concentration (Tail conviction amplification via balanced AST) ──
        if "signed_power(" not in expr and "group_neutralize(" in expr:
            for p in [1.5, 2.0]:
                p_expr = _wrap_neutralize_with_signed_power(expr, p)
                if p_expr:
                    mutations.append({
                        "expression": p_expr,
                        "archetype": f"{archetype}_Power{p}",
                        "hypothesis": f"{hypothesis} [Convex Tail Power p={p} Concentration]",
                        "universe": "TOPSP500",
                        "neutralization": neutralization,
                        "decay": decay,
                        "region": region,
                        "mutation_axis": "power",
                    })

        # ── Axis 3: Universe Restriction to TOPSP500 ──
        if universe != "TOPSP500":
            mutations.append({
                "expression": expr,
                "archetype": f"{archetype}_TOPSP500",
                "hypothesis": f"{hypothesis} [TOPSP500 Large-Cap Liquidity Shield]",
                "universe": "TOPSP500",
                "neutralization": neutralization,
                "decay": decay,
                "region": region,
                "mutation_axis": "universe",
            })

        # ── Axis 4: Neutralization Tier Swap (SUBINDUSTRY <-> SECTOR) ──
        alt_neut = "SECTOR" if neutralization.upper() == "SUBINDUSTRY" else "SUBINDUSTRY"
        alt_neut_str = alt_neut.lower()
        curr_neut_str = neutralization.lower()
        neut_expr = re.sub(rf",\s*{curr_neut_str}\)", f", {alt_neut_str})", expr)
        if neut_expr != expr:
            mutations.append({
                "expression": neut_expr,
                "archetype": f"{archetype}_{alt_neut}",
                "hypothesis": f"{hypothesis} [Convex Neutralization Swap to {alt_neut}]",
                "universe": "TOPSP500",
                "neutralization": alt_neut,
                "decay": decay,
                "region": region,
                "mutation_axis": "neutralization",
            })

        # ── Axis 5: Liquidity Volume & Conviction Gating (trade_when) ──
        if "trade_when(" not in expr:
            gated_expr = f"trade_when(volume > adv20 * 0.75, {expr}, -1)"
            mutations.append({
                "expression": gated_expr,
                "archetype": f"{archetype}_VolGated",
                "hypothesis": f"{hypothesis} [Liquidity Gated volume > adv20 * 0.75]",
                "universe": "TOPSP500",
                "neutralization": neutralization,
                "decay": decay,
                "region": region,
                "mutation_axis": "liquidity_gate",
            })
        elif "volume > adv20 * 0.75" in expr:
            for hurdle in ["0.90", "1.05", "1.20"]:
                alt_gated = expr.replace("volume > adv20 * 0.75", f"volume > adv20 * {hurdle}")
                mutations.append({
                    "expression": alt_gated,
                    "archetype": f"{archetype}_VolGated{hurdle.replace('.', '')}",
                    "hypothesis": f"{hypothesis} [Liquidity Gated volume > adv20 * {hurdle}]",
                    "universe": "TOPSP500",
                    "neutralization": neutralization,
                    "decay": decay,
                    "region": region,
                    "mutation_axis": "liquidity_gate",
                })

        log.info("[⚡ CONVEX MUTATOR] Generated %d targeted gradient mutations for %s.", len(mutations), archetype)
        return mutations
