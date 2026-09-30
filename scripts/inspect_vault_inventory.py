import os, sys
import psycopg
import dotenv

sys.stdout.reconfigure(encoding='utf-8')
dotenv.load_dotenv()

with psycopg.connect(os.environ['DATABASE_URL']) as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, alpha_id, archetype, sharpe, fitness, turnover, max_correlation, status, created_at
            FROM options_alphas
            ORDER BY sharpe DESC NULLS LAST;
        """)
        rows = cur.fetchall()
        print(f"DATABASE TABLE: 'options_alphas'")
        print(f"TOTAL ROWS IN TABLE: {len(rows)}\n")

        # Top 9 selected
        top9_ids = {'Grdg2Njo', 'N176Geqp', 'gJQWL7aK', 'levEYpmx', 'gJbAP76e', 'YPboG01w', 'KPNd6Ovl', 'Xgbv1A80', 'blbZ9Wkp'}
        
        print("=== THE 9 SELECTED FOR WEEKEND SUBMISSION ===")
        for r in rows:
            if r[1] in top9_ids:
                print(f"  [SELECTED] ID: {r[1]:<10} | Sharpe: {r[3]} | Fit: {r[4]} | TO: {float(r[5] or 0)*100:.1f}% | Corr: {r[6]} | Status: {r[7]} | Arch: {r[2]}")

        print(f"\n=== THE REMAINING {len(rows) - len(top9_ids)} ALPHAS LEFT IN 'options_alphas' ===")
        for r in rows:
            if r[1] not in top9_ids:
                print(f"  [RESERVE]  ID: {r[1]:<10} | Sharpe: {r[3]} | Fit: {r[4]} | TO: {float(r[5] or 0)*100:.1f}% | Corr: {r[6]} | Status: {r[7]} | Arch: {r[2]}")
