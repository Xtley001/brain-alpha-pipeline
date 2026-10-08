import os
import psycopg
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv("DATABASE_URL")

with psycopg.connect(db_url) as conn:
    with conn.cursor() as cur:
        print("=" * 70)
        print("OCTOBER 1 AUDIT: SIMULATIONS & SUBMISSIONS")
        print("=" * 70)

        # 1. Submissions on Oct 1
        cur.execute("""
            SELECT alpha_id, archetype, sharpe, fitness, submitted_at, created_at, status 
            FROM options_alphas 
            WHERE (submitted_at >= '2026-10-01 00:00:00+00' AND submitted_at < '2026-10-02 00:00:00+00')
               OR (created_at >= '2026-10-01 00:00:00+00' AND created_at < '2026-10-02 00:00:00+00');
        """)
        oct1_subs = cur.fetchall()
        print(f"\n1. ALPHAS SUBMITTED / RECORDED ON OCTOBER 1: {len(oct1_subs)}")
        for r in oct1_subs:
            print(f"  • {r[0]} | Arch: {r[1]} | Status: {r[6]} | SubAt: {r[4]} | Created: {r[5]}")

        # 2. Evaluations recorded on Oct 1
        cur.execute("""
            SELECT COUNT(*), COUNT(*) FILTER (WHERE status = 'PASS'), MAX(sharpe)
            FROM options_evaluations 
            WHERE created_at >= '2026-10-01 00:00:00+00' AND created_at < '2026-10-02 00:00:00+00';
        """)
        eval_row = cur.fetchone()
        print(f"\n2. DB RECORDED SIMULATIONS ON OCT 1: {eval_row[0]} (Passed: {eval_row[1]}, Max Sharpe: {eval_row[2]})")

        # 3. Total submissions across all time
        cur.execute("""
            SELECT status, COUNT(*) FROM options_alphas GROUP BY status;
        """)
        print("\n3. TOTAL LIFETIME POOL IN options_alphas:")
        for s in cur.fetchall():
            print(f"  • Status='{s[0]}': {s[1]}")
