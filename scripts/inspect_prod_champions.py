import sys
sys.path.insert(0, '.')
import brain_options.core.dns_fallback
import psycopg
from brain_options.config import OptionsConfig

cfg = OptionsConfig.from_env()
with psycopg.connect(cfg.database_url) as conn:
    with conn.cursor() as cur:
        aids = ['58gVPJln', 'RR6X0G1b', 'RR6LGgEz', 'omWexGgv', '1YZvpqKk']
        cur.execute("SELECT alpha_id, sharpe, fitness, turnover, margin, universe, neutralization, decay, expression FROM options_alphas WHERE alpha_id = ANY(%s)", (aids,))
        rows = cur.fetchall()
        for r in rows:
            print(f"ID={r[0]} | Sharpe={r[1]} | Fit={r[2]} | TO={float(r[3])*100:.1f}% | Margin={float(r[4])*10000:.1f}bps | Univ={r[5]} | Neut={r[6]} | Decay={r[7]}")
            print(f"Expr: {r[8]}")
            print("-" * 80)
