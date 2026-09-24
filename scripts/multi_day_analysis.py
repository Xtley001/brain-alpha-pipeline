import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

with psycopg.connect(os.getenv("DATABASE_URL")) as conn:
    with conn.cursor() as cur:
        print("=== CHECKING QPbbXNJK IN ALL TABLES ===")
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public';")
        tables = [t[0] for t in cur.fetchall()]
        for t in tables:
            try:
                cur.execute(f"SELECT * FROM {t} WHERE alpha_id = 'QPbbXNJK';")
                rows = cur.fetchall()
                if rows:
                    print(f"Table '{t}': {len(rows)} matching rows:")
                    for r in rows:
                        print("  ", r)
            except Exception:
                conn.rollback()

        print("\n=== MULTI-DAY EVALUATION STATS (Mon Sep 21 -> Thu Sep 24) ===")
        cur.execute("""
            SELECT 
                (created_at AT TIME ZONE 'UTC')::date as day,
                to_char(created_at AT TIME ZONE 'UTC', 'Day') as day_name,
                count(*) as total_evals,
                count(*) FILTER (WHERE stage = 'STAGE0' AND status = 'PASS') as stage0_pass,
                count(*) FILTER (WHERE sharpe >= 1.25) as high_sharpe,
                count(*) FILTER (WHERE sharpe >= 1.25 AND fitness >= 1.0) as cleared_hurdles,
                round(max(sharpe)::numeric, 2) as max_sharpe,
                round(max(fitness)::numeric, 2) as max_fitness,
                round(avg(sharpe)::numeric, 2) as avg_sharpe
            FROM options_evaluations
            WHERE created_at >= '2026-09-21 00:00:00+00'
            GROUP BY 1, 2
            ORDER BY 1 ASC;
        """)
        days = cur.fetchall()
        print(f"{'Date':<12} | {'Day':<10} | {'Total':<6} | {'S0 Pass':<8} | {'Sharpe>=1.25':<12} | {'Cleared':<8} | {'Peak Sharpe':<12} | {'Peak Fit':<10}")
        print("-" * 90)
        for d in days:
            print(f"{str(d[0]):<12} | {d[1].strip():<10} | {d[2]:<6} | {d[3]:<8} | {d[4]:<12} | {d[5]:<8} | {d[6]:<12} | {d[7]:<10}")

        print("\n=== OPTIONS_ALPHAS TABLE (ALL QUALIFIED / SUBMITTED) ===")
        cur.execute("""
            SELECT id, alpha_id, archetype, status, round(sharpe::numeric, 2), round(fitness::numeric, 2), 
                   round(turnover::numeric, 4), round(max_correlation::numeric, 4), created_at, submitted_at
            FROM options_alphas
            ORDER BY created_at DESC;
        """)
        for a in cur.fetchall():
            print(f"ID:{a[0]} | AlphaID:{a[1]} | Status:{a[3]} | Sharpe:{a[4]} | Fit:{a[5]} | TO:{a[6]} | Corr:{a[7]}")
            print(f"  Created: {a[8]} | SubAt: {a[9]} | Arch: {a[2]}")

        print("\n=== RECENT ACTIONS / EVALS FROM TODAY (2026-09-24) ===")
        cur.execute("""
            SELECT count(*), 
                   count(*) FILTER (WHERE stage = 'STAGE0' AND status = 'PASS'),
                   count(*) FILTER (WHERE sharpe >= 1.25),
                   max(sharpe),
                   max(fitness)
            FROM options_evaluations
            WHERE (created_at AT TIME ZONE 'UTC')::date = '2026-09-24';
        """)
        today_tot = cur.fetchone()
        print(f"Today (24th): Total={today_tot[0]}, S0_Pass={today_tot[1]}, Sharpe>=1.25={today_tot[2]}, PeakSharpe={today_tot[3]}, PeakFit={today_tot[4]}")
