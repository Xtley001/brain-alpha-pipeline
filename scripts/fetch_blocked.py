import os, psycopg
from dotenv import load_dotenv
load_dotenv()
db_url = os.environ.get('DATABASE_URL')
blocked = ['Vkae25pb', 'N1a8nR9o', 'MPa2a1Eo', 'JjN2O3mA', 'XgbOPxXb']
with psycopg.connect(db_url) as conn:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT alpha_id, archetype, expression, universe, neutralization, delay, decay, "
            "sharpe, fitness, turnover, returns, drawdown "
            "FROM options_alphas WHERE alpha_id = ANY(%s) ORDER BY sharpe*fitness DESC;",
            (blocked,)
        )
        rows = cur.fetchall()
        for r in rows:
            print("ID:", r[0])
            print("Archetype:", r[1])
            print("Universe:", r[3], "| Neut:", r[4], "| Delay:", r[5], "| Decay:", r[6])
            print("Sharpe:", round(r[7],2), "| Fitness:", round(r[8],2),
                  "| Turnover:", round(r[9]*100,1), "% | Return:", round(r[10]*100,1),
                  "% | MaxDD:", round(r[11]*100,1), "%")
            print("Expression:", r[2])
            print()
