"""
Tests for pipeline/brain/client.py's response-parsing helpers -- pure
functions, no real `wqb` session, no network. Covers the alpha-id
extraction and PnL-recordset -> daily-returns conversion added to wire the
correlation gate for real (code review §2.1).
"""
from pipeline.brain.client import _parse_pnl_response, _parse_sim_response


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def test_parse_sim_response_extracts_alpha_id_from_nested_is_block():
    resp = _FakeResp({
        "id": "abc123",
        "is": {"sharpe": 1.5, "fitness": 1.2, "turnover": 0.3, "returns": 0.1, "drawdown": -0.05},
    })
    result = _parse_sim_response(resp)
    assert result.alpha_id == "abc123"
    assert result.sharpe == 1.5
    assert result.fitness == 1.2


def test_parse_sim_response_tolerates_alphaid_key_variant():
    resp = _FakeResp({"alphaId": "xyz789", "sharpe": 1.0, "fitness": 0.9, "turnover": 0.2})
    result = _parse_sim_response(resp)
    assert result.alpha_id == "xyz789"


def test_parse_sim_response_alpha_id_is_none_when_absent():
    resp = _FakeResp({"sharpe": 1.0, "fitness": 0.9, "turnover": 0.2})
    result = _parse_sim_response(resp)
    assert result.alpha_id is None


def test_parse_pnl_response_diffs_cumulative_pnl_into_daily_returns():
    resp = _FakeResp({
        "records": [
            ["2026-01-01", 100.0],
            ["2026-01-02", 105.0],
            ["2026-01-03", 103.0],
        ],
        "schema": {"properties": [{"name": "date"}, {"name": "pnl"}]},
    })
    daily = _parse_pnl_response(resp)
    # First record has no prior day to diff against, so it's dropped.
    assert daily == {"2026-01-02": 5.0, "2026-01-03": -2.0}


def test_parse_pnl_response_handles_dict_shaped_records():
    resp = _FakeResp({
        "records": [
            {"date": "2026-01-01", "pnl": 10.0},
            {"date": "2026-01-02", "pnl": 12.0},
        ],
    })
    daily = _parse_pnl_response(resp)
    assert daily == {"2026-01-02": 2.0}


def test_parse_pnl_response_empty_records_returns_empty_dict():
    resp = _FakeResp({"records": []})
    assert _parse_pnl_response(resp) == {}
