import os
from dotenv import load_dotenv
import psycopg

load_dotenv()
with psycopg.connect(os.getenv("DATABASE_URL")) as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 
                COUNT(*) as total_today,
                COUNT(CASE WHEN status = 'PASS' THEN 1 END) as pass_count,
                COUNT(CASE WHEN status = 'QUALIFIED' THEN 1 END) as qualified_count,
                COUNT(CASE WHEN status = 'CORRELATED' THEN 1 END) as correlated_count,
                COUNT(CASE WHEN status = 'OPTIMIZED' THEN 1 END) as optimized_count
            FROM options_evaluations
            WHERE created_at >= '2026-09-23 00:00:00+00';
        """)
        r = cur.fetchone()
        print("=== LIVE STATS FOR TODAY (2026-09-23) ===")
        print(f"Total Evaluated Today: {r[0]}")
        print(f"Stage 0 / Fast Passes: {r[1]}")
        print(f"Diagnostic Optimizations: {r[4]}")
        print(f"Qualified Alphas: {r[2]}")
        print(f"Correlated Alphas: {r[3]}")
        
        print("\n=== BREAKDOWN BY STRATEGY / ARCHETYPE TODAY ===")
        cur.execute("""
            SELECT archetype, count(*), 
                   count(case when status in ('PASS', 'QUALIFIED', 'OPTIMIZED') then 1 end) as good_count,
                   round(max(sharpe)::numeric, 2) as max_sharpe,
                   round(max(fitness)::numeric, 2) as max_fitness
            FROM options_evaluations
            WHERE created_at >= '2026-09-23 00:00:00+00'
            GROUP BY archetype
            ORDER BY count(*) DESC;
        """)
        for arch in cur.fetchall():
            print(f"  {str(arch[0]):<55} | Count: {arch[1]:>3} | Promising: {arch[2]:>2} | Max Sharpe: {arch[3]} | Max Fit: {arch[4]}")
