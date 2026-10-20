#!/usr/bin/env python3
"""
tools/validate_cover_letter.py
------------------------------
Comprehensive Cover Letter Validator and Proofreader.

Integrates two-tier validation:
- Tier 1 (Local Deterministic Linter): Detects broken percentages ('by %'), dangling operators ('+ Airflow'),
  unpopulated placeholders ('Req ID: '), truncated URLs, and banned AI cliches at zero cost (<10ms).
- Tier 2 (OpenRouter Free Tier Proofreader): If local defects or warnings are detected (or --proofread is set),
  invokes OpenRouter zero-cost free models (e.g. cohere/north-mini-code:free) to repair metrics and polish prose.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure root directory is on sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from parsers.linter import lint_and_format


def validate_file(file_path: Path, proofread_llm: bool = False, auto_fix: bool = False, role: str = "", company: str = "") -> bool:
    if not file_path.exists():
        print(f"[validator] ERROR: File not found: {file_path}")
        return False

    content = file_path.read_text(encoding="utf-8")
    print(f"\n[validator] Auditing {file_path.name} ({len(content)} bytes)...")

    result = lint_and_format(content, proofread_llm=proofread_llm, role_title=role, company=company)

    if result["passed"]:
        print(f"[validator]  PASS: {file_path.name} satisfies all structural, metric, and stylometric rules.")
        if result.get("burstiness"):
            b = result["burstiness"]
            print(f"             Burstiness StdDev: {b.get('std_dev')} (Bursty: {b.get('is_bursty')}) | Sentences: {b.get('sentence_count')}")
        return True
    else:
        print(f"[validator]  FAIL: {file_path.name} failed validation:")
        for v in result["violations"]:
            print(f"   {v}")

        if auto_fix and result.get("proofread_info", {}).get("success"):
            fixed_text = result["clean_text"]
            file_path.write_text(fixed_text, encoding="utf-8")
            print(f"[validator]  Auto-fixed and saved to {file_path}")
            return True

        return False


def validate_all_cover_letters(proofread_llm: bool = False, auto_fix: bool = False) -> bool:
    root = Path(__file__).parent.parent
    patterns = ["documents/applications/**/cover_letter.md", "documents/applications/**/cover_letter.txt", "cover_letters/*.md"]
    found_files: List[Path] = []
    for pat in patterns:
        found_files.extend(root.glob(pat))

    if not found_files:
        print("[validator] No cover letter files discovered.")
        return True

    print(f"[validator] Found {len(found_files)} cover letters across workspace.")
    overall_success = True
    for f in found_files:
        ok = validate_file(f, proofread_llm=proofread_llm, auto_fix=auto_fix)
        if not ok:
            overall_success = False

    return overall_success


def main():
    parser = argparse.ArgumentParser(description="Cover Letter Integrity Validator & OpenRouter Proofreader")
    parser.add_argument("--input", type=str, help="Path to cover letter file")
    parser.add_argument("--all", action="store_true", help="Validate all cover letters in workspace")
    parser.add_argument("--proofread", action="store_true", help="Invoke OpenRouter Free Tier LLM to proofread/fix")
    parser.add_argument("--fix", action="store_true", help="Write cleaned/proofread text back to file")
    parser.add_argument("--role", type=str, default="", help="Target role title for context")
    parser.add_argument("--company", type=str, default="", help="Target company name for context")

    args = parser.parse_args()

    if args.all:
        success = validate_all_cover_letters(proofread_llm=args.proofread, auto_fix=args.fix)
        sys.exit(0 if success else 1)

    if not args.input:
        parser.print_help()
        sys.exit(1)

    input_path = Path(args.input)
    success = validate_file(input_path, proofread_llm=args.proofread, auto_fix=args.fix, role=args.role, company=args.company)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
