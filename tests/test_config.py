"""
Tests for pipeline/config.py's Config.from_env(). Focused on Update 10
Item 9.2: MAX_CANDIDATE_ATTEMPTS / ORPHAN_RECLAIM_MINUTES / MAX_CORRELATION
used to be bare module constants in run_worker.py with no env var --
they're now Config fields, loaded the same way every other tuning knob in
this file already is.
"""
import os

import pytest

from pipeline.config import Config


@pytest.fixture
def _base_env(monkeypatch):
    """Minimum env vars for Config.from_env() to succeed without hitting
    MissingConfigError, isolated via monkeypatch so this doesn't leak into
    other tests or depend on the real shell environment."""
    monkeypatch.setenv("DATABASE_URL", "postgres://fake")
    monkeypatch.setenv("BRAIN_USERNAME", "u")
    monkeypatch.setenv("BRAIN_PASSWORD", "p")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "c")


def test_tuning_constants_default_when_env_unset(_base_env):
    config = Config.from_env()
    assert config.max_candidate_attempts == 3
    assert config.orphan_reclaim_minutes == 30
    assert config.max_correlation == 0.7


def test_tuning_constants_load_from_env(_base_env, monkeypatch):
    monkeypatch.setenv("MAX_CANDIDATE_ATTEMPTS", "5")
    monkeypatch.setenv("ORPHAN_RECLAIM_MINUTES", "45")
    monkeypatch.setenv("MAX_CORRELATION", "0.6")
    config = Config.from_env()
    assert config.max_candidate_attempts == 5
    assert config.orphan_reclaim_minutes == 45
    assert config.max_correlation == 0.6
