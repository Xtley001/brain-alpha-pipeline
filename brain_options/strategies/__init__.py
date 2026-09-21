"""
Modular Strategy Sub-System Registry for WorldQuant BRAIN Pipeline.
Provides auto-discovery, instantiation, and candidate aggregation across all 8 quantitative strategy modules.
"""
from __future__ import annotations

from typing import Dict, List, Optional
from brain_options.specialist.templates import OptionCandidate
from brain_options.strategies.base import BaseStrategy
from brain_options.strategies.term_structure import TermStructureStrategy
from brain_options.strategies.skew import SkewStrategy
from brain_options.strategies.pcr_flow import PCRFlowStrategy
from brain_options.strategies.breakeven import BreakevenStrategy
from brain_options.strategies.forward_basis import ForwardBasisStrategy
from brain_options.strategies.short_interest import ShortInterestStrategy
from brain_options.strategies.analyst_revisions import AnalystRevisionsStrategy
from brain_options.strategies.hybrid_confluence import HybridConfluenceStrategy
from brain_options.strategies.supply_chain import SupplyChainStrategy
from brain_options.strategies.accruals_cashflow import AccrualsCashflowStrategy
from brain_options.strategies.informed_short_demand import InformedShortDemandStrategy
from brain_options.strategies.extreme_tail_risk import ExtremeTailRiskStrategy
from brain_options.strategies.iv_lead_lag import IvLeadLagStrategy
from brain_options.strategies.network_momentum import NetworkMomentumStrategy
from brain_options.strategies.formulaic_101 import Formulaic101Strategy

# Standard Strategy Registry (15 Modular Quantitative Strategies)
STRATEGY_REGISTRY: dict[str, BaseStrategy] = {
    "term_structure": TermStructureStrategy(),
    "skew": SkewStrategy(),
    "pcr_flow": PCRFlowStrategy(),
    "breakeven": BreakevenStrategy(),
    "forward_basis": ForwardBasisStrategy(),
    "short_interest": ShortInterestStrategy(),
    "analyst_revisions": AnalystRevisionsStrategy(),
    "hybrid_confluence": HybridConfluenceStrategy(),
    "supply_chain": SupplyChainStrategy(),
    "accruals_cashflow": AccrualsCashflowStrategy(),
    "informed_short_demand": InformedShortDemandStrategy(),
    "extreme_tail_risk": ExtremeTailRiskStrategy(),
    "iv_lead_lag": IvLeadLagStrategy(),
    "network_momentum": NetworkMomentumStrategy(),
    "formulaic_101": Formulaic101Strategy(),
}


def get_strategy(strategy_id: str) -> Optional[BaseStrategy]:
    """Retrieve a strategy instance by its identifier."""
    return STRATEGY_REGISTRY.get(strategy_id.lower().strip())


def list_strategy_ids() -> list[str]:
    """Returns all registered strategy IDs."""
    return list(STRATEGY_REGISTRY.keys())


def generate_modular_candidates(
    strategy_filter: Optional[str | list[str]] = None,
) -> list[OptionCandidate]:
    """
    Aggregates candidate expressions from the requested strategies.
    If strategy_filter is None or 'all', aggregates from all 8 strategies.
    """
    if strategy_filter is None or strategy_filter == "" or strategy_filter == "all":
        target_ids = list(STRATEGY_REGISTRY.keys())
    elif isinstance(strategy_filter, str):
        target_ids = [s.strip().lower() for s in strategy_filter.split(",") if s.strip()]
    else:
        target_ids = [s.strip().lower() for s in strategy_filter if s.strip()]

    candidates: list[OptionCandidate] = []
    for sid in target_ids:
        strat = STRATEGY_REGISTRY.get(sid)
        if strat:
            candidates.extend(strat.generate_candidates())

    return candidates
