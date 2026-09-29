"""
Brain Systematic Risk & Factor Models Package.
WorldQuant BRAIN Category: 'model' (ValueScore: 7.0 / 10)
"""
from brain_risk_model.specialist.generator import RiskModelGenerator
from brain_risk_model.strategies import RISK_STRATEGY_REGISTRY, generate_modular_candidates

__all__ = ["RiskModelGenerator", "RISK_STRATEGY_REGISTRY", "generate_modular_candidates"]
