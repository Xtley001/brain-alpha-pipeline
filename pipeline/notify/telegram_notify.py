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
