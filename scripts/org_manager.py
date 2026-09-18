"""
Intelligent GitHub Organizations Load Balancer & Task Dispatcher.
Coordinates and rotates heavy alpha generation, backtesting, and genetic optimization
across the 4 dedicated research organizations while keeping the primary account
exclusively dedicated to lean, timed submissions.
"""
import argparse
import json
import subprocess
import sys
from typing import Dict, List, Optional

WORKER_ORGS = [
    "xtley-alpha-research-01",
    "xtley-alpha-research-02",
    "xtley-alpha-research-03",
    "xtley-alpha-research-04",
]
PRIMARY_ACCOUNT = "Xtley001"
REPO_NAME = "brain-alpha-pipeline"


def check_org_status(org: str) -> dict:
    """Checks repository and workflow status for a given organization."""
    repo = f"{org}/{REPO_NAME}"
    status = {"org": org, "repo": repo, "online": False, "active_runs": 0, "is_private": False}
    
    # 1. Check repo visibility
    res = subprocess.run(f"gh repo view {repo} --json isPrivate,name", shell=True, capture_output=True, text=True)
    if res.returncode == 0:
        try:
            data = json.loads(res.stdout)
            status["online"] = True
            status["is_private"] = data.get("isPrivate", False)
        except Exception:
            status["online"] = True

    # 2. Check active workflow runs
    run_res = subprocess.run(
        f"gh run list --repo {repo} --status in_progress --json databaseId,workflowName",
        shell=True,
        capture_output=True,
        text=True
    )
    if run_res.returncode == 0:
        try:
            runs = json.loads(run_res.stdout)
            status["active_runs"] = len(runs)
        except Exception:
            pass

    return status


def get_cluster_status() -> list[dict]:
    """Inspects all worker organizations in the cluster."""
    print("=== Checking Alpha Generation Cluster Status ===")
    statuses = []
    for org in WORKER_ORGS:
        st = check_org_status(org)
        statuses.append(st)
        icon = "[ONLINE]" if st["online"] and st["is_private"] else "[OFFLINE]"
        print(f" {icon:<9} Org: {org:<26} | Private: {str(st['is_private']):<5} | Active Jobs: {st['active_runs']}")
    return statuses


def dispatch_generation_job(org: Optional[str] = None, archetype: Optional[str] = None):
    """
    Selects the optimal organization (least loaded) and triggers the heavy generation workflow.
    """
    statuses = get_cluster_status()
    online_workers = [s for s in statuses if s["online"]]
    if not online_workers:
        print("ERROR: No worker organizations are available.")
        return False

    # Choose worker with least active runs
    if org:
        target_worker = next((s for s in online_workers if s["org"] == org), None)
        if not target_worker:
            print(f"Worker {org} not found or offline.")
            return False
    else:
        # Load-balanced: pick worker with lowest active runs
        online_workers.sort(key=lambda s: s["active_runs"])
        target_worker = online_workers[0]

    chosen_org = target_worker["org"]
    print(f"\n>>> Routing Generation Job to: {target_repo} (Active Jobs: {target_worker['active_runs']})...")

    cmd = f"gh workflow run run.yml --repo {target_repo}"
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if res.returncode == 0:
        print(f"SUCCESS: Heavy generation workflow triggered on {target_repo}!")
        print("Output:", res.stdout.strip() or "Workflow queued successfully.")
        return True
    else:
        print(f"FAILED to trigger workflow: {res.stderr.strip()}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multi-Org Cluster Manager for Options Alpha Pipeline")
    parser.add_argument("--status", action="store_true", help="Display status of all organizations in cluster")
    parser.add_argument("--dispatch", action="store_true", help="Dispatch heavy generation job to least loaded org")
    parser.add_argument("--org", type=str, help="Specify a particular organization to dispatch to")
    args = parser.parse_args()

    if args.dispatch:
        dispatch_generation_job(org=args.org)
    else:
        get_cluster_status()
