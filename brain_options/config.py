"""
Configuration for brain_options pipeline.
Loads secrets and settings strictly from environment variables.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


class MissingConfigError(RuntimeError):
    """Raised when an essential environment variable is missing."""


def _require(name: str) -> str:
    val = os.environ.get(name)
    if val is not None:
        val = val.strip()
    if not val:
        raise MissingConfigError(f"Required environment variable '{name}' is not set.")
    return val


def _optional(name: str, default: str | None = None) -> str | None:
    val = os.environ.get(name)
    if val is None or not val.strip():
        return default
    return val.strip()


@dataclass(frozen=True)
class OptionsConfig:
    # WorldQuant BRAIN credentials
    brain_username: str
    brain_password: str
    brain_max_concurrent_sims: int = 3

    # LLM API keys
    groq_keys: list[str] = field(default_factory=list)
    cerebras_keys: list[str] = field(default_factory=list)
    openrouter_keys: list[str] = field(default_factory=list)
    gemini_keys: list[str] = field(default_factory=list)

    # Telegram notification
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None

    # Pipeline thresholds
    stage0_min_sharpe: float = 0.35
    stage0_min_fitness: float = 0.20
    filter_min_sharpe: float = 1.25
    filter_min_fitness: float = 1.00
    filter_min_turnover: float = 0.01
    filter_max_turnover: float = 0.70
    max_pool_correlation: float = 0.70

    # Database connection
    database_url: str | None = None

    # Operational settings
    universe: str = "TOP3000"
    delay: int = 1
    max_candidates_per_run: int = 10
    run_time_budget_seconds: int = 480

    @classmethod
    def from_env(cls) -> OptionsConfig:
        username = _require("BRAIN_USERNAME")
        password = _require("BRAIN_PASSWORD")
        concurrent_sims = int(_optional("BRAIN_MAX_CONCURRENT_SIMS", "3") or "3")

        groq_keys = [k for k in [os.environ.get("GROQ_API_KEY_1"), os.environ.get("GROQ_API_KEY_2")] if k and k.strip()]
        cerebras_keys = [k for k in [os.environ.get("CEREBRAS_API_KEY_1"), os.environ.get("CEREBRAS_API_KEY_2")] if k and k.strip()]
        openrouter_keys = [
            k for k in [
                os.environ.get("OPENROUTER_API_KEY_1"),
                os.environ.get("OPENROUTER_API_KEY_2"),
                os.environ.get("OPENROUTER_API_KEY_3"),
                os.environ.get("OPENROUTER_API_KEY_4"),
            ] if k and k.strip()
        ]
        gemini_keys = [k for k in [os.environ.get("GEMINI_API_KEY_1"), os.environ.get("GEMINI_API_KEY_2")] if k and k.strip()]

        return cls(
            brain_username=username,
            brain_password=password,
            brain_max_concurrent_sims=concurrent_sims,
            groq_keys=groq_keys,
            cerebras_keys=cerebras_keys,
            openrouter_keys=openrouter_keys,
            gemini_keys=gemini_keys,
            telegram_bot_token=_optional("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=_optional("TELEGRAM_CHAT_ID"),
            database_url=_optional("DATABASE_URL"),
            stage0_min_sharpe=float(_optional("STAGE0_MIN_SHARPE", "0.35") or "0.35"),
            stage0_min_fitness=float(_optional("STAGE0_MIN_FITNESS", "0.20") or "0.20"),
            filter_min_sharpe=float(_optional("FILTER_MIN_SHARPE", "1.25") or "1.25"),
            filter_min_fitness=float(_optional("FILTER_MIN_FITNESS", "1.00") or "1.00"),
            filter_min_turnover=float(_optional("FILTER_MIN_TURNOVER", "0.01") or "0.01"),
            filter_max_turnover=float(_optional("FILTER_MAX_TURNOVER", "0.70") or "0.70"),
            max_pool_correlation=float(_optional("MAX_POOL_CORRELATION", "0.70") or "0.70"),
            universe=_optional("UNIVERSE", "TOP3000") or "TOP3000",
            delay=int(_optional("DELAY", "1") or "1"),
            max_candidates_per_run=int(_optional("MAX_CANDIDATES_PER_RUN", "10") or "10"),
            run_time_budget_seconds=int(_optional("RUN_TIME_BUDGET_SECONDS", "480") or "480"),
        )
