import sys, os, asyncio, json
sys.path.insert(0, os.path.abspath("."))
from dotenv import load_dotenv
load_dotenv()
from brain_options.config import OptionsConfig
from brain_options.core.client import BrainClient

async def check_candidates():
    cfg = OptionsConfig.from_env()
    client = BrainClient(cfg.brain_username, cfg.brain_password)
    client.authenticate()
    sess = client._get_session()
    
    test_ids = [
        "ZYbeeJv0", "1YXQ8qk6", "qMxop2wj", "88jdX2n7", "blb3vrpK",
        "akbvvY61", "1YXQPrX6", "3qXLawaZ", "mLm93bz6", "0mX0kG86"
    ]
    
    for aid in test_ids:
        # Check alpha endpoint
        r = await sess.retry("GET", f"https://api.worldquantbrain.com/alphas/{aid}")
        if not r or r.status_code != 200:
            print(f"{aid}: GET failed", flush=True)
            continue
        d = r.json()
        status = d.get("status")
        stage = d.get("stage")
        is_block = d.get("is") or {}
        failed = [c.get("name") for c in (is_block.get("checks") or []) if c.get("result") == "FAIL"]
        
        # Check self correlation
        cr = await sess.retry("GET", f"https://api.worldquantbrain.com/alphas/{aid}/correlations/self")
        max_corr = 0.0
        corr_partner = None
        if cr and cr.status_code == 200 and cr.text.strip():
            cdata = json.loads(cr.text)
            for rec in cdata.get("records") or []:
                if len(rec) > 5 and isinstance(rec[5], (int, float)):
                    if rec[5] > max_corr:
                        max_corr = rec[5]
                        corr_partner = rec[0]
        print(f"{aid} ({status}/{stage}): failed_checks={failed} | max_corr={max_corr:.4f} vs {corr_partner}", flush=True)

asyncio.run(check_candidates())
