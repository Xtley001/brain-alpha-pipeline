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

    # Update 07: Gemini is no longer in the default provider chain (see
    # pipeline/llm/adapter.py docstring -- GCP billing lapse took its quota
    # to 0, and a provider that goes to zero the moment an invoice is late
    # isn't actually free). gemini_keys is kept here, still loaded from env
    # if present, purely so build_gemini_provider() can be wired back into
    # a chain later without touching Config again -- it just isn't read by
    # build_worker() right now.
    gemini_keys: list[str] = field(default_factory=list)
    groq_keys: list[str] = field(default_factory=list)
    # Update 09: Cerebras free tier (1M tokens/day, no card) -- second full
    # provider in the chain, not a fallback. Optional; empty list = skipped.
    cerebras_keys: list[str] = field(default_factory=list)
    # Update 07/08/09: OpenRouter free `:free`-tier, third leg of the chain.
    # Up to 4 accounts (Update 08). Optional -- an empty list just means
    # that step in the chain has 0 keys and falls through immediately.
    openrouter_keys: list[str] = field(default_factory=list)

    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None

    # Update 10 Item 9.3: optional ping URL for a third-party dead-man's-
    # switch / heartbeat-monitoring service (e.g. healthchecks.io,
    # Cronitor, UptimeRobot's heartbeat monitors -- any service that
    # alerts when it does NOT receive a ping within an expected window,
    # not one that polls a URL itself). Fixes the specific gap the
    # keepalive workflow left: keepalive.yml's job is itself a dead-man's-
    # switch (commits monthly so GitHub doesn't auto-disable run.yml's
    # schedule), but *that* switch has no external watchdog of its own --
    # if GitHub Actions' scheduler silently stops firing keepalive.yml (or
    # run.yml), or the repo gets auto-disabled for an unrelated reason,
    # nothing inside this repo can notice, because the thing that would
    # notice is the thing that went dark. A third-party service that
    # expects a ping every run and alerts on silence is independent of
    # GitHub Actions' own availability -- see SETUP.md's "before going
    # live" section for setup steps. None if unset, in which case the
    # ping is simply skipped (see RunReporter.safe_send_run_report's
    # sibling for the ping call site).
    healthcheck_ping_url: str | None = None

    queue_target_depth: int = 75
    stage0_min_fitness: float = 0.20
    stage0_min_sharpe: float = 0.35

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

    # Update 10 Item 9.2: previously bare module-level constants in
    # run_worker.py (MAX_CANDIDATE_ATTEMPTS, ORPHAN_RECLAIM_MINUTES,
    # MAX_CORRELATION) with no env var, inconsistent with every other
    # retry/tuning constant in this dataclass. Policy chosen: wire every
    # tuning-adjacent constant into Config uniformly, rather than carve out
    # an undocumented "these three are exempt" exception -- an
    # inconsistent mix of configurable-vs-not constants is exactly the
    # kind of thing that's easy to forget and hard to audit later.
    max_candidate_attempts: int = 3
    orphan_reclaim_minutes: int = 30
    max_correlation: float = 0.7

    @classmethod
    def from_env(cls, require_brain: bool = True, require_telegram: bool = True) -> "Config":
        gemini_keys = [
            k for k in (_optional("GEMINI_API_KEY_1"), _optional("GEMINI_API_KEY_2")) if k
        ]
        # Update 09: up to 4 Groq keys (was 2), matching the OpenRouter
        # pattern below -- 4 separate accounts, each with its own free-tier
        # quota, rotated in order by KeyedProvider.call() on 429/hard
        # failure (pipeline/llm/adapter.py). Groq is the primary provider
        # in the chain, so this is where more keys buys the most headroom.
        groq_keys = [
            k
            for k in (
                _optional("GROQ_API_KEY_1"),
                _optional("GROQ_API_KEY_2"),
                _optional("GROQ_API_KEY_3"),
                _optional("GROQ_API_KEY_4"),
            )
            if k
        ]
        # Update 09: Cerebras free tier (1M tokens/day, no card, resets
        # daily). One key is normally plenty given that daily budget for
        # this pipeline's call volume, but up to 4 accounts are supported
        # for consistency with the other two providers if ever needed.
        cerebras_keys = [
            k
            for k in (
                _optional("CEREBRAS_API_KEY_1"),
                _optional("CEREBRAS_API_KEY_2"),
                _optional("CEREBRAS_API_KEY_3"),
                _optional("CEREBRAS_API_KEY_4"),
            )
            if k
        ]
        # Update 08: up to 4 OpenRouter keys (4 separate accounts/emails).
        # KeyedProvider.call() already rotates through a provider's key list
        # in order and only advances to the next key on a 429/hard failure
        # (pipeline/llm/adapter.py) -- so this isn't new rotation logic, just
        # more keys in the list. Since OpenRouter's free tier is a per-account
        # daily cap (50 req/day, or 1000/day only after a *paid* $10 top-up --
        # see Update 07), each additional free account adds another ~50/day
        # of fallback headroom: key_1 serves until it 429s for the day, then
        # key_2, etc. This does NOT raise the 20-req/min cap, which is
        # per-account and enforced by OpenRouter regardless of how many keys
        # you rotate through -- four keys buys more requests *today*, not a
        # higher burst rate at any one moment.
        openrouter_keys = [
            k
            for k in (
                _optional("OPENROUTER_API_KEY_1"),
                _optional("OPENROUTER_API_KEY_2"),
                _optional("OPENROUTER_API_KEY_3"),
                _optional("OPENROUTER_API_KEY_4"),
            )
            if k
        ]
        return cls(
            database_url=_require("DATABASE_URL"),
            brain_username=(_require("BRAIN_USERNAME") if require_brain else _optional("BRAIN_USERNAME", "")),
            brain_password=(_require("BRAIN_PASSWORD") if require_brain else _optional("BRAIN_PASSWORD", "")),
            brain_max_concurrent_sims=int(_optional("BRAIN_MAX_CONCURRENT_SIMS", "3")),
            gemini_keys=gemini_keys,
            groq_keys=groq_keys,
            cerebras_keys=cerebras_keys,
            openrouter_keys=openrouter_keys,
            telegram_bot_token=(_require("TELEGRAM_BOT_TOKEN") if require_telegram else _optional("TELEGRAM_BOT_TOKEN")),
            telegram_chat_id=(_require("TELEGRAM_CHAT_ID") if require_telegram else _optional("TELEGRAM_CHAT_ID")),
            healthcheck_ping_url=_optional("HEALTHCHECK_PING_URL"),
            queue_target_depth=int(_optional("QUEUE_TARGET_DEPTH", "75")),
            stage0_min_fitness=float(_optional("STAGE0_MIN_FITNESS", "0.20")),
            stage0_min_sharpe=float(_optional("STAGE0_MIN_SHARPE", "0.35")),
            template_tier_max_share=float(_optional("TEMPLATE_TIER_MAX_SHARE", "0.5")),
            max_candidates_per_run=int(_optional("MAX_CANDIDATES_PER_RUN", "15")),
            run_time_budget_seconds=int(_optional("RUN_TIME_BUDGET_SECONDS", "480")),
            max_candidate_attempts=int(_optional("MAX_CANDIDATE_ATTEMPTS", "3")),
            orphan_reclaim_minutes=int(_optional("ORPHAN_RECLAIM_MINUTES", "30")),
            max_correlation=float(_optional("MAX_CORRELATION", "0.7")),
        )
