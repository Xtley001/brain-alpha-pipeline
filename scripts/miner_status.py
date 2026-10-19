#!/usr/bin/env python3
"""
Interactive Pipeline Status & Diagnostic Dashboard.
Run anytime to inspect real-time state of the 100-alpha mining pipeline:
  Usage: python scripts/miner_status.py
"""
import datetime
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import brain_options.core.dns_fallback

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

try:
    import psycopg
except ImportError:
    psycopg = None

try:
    import requests
except ImportError:
    requests = None

from brain_options.config import OptionsConfig


def get_running_processes():
    """Detects supervisor and miner PIDs and memory usage using tasklist."""
    procs = {"supervisor": None, "miner": None, "others": []}
    try:
        res = subprocess.run(
            ["tasklist", "/v", "/fo", "csv"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
        for line in res.stdout.splitlines():
            if "python.exe" in line.lower():
                parts = [p.strip('"\r ') for p in line.split('","')]
                if len(parts) >= 5:
                    pid = parts[1]
                    mem = parts[4]
                    procs["others"].append((pid, mem))
    except Exception:
        pass

    # Check command lines using powershell
    try:
        cmd = 'Get-CimInstance Win32_Process -Filter "Name = \'python.exe\'" | Select-Object ProcessId, CommandLine | ConvertTo-Csv -NoTypeInformation'
        ps_res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
        for line in ps_res.stdout.splitlines():
            line_clean = line.strip('"\r ')
            if "run_resilient_100_miner.py" in line_clean:
                m = re.search(r'"(\d+)"', line)
                if m:
                    procs["supervisor"] = m.group(1)
            elif "master_quintuple_vault_miner_500.py" in line_clean:
                m = re.search(r'"(\d+)"', line)
                if m:
                    procs["miner"] = m.group(1)
    except Exception:
        pass

    return procs


def get_db_metrics(db_url: str):
    """Fetches count breakdown and latest qualified alphas from PostgreSQL."""
    if not psycopg:
        return {"error": "psycopg not installed", "counts": {}, "qualified": 0, "recent_qualified": []}

    try:
        with psycopg.connect(db_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT status, count(*) FROM options_alphas GROUP BY status ORDER BY count(*) DESC")
                counts = dict(cur.fetchall())

                cur.execute("SELECT count(*) FROM options_alphas WHERE status = 'QUALIFIED'")
                row = cur.fetchone()
                qualified_count = row[0] if row else 0

                cur.execute(
                    """
                    SELECT alpha_id, archetype, universe, sharpe, fitness, margin, turnover, created_at
                    FROM options_alphas
                    WHERE status = 'QUALIFIED'
                    ORDER BY created_at DESC
                    LIMIT 5
                    """
                )
                recent = cur.fetchall()

                return {
                    "counts": counts,
                    "qualified": qualified_count,
                    "recent_qualified": recent,
                    "connected": True,
                }
    except Exception as e:
        return {"error": str(e), "counts": {}, "qualified": 0, "recent_qualified": [], "connected": False}


def parse_log_telemetry(log_path: str = "logs/omni_vault_miner.log"):
    """Extracts latest evaluation count, near-misses, active simulation, and rate."""
    if not os.path.exists(log_path):
        return {"exists": False}

    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()[-2000:]
    except Exception:
        return {"exists": False}

    last_eval_num = None
    qual_in_log = None
    in_flight = []
    completed = []
    near_misses = []

    # Regex patterns
    re_sim = re.compile(r"\[Worker (\d+) \| #(\d+) \| Qual: (\d+)/\d+\] Simulating ([^\s]+)")
    re_res = re.compile(r"\[Worker (\d+)\] ([a-zA-Z0-9_-]+) \| Sharpe=([-\d.]+) \| Fit=([-\d.]+) \| TO=([\d.]+)% \| Margin=([-\d.]+)bps \| DD=([\d.]+)% \| ([^\s]+)")
    re_slot = re.compile(r"Acquired simulation slot \((\d+)/(\d+) in-flight\)")

    current_slots = "Unknown"
    for line in reversed(lines):
        m_slot = re_slot.search(line)
        if m_slot and current_slots == "Unknown":
            current_slots = f"{m_slot.group(1)}/{m_slot.group(2)}"
            break

    for line in lines:
        m_sim = re_sim.search(line)
        if m_sim:
            w_id, num, q_cnt, arch = m_sim.groups()
            last_eval_num = int(num)
            qual_in_log = int(q_cnt)
            in_flight.append((w_id, arch))
            if len(in_flight) > 4:
                in_flight.pop(0)

        m_res = re_res.search(line)
        if m_res:
            w_id, a_id, sh, fit, to, mgn, dd, arch = m_res.groups()
            comp_entry = {
                "alpha_id": a_id,
                "archetype": arch,
                "sharpe": float(sh),
                "fitness": float(fit),
                "turnover": float(to),
                "margin": float(mgn),
                "drawdown": float(dd),
            }
            completed.append(comp_entry)
            if float(sh) >= 1.05:
                near_misses.append(comp_entry)

    return {
        "exists": True,
        "last_eval_num": last_eval_num,
        "qual_in_log": qual_in_log,
        "slots_in_flight": current_slots,
        "active_candidates": in_flight[-4:],
        "recent_completed": completed[-5:],
        "top_near_misses": sorted(near_misses, key=lambda x: x["sharpe"], reverse=True)[:5],
    }


def check_brain_connectivity():
    """Quick ping to WorldQuant Brain API."""
    if not requests:
        return "Unknown (requests missing)"
    t0 = time.time()
    try:
        r = requests.get("https://api.worldquantbrain.com/users/self", timeout=4.0)
        lat = (time.time() - t0) * 1000.0
        if r.status_code in (200, 401, 403):
            return f"🟢 Connected ({lat:.0f}ms latency, HTTP {r.status_code})"
        return f"🟡 Response HTTP {r.status_code} ({lat:.0f}ms)"
    except Exception as e:
        return f"🔴 Unreachable: {e}"


def main():
    config = OptionsConfig.from_env()
    procs = get_running_processes()
    db = get_db_metrics(config.database_url)
    telem = parse_log_telemetry()
    brain_status = check_brain_connectivity()

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S WAT")

    print("\n" + "=" * 78)
    print(f"  ⚡ QUANTITATIVE ALPHA PIPELINE STATUS DASHBOARD — {now_str}")
    print("=" * 78)

    # 1. System & Engine Health
    print("\n[1] ⚙️  SYSTEM PROCESSES & CONNECTIVITY")
    sup_status = f"🟢 RUNNING (PID {procs['supervisor']})" if procs["supervisor"] else "🔴 STOPPED"
    miner_status = f"🟢 RUNNING (PID {procs['miner']})" if procs["miner"] else "🔴 STOPPED"
    print(f"  • Supervisor (Watchdog):  {sup_status}")
    print(f"  • Worker Miner (4 slots): {miner_status}")
    print(f"  • WorldQuant BRAIN API:   {brain_status}")
    db_stat_str = "🟢 CONNECTED" if db.get("connected") else f"🔴 DISCONNECTED ({db.get('error')})"
    print(f"  • PostgreSQL Database:    {db_stat_str}")

    # 2. Database Vault Progress
    target = 100
    qual = db.get("qualified", 0)
    pct = (qual / target) * 100.0
    bar_len = 30
    filled = int(bar_len * (qual / target))
    bar = "█" * filled + "░" * (bar_len - filled)

    print(f"\n[2] 🏛️  POSTGRESQL QUALIFIED VAULT PROGRESS")
    print(f"  • Target:                 100 Qualified Pure-Sentiment Alphas")
    print(f"  • Current Banked:         {qual} / {target} [{bar}] {pct:.1f}%")
    print(f"  • Status Breakdown:")
    for st, count in db.get("counts", {}).items():
        print(f"      - {st:25s}: {count}")

    if db.get("recent_qualified"):
        print(f"\n  • Latest Banked Qualified Alphas:")
        for r in db["recent_qualified"]:
            a_id, arch, u, sh, fit, mgn, to, dt = r
            print(f"      • {a_id} | {arch[:35]:35s} | Sharpe={sh:.2f} | Fit={fit:.2f} | Mgn={float(mgn)*10000:.1f}bps | TO={float(to)*100:.1f}%")

    # 3. Real-Time Mining Telemetry
    print(f"\n[3] 🔬 REAL-TIME MINING TELEMETRY")
    if telem.get("exists"):
        eval_n = telem.get("last_eval_num", "N/A")
        print(f"  • Current Sim Counter:    #{eval_n} evaluated")
        print(f"  • Active Slots In-Flight: {telem.get('slots_in_flight', '4/4')}")
        if telem.get("active_candidates"):
            print(f"  • Actively Simulating in Workers:")
            for w_id, arch in telem["active_candidates"]:
                print(f"      - [Worker {w_id}] {arch}")

        if telem.get("recent_completed"):
            print(f"\n  • Last 5 Completed Simulations:")
            for c in reversed(telem["recent_completed"]):
                print(f"      - {c['alpha_id']} | Sharpe={c['sharpe']:.2f} | Fit={c['fitness']:.2f} | TO={c['turnover']:.1f}% | Mgn={c['margin']:.1f}bps | {c['archetype'][:32]}")

        if telem.get("top_near_misses"):
            print(f"\n  • Session Top Near-Misses (Sharpe >= 1.05):")
            for nm in telem["top_near_misses"][:4]:
                print(f"      ⭐ {nm['alpha_id']} | Sharpe={nm['sharpe']:.2f} | Fit={nm['fitness']:.2f} | TO={nm['turnover']:.1f}% | Mgn={nm['margin']:.1f}bps | {nm['archetype']}")
    else:
        print("  • Log file logs/omni_vault_miner.log not found or empty.")

    # 4. Actionable Cheatsheet
    print("\n[4] 🛠️  HOW TO KNOW THE STATES OF THINGS ANYTIME")
    print("  • Check this dashboard anytime: python scripts/miner_status.py")
    print("  • Tail live miner log:          Get-Content logs/omni_vault_miner.log -Tail 20 -Wait")
    print("  • Database status breakdown:    python scripts/db_status.py")
    print("  • Hourly Telegram Reports:      Delivered strictly at HH:00 WAT every hour")
    print("=" * 78 + "\n")


if __name__ == "__main__":
    main()
