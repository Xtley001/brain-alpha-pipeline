import sys
sys.path.insert(0, '.')
import brain_options.core.dns_fallback
import psycopg
from brain_options.config import OptionsConfig

cfg = OptionsConfig.from_env()
with psycopg.connect(cfg.database_url) as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT alpha_id, sharpe, fitness, turnover, margin, drawdown, expression, universe, neutralization, decay, archetype
            FROM options_alphas WHERE status = 'NEAR_MISS_RESERVE'
        """)
        rows = cur.fetchall()
        print(f"Total NEAR_MISS_RESERVE: {len(rows)}")
        for r in rows:
            print(f"ID={r[0]} | Sharpe={r[1]} | Fit={r[2]} | TO={float(r[3])*100:.1f}% | Mg={float(r[4])*10000:.1f}bps | DD={float(r[5])*100:.1f}% | Univ={r[7]} | Neut={r[8]} | Decay={r[9]}")
            print(f"Arch: {r[10]}")
            print(f"Expr: {r[6]}")
            print("-" * 70)
