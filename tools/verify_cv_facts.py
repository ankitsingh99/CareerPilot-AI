#!/usr/bin/env python3
"""
tools/verify_cv_facts.py
------------------------
Anti-Hallucination CV Fact & Provenance Auditor CLI.
Audits generated cover letters, stories, and application answers against
candidate ground truth facts.

Adapted from career-ops verify-cv-facts.mjs into CareerPilot AI universal architecture.
Rule: Zero em dashes permitted. Zero financial cost.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.cv_fact_checker import CVFactChecker


def main():
    parser = argparse.ArgumentParser(description="Audit generated application texts for hallucinations and slop")
    parser.add_argument("target", nargs="?", help="Text string or path to markdown/docx file")
    parser.add_argument("--file", "-f", dest="file_path", help="Path to text or markdown file")
    args = parser.parse_args()

    target = args.file_path or args.target
    if not target:
        parser.print_help()
        sys.exit(1)

    file_cand = Path(target)
    if file_cand.is_file():
        content = file_cand.read_text(encoding="utf-8", errors="ignore")
    else:
        content = target

    res = CVFactChecker.audit_text(content)

    print("\n" + "=" * 60)
    print(f"🛡️  FACT CHECK AUDIT: {'PASSED (100% GROUNDED)' if res['passed'] else 'FAILED (VIOLATIONS DETECTED)'}")
    print("=" * 60)
    if res["verified_claims"]:
        print("✅ Grounded Claims Verified:")
        for c in res["verified_claims"]:
            print(f"   • {c}")

    if res["violations"]:
        print("\n❌ Violations & Hallucinations Flagged:")
        for v in res["violations"]:
            print(f"   • {v}")
        print("=" * 60 + "\n")
        sys.exit(1)

    print("\n[✓] Zero hallucinations, zero corporate slop, zero em dashes.")
    print("=" * 60 + "\n")
    sys.exit(0)


if __name__ == "__main__":
    main()

