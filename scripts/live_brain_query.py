import os, sys, json
import dotenv

sys.stdout.reconfigure(encoding='utf-8')
dotenv.load_dotenv()

sys.path.insert(0, ".")
from brain_options.config import OptionsConfig
from brain_options.core.client import BrainClient

def query_brain():
    cfg = OptionsConfig.from_env()
    client = BrainClient(cfg.brain_username, cfg.brain_password)
    client.authenticate()
    session = client._get_session()

    alpha_ids = [
        # Candidate alphas
        'levEN9vx', 'JjNo2NQA', 'YP58QkYR', '6XjZKZOL', 'RRb9K8Pd', 'LLNEZ8L9', 
        'Vkae25pb', 'N1a8nR9o', 'MPa2a1Eo',
        # Vault alphas
        'Grdg2Njo', 'N176Geqp', 'gJQWL7aK', 'levEYpmx', 'gJbAP76e', 'YPboG01w', 
        'KPNd6Ovl', 'Xgbv1A80', 'blbZ9Wkp', 'YPb81N2v', 'ZYbNORZx', 'e7bWxz7E', 'mLmQjlzE'
    ]

    print("="*100)
    print("LIVE WORLDQUANT BRAIN API REAL PLATFORM AUDIT")
    print("="*100)

    for alpha_id in alpha_ids:
        url = f"https://api.worldquantbrain.com/alphas/{alpha_id}"
        resp = session.get(url)
        if resp.status_code != 200:
            print(f"\n[-] Alpha {alpha_id}: HTTP {resp.status_code} ({resp.text[:80]})")
            continue
        
        try:
            data = resp.json()
        except Exception:
            print(f"\n[-] Alpha {alpha_id}: Non-JSON response")
            continue

        is_data = data.get("is", {})
        status = data.get("status", "UNKNOWN")
        stage = data.get("stage", "UNKNOWN")
        settings = data.get("settings", {})
        
        sharpe = is_data.get("sharpe")
        fitness = is_data.get("fitness")
        turnover = is_data.get("turnover")
        margin = is_data.get("margin")
        returns = is_data.get("returns")
        drawdown = is_data.get("drawdown")
        checks_list = is_data.get("checks", [])
        expr = data.get("regular", {}).get("code", "")
        
        # If checks not in is_data, query check endpoint
        if not checks_list:
            check_url = f"https://api.worldquantbrain.com/alphas/{alpha_id}/check"
            chk_resp = session.get(check_url)
            if chk_resp.status_code == 200:
                try:
                    chk_json = chk_resp.json()
                    checks_list = chk_json.get("is", {}).get("checks", []) or chk_json.get("checks", [])
                except Exception:
                    pass

        fails = [f"{c.get('name')}: val={c.get('value')} lim={c.get('limit')}" for c in checks_list if c.get("result") == "FAIL"]
        warns = [f"{c.get('name')}" for c in checks_list if c.get("result") == "WARNING"]
        
        all_passed = (len(fails) == 0 and len(checks_list) > 0)

        print(f"\n>>> AlphaID: {alpha_id:<10} | Platform Status: {status:<12} | Stage: {stage}")
        print(f"    IS Sharpe: {sharpe} | Fitness: {fitness} | Turnover: {float(turnover or 0)*100:.1f}% | Margin: {float(margin or 0)*10000:.1f} bps | Return: {float(returns or 0)*100:.1f}% | DD: {float(drawdown or 0)*100:.1f}%")
        print(f"    Settings: Univ={settings.get('universe')}, Neut={settings.get('neutralization')}, Decay={settings.get('decay')}, Trunc={settings.get('truncation')}")
        if all_passed:
            print(f"    Platform Verification: [PASSED ALL GATES - READY TO SUBMIT]")
        else:
            print(f"    Platform Verification: [FAILS: {fails}]")
        if warns:
            print(f"    Platform Warnings: {warns}")
        print(f"    Expression: {expr[:100]}...")

if __name__ == "__main__":
    query_brain()
