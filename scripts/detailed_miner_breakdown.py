import os
import psycopg
import dotenv

dotenv.load_dotenv()
db_url = os.environ.get("DATABASE_URL")

with psycopg.connect(db_url) as conn:
    with conn.cursor() as cur:
        print("="*60)
        print("1. OPTIONS_ALPHAS (RESERVE & ACTIVE VAULT)")
        print("="*60)
        cur.execute("""
            SELECT status, count(*), avg(sharpe), avg(fitness), min(sharpe), max(sharpe)
            FROM options_alphas
            GROUP BY status
        """)
        for r in cur.fetchall():
            print(f"Status: {r[0]:<20} | Count: {r[1]:<3} | Avg Sharpe: {float(r[2] or 0):.2f} | Avg Fit: {float(r[3] or 0):.2f} | Sharpe Range: [{float(r[4] or 0):.2f} - {float(r[5] or 0):.2f}]")

        cur.execute("""
            SELECT alpha_id, archetype, sharpe, fitness, turnover, margin, max_correlation, status
            FROM options_alphas
            ORDER BY sharpe DESC NULLS LAST
        """)
        rows = cur.fetchall()
        print(f"\nTotal in options_alphas: {len(rows)}")
        for r in rows:
            print(f"  [{r[7]}] ID: {r[0]:<10} | Archetype: {r[1]:<45} | Sharpe: {r[2]} | Fit: {r[3]} | TO: {float(r[4] or 0)*100:.1f}% | Corr: {r[6]}")

        print("\n" + "="*60)
        print("2. CANDIDATES TABLE BREAKDOWN (BY ARCHETYPE / VERTICAL)")
        print("="*60)
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='candidates'")
        cand_cols = [r[0] for r in cur.fetchall()]
        print("Candidates columns:", cand_cols)

        cur.execute("SELECT count(*) FROM candidates")
        print(f"Total rows in candidates table: {cur.fetchone()[0]}")

        # Group by archetype or family
        if 'archetype' in cand_cols:
            cur.execute("""
                SELECT archetype, count(*), 
                       count(CASE WHEN sharpe >= 1.25 THEN 1 END) as sharpe_gt_125,
                       count(CASE WHEN sharpe >= 1.0 AND sharpe < 1.25 THEN 1 END) as sharpe_10_125,
                       count(CASE WHEN sharpe >= 0.8 AND sharpe < 1.0 THEN 1 END) as sharpe_08_10,
                       avg(sharpe)
                FROM candidates
                GROUP BY archetype
                ORDER BY count(*) DESC
                LIMIT 20
            """)
            print("\nCandidates top archetypes:")
            for r in cur.fetchall():
                print(f"  - {r[0][:35]:<35}: Total={r[1]:<4} | Sharpe>=1.25: {r[2]:<3} | Sharpe 1.0-1.25: {r[3]:<3} | Avg Sharpe: {float(r[5] or 0):.2f}")

        print("\n" + "="*60)
        print("3. SALVAGEABLE ALPHAS IN CANDIDATES (Sharpe >= 1.10)")
        print("="*60)
        cur.execute("""
            SELECT alpha_id, archetype, sharpe, fitness, turnover, stage, status, expression
            FROM candidates
            WHERE sharpe >= 1.10
            ORDER BY sharpe DESC
            LIMIT 25
        """)
        salvageable_cand = cur.fetchall()
        print(f"Total candidates with Sharpe >= 1.10: {len(salvageable_cand)}")
        for r in salvageable_cand:
            print(f"  AlphaID: {r[0]:<10} | Arch: {r[1][:30]:<30} | Sharpe: {r[2]:<5} | Fit: {r[3]:<5} | TO: {float(r[4] or 0)*100:.1f}% | Stage: {r[5]} | Status: {r[6]}")

        print("\n" + "="*60)
        print("4. OPTIONS EVALUATIONS TABLE (HIGH SHARPE NEAR-MISSES)")
        print("="*60)
        cur.execute("SELECT count(*) FROM options_evaluations")
        print(f"Total options_evaluations: {cur.fetchone()[0]}")
        cur.execute("SELECT count(*) FROM options_evaluations WHERE sharpe >= 1.25")
        print(f"Options evaluations with Sharpe >= 1.25: {cur.fetchone()[0]}")
        cur.execute("SELECT count(*) FROM options_evaluations WHERE sharpe >= 1.00 AND sharpe < 1.25")
        print(f"Options evaluations with Sharpe 1.00 - 1.25: {cur.fetchone()[0]}")

        print("\n" + "="*60)
        print("5. REJECTED & CORRELATED POOLS")
        print("="*60)
        cur.execute("SELECT count(*) FROM options_rejected_alphas")
        print(f"Total options_rejected_alphas: {cur.fetchone()[0]}")
        cur.execute("SELECT count(*) FROM options_correlated_alphas")
        print(f"Total options_correlated_alphas: {cur.fetchone()[0]}")
