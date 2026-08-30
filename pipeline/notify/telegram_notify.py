"""
Telegram alerts. Plain HTTP POST — no
heavyweight bot library. `requests` is imported lazily so message
*formatting* (the part unit tests exercise) never needs network access.
"""
from __future__ import annotations

from typing import Optional

# Characters that open a Markdown entity under Telegram's legacy "Markdown"
# parse_mode (the mode `_post` sends with): underscore (italic), asterisk
# (bold), backtick (code span), and square bracket (link). Update 10 Item
# 2: a BRAIN expression is arbitrary, untrusted-from-Telegram's-parser
# content interpolated straight into a backtick code span
# (format_candidate_alert/format_top_alphas) -- expressions routinely
# contain underscores and asterisks (`ts_delta`, `group_neutralize`), and
# an unescaped backtick would prematurely close the code span outright.
# Any of these can produce an unbalanced/invalid entity that the Telegram
# API rejects with a 400, which (pre-fix) propagated out of the unguarded
# send_candidate_alert call and could flip an already-`passed` candidate
# back toward pending/rejected_error (see _process_candidate).
_MARKDOWN_SPECIAL_CHARS = "_*`["


def escape_markdown(text: str) -> str:
    """Backslash-escape every legacy-Markdown entity-opening character in
    `text` so it can be safely interpolated into a Telegram message (inside
    or outside a code span) without breaking the surrounding formatting or
    producing an entity Telegram's API rejects. This is the root-cause fix
    for Update 10 Item 2 -- previously nothing escaped dynamic content
    (BRAIN expressions) before it was dropped into a backtick block."""
    escaped_chars = []
    for ch in text:
        if ch in _MARKDOWN_SPECIAL_CHARS:
            escaped_chars.append("\\")
        escaped_chars.append(ch)
    return "".join(escaped_chars)


def format_candidate_alert(candidate: dict) -> str:
    frag = "\u26a0\ufe0f fragile (single-point pass)" if candidate["fragile"] else "\u2705 robust"
    safe_expression = escape_markdown(candidate["expression"])
    return (
        f"*New alpha cleared the bar* {frag}\n\n"
        f"`{safe_expression}`\n\n"
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
    """Heartbeat report, sent unconditionally at the end of every `run_once()`
    -- pass, fail, or silence.

    Presents clean, structured operational metrics:
    - Systems status (BRAIN API & DB)
    - Active AI providers (Groq, Cerebras, OpenRouter)
    - This run's results
    - Today's cumulative activity & all-time totals
    - Errors only if any occurred
    """
    brain_flag = "✅ Online" if health.get("brain_auth_ok") else "❌ Offline"
    db_flag = "✅ Connected" if health.get("db_ok") else "❌ Disconnected"

    # AI Engine Key Health
    seen_providers = set()
    key_lines = []
    for row in health.get("llm_keys", []):
        provider = str(row.get("provider", "")).lower()
        if provider == "gemini":
            continue
        seen_providers.add(provider)
        key_label = row.get("key_label", "")
        tier = row.get("tier", "")
        stale = row.get("stale")
        if stale:
            flag = "⏳"
            status_desc = "Standby"
        elif row.get("succeeded"):
            flag = "✅"
            status_desc = "Active"
        else:
            flag = "❌"
            status_desc = "Failed"

        rolling = ""
        if row.get("attempted_last_10"):
            rolling = f" [{row['succeeded_last_10']}/{row['attempted_last_10']} successful]"
        key_lines.append(f"  • {provider.capitalize()}/{key_label} ({tier}): {flag} {status_desc}{rolling}")

    if "groq" not in seen_providers:
        key_lines.append("  • Groq: ⏳ Standby (Ready)")
    if "cerebras" not in seen_providers:
        key_lines.append("  • Cerebras: ⏳ Standby (Ready on fallback)")
    if "openrouter" not in seen_providers:
        key_lines.append("  • OpenRouter: ⏳ Standby (Ready on fallback)")

    keys_block = "\n".join(key_lines)

    # This Run Metrics
    stages = health.get("stage_counts", {})
    passed = stages.get("passed", getattr(summary, "passed", 0))
    rej_s0 = stages.get("rejected_stage0", getattr(summary, "rejected_stage0", 0))
    rej_filt = stages.get("rejected_filter", getattr(summary, "rejected_filter", 0))
    rej_corr = stages.get("rejected_correlation", getattr(summary, "rejected_correlation", 0))
    rej_err = stages.get("rejected_error", getattr(summary, "rejected_error", 0))

    reason_map = {
        "max_candidates_reached": "Max batch limit reached (15/run)",
        "queue_drained": "Queue empty (all candidates processed)",
        "time_budget_exceeded": "Time budget reached",
    }
    raw_reason = getattr(summary, "stopped_reason", "")
    friendly_reason = reason_map.get(raw_reason, raw_reason)

    # Cumulative Daily & Lifetime Analytics
    stats = health.get("stats", {})
    today_gen = stats.get("today_generated", getattr(summary, "candidates_generated", 0))
    today_proc = stats.get("today_processed", getattr(summary, "candidates_processed", 0))
    today_pass = stats.get("today_passed", passed)
    queue_remain = stats.get("queue_depth", getattr(summary, "queue_depth_before", 0))

    all_time_gen = stats.get("all_time_generated", today_gen)
    all_time_proc = stats.get("all_time_processed", today_proc)
    all_time_pass = stats.get("all_time_passed", today_pass)

    # Errors section (only rendered when errors actually occurred)
    errors_section = ""
    if getattr(summary, "errors", None):
        err_items = "\n".join(f"  • {escape_markdown(str(e))}" for e in summary.errors)
        errors_section = f"\n\n⚠️ *Errors:*\n{err_items}"

    return (
        f"📡 *BRAIN Alpha Pipeline Status*\n\n"
        f"*Systems:* BRAIN API: {brain_flag} | Database: {db_flag}\n\n"
        f"*AI Engine (LLMs):*\n{keys_block}\n\n"
        f"*This Run:*\n"
        f"  • Generated: {summary.candidates_generated} alphas\n"
        f"  • Tested: {summary.candidates_processed} (passed={passed} rejected_stage0={rej_s0} rejected_filter={rej_filt} rejected_correlation={rej_corr} rejected_error={rej_err})\n"
        f"  • Status: {friendly_reason} ({raw_reason})\n\n"
        f"*Today's Activity:*\n"
        f"  • Alphas Generated: {today_gen:,}\n"
        f"  • Alphas Tested: {today_proc:,}\n"
        f"  • Alphas Passed: {today_pass:,}\n"
        f"  • Queue Remaining: {queue_remain:,} alphas\n\n"
        f"*All-Time Statistics:*\n"
        f"  • Total Generated: {all_time_gen:,}\n"
        f"  • Total Tested: {all_time_proc:,}\n"
        f"  • Total Passed: {all_time_pass:,}"
        f"{errors_section}"
    )


def format_top_alphas(rows: list[dict]) -> str:
    """Ranked leaderboard (Update 05 feedback engine) -- `rows` from
    Repo.top_alphas(). Distinct prefix from the other message types, same
    as format_run_report/format_operational_alert."""
    if not rows:
        return "\U0001f3c6 *Top alphas*\n\n(review_store is empty so far)"
    lines = [
        f"{i+1}. `{escape_markdown(r['expression'])}` [{r['category']} / {r['generation_tier']}]\n"
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
