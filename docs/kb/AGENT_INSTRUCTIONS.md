# 🧠 AGENT OPERATING INSTRUCTIONS — Brain Alpha Pipeline
## For: Gemini / Any Future AI Agent
## Purpose: Self-operating guide to continue building this pipeline without prior context

---

## WHAT THIS PIPELINE DOES
This is a **WorldQuant BRAIN alpha mining pipeline**. It:
1. Generates alpha expressions (mathematical trading signals) from academic research papers
2. Submits those signals to the WorldQuant BRAIN API for simulation
3. Stores qualified alphas (Sharpe > threshold) in a PostgreSQL database
4. Never auto-submits to WorldQuant — all alphas need manual human review first

**Target:** 500+ qualified alphas across 5 research pillars.

---

## CRITICAL RULES — READ BEFORE DOING ANYTHING
1. **NEVER auto-submit alphas to WorldQuant BRAIN.** Store in DB only.
2. **ONE paper = ONE generator file.** Never merge knowledge across files.
3. **All generator signals must cite their paper, table, equation number.**
4. **All expressions must include a `source_kb` field** pointing to the KB markdown file.
5. **Deep extraction standard: 20-50 archetypes per paper.** Not 5. Not 10. 20-50.
6. **Always read the actual `docs/kb/extracted_text/<paper>.txt` before writing anything.**
7. **The miner runs on 4 parallel slots.** Never increase this — BRAIN API limit.
8. **Check `docs/kb/EXTRACTION_STATUS.md` to know what's done and what's next.**

---

## DIRECTORY STRUCTURE

```
brain-alpha-pipeline/
├── brain_generators/           ← Alpha expression generators (one file per paper)
│   ├── options/                ← Options pillar generators
│   ├── sentiment/              ← Sentiment/analyst pillar generators
│   ├── risk_models/            ← Risk model pillar generators
│   ├── short_interest/         ← Short interest pillar generators
│   ├── fundamental/            ← Fundamental/quality pillar generators
│   └── supply_chain/           ← Supply chain pillar generators
├── docs/kb/
│   ├── extracted_text/         ← RAW PDF TEXT (89 files) — READ THESE FIRST
│   ├── options/                ← Options KB markdown files
│   ├── sentiment/              ← Sentiment KB markdown files
│   ├── risk_models/            ← Risk model KB markdown files
│   ├── short_interest/         ← Short interest KB markdown files
│   ├── fundamental/            ← Fundamental KB markdown files
│   ├── supply_chain/           ← Supply chain KB markdown files
│   ├── frameworks/             ← Books/framework KB files
│   ├── kb_index.md             ← Master index of all papers
│   ├── AGENT_INSTRUCTIONS.md   ← THIS FILE
│   └── EXTRACTION_STATUS.md    ← Tracks which papers are done
├── scripts/
│   ├── master_quintuple_vault_miner_500.py  ← MAIN MINER — run this
│   ├── fast_qualify_evaluated_alphas.py     ← Qualification checker
│   └── hourly_report.py                     ← Status reporter
├── brain_options/              ← BRAIN API client (do not modify)
├── .env                        ← Credentials (BRAIN_USERNAME, BRAIN_PASSWORD, etc.)
└── requirements.txt
```

---

## HOW TO DEEP-READ A PAPER AND BUILD ITS KB

### Step 1: Read the extracted text
```python
# Always do this FIRST
paper_text = open('docs/kb/extracted_text/<PAPER_NAME>.txt', 'r').read()
```

### Step 2: Extract these 20 things from every paper
For each paper, find and document:
1. **Abstract** — exact quote, paste verbatim
2. **Research question** — what they set out to prove
3. **All equations** — numbered as in paper (Eq. 1, Eq. 2...)
4. **Core formula** — the main signal construction
5. **Table 1 results** — summary statistics (sample, universe, time period)
6. **Main table results** — portfolio sorts, t-stats, alphas
7. **FM regression coefficients** — the exact numbers with t-stats
8. **Holding period** — how long signal persists (weeks? months?)
9. **Sample period** — what dates were tested
10. **Universe** — what stocks (large-cap? all? options-listed only?)
11. **Control variables** — what they controlled for (FF3? FF5? momentum?)
12. **Mechanism** — WHY the signal works (not just WHAT it does)
13. **Subgroup results** — where it works best (small vs large, etc.)
14. **Robustness checks** — alternative constructions tested
15. **Failure conditions** — when the signal breaks or reverses
16. **Interaction effects** — what amplifies or dampens the signal
17. **Data requirements** — exact field names the paper uses
18. **BRAIN field mapping** — paper field → BRAIN operator equivalent
19. **Cross-paper synergies** — what other signals combine well
20. **Open questions** — what the paper explicitly leaves unanswered

### Step 3: Write the KB file
Create `docs/kb/<pillar>/<paper_shortname>.md` with all 20 extracts.
If paper covers multiple pillars, create it in EACH relevant pillar folder with a note.

### Step 4: Write/expand the generator
Create or expand `brain_generators/<pillar>/<paper_shortname>.py` with:
- 20-50 archetypes per paper
- Every archetype citing the specific extract (equation number, table, footnote)
- The `source_kb` field on every candidate dict
- Parameter grid: 4 universes × 3 neutralizations × 4 decays = 48 base archetypes
  then × signal variants = 96-200+ archetypes per paper

### Step 5: Wire into miner
Add the generator import and merge in `scripts/master_quintuple_vault_miner_500.py`

### Step 6: Update tracking
Update `docs/kb/EXTRACTION_STATUS.md` — mark paper as DONE.

---

## HOW TO RUN THE MINER
```bash
# From project root:
python scripts/master_quintuple_vault_miner_500.py
```

The miner:
- Authenticates with BRAIN API (credentials in .env)
- Builds the full vault matrix (2,800+ candidates)
- Runs 4 parallel simulation workers
- Stores qualified alphas in PostgreSQL
- Logs progress to console

**Monitor with:**
```bash
# Check qualified alpha count:
python -c "
from brain_options.store import OptionsStore
s = OptionsStore()
print(s.db.execute('SELECT COUNT(*) FROM alpha_results WHERE is_qualified=true').fetchone())
"
```

---

## HOW BRAIN EXPRESSIONS WORK

### Core operators available:
```
rank(x)              ← cross-sectional rank, 0 to 1
ts_decay_linear(x,d) ← time-series linear decay over d days
ts_delta(x, n)       ← x_today - x_{n days ago}
ts_mean(x, n)        ← rolling mean over n days
ts_std_dev(x, n)     ← rolling std dev over n days
ts_sum(x, n)         ← rolling sum over n days
ts_rank(x, n)        ← time-series rank (percentile over past n days)
ts_delay(x, n)       ← lag x by n days
group_neutralize(x, g) ← demean within group g (subindustry/sector/market)
signed_power(x, p)   ← sign(x) * |x|^p (rank-preserving power transform)
trade_when(cond, sig, else) ← conditional signal
abs(x), log(x), sqrt(x)
```

### Core fields available (BRAIN dataset fields):
```
# Price/Volume
returns, close, volume, adv20, market_cap

# Options (options dataset — requires options=True in sim config)
implied_volatility_call_{30,60,90,180}
implied_volatility_put_{30,60,90,180}
implied_volatility_mean_{30,60,90,180}
pcr_vol_{30,60,90,180}    ← put/call ratio by volume
pcr_oi_{30,60,90,180}     ← put/call ratio by open interest

# Risk models (model dataset)
beta_last_{60,90,252}_days_spy
idiosyncratic_vol_last_{60,90}_days_spy

# Analyst (analyst dataset)
earnings_surprise
analyst_rating_change
analyst_count
analyst_estimate_dispersion

# Short Interest
short_interest_ratio
institutional_ownership_percentage

# Fundamentals
gross_profit, assets, sales, net_income, debt_to_equity_ratio
capital_expenditure, r_and_d_expense, current_ratio
operating_cash_flow, earnings_before_tax

# Insider
insider_buy_transactions, insider_sell_transactions
```

### Standard archetype template:
```python
{
    "pillar": "PAPER_SIGNAL_NAME",
    "archetype": f"UniqueArchetypeName_params",
    "expression": "BRAIN_expression_string",
    "hypothesis": "Economic rationale citing paper section/table/equation",
    "universe": "TOPSP500",           # TOPSP500|TOP500|TOP1000|TOP3000
    "neutralization": "SUBINDUSTRY",  # SUBINDUSTRY|SECTOR|MARKET
    "decay": 10,                      # 5|10|14|20|30|60
    "category": "options",            # options|analyst|model|short_interest|fundamental
    "source_kb": "docs/kb/options/paper_name.md",  # REQUIRED
}
```

### Universe guidelines (from XZZ 2010 extract — large-cap bias matters):
- Options signals: use `TOPSP500` or `TOP500` (options only listed on large caps)
- Fundamental signals: use `TOP1000` or `TOP3000`
- Short interest: `TOP500` or `TOP1000`
- Risk models: all universes

---

## PAPER PRIORITY ORDER FOR DEEP EXTRACTION

### TIER 1 — Has generator, needs deep KB (do these first):
| # | Paper | Generator | KB Status |
|---|---|---|---|
| 1 | XZZ 2010 Smirk | ✅ 284 candidates | ✅ 15 extracts |
| 2 | Frazzini-Pedersen 2014 BAB | ✅ 144 candidates | ⚠️ shallow |
| 3 | Bernard-Thomas 1990 PEAD | ✅ 94 candidates | ⚠️ shallow |
| 4 | Ang-Hodrick-Xing-Zhang 2006 | ✅ 112 candidates | ⚠️ shallow |
| 5 | Pan-Poteshman 2006 PCR | ✅ 348 candidates | ⚠️ shallow |
| 6 | Carr-Wu 2009 VRP | ✅ 336 candidates | ❌ none |
| 7 | Gleason-Lee 2002 Revisions | ✅ 224 candidates | ❌ none |
| 8 | Cohen-Diether-Malloy 2007 | ✅ 180 candidates | ⚠️ shallow |
| 9 | Novy-Marx 2013 GPA | ✅ 152 candidates | ⚠️ shallow |
| 10 | Kakushadze 101 Alphas | ✅ 101 candidates | ❌ none |
| 11 | Menzly-Ozbas 2010 Supply Chain | ✅ 52 candidates | ❌ none |
| 12 | Bakshi-Kapadia-Madan 2003 | referenced | ❌ none |
| 13 | Garleanu-Pedersen-Poteshman 2009 | referenced | ❌ none |

### TIER 2 — No generator yet, high signal value:
| # | Paper | Category | Priority |
|---|---|---|---|
| 14 | Chan-Jegadeesh-Lakonishok 1996 | Sentiment | HIGH |
| 15 | Diether-Malloy-Scherbina 2002 | Sentiment | HIGH |
| 16 | Cooper-Gulen-Schill 2008 | Fundamental | HIGH |
| 17 | Piotroski 2000 F-Score | Fundamental | HIGH |
| 18 | Lakonishok-Lee 2001 Insider NPR | Short Interest | HIGH |
| 19 | Chen-Hong-Stein 2002 Breadth | Short Interest | HIGH |
| 20 | Hirshleifer-Hsu-Li 2013 Innovation | Fundamental | HIGH |
| 21 | Lee-Swaminathan 2000 Vol-Mom | Fundamental | HIGH |
| 22 | Sias-Starks-Titman 2006 Inst.Own | Fundamental | HIGH |
| 23 | Tetlock 2007 Media | Sentiment | MEDIUM |
| 24 | Da-Engelberg-Gao 2011 Attention | Sentiment | MEDIUM |
| 25 | Barrot-Sauvagnat 2016 Supply Chain | Supply Chain | MEDIUM |

### TIER 3 — Books (dense formulas, many signals per book):
| # | Book | Category | Priority |
|---|---|---|---|
| 26 | Natenberg — Option Vol & Pricing | Options | HIGH |
| 27 | Sinclair — Volatility Trading | Options | HIGH |
| 28 | Sinclair — Positional Option Trading | Options | MEDIUM |
| 29 | Grinold-Kahn — Active Portfolio Mgmt | Fundamental | HIGH |
| 30 | Lopez de Prado — AFML | Frameworks | HIGH |
| 31 | Tulchinsky — Finding Alphas | Frameworks | HIGH |
| 32 | Fabozzi — Quantitative Equity Investing | Fundamental | MEDIUM |
| 33 | Derman-Miller — Volatility Smile | Options | MEDIUM |
| 34 | Bennett — Trading Volatility | Options | MEDIUM |
| 35 | Staley — Art of Short Selling | Short Interest | MEDIUM |

### TIER 4 — AI/RL papers (framework signals):
| # | Paper | Category |
|---|---|---|
| 36 | Guo-Huang-Gao 2026 AQuA | Frameworks |
| 37 | Han-Zhang-Li 2026 QuantaAlpha | Frameworks |
| 38 | Tang-Yin-Chen 2026 AlphaAgentEvo | Frameworks |
| 39 | Xiao-Sun-Chen 2025 Trading-R1 | Frameworks |
| 40 | Yu-Zheng-Pan 2026 AlphaMemo | Frameworks |

---

## HOW TO VERIFY EVERYTHING IS WORKING

```bash
# 1. Check total candidate count
python -c "
import sys; sys.path.insert(0, '.')
from scripts.master_quintuple_vault_miner_500 import build_quintuple_vault_matrix
v = build_quintuple_vault_matrix()
print(f'Total candidates: {len(v)}')
"

# 2. Check DB qualified alpha count  
python scripts/fast_qualify_evaluated_alphas.py

# 3. Run full vault miner
python scripts/master_quintuple_vault_miner_500.py

# 4. Check git status
git log --oneline -5
git status --short
```

---

## SELF-OPERATING LOOP (for autonomous Gemini sessions)

When starting a new session, do this in order:
1. Read `docs/kb/EXTRACTION_STATUS.md` — find first PENDING paper
2. Read `docs/kb/extracted_text/<paper>.txt` — deep extract all 20 items
3. Write `docs/kb/<pillar>/<paper>.md` — rich KB with 20-50 extracts
4. Write/expand `brain_generators/<pillar>/<paper>.py` — 20-50 archetypes
5. Update miner imports and vault builder
6. Update `EXTRACTION_STATUS.md` — mark DONE
7. `git add -A; git commit -m "..."` with detailed message
8. `git push origin main`
9. Repeat for next PENDING paper
10. After every 5 papers, launch miner for a test run

**STOP CONDITION:** All papers show DONE in EXTRACTION_STATUS.md AND total candidates > 5,000 AND miner has logged 500+ qualified alphas.
