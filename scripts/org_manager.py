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

ORG_SPECIALIZATIONS = {
    "xtley-alpha-research-01": "breakeven",
    "xtley-alpha-research-02": "skew",
    "xtley-alpha-research-03": "term_structure",
    "xtley-alpha-research-04": "forward_basis,pcr_flow",
}

ORG_SCHEDULES = {
    "xtley-alpha-research-01": "0 */2 * * * (Even :00 UTC)",
    "xtley-alpha-research-02": "30 */2 * * * (Even :30 UTC)",
    "xtley-alpha-research-03": "0 1-23/2 * * * (Odd :00 UTC)",
    "xtley-alpha-research-04": "30 1-23/2 * * * (Odd :30 UTC)",
}


def check_org_status(org: str) -> dict:
    """Checks repository and workflow status for a given organization."""
    repo = f"{org}/{REPO_NAME}"
    status = {
        "org": org,
        "repo": repo,
        "online": False,
        "active_runs": 0,
        "is_private": False,
        "specialization": ORG_SPECIALIZATIONS.get(org, "general"),
        "schedule": ORG_SCHEDULES.get(org, "unscheduled"),
    }

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
    print("=" * 88)
    print(" WORLDQUANT BRAIN MULTI-ORG DIVIDE-AND-CONQUER RESEARCH CLUSTER")
    print("=" * 88)
    statuses = []
    for org in WORKER_ORGS:
        st = check_org_status(org)
        statuses.append(st)
        icon = "[ONLINE]" if st["online"] and st["is_private"] else "[OFFLINE]"
        spec = st["specialization"]
        sched = st["schedule"]
        print(f" {icon:<9} Org: {org:<24} | Spec: {spec:<22} | Active: {st['active_runs']}")
        print(f"           Schedule: {sched}")
    print("-" * 88)
    print(f" Primary Submitter Account: {PRIMARY_ACCOUNT} (drip.yml, 5 checks/day, 24h New York pacing)")
    print(" Automated Schedule Cadence: 1 run every 30 minutes 24/7 (48 runs/day total, zero slot collisions)")
    print("=" * 88)
    return statuses


def dispatch_generation_job(org: Optional[str] = None, candidates: int = 20, archetype: str = "") -> bool:
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
    target_repo = target_worker["repo"]
    spec = archetype or target_worker["specialization"]
    print(f"\n>>> Routing Generation Job to: {target_repo} (Specialization: {spec}, Active Jobs: {target_worker['active_runs']})...")

    cmd = f"gh workflow run run.yml --repo {target_repo} -f candidates={candidates}"
    if spec:
        cmd += f" -f archetype={spec}"
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if res.returncode == 0:
        print(f"SUCCESS: Heavy generation workflow triggered on {target_repo}!")
        print("Output:", res.stdout.strip() or "Workflow queued successfully.")
        return True
    else:
        print(f"FAILED to trigger workflow: {res.stderr.strip()}")
        return False


def fanout_generation_jobs(candidates_per_org: int = 20, archetype: str = "") -> list[dict]:
    """
    Fans out parallel generation jobs across all online worker organizations in the cluster
    with each worker targeting its specialized archetype.
    """
    statuses = get_cluster_status()
    online_workers = [s for s in statuses if s["online"]]
    if not online_workers:
        print("ERROR: No worker organizations are available for fanout.")
        return []

    print(f"\n>>> FANOUT: Dispatching {candidates_per_org} candidates across {len(online_workers)} specialized worker orgs...")
    results = []
    for worker in online_workers:
        repo = worker["repo"]
        spec = archetype or worker["specialization"]
        cmd = f"gh workflow run run.yml --repo {repo} -f candidates={candidates_per_org}"
        if spec:
            cmd += f" -f archetype={spec}"
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        ok = res.returncode == 0
        status_msg = f"SUCCESS (Specialization: {spec})" if ok else f"FAILED: {res.stderr.strip()}"
        print(f"  [{worker['org']}] {status_msg}")
        results.append({"org": worker["org"], "repo": repo, "success": ok, "specialization": spec})

    successful = sum(1 for r in results if r["success"])
    total_cand = successful * candidates_per_org
    print(f"\nFanout complete: {successful}/{len(online_workers)} orgs triggered ({total_cand} candidates evaluating in parallel).")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multi-Org Cluster Manager for Options Alpha Pipeline")
    parser.add_argument("--status", action="store_true", help="Display status of all organizations in cluster")
    parser.add_argument("--dispatch", action="store_true", help="Dispatch heavy generation job to least loaded org")
    parser.add_argument("--fanout", action="store_true", help="Dispatch parallel heavy generation jobs across ALL online worker orgs")
    parser.add_argument("--org", type=str, help="Specify a particular organization to dispatch to")
    parser.add_argument("--archetype", type=str, default="", help="Target specific archetype override")
    parser.add_argument("--candidates", type=int, default=20, help="Number of candidates to evaluate per job (default: 20)")
    args = parser.parse_args()

    if args.fanout:
        fanout_generation_jobs(candidates_per_org=args.candidates, archetype=args.archetype)
    elif args.dispatch:
        dispatch_generation_job(org=args.org, candidates=args.candidates, archetype=args.archetype)
    else:
        get_cluster_status()
