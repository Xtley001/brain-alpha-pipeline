import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncio, psycopg
from dotenv import load_dotenv
load_dotenv()
from brain_options.config import OptionsConfig
from brain_options.core.client import BrainClient
from brain_options.core.correlation import compute_correlation

async def test_top_evals():
    config = OptionsConfig.from_env()
    client = BrainClient(username=config.brain_username, password=config.brain_password)
    client.authenticate()
    conn = psycopg.connect(config.database_url)
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT ON (alpha_id) alpha_id, sharpe, fitness, turnover
        FROM options_evaluations
        WHERE alpha_id IS NOT NULL AND sharpe >= 1.30 AND fitness >= 1.0 AND turnover <= 0.60
        ORDER BY alpha_id, sharpe DESC LIMIT 8;
    """)
    rows = cur.fetchall()
    print("Testing 8 candidates from options_evaluations:")
    
    cur.execute("SELECT alpha_id FROM options_alphas WHERE status = 'SUBMITTED';")
    sub_ids = [r[0] for r in cur.fetchall()]
    conn.close()
    
    sub_pnls = {}
    for sid in sub_ids[:6]:
        pnl = await client.get_alpha_pnl(sid)
        if pnl:
            sub_pnls[sid] = pnl

    for aid, sh, fit, to in rows:
        chk_r = client._session.get(f"https://api.worldquantbrain.com/alphas/{aid}/check")
        chk_data = chk_r.json() if chk_r.status_code == 200 else {}
        checks = chk_data.get("checks", [])
        fails = [f"{c.get('name')}: {c.get('value')} vs {c.get('limit')}" for c in checks if c.get("result") in ("FAIL", "ERROR")]
        pnl = await client.get_alpha_pnl(aid)
        max_c = 0.0
        worst_s = ""
        if pnl:
            for sid, spnl in sub_pnls.items():
                c = abs(compute_correlation(pnl, spnl))
                if c > max_c:
                    max_c = c
                    worst_s = sid
        print(f"Alpha {aid} (Sh={sh}, Fit={fit}, TO={to*100:.1f}%): ChecksFail={fails} | MaxCorr={max_c:.2f} vs {worst_s}")

if __name__ == "__main__":
    asyncio.run(test_top_evals())
