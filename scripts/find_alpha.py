import os
import sys
from dotenv import load_dotenv
import psycopg

load_dotenv()

with psycopg.connect(os.getenv("DATABASE_URL")) as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, alpha_id, archetype, stage, status, sharpe, fitness, turnover, returns, drawdown, created_at, expression
            FROM options_evaluations
            WHERE created_at >= '2026-09-22 00:00:00+00' AND created_at < '2026-09-23 00:00:00+00'
              AND status = 'QUALIFIED';
        """)
        rows = cur.fetchall()
        print("=== QUALIFIED IN OPTIONS_EVALUATIONS (2026-09-22) ===")
        for r in rows:
            print("ID:", r[0], "AlphaID:", r[1], "Arch:", r[2], "Stage:", r[3], "Sharpe:", r[5], "Fit:", r[6], "Created:", r[10])
            print("Expression:", r[11])
            aid = r[1]
            print(f"\nSearching for alpha_id '{aid}' across all tables:")
            for tbl in ['options_alphas', 'options_correlated_alphas', 'options_rejected_alphas', 'options_learning_memory', 'candidates']:
                try:
                    cur.execute(f"SELECT * FROM {tbl} WHERE alpha_id = %s;", (aid,))
                    t_rows = cur.fetchall()
                    print(f"  Table {tbl}: {len(t_rows)} row(s)")
                    for tr in t_rows:
                        print("   ->", tr)
                except Exception as e:
                    print(f"  Table {tbl}: err {e}")

        # Also check all rows in options_alphas with created_at or submitted_at on or around Sept 22
        print("\n=== ALL ROWS IN OPTIONS_ALPHAS ===")
        cur.execute("SELECT id, alpha_id, archetype, sharpe, fitness, turnover, max_correlation, status, submitted_at, created_at FROM options_alphas ORDER BY id DESC;")
        for r in cur.fetchall():
            print(r)
