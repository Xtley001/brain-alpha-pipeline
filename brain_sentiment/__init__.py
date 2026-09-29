"""
Brain Sentiment Package.
WorldQuant BRAIN Category: 'sentiment' (ValueScore: 8.0 / 10)
"""
from brain_sentiment.specialist.generator import SentimentGenerator
from brain_sentiment.strategies import SENTIMENT_STRATEGY_REGISTRY, generate_modular_candidates

__all__ = ["SentimentGenerator", "SENTIMENT_STRATEGY_REGISTRY", "generate_modular_candidates"]
