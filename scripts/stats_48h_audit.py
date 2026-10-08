import os
import psycopg
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv("DATABASE_URL")

with psycopg.connect(db_url) as conn:
    with conn.cursor() as cur:
        print("=" * 80)
        print("48-HOUR COMPREHENSIVE PIPELINE AUDIT")
        print("=" * 80)

        # 1. options_evaluations in last 48 hours
        cur.execute("""
            SELECT 
                COUNT(*) as total_sims,
                COUNT(*) FILTER (WHERE status = 'PASS' OR status = 'QUALIFIED') as total_passed,
                COUNT(*) FILTER (WHERE status = 'FAIL') as total_failed,
                COUNT(*) FILTER (WHERE status = 'CORRELATED') as total_correlated,
                MAX(sharpe) as max_sharpe,
                AVG(sharpe) as avg_sharpe,
                MAX(fitness) as max_fitness,
                COUNT(*) FILTER (WHERE sharpe >= 1.25) as sharpe_ge_125,
                COUNT(*) FILTER (WHERE sharpe >= 1.00 AND sharpe < 1.25) as sharpe_100_124
            FROM options_evaluations
            WHERE created_at >= NOW() - INTERVAL '48 hours';
        """)
        row = cur.fetchone()
        print("\n1. EVALUATIONS SUMMARY (Last 48 Hours):")
        print(f"  • Total Simulations: {row[0]}")
        print(f"  • Total Passed (Stage 0): {row[1]}")
        print(f"  • Total Failed: {row[2]}")
        print(f"  • Total Correlated: {row[3]}")
        print(f"  • Max Sharpe: {row[4]}")
        print(f"  • Avg Sharpe: {row[5]:.3f}" if row[5] else "  • Avg Sharpe: N/A")
        print(f"  • Max Fitness: {row[6]}")
        print(f"  • Candidates with Sharpe >= 1.25: {row[7]}")
        print(f"  • Candidates with Sharpe in [1.00, 1.24]: {row[8]}")

        # Breakdown by source/archetype
        cur.execute("""
            SELECT source, status, COUNT(*), MAX(sharpe), MAX(fitness)
            FROM options_evaluations
            WHERE created_at >= NOW() - INTERVAL '48 hours'
            GROUP BY source, status
            ORDER BY source, status;
        """)
        print("\n2. EVALUATIONS BY SOURCE & STATUS (Last 48 Hours):")
        for r in cur.fetchall():
            print(f"  • Source: {r[0] or 'general':<18} | Status: {r[1]:<12} | Count: {r[2]:<5} | Max Sharpe: {r[3]} | Max Fit: {r[4]}")

        # Top 10 highest Sharpe evaluations in last 48h
        cur.execute("""
            SELECT alpha_id, archetype, source, stage, status, sharpe, fitness, turnover, returns, drawdown, created_at, expression
            FROM options_evaluations
            WHERE created_at >= NOW() - INTERVAL '48 hours'
            ORDER BY sharpe DESC NULLS LAST
            LIMIT 10;
        """)
        top_evals = cur.fetchall()
        print("\n3. TOP 10 EVALUATED CANDIDATES (Last 48 Hours):")
        for t in top_evals:
            print(f"  • ID: {t[0] or 'N/A':<10} | Sh: {t[5]} | Fit: {t[6]} | TO: {float(t[7])*100 if t[7] else 0:.1f}% | Arch: {t[1]} | Status: {t[4]} | Created: {t[10]}")

        # 4. options_alphas (Qualified and Submitted pool)
        cur.execute("""
            SELECT id, alpha_id, archetype, strategy_name, sharpe, fitness, turnover, margin, max_correlation, status, created_at, submitted_at
            FROM options_alphas
            ORDER BY id DESC;
        """)
        alphas = cur.fetchall()
        print(f"\n4. ALL OPTIONS_ALPHAS TABLE (Total: {len(alphas)} rows):")
        qualified_pool = [a for a in alphas if a[9] == 'QUALIFIED']
        submitted_pool = [a for a in alphas if a[9] == 'SUBMITTED']
        rejected_pool = [a for a in alphas if a[9] not in ('QUALIFIED', 'SUBMITTED')]
        print(f"  • Status='QUALIFIED' (Ready to Submit / Reserve): {len(qualified_pool)}")
        print(f"  • Status='SUBMITTED' (Live on BRAIN): {len(submitted_pool)}")
        print(f"  • Status=Other ({set(a[9] for a in rejected_pool)}): {len(rejected_pool)}")

        if qualified_pool:
            print("\n  >>> QUALIFIED RESERVE POOL DETAILS:")
            for q in qualified_pool:
                print(f"    - Alpha ID: {q[1]} | Arch: {q[2]} | Strat: {q[3]} | Sharpe: {q[4]} | Fitness: {q[5]} | TO: {float(q[6])*100 if q[6] else 0:.1f}% | Margin: {float(q[7])*10000 if q[7] else 0:.1f}bps | MaxCorr: {q[8]} | Created: {q[10]}")

        # Last 5 submitted
        print("\n  >>> LAST 5 SUBMITTED ALPHAS:")
        for s in submitted_pool[:5]:
            print(f"    - Alpha ID: {s[1]} | Arch: {s[2]} | Sharpe: {s[4]} | Fitness: {s[5]} | Submitted: {s[11] or s[10]}")

        # 5. options_correlated_alphas in last 48h
        cur.execute("""
            SELECT alpha_id, archetype, sharpe, fitness, max_correlation, corr_partner_alpha_id, rejection_reason, created_at
            FROM options_correlated_alphas
            WHERE created_at >= NOW() - INTERVAL '48 hours'
            ORDER BY id DESC
            LIMIT 10;
        """)
        corrs = cur.fetchall()
        print(f"\n5. CORRELATED / REJECTED CANDIDATES (Last 48 Hours: {len(corrs)} shown):")
        for c in corrs:
            print(f"  • ID: {c[0]} | Arch: {c[1]} | Sharpe: {c[2]} | Fitness: {c[3]} | Corr: {c[4]} vs {c[5]} | Reason: {c[6]}")
