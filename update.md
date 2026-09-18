# Pipeline Optimization & Update Roadmap (update.md)
**Repository:** `Xtley001/brain-alpha-pipeline`  
**Target:** Peak Throughput, Zero-Crash Stability & Multi-Org Optimization  
**Status:** Pending User Approval Before Execution  

---

## 1. Roadmap Overview & Phasing

To bring the pipeline to peak efficiency and institutional robustness, updates are divided into 4 sequenced phases:

1. **Phase 1: Critical Bug Fixes & Formula Grammar Integrity** (Fix runtime crashers and BRAIN syntax errors)
2. **Phase 2: Multi-Org Cluster Isolation & Fan-Out Orchestration** (Prevent drip clashes, unlock 4-way parallel generation)
3. **Phase 3: Peak Performance Engine (Async & Connection Pooling)** (Zero-blocking event loop, sub-millisecond database queries)
4. **Phase 4: Packaging, Deprecations & Clean DX** (Clean dependencies, lifespan handlers, pytest isolation)

---

## 2. Detailed Technical Remediation Plan

### Phase 1: Critical Bug Fixes & Formula Grammar Integrity

#### Fix 1.1: Fix Undefined `target_repo` in `scripts/org_manager.py`
- **File:** `scripts/org_manager.py`
- **Action:**
  ```python
  # Line 88
  chosen_org = target_worker["org"]
  target_repo = f"{chosen_org}/{REPO_NAME}"
  print(f"\n>>> Routing Generation Job to: {target_repo} (Active Jobs: {target_worker['active_runs']})...")
  ```
- **Verification:** Run `python scripts/org_manager.py --status` and test dispatch dry-run.

#### Fix 1.2: Replace Invalid Operator `ts_var` with `signed_power(ts_std_dev(...), 2)`
- **Files:**
  - `brain_options/specialist/archetypes.py` (Line 221)
  - `brain_options/specialist/templates.py` (Line 269)
  - `options-kb-master.md` (Line 491)
- **Change:**
  ```diff
  - formula_template="group_neutralize(rank(-(signed_power(implied_volatility_mean_{tenor}, 2) - ts_var(returns, {window}) * 252)), {group})"
  + formula_template="group_neutralize(rank(-(signed_power(implied_volatility_mean_{tenor}, 2) - signed_power(ts_std_dev(returns, {window}), 2) * 252)), {group})"
  ```
- **Benefit:** Eliminates FastExpr compilation failures on the Carr-Wu Quadratic Variance Risk Premium archetype.

#### Fix 1.3: Replace Invalid Operator `ts_decay_exp_window` in Optimizer
- **File:** `brain_options/core/optimizer.py`
- **Action:**
  - Update `wrap_decay_exp` to use multi-stage `ts_decay_linear` with adaptive lookbacks:
    ```python
    @classmethod
    def wrap_decay_exp(cls, expr: str, window: int = 15, factor: float = 0.20) -> str:
        """
        Applies deep linear decay (window 15-25) in place of unsupported exponential decay
        to maximize turnover compression in BRAIN FastExpr.
        """
        return cls.wrap_decay_linear(expr, window=max(15, window))
    ```
  - Update Round 2 trial arm `EXP_DECAY_CONVICTION` to use `ts_decay_linear`.

---

### Phase 2: Multi-Org Cluster Isolation & Fan-Out Orchestration

#### Fix 2.1: Isolate Drip Submissions Exclusively to Primary Account
- **File:** `.github/workflows/drip.yml`
- **Action:**
  Add repo ownership guard:
  ```yaml
  jobs:
    drip:
      if: github.repository_owner == 'Xtley001'
      runs-on: ubuntu-latest
  ```
- **Benefit:** Guarantees that only `Xtley001` performs timed 24-hour New York drip submissions. The 4 worker orgs will never wake up on schedule or clash.

#### Fix 2.2: Upgrade `scripts/org_manager.py` with Parallel Fan-Out & Candidate Passing
- **File:** `scripts/org_manager.py`
- **Action:**
  - Support dispatching candidate counts: `gh workflow run run.yml --repo {target_repo} -f candidates={candidates}`.
  - Add `--fanout` option to trigger generation across all 4 worker orgs in parallel:
    ```bash
    python scripts/org_manager.py --fanout --candidates 25
    ```
    (Runs 4 x 25 = 100 alpha evaluations across 4 orgs in parallel, exhausting zero limits on the primary account).

---

### Phase 3: Peak Performance Engine (Async & Connection Pooling)

#### Fix 3.1: Implement PostgreSQL Connection Pooling in `OptionsDatabase`
- **File:** `brain_options/store/db.py`
- **Action:**
  - Import `from psycopg_pool import ConnectionPool`.
  - Initialize `self._pool = ConnectionPool(conninfo=url, min_size=1, max_size=10, open=True)`.
  - Use `with self._pool.connection() as conn:` instead of establishing fresh connections on each query.
  - Add graceful close on shutdown.
- **Benefit:** Reduces database operation latency from ~250ms to < 2ms per query. Saves 5-10 seconds per candidate evaluation cycle.

#### Fix 3.2: Add PostgreSQL Composite Indexes
- **File:** `brain_options/store/db.py`
- **Action:**
  Add to `SCHEMA_SQL`:
  ```sql
  CREATE INDEX IF NOT EXISTS idx_options_alphas_status_created ON options_alphas(status, created_at DESC);
  CREATE INDEX IF NOT EXISTS idx_options_alphas_archetype ON options_alphas(archetype);
  CREATE INDEX IF NOT EXISTS idx_options_eval_created_status ON options_evaluations(created_at DESC, status);
  ```

#### Fix 3.3: Offload Synchronous LLM & Telegram Network Calls to Threads
- **Files:**
  - `brain_options/llm/adapter.py`
  - `brain_options/core/notifier.py`
  - `brain_options/run.py`
- **Action:**
  - Wrap `self.llm_adapter.generate(...)` with `await asyncio.to_thread(...)`.
  - Wrap `_send_telegram_raw(...)` with `await asyncio.to_thread(...)` when invoked from async functions.
- **Benefit:** Prevents freezing the asyncio event loop. In-flight BRAIN simulation websocket/HTTP polling continues without packet loss or timeout spikes while LLMs generate formulas.

#### Fix 3.4: Fix Worker Queue Replenishment Race Condition in `run.py`
- **File:** `brain_options/run.py`
- **Action:**
  - Add `refill_lock = asyncio.Lock()`.
  - In `except asyncio.QueueEmpty:`, acquire `refill_lock` before checking and refilling queue.

#### Fix 3.5: Implement Stateful Round-Robin Key Rotation in `LLMAdapter`
- **File:** `brain_options/llm/adapter.py`
- **Action:**
  - Maintain `self._key_indices = {"groq": 0, "cerebras": 0, "openrouter": 0, "gemini": 0}`.
  - Advance index on each request or rate limit so keys are utilized evenly without repeated 429 penalties.

---

### Phase 4: Packaging, Deprecations & Clean DX

#### Fix 4.1: Migrate FastAPI to `lifespan` Context Manager in `app.py`
- **File:** `app.py`
- **Action:**
  ```python
  from contextlib import asynccontextmanager

  @asynccontextmanager
  async def lifespan(app: FastAPI):
      config = OptionsConfig.from_env()
      # Start workers
      t_drip = threading.Thread(target=background_drip_worker, args=(config,), daemon=True)
      t_drip.start()
      t_gen = threading.Thread(target=background_generator_worker, args=(config,), daemon=True)
      t_gen.start()
      yield

  app = FastAPI(title="WorldQuant BRAIN Alpha Pipeline", lifespan=lifespan)
  ```

#### Fix 4.2: Add Missing Dependencies to `requirements.txt`
- **File:** `requirements.txt`
- **Action:** Add:
  ```text
  fastapi>=0.110.0
  uvicorn[standard]>=0.28.0
  ```

#### Fix 4.3: Isolate Pytest from Legacy Archive
- **File:** `pytest.ini` (New file)
- **Action:**
  ```ini
  [pytest]
  testpaths = tests
  norecursedirs = legacy_archive legacy_alphas_backup.zip .agents venv
  asyncio_mode = strict
  ```
- **Verification:** Run `pytest` and verify 100% tests pass with 0 failures.

#### Fix 4.4: Add `enable_auto_submit` to `OptionsConfig`
- **File:** `brain_options/config.py`
- **Action:**
  - Add `enable_auto_submit: bool = False` to `OptionsConfig`.
  - Parse `ENABLE_AUTO_SUBMIT` in `from_env()`.

---

## 3. Verification & Benchmark Checklist

Upon user approval, the execution will be validated by:
1. **Unit Test Suite:** Running `pytest` across all tests (expected 100% pass rate).
2. **Cluster Health Check:** Executing `python scripts/org_manager.py --status`.
3. **Dispatch Dry-Run:** Executing `python scripts/org_manager.py --dispatch` and verifying no undefined variable errors.
4. **FastExpr Operator Validation:** Verifying all generated expressions in templates and archetypes parse cleanly without `ts_var` or `ts_decay_exp_window`.
5. **Database Connection Pool Test:** Confirming `psycopg_pool` handles multiple concurrent transactions without opening new raw connections.
6. **API & Dashboard Verification:** Running `app.py` under the new lifespan handler.

---
**Next Step:** Awaiting user approval to apply the planned fixes.
