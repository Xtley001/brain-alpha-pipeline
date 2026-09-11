"""
Sanitize candidate queue in Postgres:
1. Reclaims orphaned 'running' candidates to 'pending'
2. Detects expressions with non-BRAIN variables/functions and marks them 'rejected_error'
   so simulation quota is spent purely on 100% syntactically valid BRAIN alphas.
"""
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(REPO_ROOT, ".env"))

from pipeline.db.repo import Repo

VALID_TOKENS = {
    # BRAIN Data fields
    'open', 'high', 'low', 'close', 'volume', 'vwap', 'returns', 'cap', 'adv20', 'sharesout', 'split', 'dividend',
    # Groups
    'sector', 'industry', 'subindustry', 'market',
    # Cross-sectional operators
    'rank', 'group_rank', 'group_neutralize', 'group_zscore', 'group_mean', 'quantile',
    # Time-series operators
    'ts_rank', 'ts_zscore', 'ts_decay_linear', 'ts_delta', 'ts_delay', 'ts_mean',
    'ts_std_dev', 'ts_max', 'ts_min', 'ts_corr', 'ts_covariance', 'ts_sum', 'ts_product',
    'ts_arg_max', 'ts_arg_min',
    # Math / transform / conditional operators
    'trade_when', 'signed_power', 'scale', 'min', 'max', 'abs', 'sign', 'log', 'hump', 'power', 'sqrt'
}


def sanitize():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not set!")
        return

    repo = Repo(db_url)
    try:
        # 1. Reclaim orphaned running
        reclaimed = repo.reclaim_orphaned_running(older_than_minutes=0)
        print(f"Reclaimed {reclaimed} orphaned running candidates back to pending.")

        # 2. Check pending expressions
        with repo._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, expression FROM candidates WHERE status = 'pending'")
                rows = cur.fetchall()
                print(f"Auditing {len(rows)} pending candidates...")

                invalid_ids = []
                for cid, expr in rows:
                    tokens = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*', expr)
                    unknowns = [t for t in tokens if t not in VALID_TOKENS and not t.isdigit()]
                    if unknowns:
                        invalid_ids.append((cid, f"Unknown BRAIN token: {unknowns[0]}"))

                print(f"Found {len(invalid_ids)} candidates with invalid tokens out of {len(rows)}.")
                
                if invalid_ids:
                    bad_cids = [x[0] for x in invalid_ids]
                    cur.execute(
                        "UPDATE candidates SET status = 'rejected_error', last_error = 'Unknown variable or operator', attempts = 3 WHERE id = ANY(%s)",
                        (bad_cids,)
                    )
                    conn.commit()
                    print(f"Successfully marked {len(bad_cids)} candidates as rejected_error.")

                
                cur.execute("SELECT status, count(*) FROM candidates GROUP BY status")
                print("Updated Candidate Statuses:", cur.fetchall())
    finally:
        repo.close()


if __name__ == "__main__":
    sanitize()
