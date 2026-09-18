"""
Multi-tier Options Candidate Generator.
Orchestrates:
1. Deterministic high-confidence templates (Tier 1)
2. Quantitative LLM Reasoning Tier with Options Knowledge Base injection (Tier 2)
3. Mechanical Mutation Tier for systematic alpha variations (Tier 3)
"""
from __future__ import annotations

import logging
from typing import List, Optional, Set
from brain_options.llm.adapter import LLMAdapter, clean_json_array
from brain_options.llm.prompts import (
    OPTIONS_REASONING_PROMPT,
    OPTIONS_SYSTEM_PROMPT,
    build_mechanical_mutation_prompt,
    build_options_system_prompt,
    build_reasoning_prompt,
)
from brain_options.specialist.catalog import OptionsCatalog
from brain_options.specialist.kb import OptionsKnowledgeBase
from brain_options.specialist.templates import OptionCandidate, generate_template_candidates

log = logging.getLogger("brain_options.generator")

import random

CORE_ARCHETYPES = ["breakeven", "skew", "term_structure", "forward_basis", "pcr_flow"]


class OptionsGenerator:
    def __init__(
        self,
        llm_adapter: LLMAdapter,
        kb: Optional[OptionsKnowledgeBase] = None,
        catalog: Optional[OptionsCatalog] = None,
    ):
        self.llm_adapter = llm_adapter
        self.kb = kb or OptionsKnowledgeBase()
        self.catalog = catalog or OptionsCatalog()
        self.evaluated_expressions: Set[str] = set()
        self._template_queue: list[OptionCandidate] = generate_template_candidates()
        self._archetype_idx = 0
        # Multi-Armed Bandit prior weights based on empirical WorldQuant options dynamics
        self.archetype_priors: dict[str, float] = {
            "breakeven": 0.40,
            "skew": 0.35,
            "term_structure": 0.15,
            "forward_basis": 0.05,
            "pcr_flow": 0.05,
        }

    def mark_evaluated(self, expression: str):
        self.evaluated_expressions.add(expression.strip())

    def is_evaluated(self, expression: str) -> bool:
        return expression.strip() in self.evaluated_expressions

    def choose_archetype(self, archetype_summary: Optional[dict[str, dict[str, float]]] = None) -> str:
        """
        Multi-Armed Bandit (MAB) archetype selection with empirical pass-rate weighting.
        Dynamically shifts generation budget toward high-yield archetypes (Breakeven & Skew)
        and preserves small exploration probability for lower-yield families.
        """
        weights = dict(self.archetype_priors)

        if archetype_summary:
            for arch_key in CORE_ARCHETYPES:
                # Find matching entries in DB summary
                matched_pass_rate = 0.0
                for db_arch, stats in archetype_summary.items():
                    if arch_key.lower() in db_arch.lower():
                        matched_pass_rate = max(matched_pass_rate, stats.get("pass_rate", 0.0))
                # Boost weight proportional to pass rate (exploration floor 0.05)
                weights[arch_key] = max(0.05, weights[arch_key] + matched_pass_rate * 0.5)

        total = sum(weights.values())
        norm_weights = [weights[a] / total for a in CORE_ARCHETYPES]
        chosen = random.choices(CORE_ARCHETYPES, weights=norm_weights, k=1)[0]
        return chosen

    def get_template_batch(self, count: int = 5, archetype: Optional[str] = None) -> list[OptionCandidate]:
        """Tier 1: Deterministic seed template candidates."""
        batch: list[OptionCandidate] = []
        tokens = [t.strip().lower() for t in archetype.split(",")] if archetype else []

        i = 0
        while i < len(self._template_queue) and len(batch) < count:
            cand = self._template_queue[i]
            if tokens:
                matches = any(
                    tok in cand.archetype_name.lower() or tok in cand.expression.lower()
                    for tok in tokens
                )
                if not matches:
                    i += 1
                    continue
            cand = self._template_queue.pop(i)
            if not self.is_evaluated(cand.expression):
                batch.append(cand)
        return batch

    def get_reasoning_batch(
        self,
        count: int = 5,
        archetype: Optional[str] = None,
        top_exemplars: Optional[list[dict]] = None,
        archetype_summary: Optional[dict] = None,
    ) -> list[OptionCandidate]:
        """
        Tier 2: Knowledge-injected LLM reasoning tier.
        Injects targeted institutional cards, formula sketches, and top RL exemplars
        from Master Books 1-4 and the PostgreSQL learning memory.
        """
        candidates: list[OptionCandidate] = []
        chunk_size = 4
        needed = count

        while needed > 0 and len(candidates) < count:
            batch_n = min(chunk_size, needed)
            target_arch = archetype or self.choose_archetype(archetype_summary)
            if "," in target_arch:
                arch_choices = [t.strip() for t in target_arch.split(",") if t.strip()]
                target_arch = random.choice(arch_choices)
            kb_cards = self.kb.get_cards_for_archetype(target_arch, max_cards=3)
            catalog_summary = self.catalog.summarize_for_prompt()

            system_prompt = build_options_system_prompt(catalog_summary)
            prompt = build_reasoning_prompt(
                target_arch,
                kb_cards,
                n=batch_n,
                top_exemplars=top_exemplars,
            )

            raw_output = self.llm_adapter.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.7,
            )
            if raw_output:
                parsed = clean_json_array(raw_output)
                for item in parsed:
                    expr = item.get("expression", "").strip()
                    if not expr or self.is_evaluated(expr):
                        continue
                    candidates.append(
                        OptionCandidate(
                            expression=expr,
                            archetype_name=item.get("archetype", target_arch.title()),
                            hypothesis=item.get("hypothesis", f"Knowledge-guided reasoning on {target_arch}"),
                            generation_source="llm_reasoning",
                        )
                    )
                    if len(candidates) >= count:
                        break

            needed -= batch_n

        return candidates


    def get_procedural_batch(self, count: int = 10, archetype: Optional[str] = None) -> list[OptionCandidate]:
        """
        Tier 4 Fail-Safe: Dynamic Procedural Options Generator.
        Generates mathematically valid, institutionally grounded options alphas across
        combinatoric parameter dimensions (tenors, windows, operators, neutralizations, gating).
        Guarantees that the pipeline never starves or evaluates 0 candidates even when
        static templates are exhausted and LLM providers are unavailable.
        """
        import math
        procedural: list[OptionCandidate] = []
        tokens = [t.strip().lower() for t in archetype.split(",")] if archetype else []

        def _add(expr: str, arch: str, hyp: str):
            clean_expr = expr.strip()
            if tokens:
                matches = any(
                    tok in arch.lower() or tok in clean_expr.lower() or tok in hyp.lower()
                    for tok in tokens
                )
                if not matches:
                    return
            if not self.is_evaluated(clean_expr) and not any(c.expression == clean_expr for c in procedural):
                procedural.append(
                    OptionCandidate(
                        expression=clean_expr,
                        archetype_name=arch,
                        hypothesis=hyp,
                        generation_source="procedural",
                    )
                )

        # 1. Forward Basis Spreads & Momentum across expanded tenors & neutralizations
        for tenor in [10, 20, 30, 60, 90, 120, 150, 180, 270, 360]:
            for grp in ["sector", "subindustry", "industry"]:
                _add(
                    f"group_neutralize(rank((forward_price_{tenor} - close) / close), {grp})",
                    "Forward Basis Spread",
                    f"Synthetic forward basis at {tenor}d tenor demeaned by {grp} captures institutional drift.",
                )
            for window in [2, 3, 5, 10, 15, 20]:
                for grp in ["sector", "subindustry"]:
                    _add(
                        f"group_neutralize(rank(ts_delta((forward_price_{tenor} - close) / close, {window})), {grp})",
                        "Forward Basis Velocity",
                        f"Acceleration in {tenor}d forward basis over {window}d demeaned by {grp} indicates institutional positioning.",
                    )
                    _add(
                        f"group_neutralize(rank(ts_zscore((forward_price_{tenor} - close) / close, {window * 2})), {grp})",
                        "Forward Basis Z-Score",
                        f"Normalized deviation of {tenor}d forward basis against {window * 2}d mean captures pricing misalignments.",
                    )

        # 2. Sqrt(T) Normalized Volatility Skew Shifts & Accelerations
        for tenor in [10, 20, 30, 60, 90, 120, 150, 180]:
            sqrt_t = round(math.sqrt(tenor / 252.0), 4)
            for window in [2, 3, 5, 8, 10, 15]:
                for grp in ["sector", "subindustry"]:
                    _add(
                        f"group_neutralize(rank(-ts_delta(implied_volatility_mean_skew_{tenor} * {sqrt_t}, {window})), {grp})",
                        "Sqrt-T Normalized Skew Acceleration",
                        f"Decay-normalized sqrt(T) downside skew shift at {tenor}d over {window}d isolates tail risk repricing.",
                    )
                    _add(
                        f"group_neutralize(rank(-ts_zscore(implied_volatility_mean_skew_{tenor} * {sqrt_t}, {window * 3})), {grp})",
                        "Sqrt-T Normalized Skew Z-Score",
                        f"Decay-normalized sqrt(T) skew z-score at {tenor}d over {window * 3}d flags extreme tail crowding.",
                    )

        # 3. Cross-Tenor Skew Curvature & Calendar Spreads
        for t1, t2 in [(10, 30), (20, 60), (30, 90), (60, 180)]:
            sq1 = round(math.sqrt(t1 / 252.0), 4)
            sq2 = round(math.sqrt(t2 / 252.0), 4)
            for grp in ["sector", "subindustry"]:
                _add(
                    f"group_neutralize(rank(-(implied_volatility_mean_skew_{t1} * {sq1} - implied_volatility_mean_skew_{t2} * {sq2})), {grp})",
                    "Cross-Tenor Skew Curvature Spread",
                    f"Calendar skew differential between {t1}d and {t2}d tenors demeaned by {grp}.",
                )
                _add(
                    f"group_neutralize(rank(-ts_delta(implied_volatility_mean_skew_{t1} * {sq1} - implied_volatility_mean_skew_{t2} * {sq2}, 5)), {grp})",
                    "Cross-Tenor Skew Spread Velocity",
                    f"5-day acceleration in calendar skew differential between {t1}d and {t2}d tenors.",
                )

        # 4. Volatility Term Structure Slopes & Inversions
        for t1, t2 in [(10, 30), (20, 60), (30, 90), (60, 180), (90, 360)]:
            for grp in ["sector", "subindustry"]:
                _add(
                    f"group_neutralize(rank(-(implied_volatility_mean_{t1} / (implied_volatility_mean_{t2} + 0.001) - 1.0)), {grp})",
                    "Volatility Term Structure Slope",
                    f"Fade extreme slope inversion between {t1}d and {t2}d ATM implied volatility demeaned by {grp}.",
                )

        # 5. PCR Smart-Money Flow to Open Interest Surge with Gating
        for tenor in [10, 20, 30, 60, 90, 120]:
            for window in [3, 5, 10, 15, 20]:
                for grp in ["subindustry", "sector"]:
                    _add(
                        f"group_neutralize(rank(-ts_rank(pcr_vol_{tenor} / (pcr_oi_{tenor} + 0.001), {window})), {grp})",
                        "PCR Volume-to-OI Flow Surge",
                        f"Surge in {tenor}d put volume relative to open interest over {window}d flags institutional positioning.",
                    )
                    _add(
                        f"trade_when(volume > adv20, group_neutralize(rank(-ts_delta(pcr_vol_{tenor} / (pcr_oi_{tenor} + 0.001), {window})), {grp}), -1)",
                        "Liquidity-Gated PCR Flow Acceleration",
                        f"Acceleration in {tenor}d put volume-to-OI flow over {window}d conditioned on liquid trading volume.",
                    )

        # 6. Call Breakeven Hurdle Rates & Repricing
        for tenor in [10, 20, 30, 60, 90, 120, 180]:
            for grp in ["sector", "subindustry"]:
                _add(
                    f"group_neutralize(rank((call_breakeven_{tenor} - close) / close), {grp})",
                    "Call Breakeven Hurdle Spread",
                    f"OI-weighted call breakeven hurdle rate at {tenor}d tenor demeaned by {grp}.",
                )
                for window in [2, 3, 5, 10]:
                    _add(
                        f"group_neutralize(rank(ts_delta((call_breakeven_{tenor} - close) / close, {window})), {grp})",
                        "Call Breakeven Hurdle Acceleration",
                        f"Acceleration in {tenor}d call breakeven hurdle rate over {window}d signals target repricing.",
                    )

        # 7. Variance Risk Premium (IV vs RV) with Jensen-Debiasing & Entry Gating
        for tenor, win, mult in [(10, 10, 15.65), (20, 20, 16.53), (30, 30, 15.87), (60, 60, 15.87)]:
            for grp in ["sector", "subindustry"]:
                _add(
                    f"group_neutralize(rank(-(implied_volatility_mean_{tenor} - ts_std_dev(returns, {win}) * {mult})), {grp})",
                    "Jensen-Debiased Variance Risk Premium",
                    f"Short over-priced {tenor}d IV relative to debiased rolling {win}d realized volatility.",
                )
                _add(
                    f"trade_when(abs(ts_zscore(implied_volatility_mean_{tenor} - ts_std_dev(returns, {win}) * {mult}, 40)) > 0.75, group_neutralize(rank(-(implied_volatility_mean_{tenor} - ts_std_dev(returns, {win}) * {mult})), {grp}), -1)",
                    "Threshold-Gated VRP Mean Reversion",
                    f"Enter {tenor}d variance risk premium only when crossing 0.75 SD mean-reversion threshold.",
                )

        return procedural[:count]

    def get_mutation_batch(
        self,
        base_candidates: list[OptionCandidate],
        count_per_base: int = 2,
        top_exemplars: Optional[list[dict]] = None,
    ) -> list[OptionCandidate]:
        """
        Tier 3: Mechanical mutation tier.
        Generates structured operator, tenor, and neutralization variations of base candidates.
        """
        if not base_candidates:
            return []

        mutations: list[OptionCandidate] = []
        for base in base_candidates[:3]:  # mutate up to 3 top candidates
            kb_cards = self.kb.get_cards_for_archetype(base.archetype_name, max_cards=2)
            prompt = build_mechanical_mutation_prompt(
                candidate_expression=base.expression,
                candidate_hypothesis=base.hypothesis,
                kb_cards=kb_cards,
                n=count_per_base,
                top_exemplars=top_exemplars,
            )
            raw_output = self.llm_adapter.generate(
                prompt=prompt,
                system_prompt=OPTIONS_SYSTEM_PROMPT,
                temperature=0.6,
            )
            if not raw_output:
                continue

            parsed = clean_json_array(raw_output)
            for item in parsed:
                expr = item.get("expression", "").strip()
                if not expr or self.is_evaluated(expr):
                    continue
                mutations.append(
                    OptionCandidate(
                        expression=expr,
                        archetype_name=f"Mutation({base.archetype_name})",
                        hypothesis=item.get("hypothesis", f"Mutation of {base.expression}"),
                        generation_source="llm_mechanical",
                    )
                )
        return mutations

    def get_next_batch(
        self,
        target_count: int = 10,
        template_ratio: float = 0.3,
        seed_candidates_for_mutation: Optional[list[OptionCandidate]] = None,
        top_exemplars: Optional[list[dict]] = None,
        archetype_summary: Optional[dict] = None,
        target_archetype: Optional[str] = None,
    ) -> list[OptionCandidate]:
        """
        Assembles a balanced candidate batch across the generation tiers:
        1. Deterministic high-confidence templates (Tier 1)
        2. Tier 3 Mutations (seeded by top performing historical alphas from memory)
        3. Tier 2 Knowledge-injected LLM reasoning (conditioned on MAB weights and RL exemplars)
        4. Dynamic procedural generator fallback (Tier 4) guarantees non-empty batch
        """
        template_count = max(1, int(target_count * template_ratio))
        remaining = target_count - template_count

        candidates: list[OptionCandidate] = self.get_template_batch(template_count, archetype=target_archetype)

        # 1. Tier 3 Mutations: if no explicit seeds, auto-seed from top exemplars in memory
        active_seeds = seed_candidates_for_mutation
        if not active_seeds and top_exemplars:
            active_seeds = [
                OptionCandidate(
                    expression=ex["expression"],
                    archetype_name=ex.get("archetype", "TopExemplar"),
                    hypothesis=ex.get("hypothesis", "Top performing alpha from learning memory"),
                    generation_source="learning_memory_seed",
                )
                for ex in top_exemplars[:3]
                if ex.get("expression")
            ]
            if target_archetype:
                tokens = [t.strip().lower() for t in target_archetype.split(",")]
                active_seeds = [
                    s for s in active_seeds
                    if any(t in s.archetype_name.lower() or t in s.expression.lower() for t in tokens)
                ]

        if active_seeds:
            mutation_slots = max(1, remaining // 2)
            mutations = self.get_mutation_batch(active_seeds, count_per_base=2, top_exemplars=top_exemplars)
            candidates.extend(mutations[:mutation_slots])

        # 2. Tier 2 LLM Reasoning (conditioned on target archetype or bandit weights)
        needed_reasoning = target_count - len(candidates)
        if needed_reasoning > 0:
            llm_candidates = self.get_reasoning_batch(
                needed_reasoning,
                archetype=target_archetype,
                top_exemplars=top_exemplars,
                archetype_summary=archetype_summary,
            )
            candidates.extend(llm_candidates)

        # 3. Fallback top-up from static templates if any remain
        if len(candidates) < target_count:
            shortfall = target_count - len(candidates)
            extra_templates = self.get_template_batch(shortfall, archetype=target_archetype)
            candidates.extend(extra_templates)

        # 4. Fail-safe Tier 4: Dynamic procedural generator guarantees batch is never empty
        if len(candidates) < target_count:
            shortfall = target_count - len(candidates)
            log.info("Top-up: generating %d fresh procedural options candidates (%s)...", shortfall, target_archetype or "all")
            procedural_candidates = self.get_procedural_batch(shortfall, archetype=target_archetype)
            candidates.extend(procedural_candidates)

        return candidates

