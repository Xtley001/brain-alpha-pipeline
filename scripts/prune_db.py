import os, sys
from dotenv import load_dotenv; load_dotenv()
import psycopg

db_url = os.environ.get('DATABASE_URL')
print(f"Connecting to DB: {db_url[:30]}...")

try:
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            print("Successfully connected! Running prune query...")
            cur.execute("SELECT count(*) FROM options_evaluations;")
            print("Current evaluations count:", cur.fetchone()[0])
            cur.execute("""
                DELETE FROM options_evaluations 
                WHERE created_at < NOW() - INTERVAL '5 days' 
                  AND (sharpe < 1.25 OR sharpe IS NULL);
            """)
            print("Deleted old sub-hurdle evaluations. Committing...")
            conn.commit()
            print("Commit complete. Running VACUUM...")
            conn.autocommit = True
            cur.execute("VACUUM options_evaluations;")
            print("VACUUM complete!")
            cur.execute("SELECT count(*) FROM options_evaluations;")
            print("New evaluations count:", cur.fetchone()[0])
except Exception as e:
    print(f"Prune failed: {e}")
