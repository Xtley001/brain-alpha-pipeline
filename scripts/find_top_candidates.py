import os
import psycopg
import dotenv

dotenv.load_dotenv()
db_url = os.environ.get("DATABASE_URL")

with psycopg.connect(db_url) as conn:
    with conn.cursor() as cur:
        print("=== TOP 20 IN OPTIONS_EVALUATIONS ===")
        cur.execute("""
            SELECT id, alpha_id, archetype, sharpe, fitness, turnover, returns, drawdown, expression, status, stage
            FROM options_evaluations
            WHERE sharpe >= 1.2
            ORDER BY sharpe DESC
            LIMIT 20
        """)
        rows = cur.fetchall()
        for r in rows:
            print(f"ID:{r[0]} | AlphaID:{r[1]} | Arch:{r[2]} | Sharpe:{r[3]} | Fit:{r[4]} | Turn:{r[5]} | Status:{r[9]} | Stage:{r[10]}")
            print(f"   Expr: {r[8][:110]}")

        print("\n=== TOP 20 IN CANDIDATES ===")
        cur.execute("""
            SELECT id, category, stage0_sharpe, stage0_fitness, status, expression
            FROM candidates
            WHERE stage0_sharpe >= 1.2
            ORDER BY stage0_sharpe DESC
            LIMIT 20
        """)
        rows = cur.fetchall()
        for r in rows:
            print(f"ID:{r[0]} | Cat:{r[1]} | Sharpe:{r[2]} | Fit:{r[3]} | Status:{r[4]}")
            print(f"   Expr: {r[5][:110]}")

        print("\n=== ALL IN OPTIONS_ALPHAS ===")
        cur.execute("""
            SELECT id, alpha_id, archetype, sharpe, fitness, margin, max_correlation, status, universe, decay
            FROM options_alphas
            ORDER BY id DESC
        """)
        rows = cur.fetchall()
        for r in rows:
            print(f"ID:{r[0]} | AlphaID:{r[1]} | Arch:{r[2]} | Sharpe:{r[3]} | Fit:{r[4]} | Margin:{r[5]} | Corr:{r[6]} | Status:{r[7]} | Univ:{r[8]} | Decay:{r[9]}")
