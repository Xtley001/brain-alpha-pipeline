import os
import psycopg
import dotenv

dotenv.load_dotenv()
db_url = os.environ.get("DATABASE_URL")

pillars = [
    'pcr_flow',
    'analyst_revisions',
    'accruals_cashflow',
    'jump_variance_moments',
    'peavrp_volatility_premia',
    'iv_lead_lag',
    'extreme_tail_risk',
    'capex_asset_growth',
    'Supply Chain Lead-Lag Momentum'
]

with psycopg.connect(db_url) as conn:
    with conn.cursor() as cur:
        for p in pillars:
            cur.execute("""
                SELECT id, alpha_id, archetype, sharpe, fitness, turnover, returns, drawdown, expression, status
                FROM options_evaluations
                WHERE archetype = %s AND sharpe IS NOT NULL AND sharpe > 0.8
                ORDER BY sharpe DESC
                LIMIT 3
            """, (p,))
            rows = cur.fetchall()
            print(f"\n=== PILLAR: {p} (Found: {len(rows)}) ===")
            for r in rows:
                print(f"ID:{r[0]} | AlphaID:{r[1]} | Sharpe:{r[3]} | Fit:{r[4]} | Turn:{r[5]} | DD:{r[7]} | Status:{r[9]}")
                print(f"   Expr: {r[8]}")
