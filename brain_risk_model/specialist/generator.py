"""
Multi-tier Institutional Risk Model Candidate Generator.
Orchestrates:
1. Deterministic high-confidence templates (Tier 1)
2. Modular Strategy Sub-Systems (Tier 2)
3. Mechanical Mutation Tier with decay and factor sweeps (Tier 3)
"""
from __future__ import annotations

import logging
import random
from typing import Any, List, Optional, Set

from brain_risk_model.specialist.catalog import RiskModelCatalog
from brain_risk_model.specialist.dedup import RiskModelDeduplicator
from brain_risk_model.specialist.kb import RiskModelKnowledgeBase
from brain_risk_model.specialist.templates import (
    RiskModelCandidate,
    compile_risk_model_invariant,
    generate_template_candidates,
)
from brain_risk_model.strategies import generate_modular_candidates

log = logging.getLogger("brain_risk_model.specialist.generator")


class RiskModelGenerator:
    def __init__(
        self,
        kb: Optional[RiskModelKnowledgeBase] = None,
        catalog: Optional[RiskModelCatalog] = None,
    ):
        self.kb = kb or RiskModelKnowledgeBase()
        self.catalog = catalog or RiskModelCatalog()
        self.deduplicator = RiskModelDeduplicator()

        seen_hashes = set()
        queue: list[RiskModelCandidate] = []
        for c in generate_template_candidates() + generate_modular_candidates():
            h = self.deduplicator.hash(c.expression)
            if h not in seen_hashes:
                seen_hashes.add(h)
                queue.append(c)

        self._template_queue: list[RiskModelCandidate] = queue
        self._archetype_idx = 0

        # Multi-Armed Bandit prior weights across risk model archetypes
        self.archetype_priors: dict[str, float] = {
            "betting_against_beta": 0.30,
            "low_risk_engine": 0.20,
            "beta_divergence": 0.15,
            "surface_acceleration": 0.15,
            "gross_profitability": 0.10,
            "blitz_volatility": 0.10,
        }

    def generate_candidate(self) -> RiskModelCandidate:
        """Pulls next deterministic candidate or mutates an existing archetype."""
        if self._template_queue:
            return self._template_queue.pop(0)

        # Tier 3: Systematic parameter & operator mutation
        archetypes = list(self.archetype_priors.keys())
        weights = list(self.archetype_priors.values())
        chosen_archetype = random.choices(archetypes, weights=weights, k=1)[0]
        card = self.kb.get_card(chosen_archetype)
        base_expr = card.formula_sketch if card else "group_neutralize(rank(-ts_decay_linear(beta_last_60_days_spy, 12)), subindustry)"

        mutated_decay = random.choice([8, 10, 12, 14, 16, 20])
        mutated_group = random.choice(["subindustry", "sector", "industry"])
        mutated_expr = compile_risk_model_invariant(base_expr, default_decay=mutated_decay, default_group=mutated_group)

        return RiskModelCandidate(
            expression=mutated_expr,
            archetype=chosen_archetype,
            family="Mutated_Risk_Model",
            hypothesis=f"Systematic exploration of {chosen_archetype} with decay={mutated_decay} and group={mutated_group}.",
            universe=random.choice(["TOP3000", "TOP2000"]),
            neutralization=mutated_group.upper(),
            decay=mutated_decay,
        )

    def total_queued(self) -> int:
        return len(self._template_queue)
