"""
Closed-Loop Diagnostic Alpha Optimizer with Reinforcement Learning.
Diagnoses simulation deficits (e.g. Fitness trapped by high turnover, sector noise dilution,
tenor mismatches) and applies targeted mathematical transformations grounded in Master Books 1-4.
"""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from brain_options.config import OptionsConfig
from brain_options.core.client import BrainClient, SimMetrics, SimSettings
from brain_options.core.filter import evaluate_alpha_metrics
from brain_options.specialist.templates import OptionCandidate
from brain_options.store.store import OptionsStore

log = logging.getLogger("brain_options.optimizer")


def _stage0_validity_reward(metrics: SimMetrics) -> float:
    """Checklist-failure penalties (LOW_SUB_UNIVERSE_SHARPE, CONCENTRATED_WEIGHT, other fails)."""
    r = 0.0
    if isinstance(metrics.raw_response, dict):
        is_block = metrics.raw_response.get("is") or {}
        checks = is_block.get("checks") or metrics.raw_response.get("checks") or []
        for chk in checks:
            if chk.get("result") == "FAIL":
                if chk.get("name") == "LOW_SUB_UNIVERSE_SHARPE":
                    r -= 8.0
                elif chk.get("name") == "CONCENTRATED_WEIGHT":
                    r -= 5.0
                elif chk.get("name") not in ("LOW_SHARPE", "LOW_FITNESS"):
                    r -= 2.0
    return r


def _stage1_hurdle_reward(metrics: SimMetrics) -> float:
    """Base reward components and hurdle bonuses (Sharpe and Fitness)."""
    # Base reward components - heavily weighting fitness to clear the 1.0 threshold
    r = metrics.sharpe + 2.5 * min(metrics.fitness, 3.0)

    # Fitness hurdle bonus (the primary qualification bottleneck)
    if metrics.fitness >= 1.0:
        r += 2.0

    # Sharpe hurdle bonus
    if metrics.sharpe >= 1.25:
        r += 2.0

    return r


def _stage2_efficiency_reward(metrics: SimMetrics) -> float:
    """Turnover-related terms (penalty tiers, sweet-spot bonus, Leland drag penalty)."""
    r = 0.0
    # Turnover penalty: BRAIN's fitness divisor is max(turnover, 0.125).
    # Turnover > 0.25 severely drags fitness down.
    if metrics.turnover > 0.25:
        r -= 3.0 * (metrics.turnover - 0.25)
    if metrics.turnover > 0.70:
        r -= 6.0 * (metrics.turnover - 0.70)
    elif metrics.turnover < 0.01:
        r -= 3.0 * (0.01 - metrics.turnover)

    # Turnover efficiency bonus: if turnover is within the sweet spot [4%, 18%]
    if 0.04 <= metrics.turnover <= 0.18 and metrics.sharpe >= 1.0:
        r += 1.5

    # Leland drag penalty: high turnover with low return
    if metrics.turnover > 0.35 and metrics.annualized_return < 0.04:
        r -= 1.5

    return r


def calculate_rl_reward(metrics: SimMetrics, is_qualified: bool = False) -> float:
    """
    Scalar Reinforcement Learning reward function:
    Rewards high Sharpe and Fitness, severely penalizes excessive turnover,
    and grants a major completion bonus for qualification.
    """
    if not metrics.is_valid:
        return -5.0

    total = (
        _stage0_validity_reward(metrics)
        + _stage1_hurdle_reward(metrics)
        + _stage2_efficiency_reward(metrics)
        + (10.0 if is_qualified else 0.0)
    )
    return round(total, 4)


@dataclass
class DiagnosticStep:
    step: int
    action_type: str
    expression: str
    settings: SimSettings
    metrics: SimMetrics
    reward: float
    description: str


class DiagnosticAlphaOptimizer:
    """
    Autonomous 'Doctor/Healer' optimization loop:
    Diagnoses checklist failures and iteratively repairs options alpha expressions.
    """

    def __init__(
        self,
        client: BrainClient,
        store: OptionsStore,
        config: OptionsConfig,
    ):
        self.client = client
        self.store = store
        self.config = config

    # -------------------------------------------------------------------------
    # Expression Transformation Operators (The Action Space)
    # -------------------------------------------------------------------------

    @staticmethod
    def _parse_call_args(expr: str, func_name: str) -> Optional[Tuple[int, int, List[str]]]:
        """Balanced-parenthesis parser returning start_idx, end_idx, and arguments list for func_name."""
        tag = func_name + "("
        idx = expr.find(tag)
        if idx == -1:
            return None
        start_paren = idx + len(tag) - 1
        depth = 0
        comma_indices: List[int] = []
        end_paren = -1
        for i in range(start_paren, len(expr)):
            ch = expr[i]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    end_paren = i
                    break
            elif ch == "," and depth == 1:
                comma_indices.append(i)
        if end_paren == -1:
            return None
        args: List[str] = []
        prev = start_paren + 1
        for c_idx in comma_indices:
            args.append(expr[prev:c_idx].strip())
            prev = c_idx + 1
        args.append(expr[prev:end_paren].strip())
        return idx, end_paren, args

    @classmethod
    def wrap_decay_linear(cls, expr: str, window: int = 15) -> str:
        """
        Wraps the inner ranking or signal with ts_decay_linear to reduce turnover
        and boost Fitness without altering cross-sectional logic.
        """
        expr = expr.strip()
        parsed = cls._parse_call_args(expr, "ts_decay_linear")
        if parsed and len(parsed[2]) == 2:
            start_idx, end_idx, (inner, old_w_str) = parsed
            try:
                old_w = int(old_w_str)
                new_w = max(window, min(30, old_w + 7))
                return expr[:start_idx] + f"ts_decay_linear({inner}, {new_w})" + expr[end_idx + 1:]
            except ValueError:
                pass

        parsed_gn = cls._parse_call_args(expr, "group_neutralize")
        if parsed_gn and len(parsed_gn[2]) == 2 and parsed_gn[0] == 0 and parsed_gn[1] == len(expr) - 1:
            inner_gn, group = parsed_gn[2]
            parsed_rank = cls._parse_call_args(inner_gn, "rank")
            if parsed_rank and len(parsed_rank[2]) == 1 and parsed_rank[0] == 0:
                inner_signal = parsed_rank[2][0]
                return f"group_neutralize(rank(ts_decay_linear({inner_signal}, {window})), {group})"

        parsed_tw = cls._parse_call_args(expr, "trade_when")
        if parsed_tw and len(parsed_tw[2]) == 3 and parsed_tw[0] == 0 and parsed_tw[1] == len(expr) - 1:
            cond, body, exit_val = parsed_tw[2]
            parsed_gn = cls._parse_call_args(body, "group_neutralize")
            if parsed_gn and len(parsed_gn[2]) == 2:
                inner_gn, group = parsed_gn[2]
                parsed_rank = cls._parse_call_args(inner_gn, "rank")
                if parsed_rank and len(parsed_rank[2]) == 1:
                    inner_signal = parsed_rank[2][0]
                    return f"trade_when({cond}, group_neutralize(rank(ts_decay_linear({inner_signal}, {window})), {group}), {exit_val})"

        return f"group_neutralize(rank(ts_decay_linear({expr}, {window})), subindustry)"

    @classmethod
    def wrap_decay_exp(cls, expr: str, window: int = 15, factor: float = 0.20) -> str:
        """
        Applies extended linear decay smoothing (window 15-25) in place of unsupported
        exponential decay to maximize turnover compression in BRAIN FastExpr.
        """
        return cls.wrap_decay_linear(expr, window=max(15, window))

    @classmethod
    def wrap_zscore(cls, expr: str, window: int = 20) -> str:
        """
        Replaces fast delta with ts_zscore(x, d) or normalizes signal
        to remove non-stationary volatility drift and extend holding periods.
        """
        expr = expr.strip()
        parsed_delta = cls._parse_call_args(expr, "ts_delta")
        if parsed_delta and len(parsed_delta[2]) == 2:
            start_idx, end_idx, (inner, _) = parsed_delta
            return expr[:start_idx] + f"ts_zscore({inner}, {window})" + expr[end_idx + 1:]

        parsed_tw = cls._parse_call_args(expr, "trade_when")
        if parsed_tw and len(parsed_tw[2]) == 3 and parsed_tw[0] == 0 and parsed_tw[1] == len(expr) - 1:
            cond, body, exit_val = parsed_tw[2]
            return f"trade_when({cond}, {cls.wrap_zscore(body, window)}, {exit_val})"

        return f"ts_zscore({expr}, {window})"

    @classmethod
    def inject_conviction_gate(cls, expr: str, threshold: float = 0.38) -> str:
        """
        Wraps expression in trade_when(abs(rank(x) - 0.5) > threshold, signal, -1).
        The exit condition '-1' directs WorldQuant BRAIN to maintain prior positions
        when signal conviction is not extreme, dropping turnover by ~65-85%.
        """
        expr = expr.strip()
        if "trade_when" in expr:
            # Update existing rank conviction threshold specifically if present
            if "abs(rank(" in expr and ") - 0.5) >" in expr:
                return re.sub(r"(abs\(rank\(.+?\)\s*-\s*0\.5\)\s*>\s*)0\.\d+", rf"\g<1>{threshold:.2f}", expr)
            return expr

        parsed_gn = cls._parse_call_args(expr, "group_neutralize")
        if parsed_gn and len(parsed_gn[2]) == 2 and parsed_gn[0] == 0 and parsed_gn[1] == len(expr) - 1:
            inner_gn, group = parsed_gn[2]
            parsed_rank = cls._parse_call_args(inner_gn, "rank")
            if parsed_rank and len(parsed_rank[2]) == 1 and parsed_rank[0] == 0 and parsed_rank[1] == len(inner_gn) - 1:
                inner_signal = parsed_rank[2][0]
                return f"trade_when(abs(rank({inner_signal}) - 0.5) > {threshold:.2f}, {expr}, -1)"

        return f"trade_when(abs(rank({expr}) - 0.5) > {threshold:.2f}, {expr}, -1)"

    @staticmethod
    def upgrade_neutralization(expr: str, target_group: str = "subindustry") -> str:
        """Upgrades coarse group neutralization (e.g. sector) to granular subindustry."""
        expr_clean = expr.strip()
        if re.search(r",\s*(sector|industry|market)\)", expr_clean, flags=re.IGNORECASE):
            return re.sub(r",\s*(sector|industry|market)\)", f", {target_group})", expr_clean, flags=re.IGNORECASE)
        if "group_neutralize" not in expr_clean.lower():
            return f"group_neutralize(rank({expr_clean}), {target_group})"
        return expr_clean

    @classmethod
    def inject_volume_gating(cls, expr: str) -> str:
        """Wraps expression in trade_when(volume > adv20, ..., -1) to eliminate Leland drag."""
        expr_clean = expr.strip()
        parsed_tw = cls._parse_call_args(expr_clean, "trade_when")
        if parsed_tw and len(parsed_tw[2]) == 3 and parsed_tw[0] == 0 and parsed_tw[1] == len(expr_clean) - 1:
            cond, body, exit_val = parsed_tw[2]
            if "volume > adv20" in cond:
                return expr_clean
            return f"trade_when((volume > adv20) && ({cond}), {body}, {exit_val})"
        return f"trade_when(volume > adv20, {expr_clean}, -1)"

    @staticmethod
    def shift_tenor(expr: str) -> str:
        """Shifts option tenors (10 -> 20 -> 30 -> 60) to align with term structure."""
        tenor_map = {
            "10": "20",
            "20": "30",
            "30": "60",
            "60": "90",
        }
        for old_t, new_t in tenor_map.items():
            pattern = rf"_({old_t})([_,\s\)])"
            if re.search(pattern, expr):
                return re.sub(pattern, f"_{new_t}\\2", expr)
        return expr

    @classmethod
    def adjust_delta_window(cls, expr: str, target_window: int = 20) -> str:
        """Increases ts_delta window (e.g. 5 -> 20) to capture monthly momentum and slow down churning."""
        expr = expr.strip()
        parsed = cls._parse_call_args(expr, "ts_delta")
        if parsed and len(parsed[2]) == 2:
            start_idx, end_idx, (inner, old_w_str) = parsed
            try:
                old_w = int(old_w_str)
                new_w = target_window if old_w < target_window else old_w + 10
                return expr[:start_idx] + f"ts_delta({inner}, {new_w})" + expr[end_idx + 1:]
            except ValueError:
                pass
        return expr

    # -------------------------------------------------------------------------
    # Optimization Loop
    # -------------------------------------------------------------------------

    async def optimize(
        self,
        candidate: OptionCandidate,
        base_settings: SimSettings,
        initial_metrics: SimMetrics,
        max_steps: int = 6,
    ) -> Tuple[OptionCandidate, SimSettings, SimMetrics, bool, List[DiagnosticStep]]:
        """
        Executes diagnostic repair trajectories on a promising candidate.
        Returns the best candidate, best settings, best metrics, and whether it qualified.
        """
        log.info("=" * 65)
        log.info("STARTING DIAGNOSTIC OPTIMIZATION: [%s]", candidate.expression[:60])
        log.info("Initial Stage 0: Sharpe=%.2f, Fitness=%.2f, Turnover=%.2f%%",
                 initial_metrics.sharpe, initial_metrics.fitness, initial_metrics.turnover * 100)

        # Invariant: Guarantee candidate is neutralized by granular subindustry
        sanitized_expr = self.upgrade_neutralization(candidate.expression, "subindustry")
        if sanitized_expr != candidate.expression:
            candidate = OptionCandidate(
                expression=sanitized_expr,
                archetype_name=candidate.archetype_name,
                hypothesis=candidate.hypothesis,
                generation_source=candidate.generation_source,
                operator_name=candidate.operator_name,
                operator_category=candidate.operator_category,
                operator_param=candidate.operator_param,
                base_alpha_id=candidate.base_alpha_id,
                n_variants_tried=candidate.n_variants_tried,
            )

        if base_settings.neutralization.upper() != "SUBINDUSTRY":
            base_settings = SimSettings(
                region=base_settings.region,
                universe=base_settings.universe,
                delay=base_settings.delay,
                decay=base_settings.decay,
                neutralization="SUBINDUSTRY",
                truncation=base_settings.truncation,
                pasteurization=base_settings.pasteurization,
                nan_handling=base_settings.nan_handling,
                unit_handling=base_settings.unit_handling,
                language=base_settings.language,
            )

        best_cand = candidate
        best_settings = base_settings
        best_metrics = initial_metrics
        best_reward = calculate_rl_reward(initial_metrics, evaluate_alpha_metrics(initial_metrics, self.config)[0])

        history: List[DiagnosticStep] = [
            DiagnosticStep(
                step=0,
                action_type="STAGE0_SCREEN",
                expression=candidate.expression,
                settings=base_settings,
                metrics=initial_metrics,
                reward=best_reward,
                description="Initial fast screen baseline",
            )
        ]

        init_qual = evaluate_alpha_metrics(initial_metrics, self.config)[0]
        init_breakdown = {
            "stage0": _stage0_validity_reward(initial_metrics),
            "stage1": _stage1_hurdle_reward(initial_metrics),
            "stage2": _stage2_efficiency_reward(initial_metrics),
            "completion": 10.0 if init_qual else 0.0,
        }
        # Record initial in learning memory
        self.store.record_learning_memory(
            candidate,
            initial_metrics,
            reward=best_reward,
            optimization_steps=0,
            status="INITIAL_SCREEN",
            reward_breakdown=init_breakdown,
        )

        current_expr = candidate.expression
        current_settings = base_settings

        for round_idx in range(1, max_steps + 1):
            # Check if current best already passes all qualification gates
            passed_filter, reason = evaluate_alpha_metrics(best_metrics, self.config)
            if passed_filter:
                log.info("[+] ALPHA QUALIFIED IN ROUND %d! (Sharpe=%.2f, Fitness=%.2f, TO=%.2f%%)",
                         round_idx - 1, best_metrics.sharpe, best_metrics.fitness, best_metrics.turnover * 100)
                break

            log.info("--- Round %d/%d: Formulating multi-arm diagnostic trials (Reason: %s) ---", round_idx, max_steps, reason)

            arms: List[Tuple[str, str, str, SimSettings]] = []

            # DEFICIT: High Turnover dragging down Fitness (The Primary Bottleneck)
            if best_metrics.turnover > 0.25 or ("Fitness" in reason and best_metrics.sharpe >= 1.0):
                if round_idx == 1:
                    # Round 1: High-conviction gating & deep smoothing
                    arms.append((
                        "CONVICTION_GATE_T38",
                        "High-conviction gate (0.38 threshold, holds top/bottom 12% names, drops turnover by ~70%)",
                        self.inject_conviction_gate(current_expr, threshold=0.38),
                        SimSettings(universe=current_settings.universe, delay=current_settings.delay, decay=16, neutralization="SUBINDUSTRY", truncation=0.05),
                    ))
                    arms.append((
                        "DEEP_SMOOTH_D22",
                        "Deep linear smoothing (window=15) with decay=22 to compress daily churn",
                        self.wrap_decay_linear(current_expr, window=15),
                        SimSettings(universe=current_settings.universe, delay=current_settings.delay, decay=22, neutralization="SUBINDUSTRY", truncation=0.05),
                    ))
                    arms.append((
                        "CONVICTION_SMOOTH_T35",
                        "Combined linear smoothing with 0.35 conviction gate and decay=18",
                        self.inject_conviction_gate(self.wrap_decay_linear(current_expr, window=12), threshold=0.35),
                        SimSettings(universe=current_settings.universe, delay=current_settings.delay, decay=18, neutralization="SUBINDUSTRY", truncation=0.05),
                    ))

                elif round_idx == 2:
                    # Round 2: Conviction calibration & Z-score stability
                    arms.append((
                        "ULTRA_CONVICTION_T42",
                        "Ultra-high conviction gate (0.42 threshold, holds top/bottom 8% names, turnover < 12%)",
                        self.inject_conviction_gate(current_expr, threshold=0.42),
                        SimSettings(universe=current_settings.universe, delay=current_settings.delay, decay=18, neutralization="SUBINDUSTRY", truncation=0.05),
                    ))
                    arms.append((
                        "ZSCORE_CONVICTION_T38",
                        "Transformed signal to 20-day rolling Z-score with 0.38 conviction gate",
                        self.inject_conviction_gate(self.wrap_zscore(current_expr, window=20), threshold=0.38),
                        SimSettings(universe=current_settings.universe, delay=current_settings.delay, decay=18, neutralization="SUBINDUSTRY", truncation=0.05),
                    ))
                    arms.append((
                        "EXP_DECAY_CONVICTION",
                        "Deep linear decay smoothing (window=15) with 0.35 conviction gate",
                        self.inject_conviction_gate(self.wrap_decay_exp(current_expr, window=15, factor=0.20), threshold=0.35),
                        SimSettings(universe=current_settings.universe, delay=current_settings.delay, decay=20, neutralization="SUBINDUSTRY", truncation=0.05),
                    ))

                elif round_idx == 3:
                    # Round 3: Tenor migration, extended lookbacks, and volume gating
                    arms.append((
                        "SHIFT_TENOR_CONVICTION",
                        "Shifted option maturity tenor forward with 0.38 conviction gate",
                        self.inject_conviction_gate(self.shift_tenor(current_expr), threshold=0.38),
                        SimSettings(universe=current_settings.universe, delay=current_settings.delay, decay=20, neutralization="SUBINDUSTRY", truncation=0.05),
                    ))
                    arms.append((
                        "DEEP_DELTA_CONVICTION",
                        "Extended delta lookback to 25 with 0.38 conviction gate and decay=22",
                        self.inject_conviction_gate(self.adjust_delta_window(current_expr, 25), threshold=0.38),
                        SimSettings(universe=current_settings.universe, delay=current_settings.delay, decay=22, neutralization="SUBINDUSTRY", truncation=0.05),
                    ))
                    arms.append((
                        "VOLUME_ADV_CONVICTION",
                        "Filtered trades by volume > adv20 with 0.36 conviction gate",
                        self.inject_volume_gating(self.inject_conviction_gate(current_expr, threshold=0.36)),
                        SimSettings(universe=current_settings.universe, delay=current_settings.delay, decay=18, neutralization="SUBINDUSTRY", truncation=0.05),
                    ))

                else:
                    # Rounds 4-6: Fine calibration of conviction threshold and decay
                    for d, thresh in [(20, 0.36), (24, 0.40), (28, 0.44)]:
                        arms.append((
                            f"CALIBRATION_D{d}_T{int(thresh*100)}",
                            f"Fine calibration: decay={d}, conviction threshold={thresh}",
                            self.inject_conviction_gate(current_expr, threshold=thresh),
                            SimSettings(universe=current_settings.universe, delay=current_settings.delay, decay=d, neutralization="SUBINDUSTRY", truncation=0.05),
                        ))

            # DEFICIT: Sharpe is borderline (0.35 - 1.25)
            elif best_metrics.sharpe < self.config.filter_min_sharpe:
                if "subindustry" not in current_expr.lower():
                    arms.append((
                        "UPGRADE_TO_SUBINDUSTRY",
                        "Escalated neutralization to subindustry",
                        self.upgrade_neutralization(current_expr, "subindustry"),
                        SimSettings(universe=current_settings.universe, delay=current_settings.delay, decay=12, neutralization="SUBINDUSTRY", truncation=0.05),
                    ))
                arms.append((
                    "SHIFT_TENOR",
                    "Migrated option tenor forward to test deeper derivative maturity",
                    self.shift_tenor(current_expr),
                    SimSettings(universe=current_settings.universe, delay=current_settings.delay, decay=14, neutralization="SUBINDUSTRY", truncation=0.05),
                ))
                arms.append((
                    "ZSCORE_TRANSFORM",
                    "Transformed raw signal into 20-day rolling Z-score to boost signal-to-noise",
                    self.wrap_zscore(current_expr, 20),
                    SimSettings(universe=current_settings.universe, delay=current_settings.delay, decay=14, neutralization="SUBINDUSTRY", truncation=0.05),
                ))

            # DEFICIT: Sub-universe Sharpe failure (Concentrated in illiquid names)
            elif "Sub-universe Sharpe" in reason or "LOW_SUB_UNIVERSE_SHARPE" in reason:
                if round_idx == 1:
                    arms.append((
                        "SUB_UNIV_TRUNCATION_01",
                        "Cap max weight at 1% (truncation=0.01) to eliminate small-cap concentration",
                        current_expr,
                        SimSettings(universe=current_settings.universe, delay=current_settings.delay, decay=max(16, current_settings.decay), neutralization="SUBINDUSTRY", truncation=0.01),
                    ))
                    arms.append((
                        "SUB_UNIV_TRUNCATION_02",
                        "Cap max weight at 2% (truncation=0.02) with higher decay",
                        current_expr,
                        SimSettings(universe=current_settings.universe, delay=current_settings.delay, decay=max(20, current_settings.decay + 4), neutralization="SUBINDUSTRY", truncation=0.02),
                    ))
                    arms.append((
                        "SUB_UNIV_INDUSTRY_NEUT",
                        "Neutralize by industry to diversify across broader peer groups",
                        self.upgrade_neutralization(current_expr, "industry"),
                        SimSettings(universe=current_settings.universe, delay=current_settings.delay, decay=max(16, current_settings.decay), neutralization="INDUSTRY", truncation=0.03),
                    ))
                else:
                    arms.append((
                        "SUB_UNIV_TRUNCATION_005",
                        "Ultra-diffuse portfolio (truncation=0.005) with decay=24",
                        current_expr,
                        SimSettings(universe=current_settings.universe, delay=current_settings.delay, decay=24, neutralization="SUBINDUSTRY", truncation=0.005),
                    ))
                    arms.append((
                        "SUB_UNIV_DEEP_CONVICTION",
                        "Deep conviction gate (0.42) with truncation=0.01 to isolate high-conviction liquid names",
                        self.inject_conviction_gate(current_expr, threshold=0.42),
                        SimSettings(universe=current_settings.universe, delay=current_settings.delay, decay=22, neutralization="SUBINDUSTRY", truncation=0.01),
                    ))
                    arms.append((
                        "SUB_UNIV_MARKET_NEUT",
                        "Broad market neutralization with decay=20 and truncation=0.02",
                        self.upgrade_neutralization(current_expr, "market"),
                        SimSettings(universe=current_settings.universe, delay=current_settings.delay, decay=20, neutralization="MARKET", truncation=0.02),
                    ))

            # DEFICIT: General fine-tuning
            else:
                for d in (16, 20, 24):
                    arms.append((
                        f"CALIBRATION_DECAY_{d}",
                        f"Standard decay calibration ({d}) with subindustry and truncation 0.05",
                        current_expr,
                        SimSettings(universe=current_settings.universe, delay=current_settings.delay, decay=d, neutralization="SUBINDUSTRY", truncation=0.05),
                    ))

            # Filter out duplicate arms against current history
            evaluated_pairs = {(step.expression, step.settings.decay, step.settings.neutralization, step.settings.truncation) for step in history}
            unique_arms = [
                arm for arm in arms
                if (arm[2], arm[3].decay, arm[3].neutralization, arm[3].truncation) not in evaluated_pairs
            ]

            if not unique_arms:
                if "trade_when" not in current_expr:
                    unique_arms = [(
                        "CONVICTION_GATE_FALLBACK",
                        "Fallback: apply state-holding conviction gate",
                        self.inject_conviction_gate(current_expr, threshold=0.38),
                        SimSettings(universe=current_settings.universe, delay=current_settings.delay, decay=current_settings.decay, neutralization="SUBINDUSTRY", truncation=0.05),
                    )]
                else:
                    log.info("No further unique diagnostic arms available for candidate. Ending optimization.")
                    break

            log.info("Firing %d concurrent diagnostic arms in parallel...", len(unique_arms))
            for i, (atype, _, aexpr, asett) in enumerate(unique_arms, 1):
                log.info("  [Arm %d] %s: %s (Decay=%d, Neut=%s)", i, atype, aexpr[:50], asett.decay, asett.neutralization)

            # Execute all arms in parallel via asyncio.gather (governed by BrainClient semaphore)
            results = await asyncio.gather(*[
                self.client.simulate_one(aexpr, asett) for _, _, aexpr, asett in unique_arms
            ])

            round_qualified = False
            for (action_type, action_desc, trial_expr, trial_settings), trial_metrics in zip(unique_arms, results):
                if not trial_metrics.is_valid:
                    log.warning("Trial simulation returned invalid metrics for [%s]. Skipping arm.", action_type)
                    history.append(DiagnosticStep(
                        step=len(history),
                        action_type=action_type,
                        expression=trial_expr,
                        settings=trial_settings,
                        metrics=trial_metrics,
                        reward=-15.0,
                        description=f"INVALID: {action_desc}",
                    ))
                    continue

                trial_qualified, _ = evaluate_alpha_metrics(trial_metrics, self.config)
                trial_reward = calculate_rl_reward(trial_metrics, trial_qualified)

                log.info("Arm [%s] Result: Sharpe=%.2f, Fitness=%.2f, TO=%.2f%%, Ret=%.2f%% -> Reward=%.2f (Qualified=%s)",
                         action_type, trial_metrics.sharpe, trial_metrics.fitness, trial_metrics.turnover * 100,
                         trial_metrics.annualized_return * 100, trial_reward, trial_qualified)

                step_record = DiagnosticStep(
                    step=len(history),
                    action_type=action_type,
                    expression=trial_expr,
                    settings=trial_settings,
                    metrics=trial_metrics,
                    reward=trial_reward,
                    description=action_desc,
                )
                history.append(step_record)

                trial_candidate = OptionCandidate(
                    expression=trial_expr,
                    archetype_name=candidate.archetype_name,
                    hypothesis=f"{candidate.hypothesis} [Optimized: {action_type}]",
                    generation_source="diagnostic_optimizer",
                )
                self.store.record_evaluated_candidate(
                    trial_candidate,
                    stage=f"DIAG_R{round_idx}_{action_type}",
                    status="QUALIFIED" if trial_qualified else "OPTIMIZED",
                    metrics=trial_metrics,
                )
                trial_breakdown = {
                    "stage0": _stage0_validity_reward(trial_metrics),
                    "stage1": _stage1_hurdle_reward(trial_metrics),
                    "stage2": _stage2_efficiency_reward(trial_metrics),
                    "completion": 10.0 if trial_qualified else 0.0,
                }
                self.store.record_learning_memory(
                    trial_candidate,
                    trial_metrics,
                    reward=trial_reward,
                    optimization_steps=round_idx,
                    parent_expression=candidate.expression,
                    mutation_type=action_type,
                    status="QUALIFIED" if trial_qualified else "OPTIMIZED",
                    reward_breakdown=trial_breakdown,
                )

                if trial_reward > best_reward or trial_qualified:
                    best_reward = trial_reward
                    best_cand = trial_candidate
                    best_settings = trial_settings
                    best_metrics = trial_metrics
                    current_expr = trial_expr
                    current_settings = trial_settings
                    log.info("[*] NEW BEST ALPHA ACHIEVED! Reward=%.2f", best_reward)

                if trial_qualified:
                    round_qualified = True

            if round_qualified:
                log.info("[SUCCESS] Candidate fully passed all criteria in round %d!", round_idx)
                break

        final_passed, final_reason = evaluate_alpha_metrics(best_metrics, self.config)
        log.info("Diagnostic Optimization finished: Qualified=%s, Best Sharpe=%.2f, Best Fitness=%.2f (Reason: %s)",
                 final_passed, best_metrics.sharpe, best_metrics.fitness, final_reason)
        return best_cand, best_settings, best_metrics, final_passed, history
