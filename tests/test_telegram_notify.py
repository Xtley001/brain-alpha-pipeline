from pipeline.notify.telegram_notify import (
    TelegramNotifier,
    format_candidate_alert,
    format_operational_alert,
    format_run_report,
)

SAMPLE_CANDIDATE = {
    "expression": "group_neutralize(rank(-ts_delta(close, 1)), sector)",
    "fragile": False,
    "sharpe": 1.53,
    "fitness": 1.21,
    "turnover": 0.284,
    "max_correlation": 0.42,
    "universe": "TOP3000",
    "delay": 1,
    "neutralization": "SUBINDUSTRY",
    "decay": 8,
    "truncation": 0.05,
    "pasteurization": True,
    "nan_handling": False,
    "robust_count": 6,
    "sweep_total": 41,
}


def test_candidate_alert_contains_expression_and_metrics():
    text = format_candidate_alert(SAMPLE_CANDIDATE)
    assert SAMPLE_CANDIDATE["expression"] in text
    assert "1.53" in text
    assert "1.21" in text
    assert "28.4%" in text
    assert "0.42" in text
    assert "6/41" in text


def test_candidate_alert_marks_fragile_vs_robust():
    robust_text = format_candidate_alert(SAMPLE_CANDIDATE)
    assert "robust" in robust_text
    assert "fragile" not in robust_text

    fragile_candidate = dict(SAMPLE_CANDIDATE, fragile=True)
    fragile_text = format_candidate_alert(fragile_candidate)
    assert "fragile" in fragile_text


def test_operational_alert_has_distinct_prefix_from_candidate_alert():
    op_text = format_operational_alert("BRAIN auth failed")
    cand_text = format_candidate_alert(SAMPLE_CANDIDATE)
    assert op_text.startswith("\u26a0\ufe0f PIPELINE:")
    assert not cand_text.startswith("\u26a0\ufe0f PIPELINE:")


def test_notifier_posts_expected_payload_via_injected_http():
    captured = {}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout

    notifier = TelegramNotifier("TESTTOKEN", "12345", http_post=fake_post)
    notifier.send_candidate_alert(SAMPLE_CANDIDATE)

    assert captured["url"] == "https://api.telegram.org/botTESTTOKEN/sendMessage"
    assert captured["json"]["chat_id"] == "12345"
    assert captured["json"]["parse_mode"] == "Markdown"
    assert SAMPLE_CANDIDATE["expression"] in captured["json"]["text"]


def test_notifier_never_sends_before_all_gates_pass_is_caller_responsibility():
    # This is a documentation-style test: the notifier itself has no gating
    # logic (by design -- gating happens in run_worker before send is ever
    # called). Confirm send_* are simple pass-throughs with no internal
    # filter that could silently swallow a call.
    sent = []
    notifier = TelegramNotifier("T", "C", http_post=lambda url, json, timeout: sent.append(json))
    notifier.send_candidate_alert(SAMPLE_CANDIDATE)
    assert len(sent) == 1


# --- heartbeat (Update 01 P1.1 / Update 02 P1.2) -------------------------


class _FakeRunSummary:
    """Minimal stand-in for run_worker.RunSummary -- format_run_report only
    reads attributes, so a plain namespace-like object is enough here and
    keeps this test file independent of run_worker.py."""

    def __init__(self, **kwargs):
        defaults = dict(
            reclaimed=0, queue_depth_before=10, candidates_generated=2,
            candidates_processed=5, batches_run=1, stopped_reason="queue_drained",
            brain_auth_ok=True, passed=1, rejected_stage0=2, rejected_filter=1,
            rejected_correlation=1, rejected_error=0, errors=[],
        )
        defaults.update(kwargs)
        for k, v in defaults.items():
            setattr(self, k, v)


def test_run_report_is_distinguishable_from_other_message_types():
    summary = _FakeRunSummary()
    health = {"brain_auth_ok": True, "db_ok": True, "llm_keys": [], "stage_counts": {}}
    text = format_run_report(summary, health)
    op_text = format_operational_alert("x")
    cand_text = format_candidate_alert(SAMPLE_CANDIDATE)
    assert text != op_text and not text.startswith(op_text[:5])
    assert text != cand_text


def test_run_report_surfaces_brain_auth_and_db_health():
    summary = _FakeRunSummary()
    healthy = format_run_report(summary, {"brain_auth_ok": True, "db_ok": True, "llm_keys": [], "stage_counts": {}})
    unhealthy = format_run_report(summary, {"brain_auth_ok": False, "db_ok": False, "llm_keys": [], "stage_counts": {}})
    assert healthy != unhealthy
    assert "\u2705" in healthy  # checkmarks when healthy
    assert "\u274c" in unhealthy  # crosses when unhealthy


def test_run_report_includes_stage_breakdown_and_stopped_reason():
    summary = _FakeRunSummary(stopped_reason="time_budget_exceeded")
    health = {
        "brain_auth_ok": True, "db_ok": True, "llm_keys": [],
        "stage_counts": {"passed": 1, "rejected_stage0": 2, "rejected_filter": 1, "rejected_correlation": 1, "rejected_error": 0},
    }
    text = format_run_report(summary, health)
    assert "time_budget_exceeded" in text
    assert "passed=1" in text
    assert "rejected_stage0=2" in text


def test_run_report_lists_llm_key_health_rows():
    summary = _FakeRunSummary()
    health = {
        "brain_auth_ok": True, "db_ok": True,
        "llm_keys": [
            {"provider": "gemini", "key_label": "key_1", "tier": "reasoning", "succeeded": True},
            {"provider": "groq", "key_label": "key_1", "tier": "mechanical", "succeeded": False},
        ],
        "stage_counts": {},
    }
    text = format_run_report(summary, health)
    assert "gemini/key_1" in text
    assert "groq/key_1" in text


def test_send_run_report_posts_via_injected_http():
    captured = {}

    def fake_post(url, json, timeout):
        captured["json"] = json

    notifier = TelegramNotifier("TESTTOKEN", "12345", http_post=fake_post)
    summary = _FakeRunSummary()
    health = {"brain_auth_ok": True, "db_ok": True, "llm_keys": [], "stage_counts": {}}
    notifier.send_run_report(summary, health)

    assert "Heartbeat" in captured["json"]["text"]
