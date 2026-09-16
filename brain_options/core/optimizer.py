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
    def wrap_decay_linear(expr: str, window: int = 8) -> str:
        """
        Wraps the inner ranking or signal with ts_decay_linear to reduce turnover
        and boost Fitness without altering cross-sectional logic.
        """
        expr = expr.strip()
        m = re.search(r"ts_decay_linear\((.+),\s*(\d+)\)", expr)
        if m:
            inner, old_w = m.group(1), m.group(2)
            new_w = max(window, min(25, int(old_w) + 5))
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
    def wrap_decay_exp(expr: str, window: int = 10, factor: float = 0.25) -> str:
        """
        Wraps or replaces linear decay with ts_decay_exp_window(x, d, factor)
        to exponentially weight recent options signals and sharply reduce churn.
        """
        expr = expr.strip()
        m_exp = re.search(r"ts_decay_exp_window\((.+),\s*(\d+),\s*([0-9\.]+)\)", expr)
        if m_exp:
            inner, old_w, old_f = m_exp.group(1), m_exp.group(2), m_exp.group(3)
            return expr.replace(m_exp.group(0), f"ts_decay_exp_window({inner}, {min(25, int(old_w) + 5)}, {old_f})")

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
    def inject_conviction_gate(expr: str, threshold: float = 0.15) -> str:
        """
        Wraps expression in trade_when(abs(rank(x) - 0.5) > threshold, signal, -1).
        The exit condition '-1' directs WorldQuant BRAIN to maintain prior positions
        when signal conviction is not extreme, dropping turnover by ~50%.
        """
        expr = expr.strip()
        if "trade_when" in expr:
            return expr

        m_gn = re.search(r"^group_neutralize\(rank\((.+)\),\s*([a-z_]+)\)$", expr)
        if m_gn:
            inner = m_gn.group(1)
            return f"trade_when(abs(rank({inner}) - 0.5) > {threshold}, {expr}, -1)"

        return f"trade_when(volume > adv20, {expr}, -1)"

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
                    # Round 1: Signal Smoothing & Lookback Expansion
                    arms.append((
                        "DELTA_EXPANSION_D16",
                        "Expanded delta lookback to 20 with decay=16 to tame daily churn",
                        self.adjust_delta_window(current_expr, 20),
                        SimSettings(universe=current_settings.universe, delay=current_settings.delay, decay=16, neutralization="SUBINDUSTRY", truncation=0.01),
                    ))
                    arms.append((
                        "EXP_DECAY_SMOOTH",
                        "Wrapped signal in ts_decay_exp_window(x, 10, 0.25) with decay=18",
                        self.wrap_decay_exp(current_expr, window=10, factor=0.25),
                        SimSettings(universe=current_settings.universe, delay=current_settings.delay, decay=18, neutralization="SUBINDUSTRY", truncation=0.01),
                    ))
                    arms.append((
                        "SMOOTH_DECAY_D20",
                        "Deep linear smoothing with decay=20 and truncation=0.01",
                        self.wrap_decay_linear(current_expr, window=10),
                        SimSettings(universe=current_settings.universe, delay=current_settings.delay, decay=20, neutralization="SUBINDUSTRY", truncation=0.01),
                    ))

                elif round_idx == 2:
                    # Round 2: Z-score Normalization & Conviction Gating
                    arms.append((
                        "ZSCORE_NORMALIZATION",
                        "Transformed signal to rolling 20-day ts_zscore with decay=16",
                        self.wrap_zscore(current_expr, window=20),
                        SimSettings(universe=current_settings.universe, delay=current_settings.delay, decay=16, neutralization="SUBINDUSTRY", truncation=0.01),
                    ))
                    arms.append((
                        "CONVICTION_GATE_HOLD",
                        "Gated positions on extreme rank conviction (trade_when -1 holds position)",
                        self.inject_conviction_gate(current_expr, threshold=0.15),
                        SimSettings(universe=current_settings.universe, delay=current_settings.delay, decay=14, neutralization="SUBINDUSTRY", truncation=0.01),
                    ))
                    arms.append((
                        "VOLUME_ADV_GATE",
                        "Filtered trades by volume > adv20 to eliminate illiquid drag",
                        self.inject_volume_gating(current_expr),
                        SimSettings(universe=current_settings.universe, delay=current_settings.delay, decay=16, neutralization="SUBINDUSTRY", truncation=0.01),
                    ))

                elif round_idx == 3:
                    # Round 3: High-conviction combined with Z-score & Tenor migration
                    arms.append((
                        "CONVICTION_ZSCORE",
                        "Combined 20-day Z-score with conviction gating and decay=18",
                        self.inject_conviction_gate(self.wrap_zscore(current_expr, 20), threshold=0.18),
                        SimSettings(universe=current_settings.universe, delay=current_settings.delay, decay=18, neutralization="SUBINDUSTRY", truncation=0.01),
                    ))
                    arms.append((
                        "SHIFT_TENOR_SMOOTH",
                        "Shifted option maturity tenor and applied exponential decay",
                        self.shift_tenor(self.wrap_decay_exp(current_expr, 12, 0.20)),
                        SimSettings(universe=current_settings.universe, delay=current_settings.delay, decay=18, neutralization="SUBINDUSTRY", truncation=0.01),
                    ))
                    arms.append((
                        "DEEP_DELTA_D24",
                        "Extended delta lookback to 25 with decay=24 and truncation=0.01",
                        self.adjust_delta_window(current_expr, 25),
                        SimSettings(universe=current_settings.universe, delay=current_settings.delay, decay=24, neutralization="SUBINDUSTRY", truncation=0.01),
                    ))

                else:
                    # Rounds 4-6: Fine calibration of truncation, decay and conviction
                    for d, trunc, thresh in [(16, 0.01, 0.20), (22, 0.01, 0.15), (26, 0.05, 0.12)]:
                        arms.append((
                            f"CALIBRATION_D{d}_T{int(trunc*100)}",
                            f"Fine calibration: decay={d}, truncation={trunc}, threshold={thresh}",
                            self.inject_conviction_gate(current_expr, threshold=thresh) if "trade_when" not in current_expr else current_expr,
                            SimSettings(universe=current_settings.universe, delay=current_settings.delay, decay=d, neutralization="SUBINDUSTRY", truncation=trunc),
                        ))

            # DEFICIT: Sharpe is borderline (0.35 - 1.25)
            elif best_metrics.sharpe < self.config.filter_min_sharpe:
                if "subindustry" not in current_expr.lower():
                    arms.append((
                        "UPGRADE_TO_SUBINDUSTRY",
                        "Escalated neutralization to subindustry",
                        self.upgrade_neutralization(current_expr, "subindustry"),
                        SimSettings(universe=current_settings.universe, delay=current_settings.delay, decay=12, neutralization="SUBINDUSTRY", truncation=0.01),
                    ))
                arms.append((
                    "SHIFT_TENOR",
                    "Migrated option tenor forward to test deeper derivative maturity",
                    self.shift_tenor(current_expr),
                    SimSettings(universe=current_settings.universe, delay=current_settings.delay, decay=14, neutralization="SUBINDUSTRY", truncation=0.01),
                ))
                arms.append((
                    "ZSCORE_TRANSFORM",
                    "Transformed raw signal into 20-day rolling Z-score to boost signal-to-noise",
                    self.wrap_zscore(current_expr, 20),
                    SimSettings(universe=current_settings.universe, delay=current_settings.delay, decay=14, neutralization="SUBINDUSTRY", truncation=0.01),
                ))

            # DEFICIT: General fine-tuning
            else:
                for d in (14, 18, 22):
                    arms.append((
                        f"CALIBRATION_DECAY_{d}",
                        f"Standard decay calibration ({d}) with subindustry and truncation 0.01",
                        current_expr,
                        SimSettings(universe=current_settings.universe, delay=current_settings.delay, decay=d, neutralization="SUBINDUSTRY", truncation=0.01),
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
                        self.inject_conviction_gate(current_expr, threshold=0.15),
                        SimSettings(universe=current_settings.universe, delay=current_settings.delay, decay=current_settings.decay, neutralization="SUBINDUSTRY", truncation=0.01),
                    )]
                else:
                    nudge_d = current_settings.decay + 4
                    unique_arms = [(
                        "DECAY_NUDGE",
                        f"Nudged decay from {current_settings.decay} to {nudge_d}",
                        current_expr,
                        SimSettings(universe=current_settings.universe, delay=current_settings.delay, decay=nudge_d, neutralization="SUBINDUSTRY", truncation=0.01),
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
