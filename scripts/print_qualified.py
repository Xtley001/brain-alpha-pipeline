import os
import psycopg
import dotenv

dotenv.load_dotenv()
db_url = os.environ.get("DATABASE_URL")

with psycopg.connect(db_url) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT alpha_id, sharpe, fitness, turnover, margin, max_correlation, status, source FROM options_alphas WHERE status = 'QUALIFIED' ORDER BY created_at DESC")
        rows = cur.fetchall()
        print(f"Total QUALIFIED alphas in DB: {len(rows)}")
        for r in rows:
            print(f"  ID: {r[0]}, Sharpe: {r[1]}, Fit: {r[2]}, TO: {r[3]}, Margin: {r[4]}, MaxCorr: {r[5]}, Source: {r[7]}")
