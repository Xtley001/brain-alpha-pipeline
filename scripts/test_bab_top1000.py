#!/usr/bin/env python3
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from brain_options.config import OptionsConfig
from brain_options.core.client import BrainClient, SimSettings

async def run_bab_top1000():
    config = OptionsConfig.from_env()
    client = BrainClient(config.brain_username, config.brain_password, max_concurrent_sims=2)
    client.authenticate()

    tests = [
        {
            "name": "BAB_TOP1000_Ind_d18",
            "expr": "group_neutralize(rank(-ts_decay_linear(beta_last_60_days_spy, 14) * ts_decay_linear(ts_zscore(returns, 5), 6)), industry)",
            "settings": SimSettings(region="USA", universe="TOP1000", delay=1, decay=18, neutralization="INDUSTRY", truncation=0.03, pasteurization=True)
        },
        {
            "name": "BAB_TOP1000_Subind_d18",
            "expr": "group_neutralize(rank(-ts_decay_linear(beta_last_60_days_spy, 14) * ts_decay_linear(ts_zscore(returns, 5), 6)), subindustry)",
            "settings": SimSettings(region="USA", universe="TOP1000", delay=1, decay=18, neutralization="SUBINDUSTRY", truncation=0.03, pasteurization=True)
        },
        {
            "name": "BAB_TOP1000_Subind_d22",
            "expr": "group_neutralize(rank(-ts_decay_linear(beta_last_60_days_spy, 18) * ts_decay_linear(ts_zscore(returns, 5), 8)), subindustry)",
            "settings": SimSettings(region="USA", universe="TOP1000", delay=1, decay=22, neutralization="SUBINDUSTRY", truncation=0.03, pasteurization=True)
        },
    ]

    for t in tests:
        print(f"\n=== SIMULATING: {t['name']} ===")
        m = await client.simulate_one(t["expr"], t["settings"])
        ret = getattr(m, "annualized_return", getattr(m, "returns", 0.0)) * 100
        print(f"[*] Result: {t['name']} | Sharpe={m.sharpe:.2f} | Fit={m.fitness:.2f} | TO={m.turnover*100:.1f}% | Ret={ret:.1f}% | DD={m.max_drawdown*100:.1f}% | Margin={m.margin*10000:.1f}bps | AID={m.alpha_id}")
        chk = client._session.get(f"https://api.worldquantbrain.com/alphas/{m.alpha_id}/check")
        if chk.status_code == 200:
            print("[*] BRAIN Platform Checklist:")
            for c in chk.json().get("is", {}).get("checks", []):
                res = c.get("result")
                name = c.get("name")
                val = c.get("value")
                lim = c.get("limit")
                print(f"    - {name}: {res} (val={val}, limit={lim})")

if __name__ == "__main__":
    asyncio.run(run_bab_top1000())
