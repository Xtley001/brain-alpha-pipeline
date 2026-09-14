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

CORE_ARCHETYPES = ["skew", "term_structure", "forward_basis", "pcr_flow", "breakeven"]


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

    def mark_evaluated(self, expression: str):
        self.evaluated_expressions.add(expression.strip())

    def is_evaluated(self, expression: str) -> bool:
        return expression.strip() in self.evaluated_expressions

    def _next_archetype(self) -> str:
        arch = CORE_ARCHETYPES[self._archetype_idx % len(CORE_ARCHETYPES)]
        self._archetype_idx += 1
        return arch

    def get_template_batch(self, count: int = 5) -> list[OptionCandidate]:
        """Tier 1: Deterministic seed template candidates."""
        batch: list[OptionCandidate] = []
        while self._template_queue and len(batch) < count:
            cand = self._template_queue.pop(0)
            if not self.is_evaluated(cand.expression):
                batch.append(cand)
        return batch

    def get_reasoning_batch(self, count: int = 5, archetype: Optional[str] = None) -> list[OptionCandidate]:
        """
        Tier 2: Knowledge-injected LLM reasoning tier.
        Injects targeted institutional cards, formula sketches, and pitfall warnings
        from Master Books 1-4. Chunks requests to at most 4 candidates per prompt
        and rotates across archetypes to ensure diversity and avoid prompt bloat/truncation.
        """
        candidates: list[OptionCandidate] = []
        chunk_size = 4
        needed = count

        while needed > 0 and len(candidates) < count:
            batch_n = min(chunk_size, needed)
            target_arch = archetype or self._next_archetype()
            kb_cards = self.kb.get_cards_for_archetype(target_arch, max_cards=3)
            catalog_summary = self.catalog.summarize_for_prompt()

            system_prompt = build_options_system_prompt(catalog_summary)
            prompt = build_reasoning_prompt(target_arch, kb_cards, n=batch_n)

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

    def get_procedural_batch(self, count: int = 10) -> list[OptionCandidate]:
        """
        Tier 4 Fail-Safe: Dynamic Procedural Options Generator.
        Generates mathematically valid, institutionally grounded options alphas across
        combinatoric parameter dimensions (tenors, windows, operators, neutralizations, gating).
        Guarantees that the pipeline never starves or evaluates 0 candidates even when
        static templates are exhausted and LLM providers are unavailable.
        """
        import math
        procedural: list[OptionCandidate] = []

        def _add(expr: str, arch: str, hyp: str):
            clean_expr = expr.strip()
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
        self, base_candidates: list[OptionCandidate], count_per_base: int = 2
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
        template_ratio: float = 0.4,
        seed_candidates_for_mutation: Optional[list[OptionCandidate]] = None,
    ) -> list[OptionCandidate]:
        """
        Assembles a balanced candidate batch across the generation tiers:
        1. Deterministic high-confidence templates (Tier 1)
        2. Tier 3 Mutations (if seeds provided)
        3. Tier 2 Knowledge-injected LLM reasoning (chunked & multi-archetype)
        4. Dynamic procedural generator fallback (Tier 4) guarantees non-empty batch
        """
        template_count = max(1, int(target_count * template_ratio))
        remaining = target_count - template_count

        candidates: list[OptionCandidate] = self.get_template_batch(template_count)

        # 1. Tier 3 Mutations (if seeds provided)
        if seed_candidates_for_mutation:
            mutations = self.get_mutation_batch(seed_candidates_for_mutation, count_per_base=2)
            candidates.extend(mutations[: max(1, remaining // 2)])

        # 2. Tier 2 LLM Reasoning (chunked across rotating archetypes)
        needed_reasoning = target_count - len(candidates)
        if needed_reasoning > 0:
            llm_candidates = self.get_reasoning_batch(needed_reasoning)
            candidates.extend(llm_candidates)

        # 3. Fallback top-up from static templates if any remain
        if len(candidates) < target_count:
            shortfall = target_count - len(candidates)
            extra_templates = self.get_template_batch(shortfall)
            candidates.extend(extra_templates)

        # 4. Fail-safe Tier 4: Dynamic procedural generator guarantees batch is never empty
        if len(candidates) < target_count:
            shortfall = target_count - len(candidates)
            log.info("Top-up: generating %d fresh procedural options candidates...", shortfall)
            procedural_candidates = self.get_procedural_batch(shortfall)
            candidates.extend(procedural_candidates)

        return candidates
