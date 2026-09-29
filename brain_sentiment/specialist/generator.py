"""
Multi-tier Institutional Sentiment Candidate Generator.
Orchestrates:
1. Deterministic high-confidence templates (Tier 1)
2. Modular Strategy Sub-Systems (Tier 2)
3. Mechanical Mutation Tier with decay and operator sweeps (Tier 3)
"""
from __future__ import annotations

import logging
import random
from typing import Any, List, Optional, Set

from brain_sentiment.specialist.catalog import SentimentCatalog
from brain_sentiment.specialist.dedup import SentimentDeduplicator
from brain_sentiment.specialist.kb import SentimentKnowledgeBase
from brain_sentiment.specialist.templates import (
    SentimentCandidate,
    compile_sentiment_invariant,
    generate_template_candidates,
)
from brain_sentiment.strategies import generate_modular_candidates

log = logging.getLogger("brain_sentiment.specialist.generator")


class SentimentGenerator:
    def __init__(
        self,
        kb: Optional[SentimentKnowledgeBase] = None,
        catalog: Optional[SentimentCatalog] = None,
        db: Optional[Any] = None,
    ):
        self.kb = kb or SentimentKnowledgeBase()
        self.catalog = catalog or SentimentCatalog()
        self.deduplicator = SentimentDeduplicator()
        self.db = db

        seen_hashes = set()
        queue: list[SentimentCandidate] = []
        for c in generate_template_candidates() + generate_modular_candidates():
            h = self.deduplicator.hash(c.expression)
            if h not in seen_hashes:
                seen_hashes.add(h)
                queue.append(c)

        self._template_queue: list[SentimentCandidate] = queue
        self._archetype_idx = 0

        # Multi-Armed Bandit prior weights across sentiment archetypes
        self.archetype_priors: dict[str, float] = {
            "pead_earnings_drift": 0.30,
            "sue_earnings_surprise": 0.25,
            "dual_target_rec_confluence": 0.15,
            "net_target_price_revisions": 0.15,
            "analyst_revision_dispersion": 0.10,
            "media_attention_buzz": 0.05,
        }

    def get_current_weights(self) -> dict[str, float]:
        """Calculates dynamic MAB sampling weights from RL state or returns base priors."""
        if self.db and hasattr(self.db, "get_empirical_archetype_weights"):
            try:
                return self.db.get_empirical_archetype_weights(
                    list(self.archetype_priors.keys()),
                    self.archetype_priors,
                )
            except Exception as e:
                log.warning("Failed to fetch empirical weights, falling back to priors: %s", e)
        return dict(self.archetype_priors)

    def generate_candidate(self) -> SentimentCandidate:
        """Pulls next deterministic candidate or mutates an existing archetype."""
        if self._template_queue:
            return self._template_queue.pop(0)

        # Tier 3: Systematic parameter & operator mutation
        weights_dict = self.get_current_weights()
        archetypes = list(weights_dict.keys())
        weights = list(weights_dict.values())
        chosen_archetype = random.choices(archetypes, weights=weights, k=1)[0]
        card = self.kb.get_card(chosen_archetype)
        base_expr = card.formula_sketch if card else "group_neutralize(rank(ts_decay_linear(snt1_d1_netearningsrevision, 12)), subindustry)"

        mutated_decay = random.choice([8, 10, 12, 14, 16, 20])
        mutated_group = random.choice(["subindustry", "sector", "industry"])
        mutated_expr = compile_sentiment_invariant(base_expr, default_decay=mutated_decay, default_group=mutated_group)

        return SentimentCandidate(
            expression=mutated_expr,
            archetype=chosen_archetype,
            family="Mutated_Sentiment",
            hypothesis=f"Systematic exploration of {chosen_archetype} with decay={mutated_decay} and group={mutated_group}.",
            universe=random.choice(["TOP3000", "TOP2000"]),
            neutralization=mutated_group.upper(),
            decay=mutated_decay,
        )

    def total_queued(self) -> int:
        return len(self._template_queue)
