-- Schema for the Agentic Alpha Generation Pipeline (v2)
-- Matches the project's data-model spec exactly. Do not deviate without updating
-- both this file and that doc together.

CREATE TABLE IF NOT EXISTS candidates (
    id              BIGSERIAL PRIMARY KEY,
    expression      TEXT NOT NULL,
    category        TEXT,               -- e.g. which of the 50 seed ideas it derives from
    generation_tier TEXT,               -- 'template' | 'llm_gemini' | 'llm_groq'
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    claimed_at      TIMESTAMPTZ,        -- set when status flips to 'running'; orphan-reclaim
                                         -- keys off this, NOT created_at (see repo.py)
    stage0_fitness  NUMERIC,
    stage0_sharpe   NUMERIC,
    status          TEXT NOT NULL DEFAULT 'pending'
                    -- 'pending' | 'running' | 'rejected_stage0' | 'rejected_correlation'
                    -- | 'rejected_filter' | 'passed' | 'submitted'
);

-- Idempotent for pre-existing deployments where `candidates` was created
-- before `claimed_at` existed: CREATE TABLE IF NOT EXISTS above is a no-op
-- against an already-existing table, so the column must be added separately.
ALTER TABLE candidates ADD COLUMN IF NOT EXISTS claimed_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS sweep_runs (
    id              BIGSERIAL PRIMARY KEY,
    candidate_id    BIGINT NOT NULL REFERENCES candidates(id),
    stage           TEXT NOT NULL,   -- 'stage0' | 'stage1' | 'stage2' | 'stage3'
    delay           SMALLINT,
    universe        TEXT,
    neutralization  TEXT,
    decay           SMALLINT,
    truncation      NUMERIC,
    pasteurization  BOOLEAN,
    nan_handling    BOOLEAN,
    sharpe          NUMERIC,
    fitness         NUMERIC,
    turnover        NUMERIC,
    returns_ann     NUMERIC,
    drawdown        NUMERIC,
    simulated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_sweep_runs_candidate ON sweep_runs(candidate_id);

CREATE TABLE IF NOT EXISTS review_store (
    id                  BIGSERIAL PRIMARY KEY,
    candidate_id        BIGINT NOT NULL REFERENCES candidates(id),
    expression          TEXT NOT NULL,
    region              TEXT NOT NULL DEFAULT 'USA',
    instrument_type     TEXT NOT NULL DEFAULT 'EQUITY',
    delay               SMALLINT NOT NULL,
    universe            TEXT NOT NULL,
    neutralization      TEXT NOT NULL,
    decay               SMALLINT NOT NULL,
    truncation          NUMERIC NOT NULL,
    pasteurization      BOOLEAN NOT NULL,
    nan_handling        BOOLEAN NOT NULL,
    sharpe              NUMERIC NOT NULL,
    fitness             NUMERIC NOT NULL,
    turnover            NUMERIC NOT NULL,
    max_correlation     NUMERIC NOT NULL,   -- vs. existing accepted/pending pool
    robust_count        SMALLINT NOT NULL,  -- variants also clearing the bar
    sweep_total         SMALLINT NOT NULL,
    fragile             BOOLEAN NOT NULL,
    telegram_sent_at     TIMESTAMPTZ,
    submitted           BOOLEAN NOT NULL DEFAULT false,
    submitted_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_review_store_fitness ON review_store(fitness DESC);
CREATE INDEX IF NOT EXISTS idx_review_store_correlation ON review_store(max_correlation ASC);

-- ASSUMPTION / DEVIATION from the literal text in 05_DATA_MODEL.md:
-- that doc shows `alpha_id TEXT PRIMARY KEY` (single-column PK) for a table
-- that is meant to hold one row per (alpha, date) daily-return observation.
-- A single-column PK on alpha_id would make it impossible to store more than
-- one date per alpha, which breaks the correlation check this table exists
-- to support (07/08 docs require real correlation math against return
-- streams). Treating this as a transcription slip rather than intent, and
-- using a composite PK instead. Flagged here and in the audit report rather
-- than silently changed with no trace.
CREATE TABLE IF NOT EXISTS pool_returns (
    alpha_id     TEXT NOT NULL,      -- your BRAIN alpha id
    return_date  DATE NOT NULL,
    daily_return NUMERIC NOT NULL,
    PRIMARY KEY (alpha_id, return_date)
);

CREATE TABLE IF NOT EXISTS llm_usage (
    id           BIGSERIAL PRIMARY KEY,
    provider     TEXT NOT NULL,     -- 'gemini' | 'groq'
    key_label    TEXT NOT NULL,     -- 'key_1' | 'key_2'
    tier         TEXT NOT NULL,     -- 'reasoning' | 'mechanical'
    called_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    succeeded    BOOLEAN NOT NULL,
    error_text   TEXT
);

-- Bookkeeping table (not in 05_DATA_MODEL.md's narrative but implied by
-- 01_DEPLOYMENT_ARCHITECTURE.md's "refreshed on a sane cadence" requirement
-- for pool_returns). Kept separate/optional: repo.py works without it, this
-- just avoids a magic env var for "when did we last refresh the pool".
CREATE TABLE IF NOT EXISTS pipeline_meta (
    key          TEXT PRIMARY KEY,
    value        TEXT,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
