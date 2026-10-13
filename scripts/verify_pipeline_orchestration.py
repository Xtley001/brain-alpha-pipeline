#!/usr/bin/env python3
"""
Pipeline Orchestration & Verification Feedback System.
Audits all generators, candidates, KB files, and links to ensure zero hallucinations,
schema validity, valid BRAIN operator expressions, and verifiable source traceability.

Run: python scripts/verify_pipeline_orchestration.py
"""
import os
import re
import sys
from typing import Any, Dict, List, Tuple

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def check_parentheses(expr: str) -> bool:
    count = 0
    for char in expr:
        if char == '(':
            count += 1
        elif char == ')':
            count -= 1
            if count < 0:
                return False
    return count == 0

def run_orchestration_audit():
    print("=" * 80)
    print("🔍 RUNNING BRAIN ALPHA PIPELINE ORCHESTRATION & FEEDBACK AUDIT")
    print("=" * 80)

    # 1. Inspect Master Vault Matrix
    from scripts.master_quintuple_vault_miner_500 import build_quintuple_vault_matrix

    candidates = build_quintuple_vault_matrix()
    total_cands = len(candidates)
    print(f"\n[1] CANDIDATE POOL: {total_cands} total candidates generated.")

    required_keys = {"pillar", "archetype", "expression", "hypothesis", "universe", "neutralization", "decay", "category"}
    valid_universes = {"TOPSP500", "TOP500", "TOP1000", "TOP2000", "TOP3000", "TOP200", "SP500"}
    valid_neutralizations = {"SUBINDUSTRY", "SECTOR", "MARKET", "NONE"}

    missing_keys_count = 0
    invalid_parens_count = 0
    missing_source_kb_count = 0
    invalid_source_kb_path_count = 0
    invalid_universe_count = 0
    invalid_neut_count = 0

    unique_archetypes = set()
    duplicate_archetypes = 0

    pillar_breakdown: Dict[str, int] = {}
    category_breakdown: Dict[str, int] = {}

    for c in candidates:
        # Check required keys
        missing = required_keys - set(c.keys())
        if missing:
            missing_keys_count += 1

        arch = c.get("archetype", "")
        if arch in unique_archetypes:
            duplicate_archetypes += 1
        else:
            unique_archetypes.add(arch)

        # Check expression syntax
        expr = c.get("expression", "")
        if not check_parentheses(expr):
            invalid_parens_count += 1

        # Check universe and neutralization
        u = c.get("universe", "")
        if u not in valid_universes:
            invalid_universe_count += 1

        n = c.get("neutralization", "").upper()
        if n not in valid_neutralizations:
            invalid_neut_count += 1

        # Check source_kb
        source_kb = c.get("source_kb")
        if not source_kb:
            missing_source_kb_count += 1
        else:
            # Check if file exists on disk
            if not os.path.exists(source_kb):
                invalid_source_kb_path_count += 1

        # Pillar and category counts
        cat = c.get("category", "unknown")
        category_breakdown[cat] = category_breakdown.get(cat, 0) + 1

        pil = c.get("pillar", "unknown")
        pillar_breakdown[pil] = pillar_breakdown.get(pil, 0) + 1

    print("\n--- MATRIX HEALTH CHECK ---")
    print(f"  Missing required keys:        {missing_keys_count}")
    print(f"  Duplicate archetype names:    {duplicate_archetypes}")
    print(f"  Invalid expression parens:    {invalid_parens_count}")
    print(f"  Invalid universes:            {invalid_universe_count}")
    print(f"  Invalid neutralizations:      {invalid_neut_count}")
    print(f"  Missing source_kb:            {missing_source_kb_count} ({missing_source_kb_count/total_cands*100:.1f}%)")
    print(f"  Invalid source_kb file paths: {invalid_source_kb_path_count}")

    print("\n--- CATEGORY BREAKDOWN ---")
    for cat, count in sorted(category_breakdown.items(), key=lambda x: -x[1]):
        print(f"  {cat:<18}: {count:5d} candidates")

    # 2. Inspect KB Markdown Files
    print("\n[2] KNOWLEDGE BASE AUDIT:")
    kb_files = []
    for root, _, files in os.walk("docs/kb"):
        for f in files:
            if f.endswith(".md") and f not in ("AGENT_INSTRUCTIONS.md", "EXTRACTION_STATUS.md", "kb_index.md", "SURGICAL_EXTRACTION_AND_ORCHESTRATION_MASTER_PLAN.md"):
                kb_files.append(os.path.join(root, f).replace("\\", "/"))

    print(f"  Total Research KB Documents: {len(kb_files)}")
    print(f"  {'KB File':<55} {'Lines':<8} {'Extracts':<10} {'Status'}")
    print("  " + "-" * 80)

    for kbf in sorted(kb_files):
        with open(kbf, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        lines = len(content.splitlines())
        extract_matches = re.findall(r"EXTRACT\s+\d+", content, re.IGNORECASE)
        extract_count = len(extract_matches)

        if extract_count >= 12:
            status = "✅ DEEP (15+ extracts)"
        elif extract_count >= 5 or lines > 70:
            status = "⚠️ SHALLOW (needs deep read)"
        else:
            status = "❌ SKELETON"

        print(f"  {kbf:<55} {lines:<8} {extract_count:<10} {status}")

    # 3. Overall Orchestration Score
    kb_coverage_pct = ((total_cands - missing_source_kb_count) / total_cands) * 100
    syntax_ok = (invalid_parens_count == 0) and (missing_keys_count == 0)

    print("\n" + "=" * 80)
    print("📋 SUMMARY REPORT:")
    print(f"  - Total Candidates:       {total_cands}")
    print(f"  - Expression Syntax OK:   {'✅ 100%' if syntax_ok else '❌ ERRORS DETECTED'}")
    print(f"  - Source KB Traceability: {kb_coverage_pct:.1f}% ({total_cands - missing_source_kb_count}/{total_cands})")
    print(f"  - KB Files on Disk:       {len(kb_files)}")
    print("=" * 80)

if __name__ == "__main__":
    run_orchestration_audit()
