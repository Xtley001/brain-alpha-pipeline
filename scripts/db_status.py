import sys
sys.path.insert(0, '.')
import psycopg
from brain_options.config import OptionsConfig

def main():
    cfg = OptionsConfig.from_env()
    with psycopg.connect(cfg.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status, count(*) FROM options_alphas GROUP BY status ORDER BY count(*) DESC")
            rows = cur.fetchall()
            print("=== DB STATUS BREAKDOWN ===")
            for st, cnt in rows:
                print(f"  {st}: {cnt}")
            cur.execute("SELECT count(*) FROM options_alphas WHERE status = 'QUALIFIED'")
            qualified = cur.fetchone()[0]
            print(f"\n=== SENTIMENT RESERVE PROGRESS ===")
            print(f"  QUALIFIED RESERVE: {qualified} / 98")
            print(f"  REMAINING TO MINE: {max(0, 98 - qualified)}")
            cur.execute("SELECT alpha_id, archetype, universe, sharpe, fitness, margin, status FROM options_alphas WHERE status = 'QUALIFIED' ORDER BY sharpe DESC")
            q_rows = cur.fetchall()
            print(f"\n=== CURRENT QUALIFIED RESERVE ({len(q_rows)}) ===")
            for r in q_rows:
                print(f"  {r[0]} | {r[2]:8s} | Sharpe={r[3]} | Fit={r[4]} | Margin={float(r[5])*10000:.1f}bps | {r[1]}")

if __name__ == "__main__":
    main()
