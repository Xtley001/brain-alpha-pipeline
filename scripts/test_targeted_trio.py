#!/usr/bin/env python3
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from brain_options.config import OptionsConfig
from brain_options.core.client import BrainClient, SimSettings

async def run_direct():
    config = OptionsConfig.from_env()
    client = BrainClient(config.brain_username, config.brain_password, max_concurrent_sims=2)
    client.authenticate()

    tests = [
        # Test 1: BAB on TOP2000 with truncation 0.01 and decay 16 (targeting Fitness >= 1.0 & Concentrated Weight PASS)
        {
            "name": "BAB_TOP2000_d16_trunc0.01",
            "expr": "group_neutralize(rank(-ts_decay_linear(beta_last_60_days_spy, 14) * ts_decay_linear(ts_zscore(returns, 5), 3)), subindustry)",
            "settings": SimSettings(region="USA", universe="TOP2000", delay=1, decay=16, neutralization="SUBINDUSTRY", truncation=0.01, pasteurization=True)
        },
        # Test 2: Apex with volume > adv20 * 0.80 (fixing holiday half-day concentration)
        {
            "name": "Apex_Vol0.80_d8",
            "expr": "trade_when(volume > adv20 * 0.80, group_neutralize(rank(0.45 * rank(ts_decay_linear(((call_breakeven_60 - forward_price_60) / (close + 0.001)), 8)) + 0.35 * rank(ts_decay_linear(((anl4_af_eps_value - anl4_afv4_eps_mean) / (anl4_afv4_dts_spe + 0.001)), 8)) - 0.20 * rank(ts_decay_linear(beta_last_60_days_spy, 8))), subindustry), -1)",
            "settings": SimSettings(region="USA", universe="TOPSP500", delay=1, decay=8, neutralization="SUBINDUSTRY", truncation=0.05, pasteurization=True)
        },
        # Test 3: Call-Put IV Asymmetry on TOPSP500 (fixing sub-universe Sharpe)
        {
            "name": "IV_Asym_TOPSP500_d18",
            "expr": "trade_when(abs(rank(ts_decay_linear((implied_volatility_call_30 - implied_volatility_put_30) / (implied_volatility_mean_30 + 0.001), 5)) - 0.5) > 0.26, group_neutralize(rank(ts_decay_linear((implied_volatility_call_30 - implied_volatility_put_30) / (implied_volatility_mean_30 + 0.001), 5)), subindustry), -1)",
            "settings": SimSettings(region="USA", universe="TOPSP500", delay=1, decay=18, neutralization="SUBINDUSTRY", truncation=0.02, pasteurization=True)
        },
    ]

    for t in tests:
        print(f"\n=======================================================")
        print(f"=== SIMULATING: {t['name']} ===")
        print(f"=======================================================")
        m = await client.simulate_one(t["expr"], t["settings"])
        ret = getattr(m, "annualized_return", getattr(m, "returns", 0.0)) * 100
        print(f"[*] Result: {t['name']} | Sharpe={m.sharpe:.2f} | Fit={m.fitness:.2f} | TO={m.turnover*100:.1f}% | Ret={ret:.1f}% | DD={m.max_drawdown*100:.1f}% | AID={m.alpha_id}")
        chk = client._session.get(f"https://api.worldquantbrain.com/alphas/{m.alpha_id}/check")
        if chk.status_code == 200:
            print("[*] BRAIN Platform Checklist:")
            for c in chk.json().get("is", {}).get("checks", []):
                res = c.get("result")
                name = c.get("name")
                val = c.get("value")
                lim = c.get("limit")
                print(f"    - {name}: {res} (value={val}, limit={lim})")

if __name__ == "__main__":
    asyncio.run(run_direct())
