"""
Pulls the complete, exact data-fields catalog directly from WorldQuant BRAIN API
for all Top 3 pillar datasets: analyst4, option8, option9, model51, model16.
Filters MATRIX fields (directly usable in Fast Expression).
"""
import os
import sys
import json
import time
import requests
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, ".")

from brain_options.config import OptionsConfig
from brain_options.core.client import BrainClient

def fetch_all_dataset_fields(session, dataset_id: str, region: str = "USA", universe: str = "TOP3000"):
    print(f"\n==========================================")
    print(f"Fetching fields for dataset: {dataset_id}...")
    print(f"==========================================")
    url = "https://api.worldquantbrain.com/data-fields"
    offset = 0
    limit = 50
    all_fields = []
    
    while True:
        params = {
            "dataset.id": dataset_id,
            "delay": 1,
            "instrumentType": "EQUITY",
            "region": region,
            "universe": universe,
            "limit": limit,
            "offset": offset,
        }
        resp = session.get(url, params=params, timeout=30)
        if resp.status_code != 200:
            print(f"Error fetching {dataset_id} offset {offset}: HTTP {resp.status_code}")
            print(resp.text[:300])
            break
            
        data = resp.json()
        total_count = data.get("count", 0)
        results = data.get("results", [])
        if not results:
            break
            
        for f in results:
            fid = f.get("id")
            desc = f.get("description") or f.get("name") or ""
            ftype = f.get("type")
            category = f.get("category", {}).get("name") if isinstance(f.get("category"), dict) else ""
            all_fields.append({
                "id": fid,
                "type": ftype,
                "description": desc,
                "dataset_id": dataset_id,
                "category": category,
            })
            
        print(f"  Fetched {len(all_fields)} / {total_count} fields...")
        offset += limit
        if offset >= total_count:
            break
        time.sleep(0.5)
        
    return all_fields

def main():
    cfg = OptionsConfig.from_env()
    client = BrainClient(cfg.brain_username, cfg.brain_password)
    client.authenticate()
    session = client._get_session()
    
    datasets = ["analyst4", "option8", "option9", "model51", "model16"]
    registry = {}
    
    for ds in datasets:
        fields = fetch_all_dataset_fields(session, ds)
        registry[ds] = fields
        print(f"--> Finished {ds}: {len(fields)} fields total.")
        
    os.makedirs("data", exist_ok=True)
    out_file = "data/brain_fields_exact.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2)
    print(f"\n[SUCCESS] Saved complete field registry to {out_file}")
    
    # Print summary of MATRIX fields for analyst4
    matrix_analyst = [x for x in registry.get("analyst4", []) if x.get("type") == "MATRIX"]
    print(f"\nTotal MATRIX fields in analyst4: {len(matrix_analyst)}")
    for x in matrix_analyst[:25]:
        print(f"  {x['id']:<35} | {x['description'][:60]}")

if __name__ == "__main__":
    main()
