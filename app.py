"""
Hugging Face Spaces Entrypoint: Unified Alpha Generator, Drip Submitter & Live Dashboard.
Runs on port 7860.
"""
from __future__ import annotations

import asyncio
import datetime
import logging
import os
import sys
import threading
import time
import zoneinfo
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from brain_options.config import OptionsConfig
from brain_options.core.client import BrainClient
from brain_options.core.drip import DripSubmitter
from brain_options.run import run_batch
from brain_options.store.store import OptionsStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("brain_options.huggingface")

from contextlib import asynccontextmanager

NY_TZ = zoneinfo.ZoneInfo("America/New_York")
UTC = datetime.timezone.utc

_drip_lock = threading.Lock()

# Global state for UI tracking
PIPELINE_STATE = {
    "status": "INITIALIZING",
    "last_batch_time": None,
    "last_drip_check": None,
    "last_submitted_alpha": None,
    "total_batches_run": 0,
    "generator_active": True,
    "drip_active": True,
    "errors": [],
}


def background_drip_worker(config: OptionsConfig):
    """Periodically checks 24-hour New York submission window and submits up to 3 alphas/day."""
    log.info("Drip Submitter background thread started.")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    while True:
        try:
            if PIPELINE_STATE["drip_active"]:
                with _drip_lock:
                    PIPELINE_STATE["last_drip_check"] = datetime.datetime.now(UTC).isoformat()
                    log.info("[HF DRIP] Checking daily submission status...")
                    client = BrainClient(
                        username=config.brain_username,
                        password=config.brain_password,
                        max_concurrent_sims=1,
                    )
                    client.authenticate()
                    store = OptionsStore(database_url=config.database_url)
                    drip = DripSubmitter(client, store, config)
                    submitted, alpha_id, msg = loop.run_until_complete(drip.check_and_drip())
                    if submitted:
                        PIPELINE_STATE["last_submitted_alpha"] = alpha_id
                        log.info("[HF DRIP] Successfully submitted alpha %s: %s", alpha_id, msg)
                    else:
                        log.info("[HF DRIP] Drip check skipped/completed: %s", msg)
        except Exception as e:
            log.error("[HF DRIP] Error in drip worker: %s", e)
            PIPELINE_STATE["errors"].append(f"Drip Error: {str(e)[:100]}")
            if len(PIPELINE_STATE["errors"]) > 10:
                PIPELINE_STATE["errors"].pop(0)

        # Check every 10 minutes
        time.sleep(600)


def background_generator_worker(config: OptionsConfig):
    """Continuously generates and tests options alphas, saving passing ones to Neon DB."""
    log.info("Alpha Generator background thread started.")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    PIPELINE_STATE["status"] = "RUNNING"

    while True:
        try:
            if PIPELINE_STATE["generator_active"]:
                log.info("[HF GENERATOR] Starting discovery batch...")
                batch_size = config.max_candidates_per_run if config.max_candidates_per_run > 0 else 15
                passed = loop.run_until_complete(
                    run_batch(config, batch_size=batch_size, mode_label="HuggingFace 24/7 Cloud")
                )
                PIPELINE_STATE["total_batches_run"] += 1
                PIPELINE_STATE["last_batch_time"] = datetime.datetime.now(UTC).isoformat()
                log.info("[HF GENERATOR] Batch complete: %d qualified. Sleeping 120s...", passed)
        except Exception as e:
            log.error("[HF GENERATOR] Error in generator worker: %s", e)
            PIPELINE_STATE["errors"].append(f"Generator Error: {str(e)[:100]}")
            if len(PIPELINE_STATE["errors"]) > 10:
                PIPELINE_STATE["errors"].pop(0)

        # Sleep between batches to respect simulation throughput
        time.sleep(120)


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = OptionsConfig.from_env()
    # Start Drip Worker thread
    t_drip = threading.Thread(target=background_drip_worker, args=(config,), daemon=True)
    t_drip.start()

    # Start Generator Worker thread
    t_gen = threading.Thread(target=background_generator_worker, args=(config,), daemon=True)
    t_gen.start()
    yield


app = FastAPI(title="WorldQuant BRAIN Alpha Pipeline", lifespan=lifespan)


@app.get("/health")
def health_check():
    """Uptime monitoring endpoint. Ping this every 10-15 minutes via cron-job.org to keep Space awake 24/7."""
    return {
        "status": "healthy",
        "service": "brain-alpha-pipeline",
        "utc_time": datetime.datetime.now(UTC).isoformat(),
        "pipeline_state": PIPELINE_STATE["status"],
        "total_batches_run": PIPELINE_STATE["total_batches_run"],
    }


@app.get("/api/stats")
def get_stats():
    config = OptionsConfig.from_env()
    store = OptionsStore(database_url=config.database_url)
    stats = store.get_options_stats()
    unsubmitted = store.get_unsubmitted_pool_alphas()
    return {
        "stats": stats,
        "unsubmitted_count": len(unsubmitted),
        "pipeline_state": PIPELINE_STATE,
    }


@app.post("/api/trigger-drip")
async def trigger_drip():
    config = OptionsConfig.from_env()
    client = BrainClient(username=config.brain_username, password=config.brain_password, max_concurrent_sims=1)
    client.authenticate()
    store = OptionsStore(database_url=config.database_url)
    drip = DripSubmitter(client, store, config)
    with _drip_lock:
        submitted, alpha_id, msg = await drip.check_and_drip()
    return {"submitted": submitted, "alpha_id": alpha_id, "message": msg}


@app.get("/", response_class=HTMLResponse)
def index_dashboard():
    config = OptionsConfig.from_env()
    stats = {}
    unsubmitted = []
    recent_subs = []
    today_ny = datetime.datetime.now(NY_TZ).date()

    try:
        store = OptionsStore(database_url=config.database_url)
        stats = store.get_options_stats()
        unsubmitted = store.get_unsubmitted_pool_alphas()

        # Query recent submissions directly from DB
        with store.db._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT alpha_id, archetype, sharpe, fitness, turnover, created_at "
                    "FROM options_alphas WHERE status = 'SUBMITTED' "
                    "ORDER BY created_at DESC LIMIT 5;"
                )
                recent_subs = cur.fetchall()
    except Exception as e:
        log.warning("Dashboard data load error: %s", e)

    recent_rows_html = "".join(
        f"<tr>"
        f"<td><span class='badge submitted'>{r[0]}</span></td>"
        f"<td>{r[1] or 'Options Factor'}</td>"
        f"<td><b>{float(r[2] or 0):.2f}</b></td>"
        f"<td><b>{float(r[3] or 0):.2f}</b></td>"
        f"<td>{float(r[4] or 0)*100:.1f}%</td>"
        f"<td>{str(r[5])[:16]}</td>"
        f"</tr>"
        for r in recent_subs
    )

    top_pool_html = "".join(
        f"<tr>"
        f"<td><span class='badge qualified'>{a.get('alpha_id')}</span></td>"
        f"<td>{a.get('archetype')}</td>"
        f"<td><b>{float(a.get('sharpe') or 0):.2f}</b></td>"
        f"<td><b>{float(a.get('fitness') or 0):.2f}</b></td>"
        f"<td>{float(a.get('turnover') or 0)*100:.1f}%</td>"
        f"</tr>"
        for a in unsubmitted[:5]
    )

    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>BRAIN Options Alpha Command Center</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
        <style>
            :root {{
                --bg-primary: #0a0d14;
                --bg-secondary: #121824;
                --bg-card: #182234;
                --accent: #3b82f6;
                --accent-hover: #2563eb;
                --emerald: #10b981;
                --purple: #8b5cf6;
                --amber: #f59e0b;
                --text-primary: #f1f5f9;
                --text-secondary: #94a3b8;
                --border: #1e293b;
            }}
            * {{ box-sizing: border-box; margin: 0; padding: 0; }}
            body {{
                font-family: 'Inter', -apple-system, sans-serif;
                background-color: var(--bg-primary);
                color: var(--text-primary);
                line-height: 1.5;
                padding: 24px;
            }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding-bottom: 24px;
                border-bottom: 1px solid var(--border);
                margin-bottom: 28px;
            }}
            .header-title h1 {{ font-size: 24px; font-weight: 700; color: #fff; letter-spacing: -0.5px; }}
            .header-title p {{ color: var(--text-secondary); font-size: 14px; }}
            .status-pill {{
                display: flex;
                align-items: center;
                gap: 8px;
                background: rgba(16, 185, 129, 0.12);
                border: 1px solid rgba(16, 185, 129, 0.3);
                color: #34d399;
                padding: 6px 14px;
                border-radius: 9999px;
                font-size: 13px;
                font-weight: 600;
            }}
            .pulse {{ width: 8px; height: 8px; border-radius: 50%; background: #10b981; box-shadow: 0 0 10px #10b981; }}
            .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 20px; margin-bottom: 30px; }}
            .card {{
                background: var(--bg-secondary);
                border: 1px solid var(--border);
                border-radius: 12px;
                padding: 20px;
                position: relative;
                overflow: hidden;
            }}
            .card-title {{ font-size: 13px; color: var(--text-secondary); font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px; }}
            .card-value {{ font-size: 32px; font-weight: 700; margin-top: 8px; color: #fff; }}
            .card-sub {{ font-size: 13px; color: var(--text-secondary); margin-top: 4px; }}
            .card::after {{
                content: '';
                position: absolute;
                top: 0; left: 0; width: 4px; height: 100%;
                background: var(--accent);
            }}
            .card.green::after {{ background: var(--emerald); }}
            .card.purple::after {{ background: var(--purple); }}
            .card.amber::after {{ background: var(--amber); }}
            .section {{ margin-bottom: 32px; background: var(--bg-secondary); border: 1px solid var(--border); border-radius: 12px; padding: 24px; }}
            .section-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; }}
            .section-title {{ font-size: 18px; font-weight: 600; }}
            table {{ width: 100%; border-collapse: collapse; text-align: left; font-size: 14px; }}
            th {{ padding: 12px 16px; background: var(--bg-card); color: var(--text-secondary); font-weight: 500; border-bottom: 1px solid var(--border); }}
            td {{ padding: 14px 16px; border-bottom: 1px solid var(--border); font-family: 'JetBrains Mono', monospace; font-size: 13px; }}
            tr:hover td {{ background: rgba(255, 255, 255, 0.02); }}
            .badge {{
                padding: 4px 8px;
                border-radius: 6px;
                font-size: 11px;
                font-weight: 600;
                font-family: 'Inter', sans-serif;
            }}
            .badge.submitted {{ background: rgba(59, 130, 246, 0.15); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); }}
            .badge.qualified {{ background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }}
            .action-bar {{ display: flex; gap: 12px; }}
            button {{
                background: var(--accent);
                color: #fff;
                border: none;
                padding: 10px 18px;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.2s ease;
            }}
            button:hover {{ background: var(--accent-hover); }}
            .ping-note {{
                background: rgba(139, 92, 246, 0.08);
                border: 1px solid rgba(139, 92, 246, 0.25);
                border-radius: 8px;
                padding: 14px 18px;
                font-size: 13px;
                color: #c4b5fd;
                margin-top: 24px;
                display: flex;
                align-items: center;
                justify-content: space-between;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <div class="header-title">
                    <h1>WorldQuant BRAIN Alpha Pipeline</h1>
                    <p>Options Specialist &bull; Continuous 24/7 Cloud Engine &bull; Silver Stage</p>
                </div>
                <div class="status-pill">
                    <div class="pulse"></div>
                    <span>{PIPELINE_STATE["status"]} &bull; 3 SUBMISSIONS / DAY</span>
                </div>
            </header>

            <div class="grid">
                <div class="card green">
                    <div class="card-title">Reserve Pool (Qualified)</div>
                    <div class="card-value">{len(unsubmitted)}</div>
                    <div class="card-sub">Ready for automated submission</div>
                </div>
                <div class="card purple">
                    <div class="card-title">Total Alphas Scored</div>
                    <div class="card-value">{stats.get("all_time_pool_alphas", 0)}</div>
                    <div class="card-sub">Sharpe &ge; 1.25 &bull; Fitness &ge; 1.0</div>
                </div>
                <div class="card amber">
                    <div class="card-title">Total Evaluated</div>
                    <div class="card-value">{stats.get("all_time_evaluated", 0):,}</div>
                    <div class="card-sub">{stats.get("all_time_stage0_pass", 0):,} cleared Stage 0</div>
                </div>
                <div class="card">
                    <div class="card-title">Cloud Engine Batches</div>
                    <div class="card-value">{PIPELINE_STATE["total_batches_run"]}</div>
                    <div class="card-sub">Last: {PIPELINE_STATE["last_batch_time"][:19] if PIPELINE_STATE["last_batch_time"] else "Starting..."}</div>
                </div>
            </div>

            <div class="section">
                <div class="section-header">
                    <div class="section-title">🏆 Recent Active Submissions on BRAIN</div>
                    <div class="action-bar">
                        <button onclick="triggerDrip()">Check & Drip Alpha Now</button>
                    </div>
                </div>
                <table>
                    <thead>
                        <tr>
                            <th>Alpha ID</th>
                            <th>Archetype</th>
                            <th>Sharpe</th>
                            <th>Fitness</th>
                            <th>Turnover</th>
                            <th>Date (UTC)</th>
                        </tr>
                    </thead>
                    <tbody>
                        {recent_rows_html or "<tr><td colspan='6'>No submissions recorded yet today.</td></tr>"}
                    </tbody>
                </table>
            </div>

            <div class="section">
                <div class="section-header">
                    <div class="section-title">💎 Top Qualified Alphas in Queue</div>
                </div>
                <table>
                    <thead>
                        <tr>
                            <th>Alpha ID</th>
                            <th>Archetype</th>
                            <th>Sharpe</th>
                            <th>Fitness</th>
                            <th>Turnover</th>
                        </tr>
                    </thead>
                    <tbody>
                        {top_pool_html or "<tr><td colspan='5'>Queue is processing...</td></tr>"}
                    </tbody>
                </table>
            </div>

            <div class="ping-note">
                <div>
                    <strong>24/7 Keep-Alive Endpoint:</strong> Ping <code>https://YOUR_SPACE_URL/health</code> every 15 minutes using <a href="https://cron-job.org" target="_blank" style="color:#60a5fa;">cron-job.org</a> or <a href="https://uptimerobot.com" target="_blank" style="color:#60a5fa;">UptimeRobot</a> (100% free) to prevent sleep.
                </div>
            </div>
        </div>

        <script>
            async function triggerDrip() {{
                const btn = event.target;
                btn.disabled = true;
                btn.innerText = "Submitting...";
                try {{
                    const res = await fetch('/api/trigger-drip', {{ method: 'POST' }});
                    const data = await res.json();
                    alert(data.message || (data.submitted ? "Submitted " + data.alpha_id : "Drip check completed"));
                    window.location.reload();
                }} catch (e) {{
                    alert("Error: " + e);
                }} finally {{
                    btn.disabled = false;
                    btn.innerText = "Check & Drip Alpha Now";
                }}
            }}
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)
