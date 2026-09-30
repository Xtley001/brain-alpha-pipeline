import os
import psycopg
import dotenv

dotenv.load_dotenv()

with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
        tables = [r[0] for r in cur.fetchall()]
        print("Checking tables for records from 2026-09-30:")
        for t in tables:
            cur.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name='{t}'")
            cols = [r[0] for r in cur.fetchall()]
            date_col = None
            for c in ["created_at", "updated_at", "timestamp", "evaluated_at", "fired_at"]:
                if c in cols:
                    date_col = c
                    break
            if date_col:
                cur.execute(f"SELECT COUNT(*) FROM {t} WHERE {date_col} >= '2026-09-30 00:00:00'")
                cnt = cur.fetchone()[0]
                if cnt > 0:
                    print(f"  {t} ({date_col}): {cnt} rows today")
                    # show latest 2
                    cur.execute(f"SELECT * FROM {t} WHERE {date_col} >= '2026-09-30 00:00:00' ORDER BY {date_col} DESC LIMIT 2")
                    for r in cur.fetchall():
                        print(f"    sample: {str(r)[:120]}")
