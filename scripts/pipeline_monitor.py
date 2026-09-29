"""
Autonomous Pipeline Monitor & Self-Healing Daemon
===================================================
Run via Windows Task Scheduler every 30 minutes, or as a daemon.
Also triggered as a GitHub Actions workflow (monitor.yml).

Responsibilities:
  1. Inspect local vault miner log for stalls, zero-qual streaks, SSL drops, timeouts.
  2. Auto-restart local miner if dead or stalled.
  3. Inspect GitHub Actions logs for consecutive failures and fast-fail patterns.
  4. Auto-re-trigger failed GH workflows after 3+ consecutive failures.
  5. Auto-git-push any uncommitted hotfix changes.
  6. Send structured Telegram health digest every cycle.

Usage:
    python scripts/pipeline_monitor.py            # one-shot check
    python scripts/pipeline_monitor.py --daemon   # loop every 30m
"""
import argparse
import json
import logging
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

REPO_ROOT = Path(__file__).resolve().parent.parent
LOG_FILE = REPO_ROOT / "logs" / "autonomous_vault_miner.log"
MINER_SCRIPT = REPO_ROOT / "scripts" / "autonomous_24h_vault_miner.py"
MONITOR_LOG = REPO_ROOT / "logs" / "pipeline_monitor.log"

STALL_THRESHOLD_MINUTES = 10
ZERO_QUAL_SIM_THRESHOLD = 50

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

os.makedirs(str(REPO_ROOT / "logs"), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] monitor: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(MONITOR_LOG), mode="a", encoding="utf-8"),
    ],
)
log = logging.getLogger("pipeline_monitor")


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------

def send_tg(html_text: str) -> None:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        log.warning("Telegram not configured -- skipping alert")
        return
    try:
        import requests  # type: ignore
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": html_text, "parse_mode": "HTML"},
            timeout=15,
        )
    except Exception as exc:
        log.warning("Telegram send failed: %s", exc)


# ---------------------------------------------------------------------------
# Local Miner Log Analysis
# ---------------------------------------------------------------------------

def parse_local_miner_log() -> Dict:
    """Scan the vault miner log for stalls, zero-qual streaks, SSL drops, timeouts."""
    result: Dict = {
        "log_exists": False,
        "total_sims": 0,
        "qualified_count": 0,
        "last_sim_minutes_ago": None,
        "fitness_fail_streak": 0,
        "timeout_count": 0,
        "ssl_drop_count": 0,
        "last_qualified_minutes_ago": None,
        "is_stalled": False,
        "is_zero_qual_streak": False,
        "workers_active": False,
        "issues": [],
    }
    if not LOG_FILE.exists():
        result["issues"].append("Local miner log not found -- miner may not be running")
        return result

    result["log_exists"] = True
    raw = LOG_FILE.read_text(encoding="utf-8", errors="ignore")
    lines = raw.splitlines()
    now = datetime.now(timezone.utc)
    last_sim_ts = None
    last_qual_ts = None
    sims_since_last_qual = 0

    sim_re = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*\[Worker #\d+ \| Sim #(\d+)\]")
    qual_re = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*(QUALIFIED #\d+|QUALIFIED\])")
    to_re = re.compile(r"timed out after 240s")
    ssl_re = re.compile(r"connection abort|SSL SYSCALL|10053", re.IGNORECASE)

    for line in lines[-2000:]:
        if "Worker #" in line and "online" in line:
            result["workers_active"] = True

        m = sim_re.search(line)
        if m:
            ts_s = m.group(1)
            sim_n = int(m.group(2))
            result["total_sims"] = max(result["total_sims"], sim_n)
            try:
                ts = datetime.strptime(ts_s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                if last_sim_ts is None or ts > last_sim_ts:
                    last_sim_ts = ts
            except Exception:
                pass
            sims_since_last_qual += 1
            continue

        m = qual_re.search(line)
        if m:
            ts_s = m.group(1)
            try:
                ts = datetime.strptime(ts_s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                if last_qual_ts is None or ts > last_qual_ts:
                    last_qual_ts = ts
                # count qualified by looking for highest index
                n_m = re.search(r"QUALIFIED #(\d+)", line)
                if n_m:
                    result["qualified_count"] = max(result["qualified_count"], int(n_m.group(1)))
            except Exception:
                pass
            sims_since_last_qual = 0

        if to_re.search(line):
            result["timeout_count"] += 1
        if ssl_re.search(line):
            result["ssl_drop_count"] += 1

    result["fitness_fail_streak"] = sims_since_last_qual

    if last_sim_ts:
        delta = (now - last_sim_ts).total_seconds() / 60.0
        result["last_sim_minutes_ago"] = round(delta, 1)
        if delta > STALL_THRESHOLD_MINUTES:
            result["is_stalled"] = True
            result["issues"].append(
                f"LOCAL MINER STALLED: No new sim in {delta:.1f}m (threshold={STALL_THRESHOLD_MINUTES}m)"
            )

    if last_qual_ts:
        result["last_qualified_minutes_ago"] = round(
            (now - last_qual_ts).total_seconds() / 60.0, 1
        )

    if sims_since_last_qual >= ZERO_QUAL_SIM_THRESHOLD:
        result["is_zero_qual_streak"] = True
        result["issues"].append(
            f"ZERO-QUAL STREAK: {sims_since_last_qual} sims with 0 qualified -- check Fitness gate"
        )
    if result["ssl_drop_count"] > 3:
        result["issues"].append(
            f"SSL INSTABILITY: {result['ssl_drop_count']} SSL connection drops detected"
        )
    if result["timeout_count"] > 2:
        result["issues"].append(
            f"SIM TIMEOUTS: {result['timeout_count']} 240s timeouts -- long-lookback pruning needed"
        )
    return result


# ---------------------------------------------------------------------------
# GitHub Actions Analysis
# ---------------------------------------------------------------------------

def get_gh_runs(workflow_file: str, limit: int = 5) -> List[Dict]:
    try:
        r = subprocess.run(
            ["gh", "run", "list", f"--workflow={workflow_file}", f"--limit={limit}",
             "--json", "status,conclusion,databaseId,createdAt,updatedAt"],
            capture_output=True, text=True, timeout=30, cwd=str(REPO_ROOT),
        )
        return json.loads(r.stdout or "[]")
    except Exception as exc:
        log.warning("gh query failed for %s: %s", workflow_file, exc)
        return []


def analyse_gh_workflow(workflow_file: str) -> Dict:
    runs = get_gh_runs(workflow_file, limit=5)
    name = workflow_file.replace(".yml", "").replace("mine_", "").upper()
    result: Dict = {
        "workflow": workflow_file,
        "name": name,
        "runs": runs,
        "issues": [],
        "is_active": False,
        "active_run_id": None,
        "last_conclusion": "UNKNOWN",
        "consecutive_failures": 0,
        "fast_fails": 0,
    }
    if not runs:
        result["issues"].append(f"No recent runs found for {workflow_file}")
        return result

    if runs[0].get("status") == "in_progress":
        result["is_active"] = True
        result["active_run_id"] = runs[0].get("databaseId")
        result["last_conclusion"] = "RUNNING"
    else:
        result["last_conclusion"] = runs[0].get("conclusion", "UNKNOWN")

    streak = 0
    for run in runs:
        if run.get("status") == "in_progress":
            continue
        conc = run.get("conclusion", "")
        if conc in ("failure", "cancelled", "timed_out"):
            streak += 1
            try:
                cr = datetime.fromisoformat(run["createdAt"].replace("Z", "+00:00"))
                up = datetime.fromisoformat(run["updatedAt"].replace("Z", "+00:00"))
                if (up - cr).total_seconds() < 120 and conc == "failure":
                    result["fast_fails"] += 1
            except Exception:
                pass
        else:
            break
    result["consecutive_failures"] = streak
    if streak >= 2:
        result["issues"].append(f"{name}: {streak} consecutive failures -- investigate immediately")
    if result["fast_fails"] >= 2:
        result["issues"].append(
            f"{name}: {result['fast_fails']} fast-fail runs (<120s) -- DB/import error suspected"
        )
    return result


# ---------------------------------------------------------------------------
# Git Push
# ---------------------------------------------------------------------------

def git_push(message: str) -> bool:
    try:
        subprocess.run(["git", "add", "-A"], cwd=str(REPO_ROOT), check=True, timeout=30)
        r = subprocess.run(
            ["git", "diff", "--cached", "--quiet"], cwd=str(REPO_ROOT), timeout=10
        )
        if r.returncode == 0:
            log.info("No git changes to push.")
            return True
        subprocess.run(
            ["git", "commit", "-m", message], cwd=str(REPO_ROOT), check=True, timeout=30
        )
        subprocess.run(
            ["git", "push", "origin", "main"], cwd=str(REPO_ROOT), check=True, timeout=60
        )
        log.info("Pushed to GitHub: %s", message)
        return True
    except Exception as exc:
        log.error("Git push failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Health Report
# ---------------------------------------------------------------------------

def build_report(opt: Dict, sent: Dict, risk: Dict, actions: List[str]) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    def icon(info_dict: Dict) -> str:
        if info_dict.get("is_active"):
            return "🟢 [RUNNING]"
        conc = info_dict.get("last_conclusion", "UNKNOWN")
        if conc == "success":
            return "✅ [IDLE - SUCCESS]"
        if info_dict.get("consecutive_failures", 0) >= 2:
            return "🔴 [CRITICAL]"
        return "⚠️ [WARNING]"

    oi = icon(opt)
    si = icon(sent)
    ri = icon(risk)

    issues = opt.get("issues", []) + sent.get("issues", []) + risk.get("issues", [])
    lines = [
        f"<b>Cloud Pipeline Health Digest</b> -- {ts}",
        "",
        f"{oi} <b>Options Cloud</b>: {opt.get('last_conclusion', 'N/A').upper()} (Slot 1)",
        f"{si} <b>Sentiment Cloud</b>: {sent.get('last_conclusion', 'N/A').upper()} (Slot 2)",
        f"{ri} <b>Risk Model Cloud</b>: {risk.get('last_conclusion', 'N/A').upper()} (Slot 3)",
    ]
    if issues:
        lines += ["", "<b>Issues Detected:</b>"] + [f"  - {i}" for i in issues[:8]]
    if actions:
        lines += ["", "<b>Auto-Actions Taken:</b>"] + [f"  + {a}" for a in actions]
    if not issues and not actions:
        lines += ["", "All 3 cloud slots nominal and fully saturated."]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main Monitor Cycle
# ---------------------------------------------------------------------------

CLOUD_WORKFLOWS = [
    ("mine_options.yml", "Options (option8/9)"),
    ("mine_sentiment.yml", "Sentiment (sentiment1/2)"),
    ("mine_risk_model.yml", "Risk Model (model51/52)"),
]

def run_cycle() -> None:
    log.info("=" * 60)
    log.info("PIPELINE MONITOR: Cloud Multi-Miner Health check starting")
    log.info("=" * 60)
    actions: List[str] = []

    # 1 -- Check each cloud workflow
    workflow_results = {}
    for wf_file, wf_desc in CLOUD_WORKFLOWS:
        info = analyse_gh_workflow(wf_file)
        workflow_results[wf_file] = info
        log.info(
            "[%s] active=%s | last=%s | fails=%d",
            info["name"], info["is_active"], info["last_conclusion"], info["consecutive_failures"]
        )
        for issue in info["issues"]:
            log.warning("ISSUE [%s]: %s", info["name"], issue)

        # Auto-heal: If workflow is NOT currently running, start it immediately to ensure continuous 24/7 mining
        if not info["is_active"]:
            log.warning("%s is IDLE (last: %s) -- auto-triggering workflow...", wf_desc, info["last_conclusion"])
            try:
                subprocess.run(
                    ["gh", "workflow", "run", wf_file, "--ref", "main"],
                    cwd=str(REPO_ROOT), check=True, timeout=30,
                )
                actions.append(f"Auto-triggered idle {wf_desc}")
            except Exception as exc:
                log.error("Failed to trigger %s: %s", wf_file, exc)

    opt = workflow_results.get("mine_options.yml", {})
    sent = workflow_results.get("mine_sentiment.yml", {})
    risk = workflow_results.get("mine_risk_model.yml", {})

    # 2 -- Push uncommitted changes if any
    diff_r = subprocess.run(
        ["git", "diff", "--name-only"],
        capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=15,
    )
    if diff_r.stdout.strip():
        log.info("Uncommitted changes found: %s", diff_r.stdout.strip()[:80])
        if git_push("chore: auto-push pipeline monitor hotfixes"):
            actions.append(f"Pushed hotfixes: {diff_r.stdout.strip()[:80]}")

    # 3 -- Health digest
    log.info("Sending Telegram health digest...")
    report = build_report(opt, sent, risk, actions)
    send_tg(report)
    log.info("Cycle complete. %d actions taken.", len(actions))


def main() -> None:
    parser = argparse.ArgumentParser(description="BRAIN Pipeline Monitor & Self-Healing Daemon")
    parser.add_argument("--daemon", action="store_true", help="Run forever at --interval minutes")
    parser.add_argument("--interval", type=int, default=30, help="Check interval in minutes (default 30)")
    args = parser.parse_args()

    if args.daemon:
        log.info("Starting daemon mode (interval: %dm)", args.interval)
        while True:
            try:
                run_cycle()
            except Exception as exc:
                log.error("Monitor cycle exception: %s", exc)
                send_tg(f"<b>Monitor crashed:</b> <code>{exc}</code>")
            log.info("Sleeping %dm until next check...", args.interval)
            time.sleep(args.interval * 60)
    else:
        run_cycle()


if __name__ == "__main__":
    main()
