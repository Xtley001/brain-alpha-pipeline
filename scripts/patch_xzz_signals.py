"""
Script to append the 3 XZZ interaction signals (Eq.3, Table 5, Footnote 8)
to xing_zhang_zhao_smirk.py
Run: python scripts/patch_xzz_signals.py
"""
import sys, os
sys.path.insert(0, '.')

target = r'brain_generators/options/xing_zhang_zhao_smirk.py'

new_signals = r"""
    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 6: SKEW x Low Turnover (Paper Eq.3 Interaction, Section V.B p.23)
    # "Informed traders choose options when stock market is illiquid."
    # Smirk is STRONGEST in low-turnover stocks. Paper test: SKEW x TURNOVER → negative.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for t in [30, 60]:
                for d in [10, 14]:
                    catalog.append({
                        "pillar": "XZZ_SMIRK_LOW_TURNOVER",
                        "archetype": f"XZZ_SmirkLowTurn_t{t}_d{d}_{u}_{g}",
                        "expression": (
                            f"trade_when(volume > adv20 * 0.70, "
                            f"trade_when(rank(adv20 / (market_cap + 0.001)) < 0.35, "
                            f"group_neutralize(signed_power(rank(-ts_decay_linear("
                            f"implied_volatility_put_{t} - implied_volatility_call_{t}, {d}"
                            f")), 0.5), {g.lower()}), -1), -1)"
                        ),
                        "hypothesis": (
                            f"XZZ2010 Eq(3) Section V.B: smirk strongest in low-turnover stocks. "
                            f"Illiquid stocks = informed traders prefer options = cleaner smirk signal. "
                            f"t={t}d, {u}."
                        ),
                        "universe": u, "neutralization": g, "decay": d,
                        "category": "options",
                        "source_kb": "docs/kb/options/xing_zhang_zhao_2010_smirk.md",
                    })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 7: SKEW x Earnings Gate (Section IV, Table 5, p.19-20)
    # "Firms with the steepest smirks are those with the WORST earnings shocks next quarter."
    # FM coeff on SKEW predicting SUE: -0.033 to -0.045, significant all horizons.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for t in [30, 60]:
                for d in [10, 14, 20]:
                    catalog.append({
                        "pillar": "XZZ_SMIRK_EARNINGS_GATE",
                        "archetype": f"XZZ_SmirkEarningsGate_t{t}_d{d}_{u}_{g}",
                        "expression": (
                            f"trade_when(volume > adv20 * 0.80, "
                            f"trade_when(rank(ts_decay_linear("
                            f"implied_volatility_put_{t} - implied_volatility_call_{t}, {d}"
                            f")) > 0.65, "
                            f"group_neutralize(signed_power(rank(-ts_decay_linear("
                            f"implied_volatility_put_{t} - implied_volatility_call_{t}, {d}"
                            f")), 0.5) * rank(-ts_decay_linear(earnings_surprise, {d})), "
                            f"{g.lower()}), -1), -1)"
                        ),
                        "hypothesis": (
                            f"XZZ2010 Table5: smirk x negative_SUE = double-confirmed bad earnings. "
                            f"Paper coeff SKEW->SUE: -0.033 to -0.045. t={t}d, {u}."
                        ),
                        "universe": u, "neutralization": g, "decay": d,
                        "category": "options",
                        "source_kb": "docs/kb/options/xing_zhang_zhao_2010_smirk.md",
                    })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 8: SKEW x High Option OI (Footnote 8 Double-Sort, p.15)
    # "Long-short strategy works BETTER for firms with more option trading."
    # Gate: high OI = actively traded options = cleaner informed signal.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for t in [30, 60]:
                for d in [10, 14]:
                    catalog.append({
                        "pillar": "XZZ_SMIRK_HIGH_OI",
                        "archetype": f"XZZ_SmirkHighOI_t{t}_d{d}_{u}_{g}",
                        "expression": (
                            f"trade_when(volume > adv20 * 0.90, "
                            f"trade_when(rank(ts_decay_linear(pcr_oi_{t}, {d})) > 0.40, "
                            f"group_neutralize(signed_power(rank(-ts_decay_linear("
                            f"implied_volatility_put_{t} - implied_volatility_call_{t}, {d}"
                            f")), 0.5), {g.lower()}), -1), -1)"
                        ),
                        "hypothesis": (
                            f"XZZ2010 Fn8: double-sort confirms smirk stronger with high option OI. "
                            f"Active options = cleaner informed flow. t={t}d, {u}."
                        ),
                        "universe": u, "neutralization": g, "decay": d,
                        "category": "options",
                        "source_kb": "docs/kb/options/xing_zhang_zhao_2010_smirk.md",
                    })

    return catalog
"""

with open(target, 'r', encoding='utf-8') as f:
    content = f.read()

if 'return catalog\n' in content:
    content = content.replace('    return catalog\n', new_signals)
    with open(target, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patched successfully.")
else:
    print("ERROR: 'return catalog' not found. File contents end:")
    print(content[-200:])

# Verify
sys.path.insert(0, '.')
# Force reload
import importlib
import brain_generators.options.xing_zhang_zhao_smirk as m
importlib.reload(m)
c = m.generate_xing_zhang_zhao_smirk_candidates()
print(f"XZZ generator now produces {len(c)} candidates (was 228)")
pillars = {}
for x in c:
    pillars[x["pillar"]] = pillars.get(x["pillar"], 0) + 1
for k, v in sorted(pillars.items()):
    print(f"  {k}: {v}")
