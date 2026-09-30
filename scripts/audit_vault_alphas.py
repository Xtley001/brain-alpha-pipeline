import os, sys
import psycopg
import dotenv

sys.stdout.reconfigure(encoding='utf-8')
dotenv.load_dotenv()

with psycopg.connect(os.environ['DATABASE_URL']) as conn:
    with conn.cursor() as cur:
        # Check all column names in options_alphas
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='options_alphas'")
        cols = [r[0] for r in cur.fetchall()]
        print("COLUMNS IN options_alphas:", cols)

        cur.execute("""
            SELECT id, alpha_id, archetype, sharpe, fitness, turnover, margin, max_correlation, status, created_at, universe, neutralization, decay
            FROM options_alphas
            ORDER BY created_at DESC;
        """)
        rows = cur.fetchall()
        print(f"\nTOTAL ROWS IN options_alphas: {len(rows)}")
        print("="*100)
        for r in rows:
            print(f"DB_ID: {r[0]:<3} | AlphaID: {r[1]:<10} | CreatedAt: {str(r[9])[:19]} | Status: {r[8]:<20} | Sharpe: {r[3]} | Fit: {r[4]} | Corr: {r[7]}")
            print(f"   Arch: {r[2]}")
            print(f"   Settings: Univ={r[10]}, Neut={r[11]}, Decay={r[12]}")
            print("-" * 100)
