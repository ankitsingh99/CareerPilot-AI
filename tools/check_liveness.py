#!/usr/bin/env python3
"""
tools/check_liveness.py
-----------------------
Zero-Token Job Liveness Pre-Flight Probe.
Verifies whether a job posting is active, expired, or removed before spending
browser automation resources or model tokens.

Adapted from career-ops check-liveness.mjs into CareerPilot AI universal architecture.
Rule: Zero em dashes permitted. Zero financial cost.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add project root to path for universal module resolution
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.job_liveness_detector import check_url_liveness, is_job_expired


def main():
    parser = argparse.ArgumentParser(description="Zero-Token Job Liveness Pre-Flight Probe")
    parser.add_argument("target", nargs="?", help="Job URL or path to text file containing job description/HTML")
    parser.add_argument("--url", "-u", dest="url", help="Job URL to probe")
    parser.add_argument("--file", "-f", dest="file_path", help="Path to text/markdown file to check")
    parser.add_argument("--timeout", "-t", type=int, default=8, help="HTTP request timeout in seconds (default: 8)")
    args = parser.parse_args()

    target = args.url or args.file_path or args.target
    if not target:
        parser.print_help()
        sys.exit(1)

    # Check if target is a local file
    file_candidate = Path(target)
    if file_candidate.is_file():
        content = file_candidate.read_text(encoding="utf-8", errors="ignore")
        expired, reason = is_job_expired(content)
        if expired:
            print(f"[EXPIRED] File '{target}' indicates job closure: {reason}")
            sys.exit(2)
        else:
            print(f"[ACTIVE] File '{target}' contains active job content.")
            sys.exit(0)

    # Otherwise treat as URL
    if target.startswith("http://") or target.startswith("https://"):
        print(f"[*] Probing URL liveness: {target}")
        is_live, reason, code = check_url_liveness(target, timeout=args.timeout)
        status = "ACTIVE" if is_live else "DEAD/EXPIRED"
        print(f"[{status}] HTTP {code}: {reason}")
        sys.exit(0 if is_live else 2)

    # Raw text check
    expired, reason = is_job_expired(target)
    if expired:
        print(f"[EXPIRED] Content indicates job closure: {reason}")
        sys.exit(2)
    else:
        print(f"[ACTIVE] No closure indicators detected in provided text.")
        sys.exit(0)


if __name__ == "__main__":
    main()
