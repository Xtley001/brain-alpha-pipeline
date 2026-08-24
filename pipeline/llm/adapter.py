"""
LLM provider adapter with key rotation, per the LLM-providers-and-keys design
§5. Falls back to the next key in a provider's list on quota-exhaustion
errors (429 / RESOURCE_EXHAUSTED), not just hard failures, and logs every
attempt (success or failure) via an injected `usage_logger` so
`llm_usage.key_label` records exactly which key was used — required by
the audit checklist's LLM key-rotation section.

Real network clients (google-genai, openai-for-groq) are imported lazily
inside the functions that need them, so this module — and its tests — never
require those packages or network access just to exercise the rotation
logic. Tests inject fake `client_factory` callables instead.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Optional, Protocol


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
    from google import genai  # lazy import — keeps this module test-safe offline

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
    from openai import OpenAI  # lazy import; Groq is OpenAI-SDK compatible

    try:
        client = OpenAI(api_key=key_value, base_url="https://api.groq.com/openai/v1")
        resp = client.chat.completions.create(model=model, messages=[{"role": "user", "content": prompt}])
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


def build_gemini_provider(gemini_keys: list[str]) -> KeyedProvider:
    keyed = [(f"key_{i+1}", k) for i, k in enumerate(gemini_keys)]
    return KeyedProvider(name="gemini", keys=keyed, call_fn=_gemini_call_fn)


def build_groq_provider(groq_keys: list[str]) -> KeyedProvider:
    keyed = [(f"key_{i+1}", k) for i, k in enumerate(groq_keys)]
    return KeyedProvider(name="groq", keys=keyed, call_fn=_groq_call_fn)


class LLMAdapter:
    """Routes reasoning-tier and mechanical-tier calls per
    the LLM-providers-and-keys design:
      - reasoning tier: Gemini Flash first, Groq 70B fallback
      - mechanical tier: Groq 8B first, Gemini fallback
    Both directions raise QuotaExhausted only after every key on every
    provider in the chain is exhausted.
    """

    def __init__(
        self,
        gemini_provider: KeyedProvider,
        groq_provider: KeyedProvider,
        usage_logger: UsageLogger = _noop_logger,
        on_total_exhaustion=None,
    ):
        self.gemini_provider = gemini_provider
        self.groq_provider = groq_provider
        self.usage_logger = usage_logger
        self.on_total_exhaustion = on_total_exhaustion  # callable(tier: str) -> None, e.g. Telegram alert

    def reasoning_call(self, prompt: str) -> tuple[str, str]:
        """Returns (response_text, provider_name) -- the provider name is
        whichever one actually answered ('gemini' or 'groq'), not just
        whichever was tried first. Update 03: propose_new_ideas() used to
        hardcode generation_tier='llm_gemini' regardless of whether this
        fell through to the Groq fallback, silently corrupting the
        generated-by-tier breakdown the heartbeat (P1.1) reports. Callers
        that only need the text can ignore the second element."""
        try:
            text = self.gemini_provider.call(prompt, "gemini-2.5-flash", "reasoning", self.usage_logger)
            return text, "gemini"
        except QuotaExhausted:
            try:
                text = self.groq_provider.call(prompt, "llama-3.3-70b-versatile", "reasoning", self.usage_logger)
                return text, "groq"
            except QuotaExhausted:
                if self.on_total_exhaustion:
                    self.on_total_exhaustion("reasoning")
                raise

    def mechanical_call(self, prompt: str) -> tuple[str, str]:
        """Returns (response_text, provider_name) -- see reasoning_call's
        docstring; same fix applies to the mechanical tier's Groq-first,
        Gemini-fallback chain."""
        try:
            text = self.groq_provider.call(prompt, "llama-3.1-8b-instant", "mechanical", self.usage_logger)
            return text, "groq"
        except QuotaExhausted:
            try:
                text = self.gemini_provider.call(prompt, "gemini-2.5-flash", "mechanical", self.usage_logger)
                return text, "gemini"
            except QuotaExhausted:
                if self.on_total_exhaustion:
                    self.on_total_exhaustion("mechanical")
                raise
