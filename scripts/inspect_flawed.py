import os
import psycopg
import dotenv

dotenv.load_dotenv()
db_url = os.environ.get("DATABASE_URL")

with psycopg.connect(db_url) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT alpha_id, expression, decay, universe, neutralization, sharpe, fitness, turnover, margin FROM options_alphas WHERE alpha_id IN ('Vkae25pb', 'N1a8nR9o', 'JjN2O3mA', 'MPa2a1Eo')")
        for r in cur.fetchall():
            print(f"ID={r[0]}, u={r[3]}, neut={r[4]}, d={r[2]}, Sharpe={r[5]}, Fit={r[6]}, TO={r[7]}, Margin={r[8]}")
            print(f"Expr: {r[1]}\n")
