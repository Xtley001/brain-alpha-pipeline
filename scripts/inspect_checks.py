import asyncio
import os
import dotenv
dotenv.load_dotenv()

import sys
sys.path.insert(0, ".")
from brain_options.config import OptionsConfig
from brain_options.core.client import BrainClient

def main():
    cfg = OptionsConfig.from_env()
    client = BrainClient(cfg.brain_username, cfg.brain_password)
    client.authenticate()
    s = client._get_session()
    blocked = ['Vkae25pb', 'N1a8nR9o', 'MPa2a1Eo', 'JjN2O3mA', 'XgbOPxXb']
    for a in blocked:
        r = s.get(f"https://api.worldquantbrain.com/alphas/{a}/check")
        if r.status_code != 200:
            print(a, "HTTP ERROR:", r.status_code)
            continue
        data = r.json()
        checks = data.get("is", {}).get("checks", []) or data.get("checks", [])
        fails = [f"{c.get('name')}: val={c.get('value')} lim={c.get('limit')}" for c in checks if c.get("result") == "FAIL"]
        passes = [f"{c.get('name')}: val={c.get('value')} lim={c.get('limit')}" for c in checks if c.get("name") in ("LOW_SUB_UNIVERSE_SHARPE", "SELF_CORRELATION")]
        print(f"Alpha {a}:")
        print(f"  Fails: {fails}")
        print(f"  Key checks: {passes}")

if __name__ == "__main__":
    main()
