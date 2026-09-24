import os
from dotenv import load_dotenv
import psycopg

load_dotenv()
with psycopg.connect(os.getenv("DATABASE_URL")) as conn:
    with conn.cursor() as cur:
        # Check all high-performing candidates today
        print("=== HIGH-PERFORMING CANDIDATES TODAY (Sharpe >= 1.20) ===")
        cur.execute("""
            SELECT id, alpha_id, archetype, stage, status, sharpe, fitness, turnover, returns, drawdown, created_at, expression
            FROM options_evaluations
            WHERE created_at >= '2026-09-23 00:00:00+00'
              AND sharpe >= 1.20
            ORDER BY sharpe DESC;
        """)
        rows = cur.fetchall()
        print(f"Total candidates today with Sharpe >= 1.20: {len(rows)}")
        for r in rows:
            print(f"ID:{r[0]} | AlphaID:{r[1]} | Stage:{r[3]} | Status:{r[4]} | Sharpe:{r[5]} | Fit:{r[6]} | TO:{r[7]} | Ret:{r[8]} | Arch:{r[2]}")
            print(f"  Expr: {r[11][:120]}...")
            print()

        # Check options_correlated_alphas from today
        print("\n=== CORRELATED ALPHAS FROM TODAY (2026-09-23) ===")
        cur.execute("""
            SELECT id, alpha_id, archetype, max_correlation, sharpe, fitness, created_at, expression
            FROM options_correlated_alphas
            WHERE created_at >= '2026-09-23 00:00:00+00'
            ORDER BY created_at DESC;
        """)
        corrs = cur.fetchall()
        print(f"Total correlated today: {len(corrs)}")
        for r in corrs:
            print(f"  AlphaID:{r[1]} | MaxCorr:{r[3]} | Sharpe:{r[4]} | Fit:{r[5]} | Arch:{r[2]}")
            print(f"    Expr: {r[7][:120]}...")

        # Check options_rejected_alphas from today
        print("\n=== REJECTED ALPHAS FROM TODAY (2026-09-23) ===")
        cur.execute("""
            SELECT id, alpha_id, archetype, rejection_reason, sharpe, fitness, created_at
            FROM options_rejected_alphas
            WHERE created_at >= '2026-09-23 00:00:00+00'
            ORDER BY created_at DESC;
        """)
        rejs = cur.fetchall()
        print(f"Total rejected today: {len(rejs)}")
        for r in rejs:
            print(f"  AlphaID:{r[1]} | Reason:{r[3]} | Sharpe:{r[4]} | Fit:{r[5]} | Arch:{r[2]}")
