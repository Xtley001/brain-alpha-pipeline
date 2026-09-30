import os
import psycopg
import dotenv

dotenv.load_dotenv()
db_url = os.environ.get("DATABASE_URL")

with psycopg.connect(db_url) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='candidates'")
        print("CANDIDATES columns:")
        for r in cur.fetchall():
            print(f"  {r[0]}: {r[1]}")
            
        cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='options_evaluations'")
        print("\nOPTIONS_EVALUATIONS columns:")
        for r in cur.fetchall():
            print(f"  {r[0]}: {r[1]}")

        cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='options_alphas'")
        print("\nOPTIONS_ALPHAS columns:")
        for r in cur.fetchall():
            print(f"  {r[0]}: {r[1]}")
