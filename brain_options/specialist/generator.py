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
from brain_options.specialist.dedup import ASTDeduplicator
from brain_options.specialist.kb import OptionsKnowledgeBase
from brain_options.specialist.templates import OptionCandidate, compile_fitness_invariant, generate_template_candidates
from brain_options.strategies import generate_modular_candidates
from brain_options.store.db import map_archetype_to_core

log = logging.getLogger("brain_options.generator")

import random

CORE_ARCHETYPES = [
    "term_structure", "skew", "pcr_flow", "breakeven", "forward_basis",
    "short_interest", "analyst_revisions", "hybrid_confluence", "supply_chain",
    "accruals_cashflow", "informed_short_demand", "extreme_tail_risk", "iv_lead_lag",
    "network_momentum", "formulaic_101", "institutional_13f_breadth",
    "insider_cluster_buying", "peavd_earnings_vol_drift", "jump_variance_moments",
    "patent_innovation_efficiency", "dynamic_short_squeeze", "order_flow_vpin",
    "gamma_pinning_clustering", "customer_supplier_cascades", "rd_capitalization_spillovers",
    "capex_asset_growth", "peavrp_volatility_premia", "realized_jump_intensity",
    "distance_to_default_debt", "macro_fomc_cpi_drift",
]


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
        self.deduplicator = ASTDeduplicator()
        self.evaluated_expressions: Set[str] = set()
        # Seed queue with both deterministic templates and all 30 modular strategy systems
        seen_hashes = set()
        queue: list[OptionCandidate] = []
        for c in generate_template_candidates() + generate_modular_candidates():
            h = self.deduplicator.hash(c.expression)
            if h not in seen_hashes:
                seen_hashes.add(h)
                queue.append(c)
        self._template_queue: list[OptionCandidate] = queue
        self._archetype_idx = 0

        # Multi-Armed Bandit prior weights across research domains (Heavy weights on 10 virgin strategies)
        self.archetype_priors: dict[str, float] = {
            "dynamic_short_squeeze": 0.12,
            "customer_supplier_cascades": 0.12,
            "order_flow_vpin": 0.10,
            "gamma_pinning_clustering": 0.10,
            "rd_capitalization_spillovers": 0.10,
            "capex_asset_growth": 0.10,
            "peavrp_volatility_premia": 0.10,
            "distance_to_default_debt": 0.10,
            "realized_jump_intensity": 0.08,
            "macro_fomc_cpi_drift": 0.08,
            "forward_basis": 0.08,
            "term_structure": 0.08,
            "pcr_flow": 0.08,
            "institutional_13f_breadth": 0.06,
            "insider_cluster_buying": 0.06,
            "peavd_earnings_vol_drift": 0.06,
            "jump_variance_moments": 0.05,
            "patent_innovation_efficiency": 0.05,
            "analyst_revisions": 0.04,
            "supply_chain": 0.04,
            "accruals_cashflow": 0.04,
            "extreme_tail_risk": 0.03,
            "informed_short_demand": 0.02,
            "iv_lead_lag": 0.02,
            "network_momentum": 0.02,
            "short_interest": 0.02,
            "formulaic_101": 0.01,
            "hybrid_confluence": 0.01,
            "breakeven": 0.00,
            "skew": 0.00,
        }

    def mark_evaluated(self, expression: str):
        cleaned = compile_fitness_invariant(expression.strip())
        self.evaluated_expressions.add(cleaned)
        self.deduplicator.add(cleaned)

    def is_evaluated(self, expression: str) -> bool:
        cleaned = compile_fitness_invariant(expression.strip())
        return cleaned in self.evaluated_expressions or self.deduplicator.is_duplicate(cleaned)

    def choose_archetype(
        self,
        archetype_summary: Optional[dict[str, dict[str, float]]] = None,
        saturated_archetypes: Optional[list[str]] = None,
    ) -> str:
        """
        Multi-Armed Bandit (MAB) archetype selection across all 15 strategies with empirical
        pass-rate weighting, repeat-collision penalties, and Dynamic Archetype Daily Caps.
        Applies a client-side hard ceiling: no single archetype family exceeds 30% of sampling share.
        """
        weights = dict(self.archetype_priors)

        if archetype_summary:
            for arch_key in CORE_ARCHETYPES:
                # Find matching entries in DB summary
                matched_pass_rate = 0.0
                recent_collisions = 0
                for db_arch, stats in archetype_summary.items():
                    if arch_key.lower() in db_arch.lower() or map_archetype_to_core(db_arch) == arch_key:
                        matched_pass_rate = max(matched_pass_rate, stats.get("pass_rate", 0.0))
                        recent_collisions += int(stats.get("corr_count", 0) or stats.get("correlated", 0))

                # Boost weight proportional to pass rate (exploration floor 0.04)
                weights[arch_key] = max(0.04, weights[arch_key] + matched_pass_rate * 0.5)

                # Priority 1: Multi-Armed Bandit repeat-collision penalty
                if recent_collisions >= 3:
                    weights[arch_key] *= 0.20
                elif recent_collisions >= 1:
                    weights[arch_key] *= 0.50

        # Dynamic Archetype Daily Caps (Pillar 1): Drop saturated archetypes to 0.02
        if saturated_archetypes:
            sat_cores = {map_archetype_to_core(s) for s in saturated_archetypes}
            for arch_key in CORE_ARCHETYPES:
                if arch_key in sat_cores or any(arch_key in s.lower() for s in saturated_archetypes):
                    weights[arch_key] = 0.02

        # Priority 1: Client-side family cap — no single archetype exceeds 30% of a batch
        total = sum(weights.values())
        clamped_weights = [min(weights[a] / total, 0.30) for a in CORE_ARCHETYPES]
        clamped_total = sum(clamped_weights)
        norm_weights = [w / clamped_total for w in clamped_weights]

        chosen = random.choices(CORE_ARCHETYPES, weights=norm_weights, k=1)[0]
        return chosen

    def get_template_batch(
        self,
        count: int = 5,
        archetype: Optional[str] = None,
        saturated_archetypes: Optional[list[str]] = None,
    ) -> list[OptionCandidate]:
        """Tier 1: Deterministic seed template candidates filtered by AST deduplication and saturation caps."""
        batch: list[OptionCandidate] = []
        batch_hashes: set[str] = set()
        tokens = [t.strip().lower() for t in archetype.split(",")] if archetype else []
        sat_cores = {map_archetype_to_core(s) for s in saturated_archetypes} if saturated_archetypes else set()

        i = 0
        while i < len(self._template_queue) and len(batch) < count:
            cand = self._template_queue[i]
            cand_core = map_archetype_to_core(cand.archetype_name)

            # Steer away from saturated daily channels if unsaturated ones remain
            if sat_cores and cand_core in sat_cores:
                i += 1
                continue

            if tokens:
                matches = any(
                    tok in cand.archetype_name.lower() or tok in cand.expression.lower() or tok == cand_core
                    for tok in tokens
                )
                if not matches:
                    i += 1
                    continue
            cand = self._template_queue.pop(i)
            if not self.is_evaluated(cand.expression):
                ast_h = self.deduplicator.hash(cand.expression)
                if ast_h not in batch_hashes:
                    batch_hashes.add(ast_h)
                    batch.append(cand)
        return batch

    def get_reasoning_batch(
        self,
        count: int = 5,
        archetype: Optional[str] = None,
        top_exemplars: Optional[list[dict]] = None,
        archetype_summary: Optional[dict] = None,
        saturated_archetypes: Optional[list[str]] = None,
    ) -> list[OptionCandidate]:
        """
        Tier 2: Knowledge-injected LLM reasoning tier.
        Injects targeted institutional cards, formula sketches, and top RL exemplars
        from Master Books 1-4 and PostgreSQL learning memory, actively avoiding saturated archetypes.
        """
        candidates: list[OptionCandidate] = []
        batch_hashes: set[str] = set()
        chunk_size = 4
        needed = count

        while needed > 0 and len(candidates) < count:
            batch_n = min(chunk_size, needed)
            target_arch = archetype or self.choose_archetype(
                archetype_summary=archetype_summary,
                saturated_archetypes=saturated_archetypes,
            )
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
                saturated_archetypes=saturated_archetypes,
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
                    ast_h = self.deduplicator.hash(expr)
                    if ast_h in batch_hashes:
                        continue
                    batch_hashes.add(ast_h)
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


    def get_procedural_batch(
        self,
        count: int = 10,
        archetype: Optional[str] = None,
        saturated_archetypes: Optional[list[str]] = None,
    ) -> list[OptionCandidate]:
        """
        Tier 4 Fail-Safe: Dynamic Procedural Options Generator.
        Generates mathematically valid, institutionally grounded options alphas across
        combinatoric parameter dimensions (tenors, windows, operators, neutralizations, gating).
        Guarantees that the pipeline never starves or evaluates 0 candidates even when
        static templates are exhausted and LLM providers are unavailable.
        """
        import math
        procedural: list[OptionCandidate] = []
        batch_hashes: set[str] = set()
        tokens = [t.strip().lower() for t in archetype.split(",")] if archetype else []
        sat_cores = {map_archetype_to_core(s) for s in saturated_archetypes} if saturated_archetypes else set()

        def _add(expr: str, arch: str, hyp: str):
            clean_expr = compile_fitness_invariant(expr.strip())
            arch_core = map_archetype_to_core(arch)
            if sat_cores and arch_core in sat_cores:
                return
            if tokens:
                matches = any(
                    tok in arch.lower() or tok in clean_expr.lower() or tok in hyp.lower() or tok == arch_core
                    for tok in tokens
                )
                if not matches:
                    return
            if not self.is_evaluated(clean_expr) and not any(c.expression == clean_expr for c in procedural):
                ast_h = self.deduplicator.hash(clean_expr)
                if ast_h in batch_hashes:
                    return
                batch_hashes.add(ast_h)
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

        # 8. Analyst Estimates & Earnings Revisions (Expanded Combinatorics)
        for win in [5, 10, 15, 20, 30, 45, 60, 90]:
            for dcy in [3, 5, 8, 10, 15, 20]:
                for grp in ["subindustry", "sector", "industry"]:
                    _add(
                        f"group_neutralize(rank(ts_decay_linear((est_eps - ts_delay(est_eps, {win})) / (abs(ts_delay(est_eps, {win})) + 0.01), {dcy})), {grp})",
                        "Analyst Revision Momentum",
                        f"Givoly & Lakonishok (1979): {win}d revision drift in consensus EPS with decay={dcy} demeaned by {grp}.",
                    )
        for win in [10, 20, 30, 60]:
            for dcy in [5, 10, 15, 20]:
                for grp in ["subindustry", "sector"]:
                    _add(
                        f"group_neutralize(rank(ts_decay_linear((est_sales - ts_delay(est_sales, {win})) / (abs(ts_delay(est_sales, {win})) + 0.01), {dcy})), {grp})",
                        "Sales Revision Momentum",
                        f"Consensus sales revision drift over {win}d with decay={dcy} demeaned by {grp}.",
                    )
        for win in [10, 20, 40, 60, 90, 120]:
            for dcy in [3, 5, 8, 10, 15, 20]:
                for grp in ["subindustry", "sector"]:
                    _add(
                        f"group_neutralize(rank(-ts_decay_linear(ts_zscore(std_dev_eps_est / (abs(est_eps) + 0.01), {win}), {dcy})), {grp})",
                        "Analyst Dispersion Fade",
                        f"Diether et al. (2002): Fade stocks with extreme {win}d analyst forecast dispersion with decay={dcy}.",
                    )
        for mom_win in [3, 5, 10, 15, 20]:
            for dcy in [3, 5, 8, 10, 15, 20]:
                for grp in ["subindustry", "sector", "industry"]:
                    _add(
                        f"trade_when(ts_delta(close, {mom_win}) > 0, group_neutralize(rank(ts_decay_linear((target_price - close) / close, {dcy})), {grp}), -1)",
                        "Price Target Implied Upside",
                        f"Fabozzi et al. (2010): Consensus price target upside conditioned on positive {mom_win}d price momentum (decay={dcy}).",
                    )
        for win in [60, 120, 252]:
            for dcy in [5, 10, 20]:
                for grp in ["subindustry", "sector"]:
                    _add(
                        f"group_neutralize(rank(ts_decay_linear((est_eps - ts_mean(est_eps, {win})) / (ts_std_dev(est_eps, {win}) + 0.01), {dcy})), {grp})",
                        "Normalized Analyst Consensus Drift",
                        f"Long-term {win}d normalized earnings revision drift with decay={dcy} demeaned by {grp}.",
                    )

        # 9. Short Interest & Securities Lending Flow (Vastly Expanded Multi-Speed Grid)
        for dcy in [3, 5, 8, 10, 15, 20, 30]:
            for grp in ["subindustry", "sector", "industry"]:
                _add(
                    f"group_neutralize(rank(-ts_decay_linear(borrow_fee * (short_interest / (float_shares + 0.001)), {dcy})), {grp})",
                    "Short Demand Borrow Surge",
                    f"Cohen et al. (2007): Elevated institutional borrow cost and high short interest with decay={dcy}.",
                )
                _add(
                    f"group_neutralize(rank(-ts_decay_linear(short_interest / (adv20 + 0.001), {dcy})), {grp})",
                    "Short Interest to Volume Ratio",
                    f"High short interest relative to 20d average daily volume with decay={dcy}.",
                )
        for delta_win in [3, 5, 10, 15]:
            for dcy in [5, 10, 15, 20]:
                for grp in ["subindustry", "sector"]:
                    _add(
                        f"group_neutralize(rank(-ts_decay_linear(ts_delta(borrow_fee, {delta_win}) * (short_interest / (float_shares + 0.001)), {dcy})), {grp})",
                        "Borrow Fee Acceleration Squeeze Risk",
                        f"Acceleration in institutional borrow cost over {delta_win}d weighted by short interest.",
                    )
                    _add(
                        f"group_neutralize(rank(-ts_decay_linear(ts_delta(short_interest / (float_shares + 0.001), {delta_win}), {dcy})), {grp})",
                        "Short Interest Flow Acceleration",
                        f"Rate of change in short interest as percentage of float over {delta_win}d.",
                    )
        for win in [20, 40, 60, 90, 126, 252]:
            for dcy in [5, 10, 15, 20]:
                for grp in ["subindustry", "sector", "industry"]:
                    _add(
                        f"group_neutralize(rank(-ts_decay_linear(ts_zscore(short_interest / (float_shares + 0.001), {win}), {dcy})), {grp})",
                        "De-Trended Short Interest Z-Score",
                        f"Rapach et al. (2016): De-trended {win}d short interest Z-score measures abnormal positioning (decay={dcy}).",
                    )
                    _add(
                        f"group_neutralize(rank(-ts_decay_linear(ts_rank(short_interest / (adv20 + 0.001), {win}), {dcy})), {grp})",
                        "Rolling Short Interest Percentile",
                        f"Rolling {win}d percentile rank of short interest relative to liquidity.",
                    )
        for win in [20, 60, 120]:
            for dcy in [5, 10, 20]:
                for grp in ["subindustry", "sector"]:
                    _add(
                        f"group_neutralize(rank(-ts_decay_linear(borrow_fee / (ts_mean(borrow_fee, {win}) + 0.01), {dcy})), {grp})",
                        "Relative Borrow Fee Dislocation",
                        f"Institutional borrow fee relative to its {win}d baseline mean.",
                    )
        for dtc in [2.0, 3.0, 4.0, 5.0, 6.0, 8.0]:
            for mom in [3, 5, 10, 20]:
                for dcy in [3, 5, 8, 10, 15, 20]:
                    for grp in ["subindustry", "sector"]:
                        _add(
                            f"trade_when((close > ts_mean(close, {mom * 2})) & (days_to_cover > {dtc}), group_neutralize(rank(ts_decay_linear(days_to_cover * ts_delta(close, {mom}), {dcy})), {grp}), -1)",
                            "Days-to-Cover Short Squeeze Breakout",
                            f"Asquith et al. (2005): Short squeeze breakout trigger on high days-to-cover names (decay={dcy}).",
                        )

        # 10. Cross-Asset Hybrids (Options + Shorts + Analyst Estimates - Multi-Speed)
        for tenor in [10, 20, 30, 60, 90, 120, 180]:
            sqrt_t = round(math.sqrt(tenor / 252.0), 4)
            for dcy in [3, 5, 8, 10, 15, 20]:
                for grp in ["subindustry", "sector", "industry"]:
                    _add(
                        f"group_neutralize(rank(-ts_decay_linear((implied_volatility_mean_skew_{tenor} * {sqrt_t}) * (borrow_fee + 1.0), {dcy})), {grp})",
                        "Volatility Smirk Borrow Fee Hybrid",
                        f"Cross-Asset Confluence: Confluence of steep {tenor}d downside put skew and high borrow fees (decay={dcy}).",
                    )
                    _add(
                        f"group_neutralize(rank(ts_decay_linear((target_price - close) / close - (implied_volatility_mean_skew_{tenor} * {sqrt_t}), {dcy})), {grp})",
                        "Revision vs Skew Divergence Hybrid",
                        f"Cross-Asset Divergence: Target price upside vs {tenor}d options downside hedging (decay={dcy}).",
                    )
                    _add(
                        f"group_neutralize(rank(-ts_decay_linear((pcr_vol_{tenor} / (pcr_oi_{tenor} + 0.001)) * (borrow_fee + 1.0), {dcy})), {grp})",
                        "PCR Borrow Fee Confluence Hybrid",
                        f"Surging {tenor}d put/call volume ratio paired with elevated borrow cost (decay={dcy}).",
                    )
                    _add(
                        f"group_neutralize(rank(-ts_decay_linear((implied_volatility_mean_{tenor} - ts_mean(implied_volatility_mean_{tenor}, 60)) * (short_interest / (float_shares + 0.001)), {dcy})), {grp})",
                        "IV Surge Short Interest Confluence",
                        f"Confluence of abnormal {tenor}d IV expansion and heavy short interest positioning.",
                    )

        # Fail-Safe Backfill: If the targeted archetype filter produced fewer than count candidates
        # (e.g. all specific variations evaluated), backfill from the broader cross-asset pool so workers NEVER starve
        if len(procedural) < count and tokens:
            log.info("Specialized procedural set yielded %d/%d candidates for '%s'. Backfilling from cross-asset pool...",
                     len(procedural), count, archetype)
            # Temporarily clear tokens to allow backfill
            saved_tokens = tokens
            tokens = []
            # Call Section 10 Cross-Asset and Section 2 Skew backfill
            for tenor in [10, 20, 30, 60, 90, 120]:
                sqrt_t = round(math.sqrt(tenor / 252.0), 4)
                for dcy in [5, 10, 15, 20]:
                    for grp in ["subindustry", "sector"]:
                        _add(
                            f"group_neutralize(rank(-ts_decay_linear((implied_volatility_mean_skew_{tenor} * {sqrt_t}) * (borrow_fee + 1.0), {dcy})), {grp})",
                            "Cross-Asset Backfill Hybrid",
                            f"Fail-safe backfill: Volatility skew and lending fee confluence (decay={dcy}).",
                        )
                        if len(procedural) >= count:
                            break
                    if len(procedural) >= count:
                        break
                if len(procedural) >= count:
                    break
            tokens = saved_tokens

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
        batch_hashes: set[str] = set()
        system_prompt = (
            "You are a WorldQuant BRAIN quantitative research assistant specializing in Equity Options alpha expressions. "
            "Your job is to apply systematic mathematical mutations to existing options alphas to explore adjacent parameter space.\n"
            "Return valid JSON array of objects with keys: expression, hypothesis, mutation_type."
        )

        for base in base_candidates:
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
                system_prompt=system_prompt,
                temperature=0.6,
            )
            if not raw_output:
                continue

            parsed = clean_json_array(raw_output)
            for item in parsed:
                expr = item.get("expression", "").strip()
                if not expr or self.is_evaluated(expr):
                    continue
                ast_h = self.deduplicator.hash(expr)
                if ast_h in batch_hashes:
                    continue
                batch_hashes.add(ast_h)
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
        saturated_archetypes: Optional[list[str]] = None,
    ) -> list[OptionCandidate]:
        """
        Assembles a balanced candidate batch across the generation tiers:
        1. Deterministic high-confidence templates (Tier 1)
        2. Tier 3 Mutations (seeded by top performing historical alphas from memory)
        3. Tier 2 Knowledge-injected LLM reasoning (conditioned on MAB weights, RL exemplars, and saturated exclusions)
        4. Dynamic procedural generator fallback (Tier 4) guarantees non-empty batch
        """
        template_count = max(1, int(target_count * template_ratio))
        remaining = target_count - template_count

        candidates: list[OptionCandidate] = self.get_template_batch(
            template_count,
            archetype=target_archetype,
            saturated_archetypes=saturated_archetypes,
        )

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
                saturated_archetypes=saturated_archetypes,
            )
            candidates.extend(llm_candidates)

        # 3. Fallback top-up from static templates if any remain
        if len(candidates) < target_count:
            shortfall = target_count - len(candidates)
            extra_templates = self.get_template_batch(
                shortfall,
                archetype=target_archetype,
                saturated_archetypes=saturated_archetypes,
            )
            candidates.extend(extra_templates)

        # 4. Fail-safe Tier 4: Dynamic procedural generator guarantees batch is never empty
        if len(candidates) < target_count:
            shortfall = target_count - len(candidates)
            log.info("Top-up: generating %d fresh procedural options candidates (%s)...", shortfall, target_archetype or "all")
            procedural_candidates = self.get_procedural_batch(
                shortfall,
                archetype=target_archetype,
                saturated_archetypes=saturated_archetypes,
            )
            candidates.extend(procedural_candidates)

        return candidates

