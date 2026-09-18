import os
import tempfile
import pytest
from brain_options.config import OptionsConfig
from brain_options.llm.adapter import LLMAdapter
from brain_options.specialist.generator import OptionsGenerator
from brain_options.store.store import OptionsStore


def test_specialization_target_archetype():
    config = OptionsConfig(brain_username="dummy", brain_password="dummy")
    llm = LLMAdapter(config)
    gen = OptionsGenerator(llm)

    # Test skew specialization
    batch_skew = gen.get_next_batch(target_count=6, template_ratio=0.5, target_archetype="skew")
    assert len(batch_skew) == 6
    for cand in batch_skew:
        # Check that either expression or archetype reflects skew
        text = f"{cand.archetype_name} {cand.expression} {cand.hypothesis}".lower()
        assert "skew" in text or "volatility" in text

    # Test breakeven specialization
    batch_be = gen.get_next_batch(target_count=6, template_ratio=0.5, target_archetype="breakeven")
    assert len(batch_be) == 6
    for cand in batch_be:
        text = f"{cand.archetype_name} {cand.expression} {cand.hypothesis}".lower()
        assert "breakeven" in text or "vrp" in text or "variance" in text or "iv" in text


def test_archive_rejected_alpha_local_store():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = OptionsStore(data_dir=tmpdir, database_url=None)
        aid = "TEST_REJECTED_001"
        cand = {
            "alpha_id": aid,
            "expression": "rank(implied_volatility_mean_skew_30)",
            "archetype": "Skew",
            "hypothesis": "Test hypothesis",
            "source": "unit_test",
            "sharpe": 0.20,
            "fitness": 0.10,
            "turnover": 0.80,
            "returns": 0.05,
            "drawdown": 0.25,
            "margin": 0.0001,
        }
        store.archive_rejected_alpha(aid, "CHECK_FAIL: LOW_SHARPE, LOW_FITNESS", cand)

        assert os.path.exists(store.rejected_csv)
        with open(store.rejected_csv, "r", encoding="utf-8") as f:
            content = f.read()
            assert aid in content
            assert "CHECK_FAIL: LOW_SHARPE, LOW_FITNESS" in content
