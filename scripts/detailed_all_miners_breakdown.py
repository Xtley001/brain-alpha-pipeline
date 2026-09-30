import os, sys
import psycopg
import dotenv

sys.stdout.reconfigure(encoding='utf-8')
dotenv.load_dotenv()
db_url = os.environ.get("DATABASE_URL")

with psycopg.connect(db_url) as conn:
    with conn.cursor() as cur:
        print("="*60)
        print("1. OPTIONS_ALPHAS TABLE (PRIMARY VAULT & RESERVE)")
        print("="*60)
        cur.execute("""
            SELECT status, count(*), avg(sharpe), avg(fitness), min(sharpe), max(sharpe)
            FROM options_alphas
            GROUP BY status
        """)
        for r in cur.fetchall():
            print(f"Status: {r[0]:<22} | Count: {r[1]:<3} | Avg Sharpe: {float(r[2] or 0):.2f} | Avg Fit: {float(r[3] or 0):.2f} | Range: [{float(r[4] or 0):.2f} - {float(r[5] or 0):.2f}]")

        print("\n" + "="*60)
        print("2. OPTIONS_EVALUATIONS BREAKDOWN BY STATUS & STAGE")
        print("="*60)
        cur.execute("""
            SELECT status, stage, count(*), avg(sharpe), avg(fitness), avg(turnover)
            FROM options_evaluations
            WHERE sharpe >= 1.25
            GROUP BY status, stage
            ORDER BY count(*) DESC
        """)
        print("Breakdown of Sharpe >= 1.25 evaluations:")
        for r in cur.fetchall():
            print(f"  Status: {str(r[0]):<20} | Stage: {str(r[1]):<30} | Count: {r[2]:<4} | Avg Sharpe: {float(r[3] or 0):.2f} | Avg Fit: {float(r[4] or 0):.2f} | Avg TO: {float(r[5] or 0)*100:.1f}%")

        print("\n" + "="*60)
        print("3. UNIQUE HIGH-PERFORMING EXPRESSIONS (Sharpe >= 1.40)")
        print("="*60)
        cur.execute("""
            SELECT alpha_id, archetype, status, stage, sharpe, fitness, turnover, returns, drawdown, expression
            FROM options_evaluations
            WHERE sharpe >= 1.40
            ORDER BY sharpe DESC
            LIMIT 15
        """)
        for r in cur.fetchall():
            print(f"AlphaID: {r[0]:<10} | Arch: {str(r[1])[:30]:<30} | Sharpe: {r[4]} | Fit: {r[5]} | TO: {float(r[6] or 0)*100:.1f}% | Ret: {float(r[7] or 0)*100:.1f}% | DD: {float(r[8] or 0)*100:.1f}%")
            print(f"   Status: {r[2]} | Stage: {r[3]}")
            print(f"   Expr: {r[9][:110]}...\n")

        print("\n" + "="*60)
        print("4. SUMMARY COUNTS ACROSS ALL 3 MINERS / VERTICALS")
        print("="*60)
        # Options evaluations
        cur.execute("SELECT count(*) FROM options_evaluations")
        opt_eval_cnt = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM options_evaluations WHERE sharpe >= 1.25")
        opt_gt_125 = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM options_evaluations WHERE sharpe >= 1.0 AND sharpe < 1.25")
        opt_10_125 = cur.fetchone()[0]

        # Candidates (Sentiment, Risk Model, Multi-miner pool)
        cur.execute("SELECT count(*) FROM candidates")
        cand_cnt = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM candidates WHERE stage0_sharpe >= 1.25")
        cand_gt_125 = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM candidates WHERE stage0_sharpe >= 1.0 AND stage0_sharpe < 1.25")
        cand_10_125 = cur.fetchone()[0]

        print(f"Options Miner Simulations Tracked: {opt_eval_cnt}")
        print(f"  - Sharpe >= 1.25: {opt_gt_125}")
        print(f"  - Sharpe 1.00 - 1.25: {opt_10_125}")
        print(f"Candidate / Cross-Vertical Pool: {cand_cnt}")
        print(f"  - Sharpe >= 1.25: {cand_gt_125}")
        print(f"  - Sharpe 1.00 - 1.25: {cand_10_125}")
        print(f"Options Vault Alphas (options_alphas): 26 (21 Submitted/Active, 4 Sub-Univ Salvageable, 1 Superseded)")
        print(f"Rejected Options Pool: {cur.execute('SELECT count(*) FROM options_rejected_alphas') or cur.fetchone()[0]}")
        print(f"Correlated Options Pool: {cur.execute('SELECT count(*) FROM options_correlated_alphas') or cur.fetchone()[0]}")
