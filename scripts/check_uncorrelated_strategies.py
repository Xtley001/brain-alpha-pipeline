import os
from dotenv import load_dotenv
import psycopg

load_dotenv()
with psycopg.connect(os.getenv("DATABASE_URL")) as conn:
    with conn.cursor() as cur:
        print("=== HISTORICAL PERFORMANCE ACROSS ALL UNCROWDED / FRESH STRATEGIES ===")
        cur.execute("""
            SELECT 
                archetype,
                COUNT(*) as total_runs,
                COUNT(CASE WHEN sharpe >= 0.60 AND fitness >= 0.30 THEN 1 END) as stage0_passes,
                COUNT(CASE WHEN sharpe >= 1.25 THEN 1 END) as high_sharpe_count,
                round(avg(sharpe)::numeric, 2) as avg_sharpe,
                round(max(sharpe)::numeric, 2) as max_sharpe,
                round(max(fitness)::numeric, 2) as max_fitness,
                round(min(turnover)::numeric, 3) as min_turnover
            FROM options_evaluations
            GROUP BY archetype
            ORDER BY max_sharpe DESC;
        """)
        for r in cur.fetchall():
            arch = str(r[0])
            print(f"Strategy: {arch:<50} | Total: {r[1]:>4} | Stage0: {r[2]:>3} | Sharpe>=1.25: {r[3]:>2} | MaxSharpe: {r[5]} | MaxFit: {r[6]}")

        print("\n=== TOP 10 HIGHEST-REWARD SEEDS IN REINFORCEMENT LEARNING MEMORY ===")
        cur.execute("""
            SELECT archetype, expression, sharpe, fitness, reward, status
            FROM options_learning_memory
            WHERE archetype NOT ILIKE '%breakeven%'
            ORDER BY reward DESC
            LIMIT 10;
        """)
        for r in cur.fetchall():
            print(f"Archetype: {r[0]} | Sharpe: {r[2]} | Fit: {r[3]} | Reward: {r[4]} | Status: {r[5]}")
            print(f"  Expr: {r[1][:100]}...")
            print()
