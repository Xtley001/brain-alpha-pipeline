import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

db_url = os.getenv("DATABASE_URL")
if not db_url:
    print("Error: DATABASE_URL not set.")
    exit(1)

with psycopg.connect(db_url) as conn:
    with conn.cursor() as cur:
        # 1. Total overview for today
        cur.execute("""
            SELECT 
                count(*) as total_sims,
                count(*) FILTER (WHERE stage = 'STAGE0' AND status = 'PASS') as stage0_passes,
                count(*) FILTER (WHERE stage LIKE 'DIAG_%' OR stage = 'RETRY_COMPLETED') as diag_passes,
                count(*) FILTER (WHERE sharpe >= 1.25) as sharpe_ge_125,
                count(*) FILTER (WHERE sharpe >= 1.25 AND fitness >= 1.00) as cleared_hurdles,
                max(sharpe) as peak_sharpe,
                max(fitness) as peak_fitness
            FROM options_evaluations
            WHERE (created_at AT TIME ZONE 'UTC')::date = '2026-09-23';
        """)
        totals = cur.fetchone()
        print("=== TODAY'S COMPLETE TOTALS (2026-09-23) ===")
        print(f"Total Simulations: {totals[0]}")
        print(f"Stage 0 Passes: {totals[1]}")
        print(f"Diagnostic Refinements: {totals[2]}")
        print(f"Sharpe >= 1.25: {totals[3]}")
        print(f"Sharpe >= 1.25 & Fitness >= 1.00: {totals[4]}")
        print(f"Peak Sharpe: {totals[5]}")
        print(f"Peak Fitness: {totals[6]}")
        print()

        # 2. Hourly Breakdown (UTC+1 / Local Time and UTC)
        cur.execute("""
            SELECT 
                to_char(created_at AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:00') as hour_utc,
                to_char(created_at AT TIME ZONE '+01', 'HH24:00') as hour_wat,
                count(*) as total_evals,
                count(*) FILTER (WHERE stage = 'STAGE0' AND status = 'PASS') as s0_pass,
                count(*) FILTER (WHERE stage LIKE 'DIAG_%') as diag_evals,
                count(*) FILTER (WHERE sharpe >= 1.25) as high_sharpe,
                round(max(sharpe)::numeric, 2) as max_sharpe,
                round(max(fitness)::numeric, 2) as max_fitness,
                round(avg(sharpe)::numeric, 2) as avg_sharpe
            FROM options_evaluations
            WHERE (created_at AT TIME ZONE 'UTC')::date = '2026-09-23'
            GROUP BY 1, 2
            ORDER BY 1 ASC;
        """)
        hourly_rows = cur.fetchall()
        print("=== HOURLY EVALUATION BREAKDOWN ===")
        print(f"{'Hour (UTC)':<18} | {'Hour (WAT/Local)':<16} | {'Total':<6} | {'S0 Pass':<8} | {'Diag Steps':<11} | {'Sharpe>=1.25':<12} | {'Peak Sharpe':<12} | {'Peak Fit':<10}")
        print("-" * 110)
        for h in hourly_rows:
            print(f"{h[0]:<18} | {h[1]:<16} | {h[2]:<6} | {h[3]:<8} | {h[4]:<11} | {h[5]:<12} | {h[6]:<12} | {h[7]:<10}")
        print()

        # 3. Strategy breakdown today
        print("=== STRATEGY BREAKDOWN TODAY ===")
        cur.execute("""
            SELECT 
                archetype,
                count(*) as count,
                count(*) FILTER (WHERE stage = 'STAGE0' AND status = 'PASS') as s0_pass,
                round(max(sharpe)::numeric, 2) as max_sharpe,
                round(max(fitness)::numeric, 2) as max_fitness
            FROM options_evaluations
            WHERE (created_at AT TIME ZONE 'UTC')::date = '2026-09-23'
            GROUP BY archetype
            ORDER BY count DESC;
        """)
        for s in cur.fetchall():
            print(f"  {str(s[0]):<55} | Total: {s[1]:>3} | S0 Pass: {s[2]:>2} | Peak Sharpe: {s[3]} | Peak Fit: {s[4]}")
