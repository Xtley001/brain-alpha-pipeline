"""
Configuration module for Risk Model Alpha Pipeline.
WorldQuant BRAIN Category: model (ValueScore: 7.0 / 10 | Ultra-Low Crowding)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class RiskModelConfig:
    category: str = "model"
    value_score: float = 7.0
    default_universes: list[str] = field(default_factory=lambda: ["TOP3000", "TOP2000", "TOP1000"])
    default_neutralizations: list[str] = field(default_factory=lambda: ["SUBINDUSTRY", "SECTOR", "INDUSTRY"])
    default_decays: list[int] = field(default_factory=lambda: [10, 12, 15, 20])
    
    # Fitness thresholds
    min_sharpe: float = 1.25
    min_fitness: float = 1.00
    max_turnover: float = 0.25
    target_turnover: float = 0.10
    max_drawdown: float = 0.35
    
    # Sub-universe Sharpe pass
    require_sub_universe_pass: bool = True
