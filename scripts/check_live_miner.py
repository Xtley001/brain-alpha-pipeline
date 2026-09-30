import os
import psycopg
import dotenv

dotenv.load_dotenv()
db_url = os.environ.get("DATABASE_URL")

with psycopg.connect(db_url) as conn:
    with conn.cursor() as cur:
        # Check column names of options_evaluations
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='options_evaluations'")
        cols = [r[0] for r in cur.fetchall()]
        print("COLS:", cols)
        
        # Check evaluations since 11:00 UTC today
        cur.execute("""
            SELECT id, alpha_id, sharpe, fitness, turnover, returns, archetype, created_at
            FROM options_evaluations
            ORDER BY id DESC
            LIMIT 20;
        """)
        rows = cur.fetchall()
        print(f"\nMost recent {len(rows)} evaluations:")
        for r in rows:
            print(f"  ID={r[0]} | Alpha={r[1]} | Sharpe={r[2]} | Fit={r[3]} | TO={r[4]} | Ret={r[5]} | Arch={r[6]} | Time={r[7]}")

        # Check max sharpe today
        cur.execute("""
            SELECT alpha_id, sharpe, fitness, turnover, returns, archetype, expression, created_at
            FROM options_evaluations
            WHERE created_at >= '2026-09-30 00:00:00'
            ORDER BY sharpe DESC
            LIMIT 15;
        """)
        top = cur.fetchall()
        print(f"\nTop 15 Sharpe today:")
        for r in top:
            print(f"  Alpha={r[0]} | Sharpe={r[1]} | Fit={r[2]} | TO={r[3]} | Arch={r[5]} | Time={r[7]}")
            print(f"    Expr: {r[6][:100]}")
