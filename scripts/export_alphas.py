"""
Export all generated alphas into CSV and JSON files within the codebase.

Fetches:
1. All alphas simulated and registered on WorldQuant BRAIN under the authenticated account.
2. All alpha candidates and sweep runs stored in the Neon Postgres pipeline database.
3. Assembles a unified master catalog sorted by performance (fitness & sharpe).

Outputs:
- all_generated_alphas.csv (at repo root for immediate accessibility)
- exported_alphas/master_generated_alphas.csv
- exported_alphas/worldquant_brain_alphas.csv
- exported_alphas/worldquant_brain_alphas.json
- exported_alphas/pipeline_candidates.csv
- exported_alphas/pipeline_sweep_runs.csv
- exported_alphas/README.md (data dictionary and usage guide)

Usage:
    python scripts/export_alphas.py
    python scripts/export_alphas.py --source brain
    python scripts/export_alphas.py --source db
    python scripts/export_alphas.py --output-dir custom_dir
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional

# Ensure repository root is on sys.path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(REPO_ROOT, ".env"))

from pipeline.brain.client import BrainClient
from pipeline.config import Config
from pipeline.db.repo import Repo

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("export_alphas")


async def fetch_brain_alphas(client: BrainClient) -> List[Dict[str, Any]]:
    """Fetch all alphas belonging to the user from WorldQuant BRAIN with pagination."""
    client.authenticate()
    session = client._get_session()
    
    alphas: List[Dict[str, Any]] = []
    limit = 100
    offset = 0
    
    log.info("Fetching alphas from WorldQuant BRAIN API (/users/self/alphas)...")
    while True:
        url = f"https://api.worldquantbrain.com/users/self/alphas?limit={limit}&offset={offset}"
        resp = await session.retry("GET", url, max_tries=5)
        if resp is None or resp.status_code >= 400:
            log.error(f"Failed to fetch BRAIN alphas at offset {offset}: status {getattr(resp, 'status_code', 'None')}")
            break
        data = resp.json()
        results = data.get("results", [])
        alphas.extend(results)
        log.info(f"  Fetched {len(results)} BRAIN alphas (total so far: {len(alphas)})")
        if not data.get("next") or len(results) < limit:
            break
        offset += limit

    log.info(f"Total BRAIN alphas fetched: {len(alphas)}")
    return alphas


def format_brain_records(brain_alphas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Transform raw BRAIN JSON into clean, flat tabular records for CSV."""
    records = []
    for a in brain_alphas:
        settings = a.get("settings") or {}
        is_metrics = a.get("is") or {}
        train_metrics = a.get("train") or {}
        test_metrics = a.get("test") or {}
        regular = a.get("regular") or {}
        
        checks = is_metrics.get("checks") or []
        failed_checks = [c.get("name") for c in checks if c.get("result") == "FAIL"]
        passed_checks = [c.get("name") for c in checks if c.get("result") == "PASS"]

        rec = {
            "alpha_id": a.get("id"),
            "expression": (regular.get("code") or "").strip(),
            "status": a.get("status"),
            "grade": a.get("grade"),
            "sharpe": is_metrics.get("sharpe"),
            "fitness": is_metrics.get("fitness"),
            "turnover": is_metrics.get("turnover"),
            "returns": is_metrics.get("returns"),
            "drawdown": is_metrics.get("drawdown"),
            "margin": is_metrics.get("margin"),
            "universe": settings.get("universe"),
            "delay": settings.get("delay"),
            "decay": settings.get("decay"),
            "neutralization": settings.get("neutralization"),
            "truncation": settings.get("truncation"),
            "pasteurization": settings.get("pasteurization"),
            "nan_handling": settings.get("nanHandling"),
            "unit_handling": settings.get("unitHandling"),
            "region": settings.get("region"),
            "instrument_type": settings.get("instrumentType"),
            "long_count": is_metrics.get("longCount"),
            "short_count": is_metrics.get("shortCount"),
            "pnl": is_metrics.get("pnl"),
            "book_size": is_metrics.get("bookSize"),
            "train_sharpe": train_metrics.get("sharpe"),
            "train_fitness": train_metrics.get("fitness"),
            "test_sharpe": test_metrics.get("sharpe"),
            "test_fitness": test_metrics.get("fitness"),
            "operator_count": regular.get("operatorCount"),
            "failed_checks": "; ".join(failed_checks),
            "passed_checks": "; ".join(passed_checks),
            "date_created": a.get("dateCreated"),
            "date_modified": a.get("dateModified"),
        }
        records.append(rec)
    return records


def fetch_db_data(database_url: str):
    """Fetch candidates and sweep runs from the Postgres database."""
    log.info("Connecting to Postgres database to fetch candidates and sweep runs...")
    repo = Repo(database_url)
    try:
        with repo._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, expression, category, generation_tier, provider, 
                           created_at, claimed_at, stage0_fitness, stage0_sharpe, 
                           status, attempts, last_error
                    FROM candidates
                    ORDER BY id ASC;
                """)
                cand_cols = [desc[0] for desc in cur.description]
                candidates = [dict(zip(cand_cols, row)) for row in cur.fetchall()]
                log.info(f"Fetched {len(candidates)} candidate alphas from DB.")

                cur.execute("""
                    SELECT id, candidate_id, stage, delay, universe, neutralization, 
                           decay, truncation, pasteurization, nan_handling, 
                           sharpe, fitness, turnover, returns_ann, drawdown, 
                           simulated_at, error_text
                    FROM sweep_runs
                    ORDER BY id ASC;
                """)
                sweep_cols = [desc[0] for desc in cur.description]
                sweep_runs = [dict(zip(sweep_cols, row)) for row in cur.fetchall()]
                log.info(f"Fetched {len(sweep_runs)} sweep runs from DB.")

                return candidates, cand_cols, sweep_runs, sweep_cols
    finally:
        repo.close()


def build_master_catalog(
    brain_records: List[Dict[str, Any]], 
    candidates: List[Dict[str, Any]], 
    sweep_runs: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Build unified catalog sorted by fitness and sharpe descending."""
    best_sweep_by_candidate: Dict[int, Dict[str, Any]] = {}
    for s in sweep_runs:
        cid = s["candidate_id"]
        fit = float(s["fitness"]) if s["fitness"] is not None else -999.0
        if cid not in best_sweep_by_candidate or fit > (float(best_sweep_by_candidate[cid]["fitness"] or -999.0)):
            best_sweep_by_candidate[cid] = s

    master: List[Dict[str, Any]] = []

    for b in brain_records:
        master.append({
            "source": "worldquant_brain",
            "source_id": b["alpha_id"],
            "expression": b["expression"],
            "sharpe": b["sharpe"],
            "fitness": b["fitness"],
            "turnover": b["turnover"],
            "returns": b["returns"],
            "drawdown": b["drawdown"],
            "margin": b["margin"],
            "universe": b["universe"],
            "neutralization": b["neutralization"],
            "delay": b["delay"],
            "decay": b["decay"],
            "truncation": b["truncation"],
            "pasteurization": b["pasteurization"],
            "nan_handling": b["nan_handling"],
            "status": b["status"],
            "grade": b["grade"],
            "generation_tier": "brain_platform",
            "provider": "brain_api",
            "category": "",
            "date_created": b["date_created"],
        })

    for c in candidates:
        best_s = best_sweep_by_candidate.get(c["id"], {})
        master.append({
            "source": "pipeline_db",
            "source_id": str(c["id"]),
            "expression": (c["expression"] or "").strip(),
            "sharpe": float(best_s["sharpe"]) if best_s.get("sharpe") is not None else None,
            "fitness": float(best_s["fitness"]) if best_s.get("fitness") is not None else None,
            "turnover": float(best_s["turnover"]) if best_s.get("turnover") is not None else None,
            "returns": float(best_s["returns_ann"]) if best_s.get("returns_ann") is not None else None,
            "drawdown": float(best_s["drawdown"]) if best_s.get("drawdown") is not None else None,
            "margin": None,
            "universe": best_s.get("universe") or "TOP3000",
            "neutralization": best_s.get("neutralization") or "SUBINDUSTRY",
            "delay": best_s.get("delay") or 1,
            "decay": best_s.get("decay") or 8,
            "truncation": float(best_s["truncation"]) if best_s.get("truncation") is not None else 0.08,
            "pasteurization": "ON" if best_s.get("pasteurization") else "OFF",
            "nan_handling": "ON" if best_s.get("nan_handling") else "OFF",
            "status": c["status"],
            "grade": "",
            "generation_tier": c["generation_tier"] or "",
            "provider": c["provider"] or "",
            "category": c["category"] or "",
            "date_created": str(c["created_at"]) if c.get("created_at") else "",
        })

    # Sort descending by fitness, then sharpe (putting None at bottom)
    def sort_key(item):
        fit = item["fitness"] if item["fitness"] is not None else -9999.0
        shp = item["sharpe"] if item["sharpe"] is not None else -9999.0
        return (float(fit), float(shp))

    master.sort(key=sort_key, reverse=True)
    return master


def write_csv(filepath: str, records: List[Dict[str, Any]], fieldnames: Optional[List[str]] = None) -> None:
    """Write list of dictionaries to CSV."""
    if not records:
        log.warning(f"No records to write for {filepath}")
        return
    if not fieldnames:
        fieldnames = list(records[0].keys())
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
    log.info(f"Saved CSV: {filepath} ({len(records)} rows, {os.path.getsize(filepath) / 1024:.1f} KB)")


def write_readme(output_dir: str, summary: Dict[str, Any]) -> None:
    readme_path = os.path.join(output_dir, "README.md")
    content = f"""# Exported Alphas Catalog

This directory contains exported datasets of all alpha signals generated, simulated, and tracked across both the **WorldQuant BRAIN Platform** and the **Pipeline Database (Neon Postgres)**.

## Summary

- **Total Unified Alpha Records**: {summary.get('master_count', 0)}
- **WorldQuant BRAIN Platform Alphas**: {summary.get('brain_count', 0)}
- **Pipeline Candidates**: {summary.get('candidates_count', 0)}
- **Pipeline Sweep Runs**: {summary.get('sweep_count', 0)}
- **Top In-Sample Sharpe Recorded**: {summary.get('top_sharpe', 'N/A')}
- **Top In-Sample Fitness Recorded**: {summary.get('top_fitness', 'N/A')}

---

## File Catalog

| File | Description | Records | Format |
| :--- | :--- | :--- | :--- |
| [`all_generated_alphas.csv`](../all_generated_alphas.csv) | Master unified file at repository root sorted by Fitness & Sharpe | {summary.get('master_count', 0)} | CSV |
| [`master_generated_alphas.csv`](./master_generated_alphas.csv) | Master catalog in export directory | {summary.get('master_count', 0)} | CSV |
| [`worldquant_brain_alphas.csv`](./worldquant_brain_alphas.csv) | Flattened simulation records directly from WorldQuant BRAIN API | {summary.get('brain_count', 0)} | CSV |
| [`worldquant_brain_alphas.json`](./worldquant_brain_alphas.json) | Complete raw nested JSON with all check results, train/test stats | {summary.get('brain_count', 0)} | JSON |
| [`pipeline_candidates.csv`](./pipeline_candidates.csv) | Alpha candidates generated by template and LLM (Groq) engines | {summary.get('candidates_count', 0)} | CSV |
| [`pipeline_sweep_runs.csv`](./pipeline_sweep_runs.csv) | Multi-stage simulation sweeps performed by the worker | {summary.get('sweep_count', 0)} | CSV |

---

## Column Descriptions (`all_generated_alphas.csv` / `master_generated_alphas.csv`)

| Column | Type | Description |
| :--- | :--- | :--- |
| `source` | string | `worldquant_brain` (on BRAIN platform) or `pipeline_db` (local candidate) |
| `source_id` | string | Alpha ID on BRAIN (e.g. `78Zzqr75`) or Candidate ID (e.g. `1`) |
| `expression` | string | FastExpr alpha formula code |
| `sharpe` | float | Annualized In-Sample Sharpe Ratio |
| `fitness` | float | WorldQuant BRAIN Fitness score |
| `turnover` | float | Daily portfolio turnover (fraction between 0.0 and 1.0) |
| `returns` | float | Annualized return |
| `drawdown` | float | Maximum drawdown |
| `margin` | float | Average profit margin per dollar traded |
| `universe` | string | Target equity universe (e.g. `TOP3000`) |
| `neutralization` | string | Group neutralization (`SUBINDUSTRY`, `SECTOR`, `INDUSTRY`, `MARKET`, `NONE`) |
| `delay` | integer | Simulation delay (`0` or `1`) |
| `decay` | integer | Signal decay (`0`, `4`, `8`, `15`, `20`) |
| `truncation` | float | Position weight truncation (e.g. `0.08`, `0.05`) |
| `pasteurization` | string | Outlier pasteurization (`ON` / `OFF`) |
| `nan_handling` | string | NaN replacement (`ON` / `OFF`) |
| `status` | string | `UNSUBMITTED`, `pending`, `passed`, `rejected_stage0`, etc. |
| `grade` | string | BRAIN grade (e.g. `INFERIOR`, `ACCEPTABLE`, etc.) |
| `generation_tier` | string | `template`, `llm`, or `brain_platform` |
| `provider` | string | LLM provider (`groq`, `brain_api`, etc.) |
| `category` | string | Seed strategy category |
| `date_created` | string | ISO timestamp of generation |

---

## How to Re-export

Run the script whenever new alphas are generated:

```bash
python scripts/export_alphas.py
```
"""
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(content)
    log.info(f"Saved documentation: {readme_path}")


async def main_async(args):
    output_dir = os.path.abspath(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)
    
    config = Config.from_env(require_brain=(args.source in ("all", "brain")), require_telegram=False)

    brain_records: List[Dict[str, Any]] = []
    candidates: List[Dict[str, Any]] = []
    sweep_runs: List[Dict[str, Any]] = []
    cand_cols: List[str] = []
    sweep_cols: List[str] = []

    # 1. BRAIN API
    if args.source in ("all", "brain"):
        try:
            client = BrainClient(config.brain_username, config.brain_password)
            brain_alphas = await fetch_brain_alphas(client)
            
            # Save raw JSON
            brain_json_path = os.path.join(output_dir, "worldquant_brain_alphas.json")
            with open(brain_json_path, "w", encoding="utf-8") as f:
                json.dump(brain_alphas, f, indent=2)
            log.info(f"Saved JSON: {brain_json_path} ({len(brain_alphas)} alphas)")

            brain_records = format_brain_records(brain_alphas)
            brain_csv_path = os.path.join(output_dir, "worldquant_brain_alphas.csv")
            write_csv(brain_csv_path, brain_records)
        except Exception as e:
            log.error(f"Error fetching BRAIN alphas: {e}", exc_info=True)

    # 2. Pipeline Database
    if args.source in ("all", "db"):
        try:
            candidates, cand_cols, sweep_runs, sweep_cols = fetch_db_data(config.database_url)
            cand_csv_path = os.path.join(output_dir, "pipeline_candidates.csv")
            write_csv(cand_csv_path, candidates, cand_cols)

            sweep_csv_path = os.path.join(output_dir, "pipeline_sweep_runs.csv")
            write_csv(sweep_csv_path, sweep_runs, sweep_cols)
        except Exception as e:
            log.error(f"Error fetching DB data: {e}", exc_info=True)

    # 3. Master Unified Catalog
    master = build_master_catalog(brain_records, candidates, sweep_runs)
    master_csv_path = os.path.join(output_dir, "master_generated_alphas.csv")
    write_csv(master_csv_path, master)

    # Root CSV
    root_csv_path = os.path.join(REPO_ROOT, args.root_csv)
    write_csv(root_csv_path, master)

    # Summary
    top_sharpe = master[0]["sharpe"] if master else "N/A"
    top_fitness = master[0]["fitness"] if master else "N/A"
    write_readme(output_dir, {
        "master_count": len(master),
        "brain_count": len(brain_records),
        "candidates_count": len(candidates),
        "sweep_count": len(sweep_runs),
        "top_sharpe": top_sharpe,
        "top_fitness": top_fitness,
    })

    log.info("=" * 60)
    log.info("ALPHA EXPORT COMPLETED SUCCESSFULLY")
    log.info(f"Master file: {root_csv_path} ({len(master)} alphas)")
    log.info(f"Export directory: {output_dir}")
    log.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Export generated alphas to CSV/JSON")
    parser.add_argument("--output-dir", default=os.path.join(REPO_ROOT, "exported_alphas"), help="Output directory")
    parser.add_argument("--root-csv", default="all_generated_alphas.csv", help="Name of master CSV at repo root")
    parser.add_argument("--source", choices=["all", "brain", "db"], default="all", help="Which sources to export")
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
