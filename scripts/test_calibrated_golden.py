import asyncio
import os
import sys
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brain_options.config import OptionsConfig
from brain_options.core.client import BrainClient, SimSettings
from brain_options.store.store import OptionsStore

async def main():
    store = OptionsStore()
    cfg = OptionsConfig.from_env()
    client = BrainClient(cfg.brain_username, cfg.brain_password, max_concurrent_sims=1, db=store)
    client.authenticate()

    test_cases = [
        # Case 1: GoldFast on TOP500 (liquid large cap)
        (
            "trade_when(volume > adv20 * 0.85, group_neutralize(rank(ts_decay_linear(ts_decay_linear(rp_css_earnings, 8), 3)) * rank(-ts_delta(close, 2) / (ts_std_dev(close, 10) + 0.001)), subindustry), -1)",
            SimSettings(decay=8, universe="TOP500", neutralization="SUBINDUSTRY", truncation=0.08, pasteurization="ON", unit_handling="VERIFY", nan_handling="OFF"),
            "GoldFast_TOP500_d8"
        ),
        # Case 2: GoldFast on TOPSP500 (S&P 500 mega cap)
        (
            "trade_when(volume > adv20 * 0.85, group_neutralize(rank(ts_decay_linear(ts_decay_linear(rp_css_earnings, 8), 3)) * rank(-ts_delta(close, 2) / (ts_std_dev(close, 10) + 0.001)), subindustry), -1)",
            SimSettings(decay=8, universe="TOPSP500", neutralization="SUBINDUSTRY", truncation=0.08, pasteurization="ON", unit_handling="VERIFY", nan_handling="OFF"),
            "GoldFast_TOPSP500_d8"
        ),
        # Case 3: GoldFast with higher volume threshold 1.00 on TOP1000
        (
            "trade_when(volume > adv20 * 1.00, group_neutralize(rank(ts_decay_linear(ts_decay_linear(rp_css_earnings, 8), 3)) * rank(-ts_delta(close, 2) / (ts_std_dev(close, 10) + 0.001)), subindustry), -1)",
            SimSettings(decay=8, universe="TOP1000", neutralization="SUBINDUSTRY", truncation=0.08, pasteurization="ON", unit_handling="VERIFY", nan_handling="OFF"),
            "GoldFast_Vol100_TOP1000_d8"
        ),
        # Case 4: GoldFast on TOP500 with decay 12
        (
            "trade_when(volume > adv20 * 0.85, group_neutralize(rank(ts_decay_linear(ts_decay_linear(rp_css_earnings, 12), 3)) * rank(-ts_delta(close, 2) / (ts_std_dev(close, 10) + 0.001)), subindustry), -1)",
            SimSettings(decay=12, universe="TOP500", neutralization="SUBINDUSTRY", truncation=0.08, pasteurization="ON", unit_handling="VERIFY", nan_handling="OFF"),
            "GoldFast_TOP500_d12"
        ),
    ]

    for expr, settings, tag in test_cases:
        print(f"\n---> Simulating {tag} (universe={settings.universe}, decay={settings.decay})...")
        metrics = await client.simulate_one(expr, settings)
        print(f"[{tag}] ID: {metrics.alpha_id} | Sharpe: {metrics.sharpe:.2f} | Fitness: {metrics.fitness:.2f} | TO: {metrics.turnover*100:.1f}% | Margin: {metrics.margin*10000:.1f}bps | MaxDD: {metrics.max_drawdown*100:.1f}%")

if __name__ == "__main__":
    asyncio.run(main())
