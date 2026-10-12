import psycopg, re, os
from dotenv import load_dotenv

load_dotenv()

# 1. DB Count
conn = psycopg.connect(os.getenv("DATABASE_URL"))
cur = conn.cursor()
cur.execute("SELECT count(*) FROM options_alphas WHERE status = 'QUALIFIED';")
qual_count = cur.fetchone()[0]
conn.close()

# 2. Parse Log
log_path = "logs/omni_vault_miner.log"
pat = re.compile(r"\[Worker \d+\] ([a-zA-Z0-9]+) \| Sharpe=([-\d\.]+) \| Fit=([-\d\.]+) \| TO=([\d\.]+)% \| Margin=([-\d\.]+)bps \| DD=([\d\.]+)% \| (.+)")
sim_pat = re.compile(r"\[Worker \d+ \| #(\d+) \| Qualified: (\d+)/\d+\]")

results = []
latest_sim = 0
if os.path.exists(log_path):
    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            m = pat.search(line)
            if m:
                aid, sh, fit, to, mg, dd, arch = m.groups()
                results.append((float(sh), float(fit), float(to), float(mg), float(dd), aid, arch.strip()))
            sm = sim_pat.search(line)
            if sm:
                latest_sim = int(sm.group(1))

results.sort(reverse=True, key=lambda x: x[0])
print(f"SIMS_COMPLETED: {len(results)}")
print(f"LATEST_SIM_INDEX: {latest_sim}")
print(f"QUALIFIED_IN_DB: {qual_count}")
print("TOP_CANDIDATES:")
for r in results[:5]:
    print(f"  {r[5]} | Sharpe={r[0]:.2f} | Fit={r[1]:.2f} | TO={r[2]:.1f}% | Margin={r[3]:.1f}bps | DD={r[4]:.1f}% | {r[6]}")
