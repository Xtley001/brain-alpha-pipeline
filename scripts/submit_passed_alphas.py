"""
Submit passed alphas to WorldQuant BRAIN platform.

Endpoints:
- POST https://api.worldquantbrain.com/alphas/{alpha_id}/submit

Usage:
    python scripts/submit_passed_alphas.py --alpha-id d5OKJYqJ
    python scripts/submit_passed_alphas.py --all-passed
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(REPO_ROOT, ".env"))

from pipeline.brain.client import BrainClient
from pipeline.config import Config
from pipeline.db.repo import Repo

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("submit_alphas")


async def submit_one(client: BrainClient, repo: Repo, alpha_id: str):
    log.info(f"Attempting to submit alpha {alpha_id} to WorldQuant BRAIN...")
    res = await client.submit_alpha(alpha_id)
    if res.get("ok"):
        log.info(f"✅ SUCCESS: Alpha {alpha_id} submitted to WorldQuant BRAIN!")
        # Update repo if present
        try:
            repo.mark_submitted(candidate_id=0)  # generic marker
        except Exception:
            pass
    else:
        log.error(f"❌ FAILED to submit alpha {alpha_id}: {res.get('message')}")
        data = res.get("data", {})
        if isinstance(data, dict):
            checks = data.get("is", {}).get("checks", [])
            for c in checks:
                if c.get("result") == "FAIL":
                    log.error(f"   Check Failed: {c.get('name')} (value={c.get('value')}, limit={c.get('limit')})")
            self_corr = data.get("is", {}).get("selfCorrelated", {}).get("records", [])
            if self_corr:
                log.error(f"   Self-correlated with existing alphas: {self_corr}")
    return res


async def submit_all_passed(client: BrainClient, repo: Repo):
    log.info("Querying review_store for passed, unsubmitted alphas...")
    candidates = repo.ranked_review_store(limit=50)
    if not candidates:
        log.info("No unsubmitted passed alphas found in review_store.")
        return

    log.info(f"Found {len(candidates)} unsubmitted candidates.")
    # Submit each sequentially
    for c in candidates:
        alpha_id = c.get("alpha_id")
        if alpha_id:
            await submit_one(client, repo, alpha_id)
            await asyncio.sleep(2.0)


async def main_async(args):
    config = Config.from_env(require_brain=True, require_telegram=False)
    client = BrainClient(config.brain_username, config.brain_password)
    client.authenticate()
    repo = Repo(config.database_url)

    try:
        if args.alpha_id:
            await submit_one(client, repo, args.alpha_id)
        elif args.all_passed:
            await submit_all_passed(client, repo)
        else:
            print("Please specify --alpha-id <id> or --all-passed")
    finally:
        repo.close()


def main():
    parser = argparse.ArgumentParser(description="Submit passed alphas to WorldQuant BRAIN")
    parser.add_argument("--alpha-id", help="Single alpha ID to submit")
    parser.add_argument("--all-passed", action="store_true", help="Submit all unsubmitted passed alphas from review_store")
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
