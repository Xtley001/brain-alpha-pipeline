"""
Telegram alerts. Plain HTTP POST — no
heavyweight bot library. `requests` is imported lazily so message
*formatting* (the part unit tests exercise) never needs network access.
"""
from __future__ import annotations

from typing import Optional


def format_candidate_alert(candidate: dict) -> str:
    frag = "\u26a0\ufe0f fragile (single-point pass)" if candidate["fragile"] else "\u2705 robust"
    return (
        f"*New alpha cleared the bar* {frag}\n\n"
        f"`{candidate['expression']}`\n\n"
        f"Sharpe: {candidate['sharpe']:.2f} | Fitness: {candidate['fitness']:.2f} | "
        f"Turnover: {candidate['turnover']:.1%}\n"
        f"Max corr vs pool: {candidate['max_correlation']:.2f}\n\n"
        f"*Settings (copy-paste into BRAIN):*\n"
        f"Region: USA | Universe: {candidate['universe']} | Delay: {candidate['delay']}\n"
        f"Neutralization: {candidate['neutralization']} | Decay: {candidate['decay']}\n"
        f"Truncation: {candidate['truncation']} | Pasteurization: {candidate['pasteurization']}\n"
        f"Nan Handling: {candidate['nan_handling']}\n\n"
        f"Robustness: {candidate['robust_count']}/{candidate['sweep_total']} "
        f"variants also cleared the bar"
    )


def format_run_report(summary, health: dict) -> str:
    """Heartbeat report (Update 01 P1.1 / Update 02 P1.2), sent unconditionally
    at the end of every `run_once()` -- pass, fail, or silence. `summary` is a
    `pipeline.run_worker.RunSummary`; `health` is the dict Worker._build_run_report
    assembles (brain_auth_ok, db_ok, llm_keys, stage_counts). The whole point of
    this message is that silence stops being a valid healthy state -- see
    Update 01/03's "black box" framing.

    Uses a distinct prefix from both format_candidate_alert and
    format_operational_alert so all three message types are visually
    distinguishable at a glance in a Telegram thread."""
    brain_flag = "\u2705" if health.get("brain_auth_ok") else "\u274c"
    db_flag = "\u2705" if health.get("db_ok") else "\u274c"

    key_lines = []
    for row in health.get("llm_keys", []):
        # Update 05: a key that hasn't been *tried* recently is a different
        # fact from a key that just failed -- rendering both as a flat ❌
        # is exactly what made a fixed key look permanently broken. `stale`
        # is only present once Repo.recent_llm_key_health() reports it;
        # older/fake health dicts without it just render as before.
        stale = row.get("stale")
        if stale:
            flag = "\u23f3"  # hourglass: no recent attempt, verdict unknown
            suffix = " (stale)"
        else:
            flag = "\u2705" if row.get("succeeded") else "\u274c"
            suffix = ""
        rolling = ""
        if row.get("attempted_last_10"):
            rolling = f" [{row['succeeded_last_10']}/{row['attempted_last_10']} last 10]"
        key_lines.append(f"  {flag} {row['provider']}/{row['key_label']} ({row['tier']}){suffix}{rolling}")
    keys_block = "\n".join(key_lines) if key_lines else "  (no llm_usage rows yet)"

    stages = health.get("stage_counts", {})
    stage_line = (
        f"passed={stages.get('passed', 0)} "
        f"rejected_stage0={stages.get('rejected_stage0', 0)} "
        f"rejected_filter={stages.get('rejected_filter', 0)} "
        f"rejected_correlation={stages.get('rejected_correlation', 0)} "
        f"rejected_error={stages.get('rejected_error', 0)}"
    )

    errors_block = ("\n".join(f"  - {e}" for e in summary.errors)) if summary.errors else "  (none)"

    return (
        f"\U0001f4e1 *Heartbeat*\n\n"
        f"BRAIN auth: {brain_flag} | DB reachable: {db_flag}\n"
        f"LLM key health:\n{keys_block}\n\n"
        f"Queue depth before: {summary.queue_depth_before}\n"
        f"Candidates generated: {summary.candidates_generated}\n"
        f"Candidates processed: {summary.candidates_processed} ({stage_line})\n"
        f"Reclaimed (orphaned): {summary.reclaimed}\n"
        f"Stopped reason: {summary.stopped_reason}\n"
        f"Errors this tick:\n{errors_block}"
    )


def format_top_alphas(rows: list[dict]) -> str:
    """Ranked leaderboard (Update 05 feedback engine) -- `rows` from
    Repo.top_alphas(). Distinct prefix from the other message types, same
    as format_run_report/format_operational_alert."""
    if not rows:
        return "\U0001f3c6 *Top alphas*\n\n(review_store is empty so far)"
    lines = [
        f"{i+1}. `{r['expression']}` [{r['category']} / {r['generation_tier']}]\n"
        f"   Fitness {r['fitness']:.2f} | Sharpe {r['sharpe']:.2f} | "
        f"Turnover {r['turnover']:.1%} | MaxCorr {r['max_correlation']:.2f} | "
        f"{r['robust_count']}/{r['sweep_total']} robust"
        for i, r in enumerate(rows)
    ]
    return "\U0001f3c6 *Top alphas*\n\n" + "\n".join(lines)


def format_operational_alert(message: str) -> str:
    """Operational alerts (LLM exhaustion, BRAIN auth failure, worker error)
    use a visually distinct prefix so they never get mistaken for a
    candidate-passed alert."""
    return f"\u26a0\ufe0f PIPELINE: {message}"


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str, http_post=None):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self._http_post = http_post  # injectable for tests; defaults to requests.post

    def _post(self, text: str) -> None:
        if self._http_post is not None:
            post = self._http_post
        else:
            import requests  # lazy import

            def post(url, json, timeout):
                resp = requests.post(url, json=json, timeout=timeout)
                resp.raise_for_status()
                return resp

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        post(url, json={"chat_id": self.chat_id, "text": text, "parse_mode": "Markdown"}, timeout=10)

    def send_candidate_alert(self, candidate: dict) -> str:
        text = format_candidate_alert(candidate)
        self._post(text)
        return text

    def send_operational_alert(self, message: str) -> str:
        text = format_operational_alert(message)
        self._post(text)
        return text

    def send_run_report(self, summary, health: dict) -> str:
        text = format_run_report(summary, health)
        self._post(text)
        return text

    def send_top_alphas(self, rows: list[dict]) -> str:
        text = format_top_alphas(rows)
        self._post(text)
        return text
