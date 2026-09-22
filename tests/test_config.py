"""
Unit tests for brain_options.config.
"""
from __future__ import annotations

import os
import pytest
from brain_options.config import OptionsConfig


def test_config_from_env():
    config = OptionsConfig.from_env()
    assert config.brain_username is not None
    assert config.brain_password is not None
    assert config.stage0_min_sharpe == 0.60
    assert config.stage0_min_fitness == 0.50
    assert config.filter_min_sharpe == 1.25
    assert config.filter_min_fitness == 1.00
    assert config.universe == "TOP3000"
    assert config.delay == 1
    assert config.enable_auto_submit is not None
