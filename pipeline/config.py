"""
Central configuration. Every secret/credential comes from an environment
variable — never hardcode a key or password here or anywhere else in the
codebase.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

# Loads variables from a local .env file into the process environment.
# On Render (and any environment where DATABASE_URL etc. are already set
# as real env vars), this is a no-op — it never overrides existing vars.
load_dotenv()


class MissingConfigError(RuntimeError):
    """Raised at startup when a required env var is missing.

    A missing var must fail loudly on
    startup, not partway through a run.
    """


def _require(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise MissingConfigError(f"Required environment variable {name} is not set")
    return val


def _optional(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


@dataclass(frozen=True)
class Config:
    database_url: str
    brain_username: str
    brain_password: str
    brain_max_concurrent_sims: int

    gemini_keys: list[str] = field(default_factory=list)
    groq_keys: list[str] = field(default_factory=list)

    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None

    queue_target_depth: int = 75
    stage0_min_fitness: float = 0.3
    stage0_min_sharpe: float = 0.5

    @classmethod
    def from_env(cls, require_brain: bool = True, require_telegram: bool = True) -> "Config":
        gemini_keys = [
            k for k in (_optional("GEMINI_API_KEY_1"), _optional("GEMINI_API_KEY_2")) if k
        ]
        groq_keys = [
            k for k in (_optional("GROQ_API_KEY_1"), _optional("GROQ_API_KEY_2")) if k
        ]
        return cls(
            database_url=_require("DATABASE_URL"),
            brain_username=(_require("BRAIN_USERNAME") if require_brain else _optional("BRAIN_USERNAME", "")),
            brain_password=(_require("BRAIN_PASSWORD") if require_brain else _optional("BRAIN_PASSWORD", "")),
            brain_max_concurrent_sims=int(_optional("BRAIN_MAX_CONCURRENT_SIMS", "3")),
            gemini_keys=gemini_keys,
            groq_keys=groq_keys,
            telegram_bot_token=(_require("TELEGRAM_BOT_TOKEN") if require_telegram else _optional("TELEGRAM_BOT_TOKEN")),
            telegram_chat_id=(_require("TELEGRAM_CHAT_ID") if require_telegram else _optional("TELEGRAM_CHAT_ID")),
            queue_target_depth=int(_optional("QUEUE_TARGET_DEPTH", "75")),
            stage0_min_fitness=float(_optional("STAGE0_MIN_FITNESS", "0.3")),
            stage0_min_sharpe=float(_optional("STAGE0_MIN_SHARPE", "0.5")),
        )