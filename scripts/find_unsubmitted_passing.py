import os, sys
import psycopg
import dotenv

sys.stdout.reconfigure(encoding='utf-8')
dotenv.load_dotenv()

sys.path.insert(0, ".")
from brain_options.config import OptionsConfig
from brain_options.core.client import BrainClient

def find_passing():
    cfg = OptionsConfig.from_env()
    client = BrainClient(cfg.brain_username, cfg.brain_password)
    client.authenticate()
    session = client._get_session()

    # Get all distinct alpha_ids from options_evaluations with sharpe >= 1.40
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT alpha_id, archetype, sharpe, fitness, turnover, returns, drawdown, expression
                FROM options_evaluations
                WHERE sharpe >= 1.40 AND alpha_id IS NOT NULL
                ORDER BY sharpe DESC
                LIMIT 40;
            """)
            rows = cur.fetchall()

    print(f"Checking {len(rows)} distinct high-Sharpe alpha_ids on BRAIN API...")
    print("="*100)

    passing_alphas = []
    failing_alphas = []
    already_active = []

    for r in rows:
        alpha_id = r[0]
        url = f"https://api.worldquantbrain.com/alphas/{alpha_id}"
        resp = session.get(url)
        if resp.status_code != 200:
            continue
        try:
            data = resp.json()
        except:
            continue
            
        status = data.get("status", "UNKNOWN")
        stage = data.get("stage", "UNKNOWN")
        is_data = data.get("is", {})
        settings = data.get("settings", {})
        
        # Check checks endpoint
        chk_resp = session.get(f"https://api.worldquantbrain.com/alphas/{alpha_id}/check")
        checks_list = []
        if chk_resp.status_code == 200:
            try:
                chk_json = chk_resp.json()
                checks_list = chk_json.get("is", {}).get("checks", []) or chk_json.get("checks", [])
            except:
                pass
                
        fails = [f"{c.get('name')}: val={c.get('value')} lim={c.get('limit')}" for c in checks_list if c.get("result") == "FAIL"]
        
        entry = {
            "alpha_id": alpha_id,
            "status": status,
            "stage": stage,
            "sharpe": is_data.get("sharpe"),
            "fitness": is_data.get("fitness"),
            "turnover": is_data.get("turnover"),
            "margin": is_data.get("margin"),
            "returns": is_data.get("returns"),
            "drawdown": is_data.get("drawdown"),
            "settings": settings,
            "fails": fails,
            "expr": data.get("regular", {}).get("code", "")
        }

        if status == "ACTIVE":
            already_active.append(entry)
        elif len(fails) == 0 and len(checks_list) > 0:
            passing_alphas.append(entry)
        else:
            failing_alphas.append(entry)

    print(f"\n1. ALREADY ACTIVE / SUBMITTED ON PLATFORM ({len(already_active)}):")
    for e in already_active:
        print(f"  [ACTIVE] ID: {e['alpha_id']:<10} | Sharpe: {e['sharpe']} | Fit: {e['fitness']} | TO: {float(e['turnover'] or 0)*100:.1f}% | Margin: {float(e['margin'] or 0)*10000:.1f}bps | Stage: {e['stage']}")

    print(f"\n2. UNSUBMITTED & 100% PASSING ALL PLATFORM CHECKS ({len(passing_alphas)}):")
    for e in passing_alphas:
        print(f"  [READY]  ID: {e['alpha_id']:<10} | Sharpe: {e['sharpe']} | Fit: {e['fitness']} | TO: {float(e['turnover'] or 0)*100:.1f}% | Margin: {float(e['margin'] or 0)*10000:.1f}bps | Status: {e['status']}")
        print(f"    Settings: Univ={e['settings'].get('universe')}, Neut={e['settings'].get('neutralization')}, Decay={e['settings'].get('decay')}")
        print(f"    Expr: {e['expr'][:100]}...\n")

    print(f"\n3. UNSUBMITTED BUT FAILED 1 CHECK ({len(failing_alphas)}):")
    for e in failing_alphas[:10]:
        print(f"  [BLOCKED] ID: {e['alpha_id']:<10} | Sharpe: {e['sharpe']} | Fails: {e['fails']}")

if __name__ == "__main__":
    find_passing()
