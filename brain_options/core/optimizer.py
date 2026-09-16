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

    # Base reward components
    r = metrics.sharpe + 1.5 * min(metrics.fitness, 2.0)

    # Turnover penalty (punish > 70% or extreme < 1%)
    if metrics.turnover > 0.70:
        r -= 3.0 * (metrics.turnover - 0.70)
    elif metrics.turnover < 0.01:
        r -= 2.0 * (0.01 - metrics.turnover)

    # Leland drag penalty: high turnover with low return
    if metrics.turnover > 0.40 and metrics.annualized_return < 0.04:
        r -= 1.0

    # Qualification bonus
    if is_qualified:
        r += 5.0

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
    def wrap_decay_linear(expr: str, window: int = 5) -> str:
        """
        Wraps the inner ranking or signal with ts_decay_linear to reduce turnover
        and boost Fitness without altering cross-sectional logic.
        """
        expr = expr.strip()
        # Case 1: If already contains ts_decay_linear, adjust the window
        m = re.search(r"ts_decay_linear\((.+),\s*(\d+)\)", expr)
        if m:
            inner, old_w = m.group(1), m.group(2)
            new_w = min(15, int(old_w) + 5)
            return expr.replace(m.group(0), f"ts_decay_linear({inner}, {new_w})")

        # Case 2: group_neutralize(rank(X), G) -> group_neutralize(rank(ts_decay_linear(X, window)), G)
        m_gn = re.search(r"^group_neutralize\(rank\((.+)\),\s*([a-z_]+)\)$", expr)
        if m_gn:
            inner, group = m_gn.group(1), m_gn.group(2)
            return f"group_neutralize(rank(ts_decay_linear({inner}, {window})), {group})"

        # Case 3: trade_when(C, group_neutralize(rank(X), G), -1)
        m_tw = re.search(r"^trade_when\((.+),\s*group_neutralize\(rank\((.+)\),\s*([a-z_]+)\),\s*(-1)\)$", expr)
        if m_tw:
            cond, inner, group, exit_val = m_tw.group(1), m_tw.group(2), m_tw.group(3), m_tw.group(4)
            return f"trade_when({cond}, group_neutralize(rank(ts_decay_linear({inner}, {window})), {group}), {exit_val})"

        # Fallback: wrap outer
        return f"group_neutralize(rank(ts_decay_linear({expr}, {window})), subindustry)"

    @staticmethod
    def upgrade_neutralization(expr: str, target_group: str = "subindustry") -> str:
        """Upgrades coarse group neutralization (e.g. sector) to granular subindustry."""
        # Replace , sector) or , industry) with , subindustry)
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
    def adjust_delta_window(expr: str) -> str:
        """Increases ts_delta window (3 -> 5 -> 10) to slow down fast signals."""
        m = re.search(r"ts_delta\((.+),\s*(\d+)\)", expr)
        if m:
            inner, old_w = m.group(1), int(m.group(2))
            new_w = 10 if old_w <= 5 else 15
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

            # Deficit A: High Turnover dragging down Fitness
            if best_metrics.turnover > 0.35 or ("Fitness" in reason and best_metrics.sharpe >= 1.0):
                # Arm 1: Mild linear decay smoothing (window 5) + decay 14
                arms.append((
                    "SMOOTH_DECAY_5_D14",
                    "Wrapped signal in ts_decay_linear(x, 5) with decay=14",
                    self.wrap_decay_linear(current_expr, window=5),
                    SimSettings(universe=current_settings.universe, delay=current_settings.delay, decay=14, neutralization=current_settings.neutralization),
                ))
                # Arm 2: Deep linear decay smoothing (window 10) + delta window expansion + decay 18 + subindustry
                arms.append((
                    "DEEP_SMOOTH_D18_SUBIND",
                    "Extended smoothing window to 10 with decay=18 and subindustry",
                    self.adjust_delta_window(self.wrap_decay_linear(current_expr, window=10)),
                    SimSettings(universe=current_settings.universe, delay=current_settings.delay, decay=18, neutralization="SUBINDUSTRY"),
                ))
                # Arm 3: High sim decay (decay 22) + subindustry
                arms.append((
                    "HIGH_SIM_DECAY_22",
                    "Set decay=22 to tame residual trading velocity",
                    current_expr,
                    SimSettings(universe=current_settings.universe, delay=current_settings.delay, decay=22, neutralization="SUBINDUSTRY"),
                ))

            # Deficit B: Sharpe is borderline (0.80 - 1.25)
            elif best_metrics.sharpe < self.config.filter_min_sharpe:
                if "subindustry" not in current_expr.lower():
                    arms.append((
                        "UPGRADE_TO_SUBINDUSTRY",
                        "Escalated neutralization to subindustry",
                        self.upgrade_neutralization(current_expr, "subindustry"),
                        SimSettings(universe=current_settings.universe, delay=current_settings.delay, decay=12, neutralization="SUBINDUSTRY"),
                    ))
                if "trade_when" not in current_expr:
                    arms.append((
                        "INJECT_VOLUME_GATE",
                        "Gated by volume > adv20 to avoid illiquid small-cap whipsaws",
                        self.inject_volume_gating(current_expr),
                        SimSettings(universe=current_settings.universe, delay=current_settings.delay, decay=10, neutralization=current_settings.neutralization),
                    ))
                arms.append((
                    "SHIFT_TENOR",
                    "Migrated option tenor forward to test deeper derivative maturity",
                    self.shift_tenor(current_expr),
                    SimSettings(universe=current_settings.universe, delay=current_settings.delay, decay=12, neutralization=current_settings.neutralization),
                ))

            # Deficit C: Default fallback sweep
            else:
                for d in (12, 16, 20):
                    arms.append((
                        f"CALIBRATION_DECAY_{d}",
                        f"Standard decay calibration ({d}) with subindustry",
                        current_expr,
                        SimSettings(universe=current_settings.universe, delay=current_settings.delay, decay=d, neutralization="SUBINDUSTRY"),
                    ))

            # Filter out duplicate arms against current history
            evaluated_pairs = {(step.expression, step.settings.decay, step.settings.neutralization) for step in history}
            unique_arms = [
                arm for arm in arms
                if (arm[2], arm[3].decay, arm[3].neutralization) not in evaluated_pairs
            ]

            if not unique_arms:
                nudge_d = current_settings.decay + 4
                unique_arms = [(
                    "DECAY_NUDGE",
                    f"Nudged decay from {current_settings.decay} to {nudge_d}",
                    current_expr,
                    SimSettings(universe=current_settings.universe, delay=current_settings.delay, decay=nudge_d, neutralization="SUBINDUSTRY"),
                )]

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
