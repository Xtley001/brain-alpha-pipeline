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
    name = workflow_file.replace(".yml", "").upper()
    result: Dict = {
        "workflow": workflow_file,
        "name": name,
        "runs": runs,
        "issues": [],
        "last_conclusion": "UNKNOWN",
        "consecutive_failures": 0,
        "fast_fails": 0,
    }
    if not runs:
        result["issues"].append(f"No recent runs found for {workflow_file}")
        return result
    result["last_conclusion"] = runs[0].get("conclusion", "UNKNOWN")
    streak = 0
    for run in runs:
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
# Process Management
# ---------------------------------------------------------------------------

def is_miner_running() -> bool:
    try:
        r = subprocess.run(
            ["wmic", "process", "where", "name='python.exe'", "get", "CommandLine"],
            capture_output=True, text=True, timeout=10,
        )
        return "autonomous_24h_vault_miner" in r.stdout
    except Exception:
        return False


def kill_miner() -> None:
    try:
        subprocess.run(
            ["wmic", "process", "where", "CommandLine like '%autonomous_24h_vault_miner%'", "delete"],
            capture_output=True, timeout=15,
        )
        time.sleep(3)
    except Exception as exc:
        log.warning("Kill miner failed: %s", exc)


def start_miner() -> bool:
    log.info("Starting local vault miner...")
    try:
        log_path = str(LOG_FILE)
        fh = open(log_path, "a", encoding="utf-8")
        subprocess.Popen(
            [sys.executable, str(MINER_SCRIPT)],
            cwd=str(REPO_ROOT),
            stdout=fh,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        log.info("Vault miner started successfully.")
        return True
    except Exception as exc:
        log.error("Failed to start vault miner: %s", exc)
        return False


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

def build_report(local: Dict, sent: Dict, risk: Dict, actions: List[str]) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    def icon(info_dict: Dict, key: str = "consecutive_failures") -> str:
        v = info_dict.get(key, 0)
        if info_dict.get("is_stalled") or info_dict.get("is_zero_qual_streak") or v >= 2:
            return "[CRITICAL]"
        if v == 1:
            return "[WARNING]"
        return "[OK]"

    li = "[CRITICAL]" if (local.get("is_stalled") or local.get("is_zero_qual_streak")) else "[OK]"
    si = icon(sent)
    ri = icon(risk)

    issues = local.get("issues", []) + sent.get("issues", []) + risk.get("issues", [])
    lines = [
        f"<b>Pipeline Health Digest</b> -- {ts}",
        "",
        f"{li} <b>Local Vault Miner</b>",
        f"  Sims: <b>{local.get('total_sims', 0)}</b> | Qualified: <b>{local.get('qualified_count', 0)}</b>",
        f"  Fitness-fail streak: {local.get('fitness_fail_streak', 0)} sims",
        f"  Last sim: {local.get('last_sim_minutes_ago', 'N/A')}m ago",
        f"  Timeouts: {local.get('timeout_count', 0)} | SSL drops: {local.get('ssl_drop_count', 0)}",
        "",
        f"{si} <b>Sentiment Cloud</b>: {sent.get('last_conclusion', 'N/A').upper()} | fails: {sent.get('consecutive_failures', 0)}",
        f"{ri} <b>Risk Model Cloud</b>: {risk.get('last_conclusion', 'N/A').upper()} | fails: {risk.get('consecutive_failures', 0)}",
    ]
    if issues:
        lines += ["", "<b>Issues Detected:</b>"] + [f"  - {i}" for i in issues[:8]]
    if actions:
        lines += ["", "<b>Auto-Actions Taken:</b>"] + [f"  + {a}" for a in actions]
    if not issues and not actions:
        lines += ["", "All systems nominal. Pipeline running at full capacity."]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main Monitor Cycle
# ---------------------------------------------------------------------------

def run_cycle() -> None:
    log.info("=" * 55)
    log.info("PIPELINE MONITOR: Health check starting")
    log.info("=" * 55)
    actions: List[str] = []

    # 1 -- Local miner log
    local = parse_local_miner_log()
    for issue in local["issues"]:
        log.warning("LOCAL ISSUE: %s", issue)

    # 2 -- Process management
    alive = is_miner_running()
    if not alive:
        log.warning("Local vault miner process NOT found -- restarting...")
        if start_miner():
            actions.append("Restarted dead local vault miner process")
            send_tg("<b>Monitor:</b> Local vault miner was dead -- <b>auto-restarted</b>.")
        else:
            send_tg(
                "<b>CRITICAL:</b> Local vault miner is dead and failed to restart. "
                "Manual intervention required."
            )
    elif local["is_stalled"]:
        log.warning(
            "Miner is running but STALLED (no sim in %sm) -- killing and restarting...",
            local["last_sim_minutes_ago"],
        )
        kill_miner()
        if start_miner():
            actions.append(
                f"Restarted stalled miner (no sim in {local['last_sim_minutes_ago']}m)"
            )
    else:
        log.info(
            "Local miner OK. Sims: %d | Qualified: %d | Last sim: %sm ago",
            local["total_sims"],
            local["qualified_count"],
            local["last_sim_minutes_ago"],
        )

    # 3 -- GitHub Actions
    log.info("Checking GitHub Actions workflow health...")
    sent = analyse_gh_workflow("mine_sentiment.yml")
    risk = analyse_gh_workflow("mine_risk_model.yml")
    for issue in sent["issues"] + risk["issues"]:
        log.warning("GH ISSUE: %s", issue)

    for wf_file, wf_info in [("mine_sentiment.yml", sent), ("mine_risk_model.yml", risk)]:
        if wf_info.get("consecutive_failures", 0) >= 3:
            log.warning(
                "%s has %d consecutive failures -- triggering manual dispatch...",
                wf_file, wf_info["consecutive_failures"],
            )
            try:
                subprocess.run(
                    ["gh", "workflow", "run", wf_file, "--ref", "main"],
                    cwd=str(REPO_ROOT), check=True, timeout=30,
                )
                actions.append(
                    f"Re-triggered {wf_file} after {wf_info['consecutive_failures']} failures"
                )
            except Exception as exc:
                log.error("Failed to trigger %s: %s", wf_file, exc)

    # 4 -- Push uncommitted changes
    diff_r = subprocess.run(
        ["git", "diff", "--name-only"],
        capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=15,
    )
    if diff_r.stdout.strip():
        log.info("Uncommitted changes found: %s", diff_r.stdout.strip()[:80])
        if git_push("chore: auto-push pipeline monitor hotfixes"):
            actions.append(f"Pushed hotfixes: {diff_r.stdout.strip()[:80]}")

    # 5 -- Health digest
    log.info("Sending Telegram health digest...")
    report = build_report(local, sent, risk, actions)
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
