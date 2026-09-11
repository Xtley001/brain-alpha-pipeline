"""
Targeted Parameter Optimizer for Near-Miss Alphas.

Takes alpha expressions that scored high Sharpe (> 1.25) but missed on Turnover (> 70%)
or Fitness (< 1.00), and systematically sweeps calibrated parameter grids:
- Decay: [4, 6, 8, 10, 12, 15, 20] (higher decay smooths rebalancing and slashes turnover)
- Neutralization: ['SUBINDUSTRY', 'SECTOR', 'INDUSTRY', 'MARKET']
- Truncation: [0.03, 0.05, 0.08]
- Signal smoothing: hump(..., 0.01), ts_decay_linear(...)

Outputs copy-paste-ready configurations for WorldQuant BRAIN whenever a combination
clears ALL criteria (Sharpe >= 1.25, Fitness >= 1.00, Turnover 1%-70%).

Usage:
    python scripts/optimize_near_misses.py
    python scripts/optimize_near_misses.py --expr "rank(-(ts_delta(close,1) - group_mean(ts_delta(close,1), 1, sector)))"
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# Ensure repository root is on sys.path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(REPO_ROOT, ".env"))

from pipeline.brain.client import BrainClient
from pipeline.config import Config
from pipeline.sweep.settings_sweep import Settings, SimResult

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("near_miss_optimizer")

# The 5 near-miss alphas from user feedback
NEAR_MISS_CANDIDATES = [
    {
        "name": "Alpha #1 (Volume-Gated Residual Momentum)",
        "expr": "trade_when(volume > adv20*0.8, rank(-(ts_delta(close,1) - group_mean(ts_delta(close,1), 1, sector))), -1)",
        "baseline": "Sharpe 2.17, Turnover 73.1%, Fitness 0.95",
        "decays": [6, 8, 10, 12, 15],
        "neutralizations": ["SUBINDUSTRY", "SECTOR", "INDUSTRY"],
        "truncations": [0.05, 0.08],
    },
    {
        "name": "Alpha #6 (Pure Sector-Demeaned Reversal)",
        "expr": "rank(-(ts_delta(close,1) - group_mean(ts_delta(close,1), 1, sector)))",
        "baseline": "Sharpe 2.17, Turnover 53.8%, Fitness 0.93",
        "decays": [6, 8, 10, 12],
        "neutralizations": ["SUBINDUSTRY", "SECTOR", "INDUSTRY"],
        "truncations": [0.03, 0.05, 0.08],
    },
    {
        "name": "Alpha #3/5 (Volume-Scaled Short Reversal)",
        "expr": "rank(-ts_delta(close, 1) * min(volume / (adv20 + 0.001), 4))",
        "baseline": "Sharpe 2.09, Turnover 84.7%, Fitness 0.95",
        "decays": [8, 12, 15, 20],
        "neutralizations": ["SUBINDUSTRY", "SECTOR"],
        "truncations": [0.03, 0.05],
    },
    {
        "name": "Alpha #2 (Low-Vol Cap Interaction)",
        "expr": "rank(-ts_zscore(ts_std_dev(returns, 252), 252) * rank(log(cap + 1)))",
        "baseline": "Sharpe 1.15, Turnover 3.4%, Fitness 1.02",
        "decays": [4, 8, 15],
        "neutralizations": ["SECTOR", "INDUSTRY", "MARKET", "NONE"],
        "truncations": [0.05, 0.08],
    },
]


def passes_all_brain_checks(res: SimResult) -> bool:
    """WorldQuant BRAIN Gold Standard criteria:
    - Sharpe >= 1.25
    - Fitness >= 1.00
    - 0.01 <= Turnover <= 0.70
    """
    if res.sharpe is None or res.fitness is None or res.turnover is None:
        return False
    return res.sharpe >= 1.25 and res.fitness >= 1.00 and 0.01 <= res.turnover <= 0.70


async def optimize_candidate(
    client: BrainClient,
    candidate: Dict[str, Any],
    semaphore: asyncio.Semaphore,
) -> List[Dict[str, Any]]:
    name = candidate["name"]
    expr = candidate["expr"]
    decays = candidate.get("decays", [6, 8, 10, 12, 15])
    neutralizations = candidate.get("neutralizations", ["SUBINDUSTRY", "SECTOR"])
    truncations = candidate.get("truncations", [0.05])
    
    log.info(f"\n{'='*70}\nOptimizing {name}\nExpression: {expr}\nBaseline: {candidate.get('baseline')}\n{'='*70}")
    
    grid = [
        Settings(
            delay=1,
            universe="TOP3000",
            neutralization=neut,
            decay=decay,
            truncation=trunc,
            pasteurization=True,
            nan_handling=False,
        )
        for neut in neutralizations
        for decay in decays
        for trunc in truncations
    ]
    log.info(f"Generated {len(grid)} targeted parameter combos to test.")

    passed_combos: List[Dict[str, Any]] = []

    async def run_one(s: Settings):
        async with semaphore:
            try:
                res = await client.simulate_one(expr, s)
                passed = passes_all_brain_checks(res)
                symbol = "✅ PASS" if passed else "❌ FAIL"
                log.info(
                    f"[{symbol}] Decay={s.decay:<2} | Neut={s.neutralization:<11} | Trunc={s.truncation:<4} "
                    f"-> Sharpe={res.sharpe:.2f}, Fitness={res.fitness:.2f}, Turnover={res.turnover*100:.1f}%"
                )
                if passed:
                    passed_combos.append({
                        "name": name,
                        "expression": expr,
                        "settings": s,
                        "result": res,
                    })
            except Exception as e:
                log.warning(f"Error testing decay={s.decay}, neut={s.neutralization}: {e}")

    # Process in bounded concurrent batches
    batch_size = client.max_concurrent_sims
    for i in range(0, len(grid), batch_size):
        batch = grid[i : i + batch_size]
        await asyncio.gather(*(run_one(s) for s in batch))
        await asyncio.sleep(1.0)  # gentle pacing

    return passed_combos


def print_passed_summary(all_passed: List[Dict[str, Any]]):
    log.info("\n" + "=" * 80)
    log.info(f"🏆 TOTAL PASSED CONFIGURATIONS FOUND: {len(all_passed)}")
    log.info("=" * 80)
    for p in all_passed:
        s: Settings = p["settings"]
        r: SimResult = p["result"]
        print(f"\n--- {p['name']} ---")
        print(f"Expression: {p['expression']}")
        print(f"Performance: Sharpe={r.sharpe:.2f} | Fitness={r.fitness:.2f} | Turnover={r.turnover*100:.2f}% | Returns={getattr(r, 'returns_ann', 0.0)*100:.2f}% | Drawdown={getattr(r, 'drawdown', 0.0)*100:.2f}%")
        print("Copy-Paste Simulation Settings for WorldQuant BRAIN:")
        print("  Region: USA")
        print("  Universe: TOP3000")
        print("  Instrument Type: EQUITY")
        print("  Delay: 1")
        print(f"  Decay: {s.decay}")
        print(f"  Neutralization: {s.neutralization}")
        print(f"  Truncation: {s.truncation}")
        print("  Pasteurization: ON")
        print("  Unit Handling: VERIFY")
        print("  NaN Handling: OFF")
        print("  Language: FASTEXPR")
        print("-" * 80)


async def main_async(args):
    config = Config.from_env(require_brain=True, require_telegram=False)
    client = BrainClient(config.brain_username, config.brain_password, max_concurrent_sims=config.brain_max_concurrent_sims)
    client.authenticate()
    semaphore = asyncio.Semaphore(config.brain_max_concurrent_sims)

    if args.expr:
        candidates = [{
            "name": "Custom Expression",
            "expr": args.expr,
            "decays": [4, 6, 8, 10, 12, 15],
            "neutralizations": ["SUBINDUSTRY", "SECTOR", "INDUSTRY"],
            "truncations": [0.05, 0.08],
        }]
    else:
        candidates = NEAR_MISS_CANDIDATES

    all_passed = []
    for cand in candidates:
        passed = await optimize_candidate(client, cand, semaphore)
        all_passed.extend(passed)

    print_passed_summary(all_passed)


def main():
    parser = argparse.ArgumentParser(description="Optimize near-miss alphas by sweeping parameter grids")
    parser.add_argument("--expr", help="Specific alpha expression to optimize")
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
