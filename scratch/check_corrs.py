import sys
import os
import asyncio
import json
sys.path.insert(0, os.path.abspath("."))
from dotenv import load_dotenv
load_dotenv()
from brain_options.config import OptionsConfig
from brain_options.core.client import BrainClient
from brain_options.store.db import OptionsDatabase

async def test_corrs():
    cfg = OptionsConfig.from_env()
    client = BrainClient(cfg.brain_username, cfg.brain_password)
    sess = client._get_session()
    db = OptionsDatabase(os.getenv("DATABASE_URL"))
    
    with db._get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT alpha_id, archetype, sharpe, fitness, margin, turnover
                FROM options_alphas
                WHERE status != 'SUBMITTED' AND status != 'CORRELATED' AND alpha_id IS NOT NULL
                LIMIT 15;
            """)
            rows = cur.fetchall()

    print(f"Checking {len(rows)} candidates for self correlation...")
    for r in rows:
        aid = r[0]
        arch = r[1]
        corr_url = f"https://api.worldquantbrain.com/alphas/{aid}/correlations/self"
        try:
            cr = await sess.retry("GET", corr_url)
            if cr and cr.status_code == 200 and cr.text.strip():
                data = cr.json()
                records = data.get("records") or []
                max_corr = 0.0
                max_partner = None
                for rec in records:
                    if len(rec) > 5 and isinstance(rec[5], (int, float)):
                        if rec[5] > max_corr:
                            max_corr = rec[5]
                            max_partner = rec[0]
                print(f"Alpha {aid} ({arch}): max_corr = {max_corr:.4f} (vs {max_partner}) | records count = {len(records)}")
            else:
                print(f"Alpha {aid} ({arch}): status={cr.status_code if cr else 'None'}, text={cr.text[:100] if cr else ''}")
        except Exception as e:
            print(f"Alpha {aid} error: {e}")

asyncio.run(test_corrs())
