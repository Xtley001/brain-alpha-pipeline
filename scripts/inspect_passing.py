import os, psycopg, dotenv
dotenv.load_dotenv()
conn = psycopg.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()
cur.execute("SELECT alpha_id, archetype, universe, neutralization, decay, expression FROM options_alphas WHERE alpha_id IN ('e7bWxz7E', 'mLmQjlzE', 'XgbOoJjx')")
for r in cur.fetchall():
    print(f"Alpha: {r[0]} | Archetype: {r[1]}")
    print(f"  Universe: {r[2]} | Neut: {r[3]} | Decay: {r[4]}")
    print(f"  Expression: {r[5]}\n")
