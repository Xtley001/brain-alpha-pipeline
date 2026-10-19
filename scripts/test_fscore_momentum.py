import sys
sys.path.insert(0, '.')
import brain_options.core.dns_fallback
import asyncio
from brain_options.config import OptionsConfig
from brain_options.core.client import BrainClient, SimSettings
from scripts.master_quintuple_vault_miner_500 import verify_checklist_passes

async def main():
    cfg = OptionsConfig.from_env()
    client = BrainClient(username=cfg.brain_username, password=cfg.brain_password, max_concurrent_sims=1)
    client.authenticate()

    expr = (
        "trade_when(volume > adv20 * 0.85, "
        "group_neutralize("
        "rank(ts_decay_linear(fscore_momentum, 10)) * "
        "rank(-ts_delta(close, 3) / (ts_std_dev(close, 20) + 0.001)), "
        "subindustry), -1)"
    )
    settings = SimSettings(
        region="USA",
        universe="TOP1000",
        delay=1,
        decay=10,
        neutralization="SUBINDUSTRY",
        truncation=0.05,
        pasteurization=True,
    )
    print("Simulating fscore_momentum...")
    print(f"Expr: {expr}")
    metrics = await client.simulate_one(expr, settings)
    if not metrics:
        print("Simulation returned None.")
        return

    print(f"\n=== SIMULATION RESULTS ===")
    print(f"Alpha ID: {metrics.alpha_id}")
    print(f"Sharpe: {metrics.sharpe:.2f}")
    print(f"Fitness: {metrics.fitness:.2f}")
    print(f"Turnover: {metrics.turnover*100:.1f}%")
    print(f"Margin: {metrics.margin*10000:.1f} bps")
    print(f"Drawdown: {metrics.max_drawdown*100:.1f}%")

    is_sub, is_clean, msg = await verify_checklist_passes(client._session, metrics.alpha_id)
    print(f"\nPlatform /check: Submissible={is_sub}, Clean={is_clean}, Msg='{msg}'")

if __name__ == "__main__":
    asyncio.run(main())
