import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncio, psycopg
from dotenv import load_dotenv
load_dotenv()
from brain_options.config import OptionsConfig
from brain_options.core.client import BrainClient
from brain_options.core.correlation import compute_correlation

async def test_rl_harvest():
    config = OptionsConfig.from_env()
    client = BrainClient(username=config.brain_username, password=config.brain_password)
    client.authenticate()

    conn = psycopg.connect(config.database_url)
    cur = conn.cursor()
    cur.execute("""
        SELECT alpha_id, expression, archetype, sharpe, fitness, turnover, returns
        FROM options_learning_memory
        WHERE alpha_id IS NOT NULL 
          AND sharpe >= 1.30 
          AND fitness >= 1.10 
          AND turnover <= 0.30
        ORDER BY reward DESC LIMIT 15;
    """)
    candidates = cur.fetchall()
    
    cur.execute("SELECT alpha_id FROM options_alphas WHERE status = 'SUBMITTED';")
    prod_ids = [r[0] for r in cur.fetchall()]
    conn.close()

    print(f"Loaded {len(candidates)} high-reward RL candidates.")
    print(f"Testing correlation against {len(prod_ids)} production anchors...")

    prod_pnls = {}
    for pid in prod_ids:
        pnl = await client.get_alpha_pnl(pid)
        if pnl:
            prod_pnls[pid] = pnl

    for aid, expr, arch, sh, fit, to, mg in candidates:
        cand_pnl = await client.get_alpha_pnl(aid)
        if not cand_pnl:
            print(f"Alpha {aid}: PnL not available on platform.")
            continue
        max_corr = 0.0
        worst_anchor = ""
        for pid, ppnl in prod_pnls.items():
            c = abs(compute_correlation(cand_pnl, ppnl))
            if c > max_corr:
                max_corr = c
                worst_anchor = pid

        chk_r = client._session.get(f"https://api.worldquantbrain.com/alphas/{aid}/check")
        chk_data = chk_r.json() if chk_r.status_code == 200 else {}
        checks = chk_data.get("checks", [])
        fails = [f"{c.get('name')}" for c in checks if c.get("result") in ("FAIL", "ERROR")]

        print(f"Alpha {aid} | Sh={sh} | Fit={fit} | TO={float(to)*100:.1f}% | MaxCorr={max_corr:.2f} vs {worst_anchor} | CheckFails={fails} | Arch={arch}")

if __name__ == "__main__":
    asyncio.run(test_rl_harvest())
