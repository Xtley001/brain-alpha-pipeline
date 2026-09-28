import psycopg, os, dotenv
dotenv.load_dotenv()
with psycopg.connect(os.environ['DATABASE_URL'], autocommit=True) as conn:
    with conn.cursor() as cur:
        cur.execute("UPDATE options_alphas SET status = 'SUPERSEDED' WHERE alpha_id = 'XgbOPxXb';")
        print("XgbOPxXb marked as SUPERSEDED.")
