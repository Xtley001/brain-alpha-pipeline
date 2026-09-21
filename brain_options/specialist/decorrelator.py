"""
Decorrelation Optimizer Engine for WorldQuant BRAIN Options Alphas.
Applies mathematical orthogonalization transforms, frequency shifts,
regime gating, and calendar curve differencing to salvage high-Sharpe,
high-Fitness alphas that failed exclusively on self-correlation.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from brain_options.specialist.dedup import ASTDeduplicator
from brain_options.specialist.templates import OptionCandidate

log = logging.getLogger("brain_options.decorrelator")


class DecorrelationEngine:
    """
    Transforms co-linear alpha expressions into orthogonal, uncorrelated signals
    while preserving their underlying economic alpha edge.
    """

    def __init__(self, deduplicator: Optional[ASTDeduplicator] = None):
        self.dedup = deduplicator or ASTDeduplicator()

    def generate_orthogonal_variants(
        self,
        base_expr: str,
        archetype: str,
        base_sharpe: float = 1.5,
        colliding_id: Optional[str] = None,
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
        """
        variants: List[OptionCandidate] = []
        seen_hashes: set[str] = set()

        def _add(cand_expr: str, transform_name: str, hypothesis: str):
            clean = cand_expr.strip()
            if not clean:
                return
            h = self.dedup.hash(clean)
            if h in seen_hashes:
                return
            seen_hashes.add(h)
            variants.append(
                OptionCandidate(
                    expression=clean,
                    archetype_name=f"Decorrelated({archetype})",
                    hypothesis=f"{hypothesis} [Salvaged from base Sharpe={base_sharpe:.2f}]",
                    generation_source="decorrelator",
                )
            )

        # -------------------------------------------------------------
        # Axis 1: Frequency Shift (Level -> Velocity via ts_delta)
        # -------------------------------------------------------------
        # Pattern: replace ts_decay_linear(X, win) or inner metric with ts_decay_linear(ts_delta(X, delta_win), decay_win)
        inner_metric_match = re.search(r"ts_decay_linear\((.+?),\s*(\d+)\)", base_expr)
        if inner_metric_match:
            inner_content = inner_metric_match.group(1).strip()
            # If already has ts_delta, adjust delta window; otherwise wrap in ts_delta
            if "ts_delta(" not in inner_content:
                for delta_win in [3, 5, 8]:
                    mod_expr = base_expr.replace(
                        inner_metric_match.group(0),
                        f"ts_decay_linear(ts_delta({inner_content}, {delta_win}), 5)",
                    )
                    _add(
                        mod_expr,
                        "Velocity Shift",
                        f"Velocity rate-of-change over {delta_win}d decorrelates from static level mispricing.",
                    )

        # -------------------------------------------------------------
        # Axis 2: Calendar Curve Differencing (Cross-Tenor Slope)
        # -------------------------------------------------------------
        # Pattern: if base uses tenor T (e.g. 90, 60, 30, 20), difference against complementary tenor
        tenor_match = re.search(r"_(10|20|30|60|90|120|180)\b", base_expr)
        if tenor_match:
            current_tenor = int(tenor_match.group(1))
            alt_tenors = [t for t in [10, 20, 30, 60, 90] if t != current_tenor]
            for alt in alt_tenors[:2]:
                # Construct curve spread
                # Replace primary field occurrences with difference: (field_{tenor} - field_{alt})
                field_prefix_match = re.search(r"([a-z_]+)_" + str(current_tenor), base_expr)
                if field_prefix_match:
                    prefix = field_prefix_match.group(1)
                    if prefix in ["implied_volatility_mean_skew", "call_breakeven", "implied_volatility_mean", "forward_price"]:
                        import math
                        sq1 = round(math.sqrt(current_tenor / 252.0), 4)
                        sq2 = round(math.sqrt(alt / 252.0), 4)
                        diff_sub = f"({prefix}_{current_tenor} * {sq1} - {prefix}_{alt} * {sq2})"
                        mod_expr = base_expr.replace(f"{prefix}_{current_tenor} * sqrt({current_tenor}/252.0)", diff_sub)
                        mod_expr = mod_expr.replace(f"{prefix}_{current_tenor} * {sq1}", diff_sub)
                        if mod_expr != base_expr:
                            _add(
                                mod_expr,
                                "Calendar Curve Spread",
                                f"Cross-tenor curve spread ({current_tenor}d vs {alt}d) eliminates market-wide drift.",
                            )

        # -------------------------------------------------------------
        # Axis 3: Bivariate Volume Regime Gating
        # -------------------------------------------------------------
        # Wrap existing trade_when or outer expression in volume gate
        if "volume > adv20" not in base_expr:
            for vol_mult in ["1.0", "1.15", "1.25"]:
                mod_expr = f"trade_when(volume > adv20 * {vol_mult}, {base_expr}, -1)"
                _add(
                    mod_expr,
                    "Volume Regime Gate",
                    f"Restricting trade entry to volume > adv20 * {vol_mult} isolates institutional flow and reduces covariance.",
                )

        # -------------------------------------------------------------
        # Axis 4: Volatility Regime Gating
        # -------------------------------------------------------------
        if "implied_volatility_mean_30 > ts_mean" not in base_expr:
            vol_gate = "implied_volatility_mean_30 > ts_mean(implied_volatility_mean_30, 40)"
            mod_expr = f"trade_when({vol_gate}, {base_expr}, -1)"
            _add(
                mod_expr,
                "Volatility Regime Gate",
                "High-volatility regime gating breaks correlation with standard-regime portfolios.",
            )

        # -------------------------------------------------------------
        # Axis 5: Neutralization & Threshold Rotation
        # -------------------------------------------------------------
        if "subindustry" in base_expr:
            # Rotate to sector with entry threshold tuning
            mod_expr = base_expr.replace("subindustry", "sector")
            _add(
                mod_expr,
                "Group Neutralization Rotation",
                "Switching neutralization from subindustry to sector alters cross-sectional weights.",
            )
        elif "sector" in base_expr:
            mod_expr = base_expr.replace("sector", "subindustry")
            _add(
                mod_expr,
                "Group Neutralization Rotation",
                "Switching neutralization from sector to subindustry enforces granular intra-industry orthogonality.",
            )

        # -------------------------------------------------------------
        # Axis 6: Order Flow Confluence Blending
        # -------------------------------------------------------------
        if "pcr_vol" not in base_expr:
            # Modulate rank output by PCR flow ratio
            rank_match = re.search(r"rank\((.+?)\)", base_expr)
            if rank_match:
                inner_rnk = rank_match.group(1)
                mod_expr = base_expr.replace(
                    rank_match.group(0),
                    f"rank({inner_rnk}) * rank(pcr_vol_20 / (pcr_oi_20 + 0.001))",
                )
                _add(
                    mod_expr,
                    "Order Flow Confluence Blend",
                    "Modulating options signal by put-call volume/OI velocity shifts weight vector away from colliding alpha.",
                )

        return variants
