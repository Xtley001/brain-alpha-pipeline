from pipeline.notify.telegram_notify import (
    TelegramNotifier,
    format_candidate_alert,
    format_operational_alert,
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
