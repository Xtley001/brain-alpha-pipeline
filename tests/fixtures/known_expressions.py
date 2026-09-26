"""Known submitted alpha expressions from options_alphas."""

KNOWN_ALPHAS = {
    "E5pNpQlm": {
        "expression": 'trade_when(abs(rank(ts_decay_linear(ts_decay_linear(((call_breakeven_90 - forward_price_90) / close * (implied_volatility_mean_skew_90 * sqrt(90/252.0)) * (implied_volatility_call_90 / (implied_volatility_put_90 + 0.001))), 8), 2)) - 0.5) > 0.28, group_neutralize(rank(ts_decay_linear(ts_decay_linear(((call_breakeven_90 - forward_price_90) / close * (implied_volatility_mean_skew_90 * sqrt(90/252.0)) * (implied_volatility_call_90 / (implied_volatility_put_90 + 0.001))), 8), 2)) * (volume / adv20), subindustry), -1)',
        "decay": 7,
        "neutralization": "SUBINDUSTRY",
        "universe": "TOP3000",
    },
    "KPNd6Ovl": {
        "expression": 'trade_when(abs(rank(ts_decay_linear(ts_decay_linear(((call_breakeven_30 - forward_price_30) / close * (implied_volatility_mean_skew_30 * sqrt(30/252.0)) * (pcr_vol_30 / (pcr_oi_30 + 0.001))), 12), 5)) - 0.5) > 0.32, group_neutralize(rank(ts_decay_linear(ts_decay_linear(((call_breakeven_30 - forward_price_30) / close * (implied_volatility_mean_skew_30 * sqrt(30/252.0)) * (pcr_vol_30 / (pcr_oi_30 + 0.001))), 12), 5)) * (volume / adv20), subindustry), -1)',
        "decay": 8,
        "neutralization": "SUBINDUSTRY",
        "universe": "TOP3000",
    },
    "YPb81N2v": {
        "expression": 'trade_when(abs(rank(ts_decay_linear(ts_decay_linear(((call_breakeven_180 - forward_price_180) / close * (implied_volatility_mean_skew_180 * sqrt(180/252.0)) * (pcr_vol_180 / (pcr_oi_180 + 0.001))), 10), 3)) - 0.5) > 0.38, group_neutralize(rank(ts_decay_linear(ts_decay_linear(((call_breakeven_180 - forward_price_180) / close * (implied_volatility_mean_skew_180 * sqrt(180/252.0)) * (pcr_vol_180 / (pcr_oi_180 + 0.001))), 10), 3)) * (volume / adv20), subindustry), -1)',
        "decay": 16,
        "neutralization": "SUBINDUSTRY",
        "universe": "TOP2000",
    },
    "gJbAP76e": {
        "expression": 'trade_when(abs(rank(ts_decay_linear((call_breakeven_30 - forward_price_30) / close * (implied_volatility_mean_skew_30 * sqrt(30/252.0)), 12)) - 0.5) > 0.35, group_neutralize(rank(ts_decay_linear((call_breakeven_30 - forward_price_30) / close * (implied_volatility_mean_skew_30 * sqrt(30/252.0)), 12)), subindustry), -1)',
        "decay": 18,
        "neutralization": "SUBINDUSTRY",
        "universe": "TOP3000",
    },
    "levEYpmx": {
        "expression": 'trade_when(abs(rank(0.65 * rank(ts_decay_linear(ts_decay_linear(((call_breakeven_180 - forward_price_180) / close * (implied_volatility_mean_skew_180 * sqrt(180/252.0)) * (pcr_vol_180 / (pcr_oi_180 + 0.001))), 10), 3)) + 0.35 * rank(ts_decay_linear(ts_decay_linear(((forward_price_90 - put_breakeven_90) / close * (implied_volatility_mean_skew_90 * sqrt(90/252.0)) * (implied_volatility_mean_90 / (implied_volatility_mean_30 + 0.001))), 10), 3))) - 0.5) > 0.26, group_neutralize(rank(0.65 * rank(ts_decay_linear(ts_decay_linear(((call_breakeven_180 - forward_price_180) / close * (implied_volatility_mean_skew_180 * sqrt(180/252.0)) * (pcr_vol_180 / (pcr_oi_180 + 0.001))), 10), 3)) + 0.35 * rank(ts_decay_linear(ts_decay_linear(((forward_price_90 - put_breakeven_90) / close * (implied_volatility_mean_skew_90 * sqrt(90/252.0)) * (implied_volatility_mean_90 / (implied_volatility_mean_30 + 0.001))), 10), 3))) * (volume / adv20), subindustry), -1)',
        "decay": 15,
        "neutralization": "SUBINDUSTRY",
        "universe": "TOP3000",
    },
}

KNOWN_LEVEYPMX_EXPR = KNOWN_ALPHAS["levEYpmx"]["expression"]
KNOWN_KPND6OVL_EXPR = KNOWN_ALPHAS["KPNd6Ovl"]["expression"]
KNOWN_E5PNPQLM_EXPR = KNOWN_ALPHAS["E5pNpQlm"]["expression"]
KNOWN_YPB81N2V_EXPR = KNOWN_ALPHAS["YPb81N2v"]["expression"]
KNOWN_GJBAP76E_EXPR = KNOWN_ALPHAS["gJbAP76e"]["expression"]
