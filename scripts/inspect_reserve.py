import os
import psycopg
import dotenv

dotenv.load_dotenv()
db_url = os.environ.get("DATABASE_URL")

with psycopg.connect(db_url) as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 
                alpha_id, archetype, universe, neutralization, decay,
                sharpe, fitness, turnover, returns, drawdown, margin, max_correlation, expression
            FROM options_alphas 
            WHERE status = 'QUALIFIED'
            ORDER BY created_at DESC
        """)
        rows = cur.fetchall()
        print(f"Total in reserve: {len(rows)}")
        for r in rows:
            print(f"ID: {r[0]} | Archetype: {r[1]}")
            print(f"Settings: Universe={r[2]}, Neutralization={r[3]}, Decay={r[4]}")
            print(f"IS Sharpe: {r[5]}")
            print(f"IS Fitness: {r[6]}")
            print(f"IS Annualized Return: {float(r[8])*100:.2f}%")
            print(f"IS Max Drawdown: {float(r[9])*100:.2f}%")
            print(f"IS Turnover: {float(r[7])*100:.2f}%")
            print(f"IS Margin: {float(r[10])*10000:.1f} bps")
            print(f"Max Portfolio Correlation: {float(r[11]):.4f}")
            print(f"Expression: {r[12]}\n")
