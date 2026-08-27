# BRAIN Alpha Pipeline

Autonomous pipeline that generates, screens, sweeps, and correlation-checks
WorldQuant BRAIN equity alpha candidates, then alerts a human via Telegram
for manual review and submission.

## Non-negotiables

- **Never submits to BRAIN.** No `submit(...)` call exists anywhere in this
  codebase. A human reads the Telegram alert and submits manually.
- **No hardcoded credentials.** All secrets come from environment variables,
  validated at startup (`pipeline/config.py`) — a missing required var fails
  loudly (`MissingConfigError`), not partway through a run.

## How it works

Each scheduled tick (`pipeline/run_worker.py`):

```
reclaim orphaned candidates
  -> top up queue (template / LLM reasoning / LLM mechanical)
  -> for each candidate: Stage 0 screen -> settings sweep -> local filter
     -> correlation check -> Telegram alert
  -> heartbeat + run_history row
```

For the full design — sweep stage breakdown, concurrency model, LLM
provider fallback chain, and observability — see
[`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md).

## Setup

See [`SETUP.md`](./SETUP.md) for prerequisites, environment configuration,
and deployment.

## Testing

```bash
PYTHONPATH=. pytest tests/ -v
```

All tests run against in-memory fakes — no live BRAIN, Postgres, Telegram,
or LLM credentials required or contacted.
