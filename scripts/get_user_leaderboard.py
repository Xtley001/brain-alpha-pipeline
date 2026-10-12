import os, sys, json, requests
import psycopg
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, ".")
from brain_options.config import OptionsConfig
from brain_options.core.client import BrainClient
from brain_options.store.store import OptionsStore

cfg = OptionsConfig.from_env()
store = OptionsStore()
client = BrainClient(cfg.brain_username, cfg.brain_password, db=store.db)
client.authenticate()
session = client._get_session()

print("="*60)
print("WORLDQUANT BRAIN LIVE ACCOUNT & LEADERBOARD AUDIT")
print("="*60)

# 1. User Profile
resp = session.get("https://api.worldquantbrain.com/users/self")
if resp.status_code == 200:
    u = resp.json()
    print(f"User: {u.get('firstName', '')} {u.get('lastName', '')} ({u.get('email', '')})")
    print(f"Country: {u.get('country', '')} | Level: {u.get('level', '')} | Tier: {u.get('tier', '')}")
    print(f"Status: {u.get('status', '')} | Roles: {u.get('roles', [])}")
    print(f"Points / Score: {u.get('score', 'N/A')} | Rank: {u.get('rank', 'N/A')}")
else:
    print(f"users/self returned HTTP {resp.status_code}: {resp.text[:100]}")

# 2. User Submissions & Alphas count
resp = session.get("https://api.worldquantbrain.com/users/self/alphas?limit=1&status=SUBMITTED")
if resp.status_code == 200:
    sub_data = resp.json()
    print(f"Platform Submitted Alphas Count: {sub_data.get('count', 'N/A')}")

# 3. User Points / History
resp = session.get("https://api.worldquantbrain.com/users/self/points")
if resp.status_code == 200:
    pts = resp.json()
    print("\n--- Points Breakdown ---")
    print(json.dumps(pts, indent=2)[:500])

# 4. Competitions
resp = session.get("https://api.worldquantbrain.com/users/self/competitions")
if resp.status_code == 200:
    comps = resp.json()
    print("\n--- Competitions ---")
    print(json.dumps(comps, indent=2)[:500])

# 5. Leaderboards / Rankings
for ep in [
    "https://api.worldquantbrain.com/rankings",
    "https://api.worldquantbrain.com/users/self/rankings",
    "https://api.worldquantbrain.com/leaderboards",
]:
    r = session.get(ep)
    if r.status_code == 200:
        print(f"\n--- {ep} ---")
        try:
            print(json.dumps(r.json(), indent=2)[:500])
        except Exception:
            print(r.text[:200])

store.db.close()
