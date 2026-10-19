#!/usr/bin/env python3
"""
Dedicated Top 3 Category First-50 Alpha Miner & Qualifier.
Focuses strictly on:
  - Model (Value Score: 7.0) — Datasets: model51, model16
  - Option (Value Score: 6.0) — Datasets: option8, option9
  - Analyst & Fundamental (Value Score: 5.0) — Datasets: analyst4, fundamental6
  - Apex Tri-Factor Cross-Category Synthesis (Orthogonal fusion)

Governance & Safety Rules:
  - 100% ZERO AUTO-SUBMISSIONS TO BRAIN: All qualified alphas are banked to PostgreSQL
    (options_alphas table) with status 'QUALIFIED'.
  - No submissions occur until explicit user command.
  - Pairwise correlation |rho| <= 0.62 vs all baselines.
  - Strict BRAIN Hurdle Gate: Sharpe >= 1.25, Fitness >= 1.00, Turnover <= 25%, Margin >= 25 bps.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.master_quintuple_vault_miner_500 import (
    get_current_qualified_count,
    run_quintuple_vault_miner,
    send_tg_message,
)


def main():
    parser = argparse.ArgumentParser(description="Dedicated Top 3 Category First-50 Alpha Miner")
    parser.add_argument("--target", type=int, default=50, help="Target count of qualified alphas to bank (default: 50)")
    parser.add_argument(
        "--pillar",
        type=str,
        default="top3",
        choices=["top3", "options", "risk", "fundamental", "apex"],
        help="Target pillar to focus on (default: top3)",
    )
    args = parser.parse_args()

    asyncio.run(run_quintuple_vault_miner(target_count=args.target, pillar=args.pillar))


if __name__ == "__main__":
    main()
