# brain-alpha-pipeline

Autonomous WorldQuant BRAIN alpha discovery, simulation, orthogonalization, and reserve vault pipeline.

[![CI](https://img.shields.io/github/actions/workflow/status/Xtley001/brain-alpha-pipeline/ci.yml?branch=main&label=pipeline%20ci)](https://github.com/Xtley001/brain-alpha-pipeline/actions)
[![Libraries CI](https://img.shields.io/github/actions/workflow/status/Xtley001/brain-libraries/ci.yml?branch=main&label=libraries%20ci)](https://github.com/Xtley001/brain-libraries/actions)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](./LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![PyPI](https://img.shields.io/pypi/v/brain-synthesis?label=PyPI%20Suite)](https://pypi.org/project/brain-synthesis/)
[![Total Suite Downloads](https://img.shields.io/badge/total%20downloads-3.0k%2B%20across%20suite-blue)](https://github.com/Xtley001/brain-libraries#package-index)

`brain-alpha-pipeline` is an institutional quantitative alpha research pipeline and autonomous mining system for WorldQuant BRAIN. It mines high-value, uncrowded data categories—Options Analytics (ValueScore: 6.0), Systematic Risk & Valuation Models (ValueScore: 7.0), and Analyst Estimates (ValueScore: 5.0)—while applying 10-axis orthogonal decorrelation, AST-diff motif mining, and asymmetric veto memory to guarantee sub-0.70 correlation against existing platform submissions. Synthesizes multi-asset alphas via Hierarchical Risk Parity (HRP) and dynamic market regime detection. State is persisted in Neon PostgreSQL with zero-config local fallback. For the full quantitative methodology and mathematical specifications, see the [whitepaper](./docs/institutional_sentiment_and_risk_canon.md).

## Quickstart

### Option A: Install Modular Libraries via Pip & Use Unified CLI

```bash
# Install the complete 7-library suite and global CLI
pip install brain-synthesis

# Generate 3 candidates across all high-value data domains
brain generate --domain all --count 3

# Apply orthogonal decorrelation transforms to pass BRAIN's correlation gate (|rho| < 0.70)
brain decorrelate "rank(implied_volatility_call_30)" --base-sharpe 1.55

# Inspect storage subsystem health and cache counts
brain store
```

### Option B: Local Repository Setup & Autonomous 24/7 Miner

```bash
git clone https://github.com/Xtley001/brain-alpha-pipeline.git
cd brain-alpha-pipeline
pip install -r requirements.txt
cp .env.example .env   # configure BRAIN, Neon DB, and Telegram credentials

# Launch autonomous multi-worker vault miner
python scripts/autonomous_24h_vault_miner.py
```

## Architecture

```mermaid
graph TD
    A["WorldQuant BRAIN Top 3 Multi-Category Engine"] --> B["brain_options (ValueScore: 6.0)<br/>30 Volatility & Skew Strategies"]
    A --> C["brain_generators/fundamental (ValueScore: 5.0)<br/>Analyst Estimates, Revision Dispersion & SUE"]
    A --> D["brain_risk_model (ValueScore: 7.0)<br/>BAB, Beta Divergence & Factor Surfaces"]
    B --> E["brain_synthesis (Tri-Factor Apex)"]
    C --> E
    D --> E
    E --> F["1,800+ Point Hybrid Alphas<br/>|rho| < 0.30 Uniqueness"]
```

```
brain-alpha-pipeline/
├── brain_generators/         # Domain alpha generation engines (options, risk, analyst)
├── brain_options/            # Options analytics runner & strategies
├── brain_risk_model/         # Risk models & BAB strategies
├── brain_synthesis/          # Cross-factor synthesis coordinator
├── scripts/                  # Standalone 24/7 vault miner & backtest utilities
├── docs/                     # Extended whitepapers, guides & articles
│   ├── articles/             # 5-part WorldQuant BRAIN Masterclass series
│   └── HOW_IT_WORKS.md       # Pipeline architecture & simulation lifecycle
├── tests/                    # Pipeline integration test suite (100+ tests)
└── .github/workflows/        # Continuous discovery & mining automations
```

> **Note:** The underlying modular quantitative libraries ([`brain-alpha-core`](https://pypi.org/project/brain-alpha-core/), [`brain-store`](https://pypi.org/project/brain-store/), [`brain-decorrelator`](https://pypi.org/project/brain-decorrelator/), [`brain-options`](https://pypi.org/project/brain-options/), [`brain-risk-model`](https://pypi.org/project/brain-risk-model/), and [`brain-synthesis`](https://pypi.org/project/brain-synthesis/)) are developed and maintained in the dedicated [Xtley001/brain-libraries](https://github.com/Xtley001/brain-libraries) repository and published to PyPI.

## Data Categories & Coverage

| Package | Category ID | ValueScore | Theoretical Foundation | Core Field Examples | Status |
|---|---|:---:|---|---|:---:|
| [`brain-options`](https://pypi.org/project/brain-options/) | `option` | **6.0** | Sinclair (2010), Bali (2008), Xing et al. (2010) | `implied_volatility_call_30`, `option_breakeven_60`, `pcr_vol_30` | Active |
| [`brain-risk-model`](https://pypi.org/project/brain-risk-model/) | `model` | **7.0** | Frazzini & Pedersen (2014), Ang et al. (2006) | `beta_last_60_days_spy`, `unsystematic_risk_last_30_days`, `fscore_bfl_quality` | Active |
| `analyst` | `analyst` | **5.0** | Givoly & Lakonishok (1979), Diether et al. (2002) | `anl4_adxqfv110_pu`, `anl4_afv4_dts_spe`, `actual_eps_value_quarterly` | Active |
| [`brain-synthesis`](https://pypi.org/project/brain-synthesis/) | `top3_tri_factor` | **7.0+** | Orthogonal Tri-Factor Confluence | Cross-dataset composite formulations | Active |

## Workflows

| Workflow | Trigger | Purpose |
|---|---|---|
| [`run.yml`](.github/workflows/run.yml) | 48× daily + manual | Discovers and simulates alpha candidates on WorldQuant BRAIN |
| [`mine_options.yml`](.github/workflows/mine_options.yml) | Scheduled / Dispatch | Dedicated Options category alpha mining worker |
| [`mine_risk_model.yml`](.github/workflows/mine_risk_model.yml) | Scheduled / Dispatch | Dedicated Risk Model category alpha mining worker |
| [`health.yml`](.github/workflows/health.yml) | Hourly | Transmits Telegram health heartbeat and discovery funnel telemetry |
| [`daily_digest.yml`](.github/workflows/daily_digest.yml) | Daily at 23:00 UTC | Generates end-of-day summary of simulated, qualified, and reserve alphas |
| [`ci.yml`](.github/workflows/ci.yml) | Push / PR | Runs end-to-end pipeline test suite and orchestration verification |

## Testing

```bash
# Run complete pipeline test suite (104 tests)
pytest tests/ -v
```

## Security

Report vulnerabilities per our [security policy](./SECURITY.md). Never commit API keys or PostgreSQL credentials; all secrets must be configured via environment variables.

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for code style, AST compiler constraints, and pull request guidelines.

## License

Released under the [MIT License](./LICENSE). Maintained by [Xtley001](https://github.com/Xtley001).
