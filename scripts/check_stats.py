import os
import sys
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import psycopg

load_dotenv()

db_url = os.getenv("DATABASE_URL")
if not db_url:
    print("No DATABASE_URL found in .env")
    sys.exit(1)

with psycopg.connect(db_url, connect_timeout=15) as conn:
    with conn.cursor() as cur:
        # Check org_runs
        print("=== ORG RUNS (RECENT 25) ===")
        cur.execute("SELECT * FROM org_runs LIMIT 25;")
        for r in cur.fetchall():
            print(f"  {r}")
        print()

        # Check run_history
        print("=== RUN HISTORY (RECENT 20) ===")
        cur.execute("SELECT * FROM run_history LIMIT 20;")
        for r in cur.fetchall():
            print(f"  {r}")
        print()

        # Yesterday's Stats Breakdown (2026-09-22)
        print("=== YESTERDAY (2026-09-22) BREAKDOWN ===")
        cur.execute("""
            SELECT status, count(*), 
                   round(avg(sharpe)::numeric, 3), 
                   round(avg(fitness)::numeric, 3),
                   round(avg(turnover)::numeric, 4)
            FROM options_evaluations
            WHERE (created_at AT TIME ZONE 'UTC')::date = '2026-09-22'
            GROUP BY status;
        """)
        for r in cur.fetchall():
            print(f"  Status: {r[0]:<15} | Count: {r[1]:>5} | AvgSharpe: {r[2]} | AvgFitness: {r[3]} | AvgTurnover: {r[4]}")
        print()

        print("=== YESTERDAY'S ARCHETYPES EVALUATED ===")
        cur.execute("""
            SELECT archetype, count(*),
                   COUNT(CASE WHEN status IN ('QUALIFIED', 'PASS', 'CORRELATED') THEN 1 END) as good_count,
                   round(max(sharpe)::numeric, 2) as max_sharpe
            FROM options_evaluations
            WHERE (created_at AT TIME ZONE 'UTC')::date = '2026-09-22'
            GROUP BY archetype
            ORDER BY count(*) DESC;
        """)
        for r in cur.fetchall():
            print(f"  Archetype: {str(r[0]):<50} | Count: {r[1]:>4} | Good: {r[2]:>3} | MaxSharpe: {r[3]}")
        print()

        # Today's Stats Breakdown (2026-09-23)
        print("=== TODAY (2026-09-23) BREAKDOWN ===")
        cur.execute("""
            SELECT status, count(*), 
                   round(avg(sharpe)::numeric, 3), 
                   round(avg(fitness)::numeric, 3),
                   round(avg(turnover)::numeric, 4)
            FROM options_evaluations
            WHERE (created_at AT TIME ZONE 'UTC')::date = '2026-09-23'
            GROUP BY status;
        """)
        for r in cur.fetchall():
            print(f"  Status: {r[0]:<15} | Count: {r[1]:>5} | AvgSharpe: {r[2]} | AvgFitness: {r[3]} | AvgTurnover: {r[4]}")
        print()

        print("=== TODAY (2026-09-23) ALL EVALUATIONS ===")
        cur.execute("""
            SELECT id, stage, status, sharpe, fitness, turnover, alpha_id, archetype, created_at, expression
            FROM options_evaluations
            WHERE (created_at AT TIME ZONE 'UTC')::date = '2026-09-23'
            ORDER BY created_at ASC;
        """)
        rows = cur.fetchall()
        print(f"Total evaluated today: {len(rows)}")
        for r in rows:
            print(f"  [{r[8]}] ID:{r[0]} | Stage:{r[1]} | Status:{r[2]} | Sharpe:{r[3]} | Fit:{r[4]} | AlphaID:{r[6]} | Arch:{r[7]}")
            print(f"     Expr: {r[9][:110]}")
        print()

        # Correlated Alphas from yesterday and today
        print("=== CORRELATED ALPHAS (2026-09-22 and 2026-09-23) ===")
        cur.execute("""
            SELECT id, alpha_id, archetype, max_correlation, sharpe, fitness, turnover, returns, drawdown, created_at, expression
            FROM options_correlated_alphas
            WHERE created_at >= '2026-09-22 00:00:00+00'
            ORDER BY created_at DESC;
        """)
        corrs = cur.fetchall()
        print(f"Total correlated alphas in 22nd-23rd: {len(corrs)}")
        for r in corrs:
            print(f"  ID:{r[0]} | AlphaID:{r[1]} | Arch:{r[2]} | MaxCorr:{r[3]} | Sharpe:{r[4]} | Fit:{r[5]} | Time:{r[9]}")
            print(f"     Expr: {r[10]}")
        print()

        # Telegram Pacer / Hourly health
        print("=== CLUSTER SESSION CACHE DETAILS ===")
        cur.execute("SELECT key, token_type, expires_at, updated_at FROM cluster_session_cache;")
        for r in cur.fetchall():
            print(f"  Key: {r[0]} | Type: {r[1]} | Exp: {r[2]} | Updated: {r[3]}")
