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

async def find_clean():
    cfg = OptionsConfig.from_env()
    client = BrainClient(cfg.brain_username, cfg.brain_password)
    client.authenticate()
    sess = client._get_session()
    db = OptionsDatabase(os.getenv("DATABASE_URL"))
    
    with db._get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT alpha_id, archetype, sharpe, fitness, margin, turnover,
                       (1.0 * COALESCE(sharpe, 0) + 1.2 * COALESCE(fitness, 0) + 200 * COALESCE(margin, 0) - 0.5 * COALESCE(turnover, 0)) AS cqs
                FROM options_alphas
                WHERE status != 'SUBMITTED' AND status != 'CORRELATED' AND alpha_id IS NOT NULL
                ORDER BY cqs DESC, sharpe DESC
                LIMIT 20;
            """)
            rows = cur.fetchall()

    print(f"Loaded {len(rows)} candidates. Verifying on BRAIN...", flush=True)
    clean_candidates = []
    for r in rows:
        aid = r[0]
        arch = r[1]
        cqs = float(r[6])
        # Check alpha endpoint
        resp = await sess.retry("GET", f"https://api.worldquantbrain.com/alphas/{aid}", max_tries=3)
        if not resp or resp.status_code != 200:
            print(f"Skipping {aid}: HTTP {resp.status_code if resp else 'None'}", flush=True)
            continue
        data = resp.json()
        if data.get("status") != "UNSUBMITTED":
            print(f"Skipping {aid}: status is {data.get('status')}", flush=True)
            continue
        
        # Check checks
        is_block = data.get("is") or {}
        failed = [c.get("name") for c in (is_block.get("checks") or []) if c.get("result") == "FAIL"]
        if failed:
            print(f"Skipping {aid}: failed checks {failed}", flush=True)
            continue

        # Check self correlation
        corr_resp = await sess.retry("GET", f"https://api.worldquantbrain.com/alphas/{aid}/correlations/self", max_tries=2)
        max_corr = 0.0
        corr_partner = None
        if corr_resp and corr_resp.status_code == 200 and corr_resp.text.strip():
            cdata = json.loads(corr_resp.text)
            for rec in cdata.get("records") or []:
                if len(rec) > 5 and isinstance(rec[5], (int, float)):
                    if rec[5] > max_corr:
                        max_corr = rec[5]
                        corr_partner = rec[0]

        if max_corr >= 0.70:
            print(f"Skipping {aid} ({arch}): HIGH SELF-CORRELATION {max_corr:.4f} with {corr_partner}", flush=True)
            # Mark correlated in DB
            db.mark_alpha_correlated(aid, f"High self-correlation {max_corr:.4f} with {corr_partner}")
            continue

        print(f"[READY CANDIDATE]: {aid} ({arch}) | CQS={cqs:.2f} | Sharpe={r[2]} | Fit={r[3]} | MaxCorr={max_corr:.4f} vs {corr_partner}", flush=True)
        clean_candidates.append({
            "alpha_id": aid,
            "archetype": arch,
            "cqs": cqs,
            "sharpe": float(r[2]),
            "fitness": float(r[3]),
            "margin": float(r[4]),
            "turnover": float(r[5]),
            "max_corr": max_corr,
        })
        if len(clean_candidates) >= 3:
            break

    print("\nClean candidates found:", len(clean_candidates), flush=True)

asyncio.run(find_clean())
