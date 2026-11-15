import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import brain_options.core.dns_fallback
from dotenv import load_dotenv; load_dotenv()
import psycopg
import requests
import numpy as np
from brain_options.config import OptionsConfig as Config

cfg = Config.from_env()

# Load reference PnLs
REF_CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "ref_pnls_cache.json")
with open(REF_CACHE_FILE, "r") as f:
    ref_pnls = json.load(f)

print(f"Loaded {len(ref_pnls)} reference PnLs from cache.", flush=True)

# Authenticate with BRAIN
s = requests.Session()
s.auth = (cfg.brain_username, cfg.brain_password)
resp = s.post("https://api.worldquantbrain.com/authentication")
if resp.status_code not in (200, 201):
    print(f"Auth failed: {resp.status_code}", flush=True)
    sys.exit(1)
print("Authenticated with BRAIN API.", flush=True)

# Connect to DB
conn = psycopg.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()

# Get unclassified high-performing candidates
cur.execute("""
    SELECT DISTINCT e.alpha_id, e.sharpe, e.fitness, e.turnover, e.returns, e.drawdown, e.expression, e.archetype
    FROM options_evaluations e
    LEFT JOIN options_alphas a ON e.alpha_id = a.alpha_id
    WHERE e.sharpe >= 1.25 AND e.fitness >= 1.00 AND e.turnover BETWEEN 0.01 AND 0.70 AND e.drawdown <= 0.35
      AND a.alpha_id IS NULL
    ORDER BY e.sharpe DESC
""")
candidates = cur.fetchall()
print(f"Found {len(candidates)} unclassified candidates meeting base metric hurdles.", flush=True)

def compute_correlation(cand_daily, ref_dict):
    max_c = 0.0
    worst_ref = ""
    for ref_id, r_dict in ref_dict.items():
        common_dates = sorted(set(cand_daily.keys()).intersection(set(r_dict.keys())))
        if len(common_dates) < 50:
            continue
        v1 = np.array([cand_daily[d] for d in common_dates], dtype=float)
        v2 = np.array([r_dict[d] for d in common_dates], dtype=float)
        s1, s2 = np.std(v1), np.std(v2)
        if s1 > 0 and s2 > 0:
            corr = float(np.corrcoef(v1, v2)[0, 1])
            if not np.isnan(corr) and abs(corr) > abs(max_c):
                max_c = corr
                worst_ref = ref_id
    return max_c, worst_ref

CRITICAL_CHECKS = [
    "LOW_SHARPE", "LOW_FITNESS", "LOW_TURNOVER",
    "HIGH_TURNOVER", "CONCENTRATED_WEIGHT", "LOW_SUB_UNIVERSE_SHARPE"
]

qualified_count = 0
failed_checklist = 0
failed_collision = 0
failed_margin = 0

for i, (aid, sh, fit, to, ret, dd, expr, arch) in enumerate(candidates):
    print(f"\n[{i+1}/{len(candidates)}] Testing AID={aid} (Sharpe={sh}, Fit={fit}, TO={to*100:.1f}%, Arch={arch})...", flush=True)
    
    # 1. BRAIN platform checklist
    try:
        chk_resp = s.get(f"https://api.worldquantbrain.com/alphas/{aid}/check", timeout=15)
        if chk_resp.status_code != 200:
            print(f"  -> Check status {chk_resp.status_code}: skipping", flush=True)
            continue
        checks = chk_resp.json().get("is", {}).get("checks", [])
        chk_map = {c.get("name"): c.get("result") for c in checks}
        
        failed = [k for k in CRITICAL_CHECKS if chk_map.get(k) != "PASS"]
        if failed:
            print(f"  -> Checklist FAIL: {failed}", flush=True)
            failed_checklist += 1
            cur.execute("""
                INSERT INTO options_alphas (
                    alpha_id, expression, archetype, source, sharpe, fitness, turnover, returns, drawdown, status, created_at
                ) VALUES (%s, %s, %s, 'salvage_screener', %s, %s, %s, %s, %s, 'REJECTED_CHECKLIST', NOW())
                ON CONFLICT (alpha_id) DO UPDATE SET status = 'REJECTED_CHECKLIST'
            """, (aid, expr, arch or "Unknown", sh, fit, to, ret, dd))
            conn.commit()
            continue
    except Exception as e:
        print(f"  -> Checklist check error: {e}", flush=True)
        continue
        
    # 2. Get details & margin
    try:
        alpha_resp = s.get(f"https://api.worldquantbrain.com/alphas/{aid}", timeout=15)
        if alpha_resp.status_code != 200:
            print(f"  -> Alpha details status {alpha_resp.status_code}: skipping", flush=True)
            continue
        alpha_data = alpha_resp.json()
        stats = alpha_data.get("is", {})
        margin = stats.get("margin", 0.0)
        settings = alpha_data.get("settings", {})
        universe = settings.get("universe", "Unknown")
        decay = settings.get("decay", 0)
        neut = settings.get("neutralization", "Unknown")
        
        if margin < 0.0004:
            print(f"  -> Margin FAIL: {margin*10000:.1f} bps < 4.0 bps", flush=True)
            failed_margin += 1
            cur.execute("""
                INSERT INTO options_alphas (
                    alpha_id, expression, archetype, source, sharpe, fitness, turnover, returns, drawdown, margin,
                    universe, neutralization, decay, status, created_at
                ) VALUES (
                    %s, %s, %s, 'salvage_screener', %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, 'REJECTED_MARGIN', NOW()
                ) ON CONFLICT (alpha_id) DO UPDATE SET status = 'REJECTED_MARGIN', margin = EXCLUDED.margin
            """, (aid, expr, arch or "Unknown", sh, fit, to, ret, dd, margin, universe, neut, decay))
            conn.commit()
            continue
    except Exception as e:
        print(f"  -> Alpha details error: {e}", flush=True)
        continue
        
    # 3. Correlation Gate
    try:
        pnl_resp = None
        for attempt in range(4):
            r = s.get(f"https://api.worldquantbrain.com/alphas/{aid}/recordsets/pnl", timeout=20)
            if r.status_code == 200 and r.text.strip():
                pnl_resp = r
                break
            time.sleep(1.0)
            
        if not pnl_resp:
            print(f"  -> PnL download failed", flush=True)
            continue
            
        records = pnl_resp.json().get("records") or []
        cand_daily = {}
        prev = None
        for r in records:
            if isinstance(r, list) and len(r) >= 2:
                dt, pnl = str(r[0]), float(r[1])
                if prev is not None:
                    cand_daily[dt] = pnl - prev
                prev = pnl
                
        max_c, worst_ref = compute_correlation(cand_daily, ref_pnls)
        print(f"  -> Max Corr: {max_c:+.4f} (vs {worst_ref}) | Margin: {margin*10000:.1f} bps", flush=True)
        
        if abs(max_c) >= 0.70:
            print(f"  -> Collision FAIL: |{max_c:+.4f}| >= 0.70", flush=True)
            failed_collision += 1
            cur.execute("""
                INSERT INTO options_alphas (
                    alpha_id, expression, archetype, source, sharpe, fitness, turnover, returns, drawdown, margin,
                    max_correlation, universe, neutralization, decay, status, created_at
                ) VALUES (
                    %s, %s, %s, 'salvage_screener', %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, 'REJECTED_COLLISION', NOW()
                ) ON CONFLICT (alpha_id) DO UPDATE SET status = 'REJECTED_COLLISION', max_correlation = %s
            """, (aid, expr, arch or "Unknown", sh, fit, to, ret, dd, margin, max_c, universe, neut, decay, max_c))
            conn.commit()
            continue
            
        # 4. QUALIFIED! Committing to database vault
        print(f"  *** QUALIFIED! VAULTING ALPHA {aid} (Sharpe={sh}, Fit={fit}, Corr={max_c:+.4f}) ***", flush=True)
        cur.execute("""
            INSERT INTO options_alphas (
                alpha_id, expression, archetype, source, sharpe, fitness, turnover, 
                returns, drawdown, margin, max_correlation, universe, neutralization, decay,
                status, created_at
            ) VALUES (
                %s, %s, %s, 'salvage_screener', %s, %s, %s, 
                %s, %s, %s, %s, %s, %s, %s,
                'QUALIFIED', NOW()
            ) ON CONFLICT (alpha_id) DO UPDATE SET 
                status = 'QUALIFIED',
                sharpe = EXCLUDED.sharpe,
                fitness = EXCLUDED.fitness,
                turnover = EXCLUDED.turnover,
                returns = EXCLUDED.returns,
                drawdown = EXCLUDED.drawdown,
                margin = EXCLUDED.margin,
                max_correlation = EXCLUDED.max_correlation
        """, (
            aid, expr, arch or "Vault_Salvaged", sh, fit, to, 
            ret, dd, margin, max_c, universe, neut, decay
        ))
        conn.commit()
        
        # Add to ref_pnls cache
        ref_pnls[aid] = cand_daily
        with open(REF_CACHE_FILE, "w") as f:
            json.dump(ref_pnls, f)
            
        qualified_count += 1
        print(f"  >>> SUCCESS: Alpha {aid} VAULTED! Total Qualified in Vault: {qualified_count} <<<", flush=True)
        
    except Exception as e:
        print(f"  -> Error in corr/vault: {e}", flush=True)
        continue

print("\n" + "="*60, flush=True)
print(f"FINAL SCREENER REPORT: Screened {len(candidates)} candidates.", flush=True)
print(f"QUALIFIED & VAULTED: {qualified_count}", flush=True)
print(f"Failed Checklist: {failed_checklist}", flush=True)
print(f"Failed Margin: {failed_margin}", flush=True)
print(f"Failed Collision: {failed_collision}", flush=True)
print("="*60, flush=True)
