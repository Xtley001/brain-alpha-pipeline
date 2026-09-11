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
        from Master Books 1-4 for the designated archetype.
        """
        target_arch = archetype or self._next_archetype()
        kb_cards = self.kb.get_cards_for_archetype(target_arch, max_cards=3)
        catalog_summary = self.catalog.summarize_for_prompt()

        system_prompt = build_options_system_prompt(catalog_summary)
        prompt = build_reasoning_prompt(target_arch, kb_cards, n=count)

        raw_output = self.llm_adapter.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.7,
        )
        if not raw_output:
            return []

        parsed = clean_json_array(raw_output)
        candidates: list[OptionCandidate] = []
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
        return candidates

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
        Assembles a balanced candidate batch across the 3 generation tiers.
        """
        template_count = max(1, int(target_count * template_ratio))
        remaining = target_count - template_count

        candidates: list[OptionCandidate] = self.get_template_batch(template_count)

        # 1. Tier 3 Mutations (if seeds provided)
        if seed_candidates_for_mutation:
            mutations = self.get_mutation_batch(seed_candidates_for_mutation, count_per_base=2)
            candidates.extend(mutations[: max(1, remaining // 2)])

        # 2. Tier 2 LLM Reasoning
        needed_reasoning = target_count - len(candidates)
        if needed_reasoning > 0:
            llm_candidates = self.get_reasoning_batch(needed_reasoning)
            candidates.extend(llm_candidates)

        # 3. Fallback top-up from templates if LLM returned fewer candidates
        if len(candidates) < target_count:
            shortfall = target_count - len(candidates)
            extra_templates = self.get_template_batch(shortfall)
            candidates.extend(extra_templates)

        return candidates
