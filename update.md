# System Architecture Update: Closed-Loop Reinforcement Learning & Diagnostic Alpha Optimizer

## 1. Executive Summary & Why Reinforcement Learning?

The primary objective of the WorldQuant BRAIN Options Alpha Pipeline is to autonomously generate, optimize, and qualify valid options alphas into the platform at scale.

Previously, the pipeline operated in an **open-loop, blind search** mode:
1. Candidates were generated either from static templates or static LLM prompts without visibility into prior outcomes.
2. When a candidate passed Stage 0 (e.g., achieving Sharpe 1.83), the system performed a static 25-simulation parameter sweep of the exact same un-smoothed formula.
3. If it failed the local filter (e.g., Fitness 0.84 < 1.00 due to 52% turnover), it gave up immediately with zero diagnostic feedback.
4. Concurrently, 25 simulations with concurrency 3 took ~16 minutes, causing GitHub Actions to hit job timeouts and terminate 9 passing candidates mid-flight.

This update transforms the pipeline into a **Closed-Loop Reinforcement Learning (RL) & Diagnostic Optimizer**:
- **Diagnosis-driven remediation**: The system diagnoses the exact checklist deficit (e.g. "Fitness below 1.0 due to high turnover") and mathematically applies targeted remedies.
- **Symbolic Policy Evolution**: High-performing alphas serve as parents for structured mutation and crossover.
- **Multi-Armed Bandit (MAB) Archetype Allocation**: Sampling probabilities dynamically track the real-world pass rate of options archetypes (e.g., shifting resources away from failing PCR reversals and doubling down on Call Breakeven and Vol Skew shocks).
- **In-Context LLM Policy Memory**: Groq / OpenRouter reasoning prompts are conditioned on the top-performing alpha formulas from the PostgreSQL database.

---

## 2. Why Language-Model-Guided Evolutionary RL (And Why NOT PPO/DQN)?

### The Failure of Deep RL (PPO/DQN) in This Domain:
Traditional Deep RL (such as Proximal Policy Optimization or Deep Q-Networks training neural network weights on daily asset returns) fails in the WorldQuant BRAIN environment because:
1. **Sample Inefficiency**: Deep RL requires $10^6$ to $10^8$ interaction steps to converge. WorldQuant BRAIN rate limits simulations to 3 concurrent slots, each taking 30–45 seconds. Running $100,000$ simulations would take months and result in account bans.
2. **Action Space Mismatch**: Alphas on BRAIN are **closed-form symbolic domain-specific language expressions** (`FASTEXPR`). Neural networks output continuous weight vectors or unconstrained token sequences that frequently violate grammar, invent nonexistent variables, or fail platform syntax parsers.
3. **No Financial Economics Grounding**: Pure gradient ascent on reward has no knowledge of derivative pricing theorems (e.g. Sinclair's $\sqrt{T}$ skew scaling, Leland's transaction drag, or zero-delta straddle strikes).

### The Chosen Solution: Language-Model-Guided Evolutionary RL with Diagnostic Policy Updates
Instead, we implement **Symbolic Policy Optimization with Diagnostic Credit Assignment**:
- **Environment**: WorldQuant BRAIN Simulation Engine (Equities USA, `TOP3000`, `delay=1`).
- **State Space ($S$)**: The candidate expression $E$, its simulation vector $\mathbf{M} = (\text{Sharpe}, \text{Fitness}, \text{Turnover}, \text{Returns}, \text{Drawdown}, \text{Margin})$, and its structural archetype $A$.
- **Action Space ($A$)**: A finite set of mathematically grounded symbolic transformation operators:
  1. $\mathcal{O}_{\text{smooth}}$: Expression-level smoothing (`ts_decay_linear(E, w)`, `ts_mean(E, w)`) $\rightarrow$ targets Turnover reduction and Fitness enhancement.
  2. $\mathcal{O}_{\text{window}}$: Time-series window expansion ($w \rightarrow w + 5$) $\rightarrow$ dampens signal velocity.
  3. $\mathcal{O}_{\text{tenor}}$: Tenor migration ($T \in \{10, 20, 30, 60, 90\}$) $\rightarrow$ aligns with derivative term structure.
  4. $\mathcal{O}_{\text{neut}}$: Neutralization refinement (`sector` $\rightarrow$ `subindustry`) $\rightarrow$ eliminates uncompensated industry risk.
  5. $\mathcal{O}_{\text{gate}}$: Liquidity/regime conditioning (`trade_when(volume > adv20, E, -1)`) $\rightarrow$ protects against illiquid Leland drag.
  6. $\mathcal{O}_{\text{mutate}}$: LLM-guided economic mutation conditioned on Master Knowledge Base cards.
- **Reward Function ($R$)**:
  $$R(\mathbf{M}) = w_1 \cdot \text{Sharpe} + w_2 \cdot \min(\text{Fitness}, 2.0) - w_3 \cdot \max(0, \text{Turnover} - 0.70) - w_4 \cdot \max(0, 0.01 - \text{Turnover}) + \mathbb{I}_{\text{QUALIFIED}} \cdot 5.0$$
- **Policy Adaptation**:
  1. **Bandit Level**: An Upper Confidence Bound (UCB1) algorithm tracks the reward distribution across the 5 core options archetypes. Archetypes generating high Sharpe/Fitness receive exponentially higher generation share.
  2. **In-Context Level**: The top-$K$ highest-reward expressions from PostgreSQL are retrieved and embedded dynamically into the LLM system prompt as few-shot positive exemplars, alongside explicit negative constraints derived from low-reward failures.
  3. **Local Trajectory Level (The Diagnostic Optimizer)**: When an alpha passes Stage 0, the policy executes an iterative diagnostic trajectory ($t_1, t_2, \dots, t_K$) directly repairing the failing metrics.

---

## 3. The Diagnostic Optimizer ("The Doctor / Healer" Pipeline)

When a candidate clears Stage 0, rather than running a blind grid, it enters the **Diagnostic Optimizer**:

### Step 1: Automated Checklist Diagnosis
The engine inspects the simulation metrics against the BRAIN qualification criteria:
- **Case 1 (Turnover Trap / Low Fitness)**: `Sharpe >= 1.25`, but `Fitness < 1.00` and `Turnover > 30%`.
  - *Diagnosis*: Signal is predictive but overly volatile, causing excessive turnover that depresses the denominator $\sqrt{\text{Turnover}}$ in the fitness formula.
  - *Action*: Apply $\mathcal{O}_{\text{smooth}}$ (`ts_decay_linear(expr, 5)` or `ts_decay_linear(expr, 10)`) and test simulation decay $\in [12, 16, 20]$.
- **Case 2 (Borderline Sharpe)**: `1.00 <= Sharpe < 1.25`.
  - *Diagnosis*: Underlying pricing anomaly exists but is diluted by group factor noise or illiquid tail names.
  - *Action*: Escalate neutralization to `SUBINDUSTRY` and inject volume gating `trade_when(volume > adv20, expr, -1)`.
- **Case 3 (Tenor Misalignment)**: `Sharpe < 1.00` on a short tenor (e.g., 10d).
  - *Diagnosis*: Option prices at 10d are dominated by settlement convention noise and microstructure bid-ask bounce (Master Book 4, Ch. 2).
  - *Action*: Shift tenor to 20d or 30d, applying $\sqrt{T}$ normalization according to Sinclair/Derman rules.

### Step 2: Adaptive Iteration Budget
- Promising candidates (Sharpe $\ge 1.00$) are allocated an **optimization budget of up to 6–8 targeted simulations**.
- Candidates that fail to improve after 2 successive iterations are early-stopped, preserving quota and execution time.
- Total optimization time per candidate: **2 to 3 minutes**, eliminating GitHub Actions container timeouts completely.

---

## 4. PostgreSQL Database Schema Enhancements

To persist the learning memory across stateless GitHub Actions workflow runs, we add a dedicated learning memory table in Neon PostgreSQL:

```sql
CREATE TABLE IF NOT EXISTS options_learning_memory (
    id SERIAL PRIMARY KEY,
    expression TEXT NOT NULL UNIQUE,
    archetype VARCHAR(128) NOT NULL,
    sharpe NUMERIC(8, 4),
    fitness NUMERIC(8, 4),
    turnover NUMERIC(8, 4),
    annualized_return NUMERIC(8, 4),
    reward NUMERIC(10, 4),
    optimization_steps INTEGER DEFAULT 0,
    parent_expression TEXT,
    mutation_type VARCHAR(64),
    status VARCHAR(32),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_options_learning_reward ON options_learning_memory(reward DESC);
CREATE INDEX IF NOT EXISTS idx_options_learning_archetype ON options_learning_memory(archetype);
```

### Table Roles:
1. `options_evaluations`: Comprehensive audit log of every simulation ever executed.
2. `options_learning_memory`: The active "brain" repository of top performers, mutations, and calculated RL rewards used to condition future prompts and mutations.
3. `options_alphas`: Officially qualified and accepted alphas meeting all BRAIN criteria.

---

## 5. Knowledge Base (Books 1–4) Direct Formula Integration

The update directly injects key formulas from `options-kb-master-books1-4.md`:
1. **Sqrt-T Normalization (Books 2 & 3)**:
   Every skew candidate must normalize cross-tenor skew by $\sqrt{T / 252.0}$ before cross-sectional ranking.
2. **Optimal Mean-Reversion Entry Gate (Sinclair, Book 1, Ch. 6)**:
   Spread-fading alphas are conditioned on `trade_when(abs(ts_zscore(spread, window)) > 0.75, ..., -1)`.
3. **Leland Drag Protection (Derman, Book 3, Ch. 7 & Sinclair, Book 1, Ch. 4)**:
   Signals with turnover $> 50\%$ without expression smoothing are rejected prior to simulation to eliminate transaction drag false positives.
4. **Call Breakeven Hurdle Repricing (Book 4, Natenberg & Book 2)**:
   Accelerating the highest-performing empirical family: `(call_breakeven_{tenor} - close) / close` with linear decay smoothing.

---

## 6. GitHub Actions Workflow Calibration

In `.github/workflows/run.yml`:
- Update `timeout-minutes: 30` to provide sufficient headroom for multi-step diagnostic iterations.
- Configure `RUN_TIME_BUDGET_SECONDS: 600` (10 minutes of active simulation per cron run).
- Set batch size to 10 candidates with targeted optimization on Stage 0 passers.
- Ensure candidate history and database sync are committed reliably.
