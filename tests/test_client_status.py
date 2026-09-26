import pytest
from brain_options.core.client import parse_brain_sim_response, SimMetrics, ACCEPTED_SIM_STATUSES

def test_parse_brain_sim_response_warning_status():
    mock_resp = {
        "alpha": "testAlpha123",
        "status": "WARNING",
        "is": {
            "sharpe": 1.45,
            "fitness": 1.20,
            "turnover": 0.08,
            "returns": 0.09,
            "maxDrawdown": 0.05,
            "margin": 0.002
        }
    }
    metrics = parse_brain_sim_response(mock_resp)
    assert metrics.alpha_id == "testAlpha123"
    assert metrics.status == "WARNING"
    assert metrics.sharpe == 1.45
    assert metrics.is_valid is True

def test_parse_brain_sim_response_complete_status():
    mock_resp = {
        "alpha": "testAlpha456",
        "status": "COMPLETE",
        "is": {
            "sharpe": 1.82,
            "fitness": 1.57,
            "turnover": 0.09,
            "returns": 0.095,
            "maxDrawdown": 0.10,
            "margin": 0.003
        }
    }
    metrics = parse_brain_sim_response(mock_resp)
    assert metrics.is_valid is True

def test_parse_brain_sim_response_error_status_zero_metrics():
    mock_resp = {
        "alpha": None,
        "status": "ERROR",
        "is": {
            "sharpe": 0.0,
            "fitness": 0.0
        }
    }
    metrics = parse_brain_sim_response(mock_resp)
    assert metrics.is_valid is False
