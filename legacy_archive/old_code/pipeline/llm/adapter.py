"""
LLM provider adapter with key rotation, per the LLM-providers-and-keys design
§5. Falls back to the next key in a provider's list on quota-exhaustion
errors (429 / RESOURCE_EXHAUSTED), not just hard failures, and logs every
attempt (success or failure) via an injected `usage_logger` so
`llm_usage.key_label` records exactly which key was used -- required by
the audit checklist's LLM key-rotation section.

Real network clients (openai-for-groq/openrouter, google-genai) are imported
lazily inside the functions that need them, so this module -- and its tests
-- never require those packages or network access just to exercise the
rotation logic. Tests inject fake `call_fn` callables instead.

--- Update 07: provider chain, Gemini dropped from the active path ---
2026-08-24's llm_usage.error_text audit turned up 4 independent failures,
not 1:
  - gemini/key_1: 404 "no longer available to new users" -- a project
    provisioning quirk, separate from 2.5 Flash's general Oct 2026 sunset.
  - gemini/key_2: 429 RESOURCE_EXHAUSTED with quota_limit_value: '0' -- an
    outstanding GCP billing balance put this project's Generative Language
    API quota at zero. Confirmed via direct curl that the key itself still
    authenticates fine once billing is caught up -- this is an account
    problem, not a code problem, and it doesn't resolve by retrying.
  - groq/key_1: 401 invalid_api_key -- dead key, unrelated to the above.
  - groq/key_2: 404 model_not_found -- fixed by Update 06's model swap.
Per-tier decision going forward: Gemini requires GCP billing to stay
current to be usable at all, which makes it the opposite of "free" the
moment a balance goes unpaid. Rather than keep a provider in the primary
chain that silently goes to a hard 0-quota the instant billing lapses,
Gemini is left wired (the client/call_fn stays below, tested, ready) but
out of the default chain build_default_llm_adapter() constructs. Re-adding
it later, once/if billing is sorted, is one line in run_worker.py.

Groq is the primary provider. Cerebras (Update 09) is added as a second
full-weight provider, not a fallback afterthought — a genuinely free,
no-card 1M-tokens/day tier is real daily volume, not an emergency valve.
OpenRouter's `:free`-suffixed models stay in the chain as the third leg:
still free/no-card, but request-capped rather than token-capped (20
req/min, 50 req/day *per account* -- see build_default_llm_adapter()'s
docstring for why multiple accounts change the daily math but not the
per-minute one). All three providers rotate through their own key list
first (Update 05/06's per-key rotation, unchanged), and a whole provider
is only skipped once every key on it has 429'd or hard-failed for that
call -- there's no "try them all in parallel and see who answers first"
mode, deliberately: a single generation call only needs one successful
response, so firing the same prompt at 3 providers at once would just
burn free quota on 2 wasted calls for every 1 you keep. Sequential
fallback already gives "when one hits its limit, the next one picks up
the very same call" -- that's what QuotaExhausted bubbling through the
chain does.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Optional, Protocol

# --- Update 06/07/09: model IDs, centralized ---
# Update 06: both provider chains went fully dark on 2026-08-24 because
# these were hardcoded literals scattered across reasoning_call()/
# mechanical_call() and had silently drifted out from under us:
#   - gemini-2.5-flash: 404 NOT_FOUND ("no longer available to new users
#     ... use models/gemini-3.6-flash"). Google's deprecations page lists
#     2.5 Flash's *shutdown* as no earlier than Oct 16 2026, but "no longer
#     available to NEW projects/keys" is a separate, earlier cutover than
#     the shutdown date.

#   - llama-3.3-70b-versatile / llama-3.1-8b-instant: Groq announced
#     deprecation of both on 2026-06-17 with an August 2026 sunset; we're
#     past that now, hence the flat 404 model_not_found on every call.
# Pulled out to named constants so the *next* forced migration (there will
# be one) is a one-line change instead of a grep.
GEMINI_MODEL = "gemini-3.6-flash"  # kept for the not-wired-in-by-default Gemini provider, see module docstring
GROQ_REASONING_MODEL = "openai/gpt-oss-120b"  # replaces llama-3.3-70b-versatile
GROQ_MECHANICAL_MODEL = "openai/gpt-oss-20b"  # replaces llama-3.1-8b-instant

# Update 09: Cerebras free tier -- no card, ~1M tokens/day (resets daily,
# doesn't expire), OpenAI-compatible at https://api.cerebras.ai/v1. Request
# rate is low (published figures range ~5-30 req/min depending on source/
# account -- Cerebras doesn't publish one canonical number, check the
# Limits page in your own dashboard), but this pipeline only ever needs a
# couple of short calls per 10-minute tick, so the *token* budget is what
# actually matters here, and 1M/day dwarfs what a tick needs. Free-tier
# catalog is currently just gpt-oss-120b and zai-glm-4.7 -- same model
# family as the Groq default, which also makes it a clean drop-in.
CEREBRAS_REASONING_MODEL = "gpt-oss-120b"
CEREBRAS_MECHANICAL_MODEL = "gpt-oss-120b"

# Update 07: OpenRouter free-tier fallback models. `:free` suffix = $0/token
# on OpenRouter; this roster rotates (models get delisted with little
# notice), so treat these as "known-good as of 2026-08-24", not permanent --
# check https://openrouter.ai/models?max_price=0 if this tier starts
# QuotaExhausted-ing more than Groq/Cerebras do.
OPENROUTER_REASONING_MODEL = "meta-llama/llama-3.3-70b-instruct:free"
OPENROUTER_MECHANICAL_MODEL = "meta-llama/llama-3.1-8b-instruct:free"


class QuotaExhausted(Exception):
    """Raised when every configured key for a provider is exhausted."""


class RateLimitError(Exception):
    """Raised by a client call to signal 429 / RESOURCE_EXHAUSTED specifically,
    as opposed to some other hard failure. Real client wrappers should catch
    provider-specific exceptions and re-raise as this where applicable."""

    def __init__(self, message: str, retry_after: Optional[float] = None):
        super().__init__(message)
        self.retry_after = retry_after


UsageLogger = Callable[[str, str, str, bool, Optional[str]], None]
# (provider, key_label, tier, succeeded, error_text) -> None


def _noop_logger(provider: str, key_label: str, tier: str, succeeded: bool, error_text: Optional[str]) -> None:
    pass


class LLMClient(Protocol):
    def __call__(self, prompt: str, model: str) -> str: ...


@dataclass
class KeyedProvider:
    """A provider with an ordered list of (key_label, key_value) pairs and a
    call function that takes (prompt, model, key_value) -> str, raising
    RateLimitError on quota exhaustion for that specific key."""

    name: str
    keys: list  # list[(key_label, key_value)]
    call_fn: Callable[[str, str, str], str]

    def call(self, prompt: str, model: str, tier: str, usage_logger: UsageLogger, sleep_fn=time.sleep) -> str:
        last_err: Optional[Exception] = None
        for key_label, key_value in self.keys:
            if not key_value:
                continue
            try:
                result = self.call_fn(prompt, model, key_value)
                usage_logger(self.name, key_label, tier, True, None)
                return result
            except RateLimitError as e:
                last_err = e
                usage_logger(self.name, key_label, tier, False, str(e))
                # Only a rate limit is transient/self-resolving -- worth a
                # short backoff before trying the next key. A hard failure
                # (bad key, auth error, wrong model name) will never
                # resolve itself, so paying a fixed sleep for it on every
                # key, every call, is pure wasted wall-clock (Update 05).
                sleep_fn(e.retry_after if e.retry_after else 2.0)
                continue
            except Exception as e:  # noqa: BLE001 - any hard failure also falls through to next key
                last_err = e
                usage_logger(self.name, key_label, tier, False, str(e))
                continue
        raise QuotaExhausted(f"All {self.name} keys exhausted: {last_err}")


def _gemini_call_fn(prompt: str, model: str, key_value: str) -> str:
    from google import genai  # lazy import -- keeps this module test-safe offline

    try:
        client = genai.Client(api_key=key_value)
        resp = client.models.generate_content(model=model, contents=prompt)
        return resp.text
    except Exception as e:  # noqa: BLE001
        # Prefer the SDK's own status code when it's exposed -- matching on
        # e.message substrings breaks silently the moment google-genai
        # changes its wording. code/status_code cover the shapes seen
        # across recent google-genai versions; the substring match stays
        # only as a last-resort fallback for versions/wrappers that don't
        # expose either (Update 05).
        code = getattr(e, "code", None) or getattr(e, "status_code", None)
        msg = str(e)
        if code == 429 or "429" in msg or "RESOURCE_EXHAUSTED" in msg.upper():
            raise RateLimitError(msg) from e
        raise


def _groq_call_fn(prompt: str, model: str, key_value: str) -> str:
    import random
    from openai import OpenAI  # lazy import; Groq is OpenAI-SDK compatible

    temp = random.choice([0.7, 0.75, 0.8, 0.85, 0.9, 0.95])
    try:
        client = OpenAI(api_key=key_value, base_url="https://api.groq.com/openai/v1")
        resp = client.chat.completions.create(model=model, messages=[{"role": "user", "content": prompt}], temperature=temp)
        return resp.choices[0].message.content
    except Exception as e:  # noqa: BLE001
        # openai-python raises a typed openai.RateLimitError with a
        # `.status_code` on real 429s -- prefer that over the message
        # substring match, which is what's left for wrappers/mocks that
        # don't set it (Update 05).
        status_code = getattr(e, "status_code", None)
        msg = str(e)
        if status_code == 429 or "429" in msg or "rate_limit" in msg.lower():
            raise RateLimitError(msg) from e
        raise


def _cerebras_call_fn(prompt: str, model: str, key_value: str) -> str:
    """Cerebras is OpenAI-SDK compatible (Update 09)."""
    import random
    from openai import OpenAI  # lazy import; Cerebras is OpenAI-SDK compatible

    temp = random.choice([0.7, 0.75, 0.8, 0.85, 0.9, 0.95])
    try:
        client = OpenAI(api_key=key_value, base_url="https://api.cerebras.ai/v1")
        resp = client.chat.completions.create(model=model, messages=[{"role": "user", "content": prompt}], temperature=temp)
        return resp.choices[0].message.content
    except Exception as e:  # noqa: BLE001
        status_code = getattr(e, "status_code", None)
        msg = str(e)
        if status_code == 429 or "429" in msg or "rate_limit" in msg.lower():
            raise RateLimitError(msg) from e
        raise


def _openrouter_call_fn(prompt: str, model: str, key_value: str) -> str:
    """OpenRouter is OpenAI-SDK compatible (Update 07). Free `:free` models
    are request-rate-limited (20/min, 50/day per account) rather than
    quota-billed, so a 429 here almost always means "come back tomorrow",
    not "add a key" -- there's no second free OpenRouter key to fall back
    to within one account, which is exactly why this sits behind Groq in
    the chain instead of beside it."""
    import random
    from openai import OpenAI  # lazy import; OpenRouter is OpenAI-SDK compatible

    temp = random.choice([0.7, 0.75, 0.8, 0.85, 0.9, 0.95])
    try:
        client = OpenAI(api_key=key_value, base_url="https://openrouter.ai/api/v1")
        resp = client.chat.completions.create(model=model, messages=[{"role": "user", "content": prompt}], temperature=temp)
        return resp.choices[0].message.content
    except Exception as e:  # noqa: BLE001
        status_code = getattr(e, "status_code", None)
        msg = str(e)
        if status_code == 429 or "429" in msg or "rate_limit" in msg.lower():
            raise RateLimitError(msg) from e
        raise


def build_gemini_provider(gemini_keys: list[str]) -> KeyedProvider:
    """Not wired into build_default_llm_adapter() by default -- see module
    docstring's Update 07 note. Still here, still tested, so re-enabling it
    (once GCP billing is settled) is passing this into a chain again, not
    rewriting anything."""
    keyed = [(f"key_{i+1}", k) for i, k in enumerate(gemini_keys)]
    return KeyedProvider(name="gemini", keys=keyed, call_fn=_gemini_call_fn)


def build_groq_provider(groq_keys: list[str]) -> KeyedProvider:
    keyed = [(f"key_{i+1}", k) for i, k in enumerate(groq_keys)]
    return KeyedProvider(name="groq", keys=keyed, call_fn=_groq_call_fn)


def build_cerebras_provider(cerebras_keys: list[str]) -> KeyedProvider:
    keyed = [(f"key_{i+1}", k) for i, k in enumerate(cerebras_keys)]
    return KeyedProvider(name="cerebras", keys=keyed, call_fn=_cerebras_call_fn)


def build_openrouter_provider(openrouter_keys: list[str]) -> KeyedProvider:
    keyed = [(f"key_{i+1}", k) for i, k in enumerate(openrouter_keys)]
    return KeyedProvider(name="openrouter", keys=keyed, call_fn=_openrouter_call_fn)


@dataclass
class ProviderStep:
    """One link in a tier's provider chain: try `provider` with `model`,
    move to the next step in the chain on QuotaExhausted."""

    provider: KeyedProvider
    model: str


class LLMAdapter:
    """Routes reasoning-tier and mechanical-tier calls through an ordered
    chain of providers per tier (Update 07 -- previously hardcoded to
    exactly gemini-then-groq / groq-then-gemini). A tier only raises
    QuotaExhausted after every key on every provider in its chain is
    exhausted. Chain order and membership is entirely caller-supplied (see
    build_default_llm_adapter() for the current default: Groq, then
    OpenRouter free tier as a last resort)."""

    def __init__(
        self,
        reasoning_chain: list[ProviderStep],
        mechanical_chain: list[ProviderStep],
        usage_logger: UsageLogger = _noop_logger,
        on_total_exhaustion=None,
    ):
        if not reasoning_chain or not mechanical_chain:
            raise ValueError("reasoning_chain and mechanical_chain must each have at least one provider step")
        self.reasoning_chain = reasoning_chain
        self.mechanical_chain = mechanical_chain
        self.usage_logger = usage_logger
        self.on_total_exhaustion = on_total_exhaustion  # callable(tier: str) -> None, e.g. Telegram alert

    def _call_chain(self, chain: list[ProviderStep], prompt: str, tier: str) -> tuple[str, str]:
        """Returns (response_text, provider_name) -- the provider name is
        whichever one in the chain actually answered, not just whichever
        was tried first (Update 03's fix, generalized in Update 07 to an
        arbitrary-length chain instead of a hardcoded pair). Callers that
        only need the text can ignore the second element."""
        last_exc: Optional[QuotaExhausted] = None
        for step in chain:
            try:
                text = step.provider.call(prompt, step.model, tier, self.usage_logger)
                return text, step.provider.name
            except QuotaExhausted as e:
                last_exc = e
                continue
        if self.on_total_exhaustion:
            self.on_total_exhaustion(tier)
        raise QuotaExhausted(f"All providers exhausted for {tier} tier: {last_exc}")

    def reasoning_call(self, prompt: str) -> tuple[str, str]:
        return self._call_chain(self.reasoning_chain, prompt, "reasoning")

    def mechanical_call(self, prompt: str) -> tuple[str, str]:
        return self._call_chain(self.mechanical_chain, prompt, "mechanical")


def build_default_llm_adapter(
    groq_keys: list[str],
    cerebras_keys: Optional[list[str]] = None,
    openrouter_keys: Optional[list[str]] = None,
    usage_logger: UsageLogger = _noop_logger,
    on_total_exhaustion=None,
) -> LLMAdapter:
    """The pipeline's actual default chain (Update 09): Groq, then
    Cerebras, then OpenRouter's free `:free` models, in that order, on both
    tiers. Gemini is deliberately absent -- see module docstring. All three
    providers are genuinely free/no-card; the order is "which one has the
    most generous limits for our workload" (Groq's own free tier, then
    Cerebras's 1M-tokens/day, then OpenRouter's 20/min-50/day-per-account),
    not "primary vs emergency" -- a whole provider is only skipped for a
    given call once every key configured on it has failed for that call.
    `cerebras_keys`/`openrouter_keys` are optional; pass an empty/None list
    to skip a provider entirely -- its step in the chain still exists, just
    with 0 keys, so it immediately QuotaExhausts and falls through to the
    next step (matching pre-Update-09 behavior when that provider isn't
    configured)."""
    groq = build_groq_provider(groq_keys)
    cerebras = build_cerebras_provider(cerebras_keys or [])
    openrouter = build_openrouter_provider(openrouter_keys or [])
    return LLMAdapter(
        reasoning_chain=[
            ProviderStep(groq, GROQ_REASONING_MODEL),
            ProviderStep(cerebras, CEREBRAS_REASONING_MODEL),
            ProviderStep(openrouter, OPENROUTER_REASONING_MODEL),
        ],
        mechanical_chain=[
            ProviderStep(groq, GROQ_MECHANICAL_MODEL),
            ProviderStep(cerebras, CEREBRAS_MECHANICAL_MODEL),
            ProviderStep(openrouter, OPENROUTER_MECHANICAL_MODEL),
        ],
        usage_logger=usage_logger,
        on_total_exhaustion=on_total_exhaustion,
    )
