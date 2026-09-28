import os, psycopg, dotenv
dotenv.load_dotenv()
conn = psycopg.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()
cur.execute("""
    SELECT alpha_id, archetype, sharpe, fitness, max_correlation, status, (sharpe * fitness) AS is_score
    FROM options_alphas
    WHERE status = 'QUALIFIED'
    ORDER BY is_score DESC;
""")
rows = cur.fetchall()
print(f"Total QUALIFIED in Database Vault: {len(rows)}")
for i, r in enumerate(rows):
    print(f"#{i+1:02d} | ID: {r[0]} | Archetype: {r[1]} | Sharpe: {r[2]} | Fitness: {r[3]} | Corr: {r[4]} | IS Score: {round(r[6], 3)}")
