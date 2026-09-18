import sys
import os
sys.path.insert(0, os.path.abspath("."))
from dotenv import load_dotenv
load_dotenv()
from brain_options.store.db import OptionsDatabase

db = OptionsDatabase(os.getenv("DATABASE_URL"))
with db._get_connection() as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT alpha_id, status, archetype, sharpe, fitness, margin, turnover FROM options_alphas WHERE alpha_id = 'mLmkaxd6'")
        print("mLmkaxd6:", cur.fetchone())

        cur.execute("SELECT count(*) FROM options_alphas WHERE status != 'SUBMITTED' AND status != 'CORRELATED' AND alpha_id IS NOT NULL")
        print("Total eligible unsubmitted:", cur.fetchone()[0])

        cur.execute("""
            SELECT alpha_id, archetype, sharpe, fitness, margin, turnover,
                   (1.0 * COALESCE(sharpe, 0) + 1.2 * COALESCE(fitness, 0) + 200 * COALESCE(margin, 0) - 0.5 * COALESCE(turnover, 0)) AS cqs
            FROM options_alphas
            WHERE status != 'SUBMITTED' AND status != 'CORRELATED' AND alpha_id IS NOT NULL
            ORDER BY cqs DESC, sharpe DESC
            LIMIT 10;
        """)
        print("\nTop 10 candidates by CQS:")
        for r in cur.fetchall():
            print(r)
