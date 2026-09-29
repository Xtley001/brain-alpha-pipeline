!/usr/bin/env python3
"""
Autonomous Pipeline Monitor & Self-Healing Daemon
===================================================
Runs every 30 minutes (via Windows Task Scheduler) and:

1. INSPECTS local vault miner log (logs/autonomous_vault_miner.log)
   - Detects stalled miner (no new sim in > 10 minutes)
   - Detects zero-qualification streaks (> 50 sims with 0 qualified)
   - Detects SSL/DB connection drops and sim timeouts
   - Auto-restarts the local miner if dead or stalled

2. INSPECTS GitHub Actions logs (via gh CLI)
   - Checks last run status for mine_sentiment.yml / mine_risk_model.yml
   - Flags fast-fail runs (< 120s) as infrastructure issues
   - Auto-triggers workflow re-run after 3 consecutive failures

3. REPORTS via Telegram structured health digest every cycle

4. Auto-commits and pushes pending hotfixes to GitHub

Usage:
    python scripts/pipeline_monitor.py             # one check now
    python scripts/pipeline_monitor.py --daemon    # loop every 30m
"""
from __future__ import annotations

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
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

# ── Config ───────────────────────────────────
REPO_ROOT    = Path(__file__).resolve().parent.parent
LOG_FILE     = REPO_ROOT / "logs" / "autonomous_vault_miner.log"
MINER_SCRIPT = REPO_ROOT / "scripts" / "autonomous_24h_vault_miner.py"
MONITOR_LOG  = REPO_ROOT / "logs" / "pipeline_monitor.log"

STALL_THRESHOLD_MINUTES  = 10
ZERO_QUAL_SIM_THRESHOLD  = 50

TELEGRAM_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN", "")
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


# ── Telegram ─────────────────────────────────
def send_tg(html_text: str) -> None:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        log.warning("Telegram not configured — skipping alert")
        return
    try:
        import requests
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": html_text, "parse_mode": "HTML"},
            timeout=15,
        )
    except Exception as e:
        log.warning("Telegram send failed: %s", e)


# ── Local Miner Log Analysis ──────────────────
def parse_local_miner_log() -> Dict:
    result = {
        "log_exists": False, "total_sims": 0, "qualified_count": 0,
        "last_sim_minutes_ago": None, "last_sim_line": "",
        "fitness_fail_streak": 0, "timeout_count": 0, "ssl_drop_count": 0,
        "last_qualified_minutes_ago": None, "is_stalled": False,
        "is_zero_qual_streak": False, "workers_active": False, "issues": [],
    }
    if not LOG_FILE.exists():
        result["issues"].append("Local miner log does not exist — miner may not be running")
        return result

    result["log_exists"] = True
    lines = LOG_FILE.read_text(encoding="utf-8", errors="ignore").splitlines()
    now = datetime.now(timezone.utc)
    last_sim_ts = None
    last_qual_ts = None
    sims_since_last_qual = 0

    sim_re  = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*\[Worker #\d+ \| Sim #(\d+)\]")
    qual_re = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*\u2605 \[QUALIFIED #(\d+)")
    to_re   = re.compile(r"timed out after 240s")
    ssl_re  = re.compile(r"connection abort|SSL SYSCALL|10053", re.I)

    for line in lines[-2000:]:
        if "Worker #" in line and "online" in line:
            result["workers_active"] = True
        m = sim_re.search(line)
        if m:
            ts_s, sim_n = m.group(1), int(m.group(2))
            result["total_sims"] = max(result["total_sims"], sim_n)
            try:
                ts = datetime.strptime(ts_s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                if last_sim_ts is None or ts > last_sim_ts:
                    last_sim_ts = ts; result["last_sim_line"] = line.strip()
            except Exception:
                pass
            sims_since_last_qual += 1
        m = qual_re.search(line)
        if m:
            ts_s, qn = m.group(1), int(m.group(2))
            result["qualified_count"] = max(result["qualified_count"], qn)
            try:
                ts = datetime.strptime(ts_s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                if last_qual_ts is None or ts > last_qual_ts:
                    last_qual_ts = ts
            except Exception:
                pass
            sims_since_last_qual = 0
        if to_re.search(line):   result["timeout_count"] += 1
        if ssl_re.search(line):  result["ssl_drop_count"] += 1

    result["fitness_fail_streak"] = sims_since_last_qual
    if last_sim_ts:
        d = (now - last_sim_ts).total_seconds() / 60
        result["last_sim_minutes_ago"] = round(d, 1)
        if d > STALL_THRESHOLD_MINUTES:
            result["is_stalled"] = True
            result["issues"].append(f"LOCAL MINER STALLED: No new sim in {d:.1f}m")
    if last_qual_ts:
        result["last_qualified_minutes_ago"] = round((now - last_qual_ts).total_seconds() / 60, 1)
    if sims_since_last_qual >= ZERO_QUAL_SIM_THRESHOLD:
        result["is_zero_qual_streak"] = True
        result["issues"].append(f"ZERO-QUAL STREAK: {sims_since_last_qual} sims, 0 qualified — check Fitness gate")
    if result["ssl_drop_count"] > 3:
        result["issues"].append(f"SSL INSTABILITY: {result['ssl_drop_count']} SSL drops detected")
    if result["timeout_count"] > 2:
        result["issues"].append(f"SIM TIMEOUTS: {result['timeout_count']} 240s timeouts — long-lookback pruning needed")
    return result


# ── GitHub Actions Analysis ───────────────────
def get_gh_runs(workflow_file: str, limit: int = 5) -> List[Dict]:
    try:
        r = subprocess.run(
            ["gh", "run", "list", f"--workflow={workflow_file}", f"--limit={limit}",
             "--json", "status,conclusion,databaseId,createdAt,updatedAt"],
            capture_output=True, text=True, timeout=30, cwd=str(REPO_ROOT)
        )
        return json.loads(r.stdout or "[]")
    except Exception as e:
        log.warning("gh query failed for %s: %s", workflow_file, e)
        return []


def analyse_gh_workflow(workflow_file: str) -> Dict:
    runs = get_gh_runs(workflow_file, limit=5)
    name = workflow_file.replace(".yml","").upper()
    result = {"workflow": workflow_file, "name": name, "runs": runs,
              "issues": [], "last_conclusion": "UNKNOWN",
              "consecutive_failures": 0, "fast_fails": 0}
    if not runs:
        result["issues"].append(f"No recent runs found for {workflow_file}")
        return result
    result["last_conclusion"] = runs[0].get("conclusion", "UNKNOWN")
    streak = 0
    for r in runs:
        c = r.get("conclusion", "")
        if c in ("failure", "cancelled", "timed_out"):
            streak += 1
            try:
                cr = datetime.fromisoformat(r["createdAt"].replace("Z", "+00:00"))
                up = datetime.fromisoformat(r["updatedAt"].replace("Z", "+00:00"))
                if (up - cr).total_seconds() < 120 and c == "failure":
                    result["fast_fails"] += 1
            except Exception:
                pass
        else:
            break
    result["consecutive_failures"] = streak
    if streak >= 2:
        result["issues"].append(f"{name}: {streak} consecutive failures")
    if result["fast_fails"] >= 2:
        result["issues"].append(f"{name}: {result['fast_fails']} fast-fail runs (<120s) — DB/import error suspected")
    return result


# ── Process Management ────────────────────────
def is_miner_running() -> bool:
    try:
        r = subprocess.run(
            ["wmic", "process", "where", "name='python.exe'", "get", "CommandLine"],
            capture_output=True, text=True, timeout=10
        )
        return "autonomous_24h_vault_miner" in r.stdout
    except Exception:
        return False


def kill_miner() -> None:
    try:
        subprocess.run(
            ["wmic", "process", "where",
             "CommandLine like '%autonomous_24h_vault_miner%'", "delete"],
            capture_output=True, timeout=15
        )
        time.sleep(3)
    except Exception as e:
        log.warning("Kill miner failed: %s", e)


def start_miner() -> bool:
    log.info("Starting local vault miner...")
    try:
        log_path = str(LOG_FILE)
        f = open(log_path, "a", encoding="utf-8")
        subprocess.Popen(
            [sys.executable, str(MINER_SCRIPT)],
            cwd=str(REPO_ROOT), stdout=f, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        log.info("Vault miner started successfully.")
        return True
    except Exception as e:
        log.error("Failed to start vault miner: %s", e)
        return False


# ── Git Push ──────────────────────────────────
def git_push(message: str) -> bool:
    try:
        subprocess.run(["git","add","-A"], cwd=str(REPO_ROOT), check=True, timeout=30)
        r = subprocess.run(["git","diff","--cached","--quiet"], cwd=str(REPO_ROOT), timeout=10)
        if r.returncode == 0:
            log.info("No git changes to push."); return True
        subprocess.run(["git","commit","-m",message], cwd=str(REPO_ROOT), check=True, timeout=30)
        subprocess.run(["git","push","origin","main"], cwd=str(REPO_ROOT), check=True, timeout=60)
        log.info("Pushed to GitHub: %s", message)
        return True
    except Exception as e:
        log.error("Git push failed: %s", e)
        return False


# ── Health Report ─────────────────────────────
def build_report(local: Dict, sent: Dict, risk: Dict, actions: List[str]) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    li = "🔴" if local["is_stalled"] else ("🟡" if local["is_zero_qual_streak"] else "🟢")
    si = "🔴" if sent.get("consecutive_failures",0)>=2 else ("🟡" if sent.get("consecutive_failures",0)==1 else "🟢")
    ri = "🔴" if risk.get("consecutive_failures",0)>=2 else ("🟡" if risk.get("consecutive_failures",0)==1 else "🟢")
    issues = local.get("issues",[]) + sent.get("issues",[]) + risk.get("issues",[])
    lines = [
        f"📡 <b>Pipeline Health Digest</b> — {ts}",
        "",
        f"{li} <b>Local Vault Miner</b>",
        f"  Sims: <b>{local.get('total_sims',0)}</b> | Qualified: <b>{local.get('qualified_count',0)}</b>",
        f"  Fitness-fail streak: {local.get('fitness_fail_streak',0)} sims",
        f"  Last sim: {local.get('last_sim_minutes_ago','N/A')}m ago",
        f"  Timeouts: {local.get('timeout_count',0)} | SSL drops: {local.get('ssl_drop_count',0)}",
        "",
        f"{si} <b>Sentiment Cloud</b>: {sent.get('last_conclusion','N/A').upper()} | fails: {sent.get('consecutive_failures',0)}",
        f"{ri} <b>Risk Model Cloud</b>: {risk.get('last_conclusion','N/A').upper()} | fails: {risk.get('consecutive_failures',0)}",
    ]
    if issues:
        lines += ["", "⚠️ <b>Issues:</b>"] + [f"  • {i}" for i in issues[:6]]
    if actions:
        lines += ["", "🔧 <b>Auto-Actions:</b>"] + [f"  ✅ {a}" for a in actions]
    if not issues and not actions:
        lines += ["", "✅ <b>All systems nominal.</b>"]
    return "\n".join(lines)


# ── Main ──────────────────────────────────────
def run_cycle() -> None:
    log.info("=" * 55)
    log.info("PIPELINE MONITOR: Health check cycle starting")
    log.info("=" * 55)
    actions: List[str] = []

    local = parse_local_miner_log()
    for i in local["issues"]: log.warning("LOCAL: %s", i)

    # Check + manage miner process
    alive = is_miner_running()
    if not alive:
        log.warning("Miner NOT running — restarting...")
        if start_miner():
            actions.append("Restarted dead local vault miner")
            send_tg("🔄 <b>Monitor:</b> Local miner was dead — <b>auto-restarted</b>.")
        else:
            send_tg("🚨 <b>CRITICAL:</b> Miner is dead and failed to restart. Manual fix needed.")
    elif local["is_stalled"]:
        log.warning("Miner stalled — killing & restarting...")
        kill_miner()
        if start_miner():
            actions.append(f"Restarted stalled miner (no sim in {local['last_sim_minutes_ago']}m)")

    # GitHub Actions
    sent = analyse_gh_workflow("mine_sentiment.yml")
    risk = analyse_gh_workflow("mine_risk_model.yml")
    for i in sent["issues"] + risk["issues"]: log.warning("GH: %s", i)

    for wf, info in [("mine_sentiment.yml", sent), ("mine_risk_model.yml", risk)]:
        if info.get("consecutive_failures", 0) >= 3:
            try:
                subprocess.run(["gh","workflow","run",wf,"--ref","main"],
                               cwd=str(REPO_ROOT), check=True, timeout=30)
                actions.append(f"Re-triggered {wf} after {info['consecutive_failures']} failures")
            except Exception as e:
                log.error("Failed to trigger %s: %s", wf, e)

    # Push any pending code changes
    diff_r = subprocess.run(["git","diff","--name-only"], capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=15)
    if diff_r.stdout.strip():
        if git_push("chore: auto-push pipeline monitor hotfixes"):
            actions.append(f"Pushed hotfixes: {diff_r.stdout.strip()[:80]}")

    report = build_report(local, sent, risk, actions)
    send_tg(report)
    log.info("Cycle done. %d actions taken.", len(actions))


def main() -> None:
    parser = argparse.ArgumentParser(description="BRAIN Pipeline Monitor")
    parser.add_argument("--daemon", action="store_true", help="Run every --interval minutes forever")
    parser.add_argument("--interval", type=int, default=30, help="Check interval in minutes")
    args = parser.parse_args()
    if args.daemon:
        log.info("Daemon mode: interval=%dm", args.interval)
        while True:
            try:
                run_cycle()
            except Exception as e:
                log.error("Cycle exception: %s", e)
                send_tg(f"🚨 <b>Monitor crashed:</b> <code>{e}</code>")
            log.info("Sleeping %dm...", args.interval)
            time.sleep(args.interval * 60)
    else:
        run_cycle()


if __name__ == "__main__":
    main()