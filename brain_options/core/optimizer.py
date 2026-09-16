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


def calculate_rl_reward(metrics: SimMetrics, is_qualified: bool = False) -> float:
    """
    Scalar Reinforcement Learning reward function:
    Rewards high Sharpe and Fitness, severely penalizes excessive turnover,
    and grants a major completion bonus for qualification.
    """
    if not metrics.is_valid:
        return -5.0

    # Base reward components - heavily weighting fitness to clear the 1.0 threshold
    r = metrics.sharpe + 2.5 * min(metrics.fitness, 3.0)

    # Fitness hurdle bonus (the primary qualification bottleneck)
    if metrics.fitness >= 1.0:
        r += 2.0

    # Sharpe hurdle bonus
    if metrics.sharpe >= 1.25:
        r += 2.0

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

    # Qualification completion bonus
    if is_qualified:
        r += 10.0

    return round(r, 4)


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
    def wrap_decay_linear(expr: str, window: int = 15) -> str:
        """
        Wraps the inner ranking or signal with ts_decay_linear to reduce turnover
        and boost Fitness without altering cross-sectional logic.
        """
        expr = expr.strip()
        m = re.search(r"ts_decay_linear\((.+),\s*(\d+)\)", expr)
        if m:
            inner, old_w = m.group(1), m.group(2)
            new_w = max(window, min(30, int(old_w) + 7))
            return expr.replace(m.group(0), f"ts_decay_linear({inner}, {new_w})")

        m_gn = re.search(r"^group_neutralize\(rank\((.+)\),\s*([a-z_]+)\)$", expr)
        if m_gn:
            inner, group = m_gn.group(1), m_gn.group(2)
            return f"group_neutralize(rank(ts_decay_linear({inner}, {window})), {group})"

        m_tw = re.search(r"^trade_when\((.+),\s*group_neutralize\(rank\((.+)\),\s*([a-z_]+)\),\s*(-1)\)$", expr)
        if m_tw:
            cond, inner, group, exit_val = m_tw.group(1), m_tw.group(2), m_tw.group(3), m_tw.group(4)
            return f"trade_when({cond}, group_neutralize(rank(ts_decay_linear({inner}, {window})), {group}), {exit_val})"

        return f"group_neutralize(rank(ts_decay_linear({expr}, {window})), subindustry)"

    @staticmethod
    def wrap_decay_exp(expr: str, window: int = 12, factor: float = 0.20) -> str:
        """
        Wraps or replaces linear decay with ts_decay_exp_window(x, d, factor)
        to exponentially weight recent options signals and sharply reduce churn.
        """
        expr = expr.strip()
        m_exp = re.search(r"ts_decay_exp_window\((.+),\s*(\d+),\s*([0-9\.]+)\)", expr)
        if m_exp:
            inner, old_w, old_f = m_exp.group(1), m_exp.group(2), m_exp.group(3)
            return expr.replace(m_exp.group(0), f"ts_decay_exp_window({inner}, {min(28, int(old_w) + 5)}, {old_f})")

        m_lin = re.search(r"ts_decay_linear\((.+),\s*(\d+)\)", expr)
        if m_lin:
            inner, old_w = m_lin.group(1), m_lin.group(2)
            return expr.replace(m_lin.group(0), f"ts_decay_exp_window({inner}, {old_w}, {factor})")

        m_gn = re.search(r"^group_neutralize\(rank\((.+)\),\s*([a-z_]+)\)$", expr)
        if m_gn:
            inner, group = m_gn.group(1), m_gn.group(2)
            return f"group_neutralize(rank(ts_decay_exp_window({inner}, {window}, {factor})), {group})"

        return f"group_neutralize(rank(ts_decay_exp_window({expr}, {window}, {factor})), subindustry)"

    @staticmethod
    def wrap_zscore(expr: str, window: int = 20) -> str:
        """
        Replaces fast delta with ts_zscore(x, d) or normalizes signal
        to remove non-stationary volatility drift and extend holding periods.
        """
        expr = expr.strip()
        m_delta = re.search(r"ts_delta\((.+),\s*(\d+)\)", expr)
        if m_delta:
            inner = m_delta.group(1)
            return expr.replace(m_delta.group(0), f"ts_zscore({inner}, {window})")

        m_gn = re.search(r"^group_neutralize\(rank\((.+)\),\s*([a-z_]+)\)$", expr)
        if m_gn:
            inner, group = m_gn.group(1), m_gn.group(2)
            return f"group_neutralize(rank(ts_zscore({inner}, {window})), {group})"

        return f"ts_zscore({expr}, {window})"

    @staticmethod
    def inject_conviction_gate(expr: str, threshold: float = 0.38) -> str:
        """
        Wraps expression in trade_when(abs(rank(x) - 0.5) > threshold, signal, -1).
        The exit condition '-1' directs WorldQuant BRAIN to maintain prior positions
        when signal conviction is not extreme, dropping turnover by ~65-85%.
        """
        expr = expr.strip()
        if "trade_when" in expr:
            # Update existing rank conviction threshold if present
            if "abs(rank(" in expr and ") - 0.5) >" in expr:
                return re.sub(r">\s*0\.\d+", f"> {threshold:.2f}", expr)
            return expr

        m_gn = re.search(r"^group_neutralize\(rank\((.+)\),\s*([a-z_]+)\)$", expr)
        if m_gn:
            inner = m_gn.group(1)
            return f"trade_when(abs(rank({inner}) - 0.5) > {threshold:.2f}, {expr}, -1)"

        return f"trade_when(abs(rank({expr}) - 0.5) > {threshold:.2f}, {expr}, -1)"

    @staticmethod
    def upgrade_neutralization(expr: str, target_group: str = "subindustry") -> str:
        """Upgrades coarse group neutralization (e.g. sector) to granular subindustry."""
        new_expr = re.sub(r",\s*(sector|industry|market)\)", f", {target_group})", expr)
        return new_expr

    @staticmethod
    def inject_volume_gating(expr: str) -> str:
        """Wraps expression in trade_when(volume > adv20, ..., -1) to eliminate Leland drag."""
        if "trade_when" in expr:
            return expr
        return f"trade_when(volume > adv20, {expr}, -1)"

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

    @staticmethod
    def adjust_delta_window(expr: str, target_window: int = 20) -> str:
        """Increases ts_delta window (e.g. 5 -> 20) to capture monthly momentum and slow down churning."""
        m = re.search(r"ts_delta\((.+),\s*(\d+)\)", expr)
        if m:
            inner, old_w = m.group(1), int(m.group(2))
            new_w = target_window if old_w < target_window else old_w + 10
            return expr.replace(m.group(0), f"ts_delta({inner}, {new_w})")
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

        # Record initial in learning memory
        self.store.record_learning_memory(
            candidate,
            initial_metrics,
            reward=best_reward,
            optimization_steps=0,
            status="INITIAL_SCREEN",
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
                        "Exponential decay smoothing (factor=0.20) with 0.35 conviction gate",
                        self.inject_conviction_gate(self.wrap_decay_exp(current_expr, window=12, factor=0.20), threshold=0.35),
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
                self.store.record_learning_memory(
                    trial_candidate,
                    trial_metrics,
                    reward=trial_reward,
                    optimization_steps=round_idx,
                    parent_expression=candidate.expression,
                    mutation_type=action_type,
                    status="QUALIFIED" if trial_qualified else "OPTIMIZED",
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
        log.info("Diagnostic Optimization finished: Qualified=%s (Reason: %s)", final_passed, final_reason)
        return best_cand, best_settings, best_metrics, final_passed, history
