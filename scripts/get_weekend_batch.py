import os, sys
import psycopg
import dotenv

sys.stdout.reconfigure(encoding='utf-8')
dotenv.load_dotenv()

with psycopg.connect(os.environ['DATABASE_URL']) as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT alpha_id, archetype, sharpe, fitness, turnover, margin, max_correlation, expression, universe, neutralization, decay
            FROM options_alphas
            WHERE status = 'SUBMITTED' AND (max_correlation IS NULL OR max_correlation < 0.70)
            ORDER BY sharpe DESC;
        """)
        rows = cur.fetchall()
        print(f"Total Low-Correlation Alphas Ready in Vault: {len(rows)}")
        for idx, r in enumerate(rows[:9], 1):
            day = "FRIDAY (Batch 1)" if idx <= 3 else ("SATURDAY (Batch 2)" if idx <= 6 else "SUNDAY (Batch 3)")
            print(f"\n--- {day} | Alpha #{idx} ---")
            print(f"Alpha ID: {r[0]} | Archetype: {r[1]}")
            print(f"Metrics: Sharpe={r[2]} | Fitness={r[3]} | Turnover={float(r[4] or 0)*100:.1f}% | Margin={float(r[5] or 0)*10000:.1f} bps | Max Corr={r[6]}")
            print(f"Simulation Settings: Universe={r[8]}, Neutralization={r[9]}, Decay={r[10]}")
            print(f"Expression:\n{r[7]}")
