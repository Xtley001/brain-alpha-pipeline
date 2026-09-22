"""
Decorrelation Optimizer Engine for WorldQuant BRAIN Options Alphas.
Applies mathematical orthogonalization transforms, frequency shifts,
regime gating, and calendar curve differencing to salvage high-Sharpe,
high-Fitness alphas that failed exclusively on self-correlation.
"""
from __future__ import annotations

import logging
import math
import re
from typing import Any, Dict, List, Optional, Tuple

from brain_options.specialist.dedup import ASTDeduplicator
from brain_options.specialist.templates import OptionCandidate

log = logging.getLogger("brain_options.decorrelator")


class DecorrelationEngine:
    """
    Transforms co-linear alpha expressions into orthogonal, uncorrelated signals
    while preserving their underlying economic alpha edge.
    Features robust regex rewriting, per-axis attempt tracking, and audit logging.
    """

    def __init__(self, deduplicator: Optional[ASTDeduplicator] = None):
        self.dedup = deduplicator or ASTDeduplicator()

    def generate_orthogonal_variants(
        self,
        base_expr: str,
        archetype: str,
        base_sharpe: float = 1.5,
        colliding_id: Optional[str] = None,
        corr_partner_id: Optional[str] = None,
        decorrelation_attempts: int = 0,
    ) -> List[OptionCandidate]:
        """
        Generates 5 to 8 systematic orthogonal variants of a high-Sharpe candidate.
        Each variant attacks self-correlation along an independent mathematical axis:
        1. Frequency shift (Level -> Velocity / Acceleration via ts_delta)
        2. Calendar curve differencing (Single-tenor -> Term structure differential)
        3. Bivariate liquidity regime gating (Volume > adv20 surge)
        4. Volatility regime conditioning (ATM IV > rolling mean)
        5. Group neutralization rotation (sector <-> subindustry)
        6. Microstructure flow confluence (Order flow velocity weighting)

        Tracks attempted vs. successful mutations per axis and logs audit diagnostics.
        """
        variants: List[OptionCandidate] = []
        seen_hashes: set[str] = set()

        # Audit tracker per axis for the base alpha
        axis_audit: Dict[str, Dict[str, Any]] = {
            "Axis 1 (Velocity Shift)": {"attempted": False, "applied": 0, "reasons": []},
            "Axis 2 (Calendar Curve Spread)": {"attempted": False, "applied": 0, "reasons": []},
            "Axis 3 (Volume Regime Gate)": {"attempted": False, "applied": 0, "reasons": []},
            "Axis 4 (Volatility Regime Gate)": {"attempted": False, "applied": 0, "reasons": []},
            "Axis 5 (Neutralization Rotation)": {"attempted": False, "applied": 0, "reasons": []},
            "Axis 6 (Order Flow Confluence)": {"attempted": False, "applied": 0, "reasons": []},
        }

        alpha_ref = colliding_id or (base_expr[:30] + "...")

        def _add(cand_expr: str, axis_key: str, transform_name: str, hypothesis: str) -> bool:
            clean = cand_expr.strip()
            if not clean:
                axis_audit[axis_key]["reasons"].append("Empty candidate expression")
                return False
            h = self.dedup.hash(clean)
            if h in seen_hashes:
                axis_audit[axis_key]["reasons"].append("Duplicate hash within batch")
                return False
            seen_hashes.add(h)
            variants.append(
                OptionCandidate(
                    expression=clean,
                    archetype_name=f"Decorrelated({archetype})",
                    hypothesis=f"{hypothesis} [Salvaged from base Sharpe={base_sharpe:.2f}]",
                    generation_source="decorrelator",
                    base_alpha_id=colliding_id,
                )
            )
            axis_audit[axis_key]["applied"] += 1
            return True

        # -------------------------------------------------------------
        # Axis 1: Frequency Shift (Level -> Velocity via ts_delta)
        # -------------------------------------------------------------
        axis_key = "Axis 1 (Velocity Shift)"
        axis_audit[axis_key]["attempted"] = True
        decay_match = re.search(r"ts_decay_linear\s*\(\s*(.+?)\s*,\s*(\d+)\s*\)", base_expr)
        if decay_match:
            inner_content = decay_match.group(1).strip()
            # If not already differentiated, wrap with ts_delta across lookbacks
            if "ts_delta(" not in inner_content:
                for delta_win in [3, 5, 8]:
                    sub_str = f"ts_decay_linear(ts_delta({inner_content}, {delta_win}), 5)"
                    # Robust substitution replacing the exact matched decay block
                    mod_expr = base_expr[:decay_match.start()] + sub_str + base_expr[decay_match.end():]
                    if mod_expr != base_expr:
                        _add(
                            mod_expr,
                            axis_key,
                            "Velocity Shift",
                            f"Velocity rate-of-change over {delta_win}d decorrelates from static level mispricing.",
                        )
                    else:
                        log.warning("%s: Pattern matched decay block in %s, but substitution was no-op.", axis_key, alpha_ref)
                        axis_audit[axis_key]["reasons"].append("Decay replacement was no-op")
            else:
                axis_audit[axis_key]["reasons"].append("Expression already contains ts_delta")
        else:
            axis_audit[axis_key]["reasons"].append("No ts_decay_linear block found in expression")

        # -------------------------------------------------------------
        # Axis 2: Calendar Curve Differencing (Cross-Tenor Differential)
        # -------------------------------------------------------------
        axis_key = "Axis 2 (Calendar Curve Spread)"
        axis_audit[axis_key]["attempted"] = True
        # Find any options field with a tenor suffix
        tenor_field_pattern = r"\b([a-z_]+)_(10|20|30|60|90|120|180|270|360)\b"
        tenor_matches = list(re.finditer(tenor_field_pattern, base_expr))

        if tenor_matches:
            target_prefixes = ["implied_volatility_mean_skew", "call_breakeven", "implied_volatility_mean", "forward_price"]
            valid_field_found = False
            for match in tenor_matches:
                prefix = match.group(1)
                current_tenor = int(match.group(2))
                if prefix in target_prefixes:
                    valid_field_found = True
                    alt_tenors = [t for t in [10, 20, 30, 60, 90] if t != current_tenor]
                    for alt in alt_tenors[:2]:
                        sq1 = round(math.sqrt(current_tenor / 252.0), 4)
                        sq2 = round(math.sqrt(alt / 252.0), 4)
                        diff_sub = f"({prefix}_{current_tenor} * {sq1} - {prefix}_{alt} * {sq2})"

                        # Robust regex matching: matches prefix_tenor with optional * sqrt(T/252) or * float in any spacing/order
                        # Case A: prefix_tenor * sqrt(...) or prefix_tenor * float
                        pat_forward = rf"\b{prefix}_{current_tenor}\s*\*\s*(?:sqrt\s*\(\s*{current_tenor}\s*/\s*252(?:\.0)?\s*\)|[0-9.]+)"
                        # Case B: sqrt(...) * prefix_tenor or float * prefix_tenor
                        pat_reverse = rf"(?:sqrt\s*\(\s*{current_tenor}\s*/\s*252(?:\.0)?\s*\)|[0-9.]+)\s*\*\s*{prefix}_{current_tenor}\b"
                        # Case C: bare prefix_tenor without explicit multiplier
                        pat_bare = rf"\b{prefix}_{current_tenor}\b"

                        mod_expr = None
                        if re.search(pat_forward, base_expr):
                            mod_expr = re.sub(pat_forward, diff_sub, base_expr, count=1)
                        elif re.search(pat_reverse, base_expr):
                            mod_expr = re.sub(pat_reverse, diff_sub, base_expr, count=1)
                        elif re.search(pat_bare, base_expr):
                            diff_bare = f"({prefix}_{current_tenor} - {prefix}_{alt})"
                            mod_expr = re.sub(pat_bare, diff_bare, base_expr, count=1)

                        if mod_expr and mod_expr != base_expr:
                            _add(
                                mod_expr,
                                axis_key,
                                "Calendar Curve Spread",
                                f"Cross-tenor curve spread ({current_tenor}d vs {alt}d) eliminates market-wide drift.",
                            )
                        else:
                            log.warning("%s: Pattern matched field '%s_%d' in %s, but regex substitution produced no change.",
                                        axis_key, prefix, current_tenor, alpha_ref)
                            axis_audit[axis_key]["reasons"].append(f"Substitution no-op for {prefix}_{current_tenor} vs {alt}")
                    break  # Diff on first eligible field
            if not valid_field_found:
                axis_audit[axis_key]["reasons"].append(f"No eligible option field prefix found in matches: {[m.group(0) for m in tenor_matches]}")
        else:
            axis_audit[axis_key]["reasons"].append("No option tenor fields matching _(10|20|30|...) found")

        # -------------------------------------------------------------
        # Axis 3: Bivariate Volume Regime Gating
        # -------------------------------------------------------------
        axis_key = "Axis 3 (Volume Regime Gate)"
        axis_audit[axis_key]["attempted"] = True
        if "volume > adv20" not in base_expr:
            for vol_mult in ["1.0", "1.15", "1.25"]:
                mod_expr = f"trade_when(volume > adv20 * {vol_mult}, {base_expr}, -1)"
                _add(
                    mod_expr,
                    axis_key,
                    "Volume Regime Gate",
                    f"Restricting trade entry to volume > adv20 * {vol_mult} isolates institutional flow and reduces covariance.",
                )
        else:
            axis_audit[axis_key]["reasons"].append("Expression already gated by volume > adv20")

        # -------------------------------------------------------------
        # Axis 4: Volatility Regime Gating
        # -------------------------------------------------------------
        axis_key = "Axis 4 (Volatility Regime Gate)"
        axis_audit[axis_key]["attempted"] = True
        if "implied_volatility_mean_30 > ts_mean" not in base_expr and "implied_volatility_mean" in base_expr:
            vol_gate = "implied_volatility_mean_30 > ts_mean(implied_volatility_mean_30, 40)"
            mod_expr = f"trade_when({vol_gate}, {base_expr}, -1)"
            _add(
                mod_expr,
                axis_key,
                "Volatility Regime Gate",
                "High-volatility regime gating breaks correlation with standard-regime portfolios.",
            )
        else:
            axis_audit[axis_key]["reasons"].append("Already vol-gated or base does not use implied_volatility_mean")

        # -------------------------------------------------------------
        # Axis 5: Neutralization & Threshold Rotation
        # -------------------------------------------------------------
        axis_key = "Axis 5 (Neutralization Rotation)"
        axis_audit[axis_key]["attempted"] = True
        if "subindustry" in base_expr:
            mod_expr = re.sub(r"\bsubindustry\b", "sector", base_expr)
            if mod_expr != base_expr:
                _add(
                    mod_expr,
                    axis_key,
                    "Group Neutralization Rotation",
                    "Switching neutralization from subindustry to sector alters cross-sectional weights.",
                )
            else:
                axis_audit[axis_key]["reasons"].append("subindustry substitution was no-op")
        elif "sector" in base_expr:
            mod_expr = re.sub(r"\bsector\b", "subindustry", base_expr)
            if mod_expr != base_expr:
                _add(
                    mod_expr,
                    axis_key,
                    "Group Neutralization Rotation",
                    "Switching neutralization from sector to subindustry enforces granular intra-industry orthogonality.",
                )
            else:
                axis_audit[axis_key]["reasons"].append("sector substitution was no-op")
        else:
            axis_audit[axis_key]["reasons"].append("Neither sector nor subindustry found in base expression")

        # -------------------------------------------------------------
        # Axis 6: Order Flow Confluence Blending
        # -------------------------------------------------------------
        axis_key = "Axis 6 (Order Flow Confluence)"
        axis_audit[axis_key]["attempted"] = True
        if "pcr_vol" not in base_expr:
            rank_match = re.search(r"rank\s*\((.+?)\)", base_expr)
            if rank_match:
                inner_rnk = rank_match.group(1)
                mod_expr = (
                    base_expr[:rank_match.start()]
                    + f"rank({inner_rnk}) * rank(pcr_vol_20 / (pcr_oi_20 + 0.001))"
                    + base_expr[rank_match.end():]
                )
                if mod_expr != base_expr:
                    _add(
                        mod_expr,
                        axis_key,
                        "Order Flow Confluence Blend",
                        "Modulating options signal by put-call volume/OI velocity shifts weight vector away from colliding alpha.",
                    )
                else:
                    axis_audit[axis_key]["reasons"].append("Confluence rank substitution was no-op")
            else:
                axis_audit[axis_key]["reasons"].append("No rank() call found for confluence modulation")
        else:
            axis_audit[axis_key]["reasons"].append("Expression already contains pcr_vol")

        # -------------------------------------------------------------
        # Post-Processing: Embed Multiple-Testing Metadata on Candidates
        # -------------------------------------------------------------
        total_variants = len(variants)
        final_candidates: List[OptionCandidate] = []
        for v in variants:
            # Stamp n_variants_tried, base_alpha_id, corr_partner_alpha_id, and decorrelation_attempts explicitly
            updated = OptionCandidate(
                expression=v.expression,
                archetype_name=v.archetype_name,
                hypothesis=f"{v.hypothesis} [base_alpha={colliding_id or 'unknown'}, n_variants_tried={total_variants}]",
                generation_source=v.generation_source,
                n_variants_tried=total_variants,
                base_alpha_id=colliding_id,
                corr_partner_alpha_id=corr_partner_id,
                decorrelation_attempts=decorrelation_attempts,
            )
            final_candidates.append(updated)

        # -------------------------------------------------------------
        # Audit Diagnostic Reporting
        # -------------------------------------------------------------
        summary_items = []
        for axis_name, data in axis_audit.items():
            if data["applied"] > 0:
                summary_items.append(f"{axis_name}: {data['applied']} applied")
            elif data["attempted"]:
                reasons_str = "; ".join(data["reasons"]) if data["reasons"] else "criteria not met"
                summary_items.append(f"{axis_name}: 0 ({reasons_str})")

        log.info(
            "Decorrelation mutation audit for %s: %s | Total variants generated: %d",
            alpha_ref, " | ".join(summary_items), total_variants,
        )

        return final_candidates
