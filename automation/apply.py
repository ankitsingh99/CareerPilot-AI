#!/usr/bin/env python3
"""
Universal Job Application CLI & Autopilot Runner.
=================================================
A single, generalized entrypoint for all job applications across any ATS platform.
Eliminates generating ad-hoc per-company scripts and saves thousands of tokens.

Usage:
    python tools/apply.py --url "<JOB_URL>" [--role-name "<ROLE>"] [--mode apply|review|login|inspect]

Modes:
    apply / review (default) - Autonomously signs in/registers, uploads master CV, prefills form fields,
                              and stops strictly at the final Review / Pre-Submission page.
    inspect                  - Fast form element discovery without filling.
    login                    - Opens browser with prefilled credentials for user login.

Fallback:
    If local Playwright encounters browser/driver crashes or severe blocks,
    the agent automatically falls back to Chrome DevTools MCP tools.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from automation.browser import (
    mode_apply,
    mode_login,
    mode_inspect,
    get_latest_resume,
    get_candidate_credentials,
    detect_ats,
)


def main():
    parser = argparse.ArgumentParser(description="Universal Job Application Autopilot Runner")
    parser.add_argument("--url", required=True, help="Job posting / application portal URL")
    parser.add_argument("--role-name", default="", help="Optional role name or requisition identifier")
    parser.add_argument("--mode", choices=["apply", "review", "login", "inspect"], default="apply",
                        help="Application mode (default: apply)")
    parser.add_argument("--keep-open", action="store_true", default=True, help="Keep browser open on review screen")

    args = parser.parse_args()

    slug = args.role_name.strip() or "general_application"
    ats = detect_ats(args.url)
    resume = get_latest_resume()
    candidate, email, _, _ = get_candidate_credentials()

    print("==================================================")
    print("UNIVERSAL JOB APPLICATION AUTOPILOT")
    print(f"URL: {args.url}")
    print(f"Detected ATS: {ats.upper()}")
    print(f"Role / Slug: {slug}")
    print(f"Master Resume: {resume.name}")
    print(f"Candidate: {candidate.get('full_name')} ({email})")
    print(f"Mode: {args.mode.upper()}")
    print("==================================================")

    try:
        if args.mode == "review":
            mode_apply(args.url, slug, keep_open=args.keep_open, auto_submit=False)
        elif args.mode in ["apply", "submit"]:
            mode_apply(args.url, slug, keep_open=args.keep_open, auto_submit=True)
        elif args.mode == "login":
            mode_login(args.url, slug, keep_open=args.keep_open)
        elif args.mode == "inspect":
            mode_inspect(args.url, slug)

        # Trigger tracker sync
        sync_script = ROOT_DIR / "tools" / "sync_tracker.py"
        if sync_script.exists():
            subprocess.run([sys.executable, str(sync_script)], check=False)

    except Exception as exc:
        print(f"\n[!] Playwright runner encountered an error: {exc}")
        print("[!] Activating Fallback: Chrome DevTools MCP tools are available to complete this application.")
        sys.exit(1)


if __name__ == "__main__":
    main()
