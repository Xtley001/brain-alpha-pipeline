"""
Utility script to requeue all falsely rejected candidates back to 'pending'.
Because of the historical BRAIN response-parsing bug where /simulations was parsed
directly before fetching /alphas/{alpha_id}, all historical candidates were recorded
with Sharpe=0.0 and marked as 'rejected_stage0'.

This script resets them back to 'pending' so the worker can re-evaluate them accurately.
"""
from __future__ import annotations

import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from pipeline.config import Config
from pipeline.db.repo import Repo


def main():
    config = Config.from_env()
    repo = Repo(config.database_url)
    with repo._get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE candidates
                SET status = 'pending',
                    attempts = 0,
                    stage0_sharpe = NULL,
                    stage0_fitness = NULL,
                    last_error = NULL
                WHERE status = 'rejected_stage0'
                """
            )
            count = cur.rowcount
            conn.commit()
            print(f"Successfully requeued {count} candidates to 'pending' state.")
    repo.close()


if __name__ == "__main__":
    main()
