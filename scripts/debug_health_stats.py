import os
import psycopg
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv("DATABASE_URL")
print("Connecting to:", db_url[:30], "...")

with psycopg.connect(db_url) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='options_alphas';")
        cols = cur.fetchall()
        print("\n--- COLUMNS IN options_alphas ---")
        for c in cols:
            print(f"  {c[0]} ({c[1]})")

        cur.execute("SELECT status, COUNT(*) FROM options_alphas GROUP BY status;")
        print("\n--- STATUS BREAKDOWN IN options_alphas ---")
        for s in cur.fetchall():
            print(f"  status='{s[0]}': {s[1]} rows")

        cur.execute("SELECT id, alpha_id, status, created_at, submitted_at, archetype FROM options_alphas ORDER BY id DESC LIMIT 20;")
        print("\n--- LATEST 20 ROWS IN options_alphas ---")
        for r in cur.fetchall():
            print(f"  id={r[0]}, alpha_id={r[1]}, status={r[2]}, created_at={r[3]}, archetype={r[5]}")

        cur.execute("SELECT COUNT(*) FROM options_evaluations;")
        print(f"\n--- TOTAL ROWS IN options_evaluations: {cur.fetchone()[0]} ---")

        cur.execute("SELECT COUNT(*) FROM options_evaluations WHERE created_at >= (CURRENT_TIMESTAMP AT TIME ZONE 'America/New_York')::date;")
        print(f"--- TODAY (NY date) EVALUATIONS: {cur.fetchone()[0]} ---")

        cur.execute("SELECT COUNT(*) FROM options_evaluations WHERE created_at >= CURRENT_DATE;")
        print(f"--- TODAY (UTC date) EVALUATIONS: {cur.fetchone()[0]} ---")

        cur.execute("SELECT created_at FROM options_evaluations ORDER BY id DESC LIMIT 5;")
        print("--- LATEST 5 EVALUATIONS CREATED_AT ---")
        for r in cur.fetchall():
            print(f"  {r[0]}")
