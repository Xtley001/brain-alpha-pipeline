"""
Central configuration. Every secret/credential comes from an environment
variable — never hardcode a key or password here or anywhere else in the
codebase.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


class MissingConfigError(RuntimeError):
    """Raised at startup when a required env var is missing.

    A missing var must fail loudly on
    startup, not partway through a run.
    """


def _require(name: str) -> str:
    val = os.environ.get(name)
    if val is not None:
        val = val.strip()
    if not val:
        raise MissingConfigError(f"Required environment variable {name} is not set")
    return val


def _optional(name: str, default: str | None = None) -> str | None:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip()


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

    # Update 05: the fixed 53-expression template pool almost always covers
    # a tick's whole `needed` gap on its own (queue_target_depth - depth is
    # rarely > 53 under a 10-minute cron cadence), which meant the LLM
    # reasoning/mechanical tiers effectively never ran -- so llm_usage never
    # got fresh rows and the heartbeat's "LLM key health" stayed frozen on
    # whatever the very first cold-start attempt logged, forever, even after
    # keys were rotated/fixed. This caps how much of `needed` the template
    # tier is allowed to fill per tick, guaranteeing the LLM tiers get
    # exercised (and llm_usage gets fresh, trustworthy rows) every tick the
    # queue needs topping up at all, not just on the rare tick the deficit
    # outruns the template pool.
    template_tier_max_share: float = 0.5

    # --- bounded-batch (cron) run tuning ---
    # How many candidates a single `run_once()` invocation will claim and
    # process (across possibly several BRAIN_MAX_CONCURRENT_SIMS-sized
    # batches) before exiting, regardless of how deep the queue is. Default
    # is 5x the concurrency cap: enough to make a single cron tick do real
    # work (per the handoff doc's "process more per tick" mitigation) without
    # letting one invocation run away and blow past the cron execution
    # window if BRAIN simulations turn out to be fast that tick.
    max_candidates_per_run: int = 15
    # Wall-clock ceiling (seconds) on the batch-processing portion of
    # `run_once()`. Render's free/cheap cron tier does not publish a hard
    # per-invocation timeout as of this writing (see refactor summary), so
    # this defaults conservatively short (8 min) to leave headroom under
    # any schedule interval of 10+ minutes and under Render's platform-wide
    # 12-hour cron kill switch. Any candidates left claimed-but-unprocessed
    # when the budget trips stay in 'running' and are picked up by
    # `reclaim_orphaned_running()` on a future run -- never silently lost.
    run_time_budget_seconds: int = 480

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
            template_tier_max_share=float(_optional("TEMPLATE_TIER_MAX_SHARE", "0.5")),
            max_candidates_per_run=int(_optional("MAX_CANDIDATES_PER_RUN", "15")),
            run_time_budget_seconds=int(_optional("RUN_TIME_BUDGET_SECONDS", "480")),
        )
