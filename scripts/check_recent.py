import os
from dotenv import load_dotenv
import psycopg

load_dotenv()
with psycopg.connect(os.getenv("DATABASE_URL")) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM options_evaluations WHERE created_at >= NOW() - INTERVAL '30 minutes';")
        cnt = cur.fetchone()[0]
        print(f"Evaluations in last 30 minutes: {cnt}")
        cur.execute("SELECT id, alpha_id, archetype, stage, status, sharpe, fitness, created_at FROM options_evaluations ORDER BY id DESC LIMIT 10;")
        for r in cur.fetchall():
            print(r)
