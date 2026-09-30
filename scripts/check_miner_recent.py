import os
import psycopg
import dotenv

dotenv.load_dotenv()

with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='pipeline_alerts_log'")
        cols = [r[0] for r in cur.fetchall()]
        print("Alerts columns:", cols)
        cur.execute("SELECT * FROM pipeline_alerts_log ORDER BY id DESC LIMIT 5;")
        for r in cur.fetchall():
            print("Alert:", r)
