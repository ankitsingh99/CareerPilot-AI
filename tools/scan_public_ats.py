#!/usr/bin/env python3
"""
tools/scan_public_ats.py
------------------------
Universal Zero-Token Public ATS Multi-Board Scanner.
Polls public ATS APIs (Greenhouse, Lever, Ashby, SmartRecruiters, Workable,
BambooHR, Breezy, Recruitee) without requiring logins or credentials.

Adapted from career-ops scan.mjs and providers/ into CareerPilot AI universal architecture.
Rule: Zero em dashes permitted. Zero financial cost.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Dict, Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from discovery.ats_discovery.boards import POLLERS
from core.db import get_connection, upsert_job
from core.job_liveness_detector import normalize_for_match


def detect_ats_and_slug(url_or_slug: str) -> tuple[str, str]:
    """Infers ATS provider and company slug from a URL or slug string."""
    u = url_or_slug.strip().lower()
    if "greenhouse.io" in u:
        parts = u.split("greenhouse.io/")[-1].split("/")[0].split("?")[0]
        return "greenhouse", parts
    if "lever.co" in u:
        parts = u.split("lever.co/")[-1].split("/")[0].split("?")[0]
        return "lever", parts
    if "ashbyhq.com" in u:
        parts = u.split("ashbyhq.com/")[-1].split("/")[0].split("?")[0]
        return "ashby", parts
    if "smartrecruiters.com" in u:
        parts = u.split("smartrecruiters.com/")[-1].split("/")[0].split("?")[0]
        return "smartrecruiters", parts
    if "workable.com" in u:
        parts = u.split("workable.com/")[-1].split("/")[0].split("?")[0]
        return "workable", parts
    if "bamboohr.com" in u:
        # e.g. https://company.bamboohr.com
        parts = u.split(".bamboohr.com")[0].split("//")[-1]
        return "bamboohr", parts
    if "breezy.hr" in u:
        parts = u.split(".breezy.hr")[0].split("//")[-1]
        return "breezy", parts
    if "recruitee.com" in u:
        parts = u.split(".recruitee.com")[0].split("//")[-1]
        return "recruitee", parts

    # Fallback to greenhouse if only a slug is provided
    return "greenhouse", url_or_slug.strip()


def scan_board(
    ats: str,
    slug: str,
    keywords: List[str] = None,
    location_filter: str = "india",
    record_db: bool = True
) -> List[Dict[str, Any]]:
    """Polls ATS and returns matching opportunities."""
    ats_clean = ats.lower().strip()
    poller = POLLERS.get(ats_clean)
    if not poller:
        raise ValueError(f"Unsupported ATS '{ats}'. Supported: {', '.join(POLLERS.keys())}")

    print(f"[*] Scanning {ats.upper()} for company slug: '{slug}'...")
    results = []
    kw_list = [k.lower().strip() for k in keywords] if keywords else []
    loc_filter = location_filter.lower().strip() if location_filter else ""

    try:
        jobs = list(poller(slug))
        print(f"[+] Retrieved {len(jobs)} total postings from {slug}.")
    except Exception as e:
        print(f"[-] Error querying {ats} for '{slug}': {e}")
        return []

    for j in jobs:
        title = j.get("title", "")
        loc = j.get("location", "")
        wp = j.get("workplace_type", "")
        combined = f"{title} {loc} {wp}".lower()

        # Location check
        if loc_filter:
            is_loc_match = loc_filter in combined or "remote" in wp or "anywhere" in combined
            if not is_loc_match:
                continue

        # Keywords check
        if kw_list:
            if not any(k in combined for k in kw_list):
                continue

        results.append(j)

        if record_db:
            try:
                upsert_job(
                    company=j["company"],
                    title=j["title"],
                    url=j["url"],
                    location=j["location"],
                    salary=f"{j.get('salary_min') or ''}-{j.get('salary_max') or ''}" if j.get('salary_min') else "",
                    jd_text=j.get("jd_text", ""),
                    source=f"ats:{ats}"
                )
            except Exception:
                pass

    print(f"[✓] {len(results)} matching opportunities found.")
    return results


def main():
    parser = argparse.ArgumentParser(description="Universal Zero-Token Public ATS Scanner")
    parser.add_argument("target", help="Company slug or careers board URL")
    parser.add_argument("--ats", "-a", choices=list(POLLERS.keys()), help="ATS name (optional if URL provided)")
    parser.add_argument("--keywords", "-k", nargs="*", default=["data", "analytics", "engineer", "scientist", "consultant"], help="Keyword filters")
    parser.add_argument("--location", "-l", default="india", help="Location filter (default: india, pass '' for all)")
    parser.add_argument("--no-db", action="store_true", help="Do not save to jobs.db")
    args = parser.parse_args()

    detected_ats, slug = detect_ats_and_slug(args.target)
    ats = args.ats or detected_ats

    matches = scan_board(
        ats=ats,
        slug=slug,
        keywords=args.keywords,
        location_filter=args.location,
        record_db=not args.no_db
    )

    if matches:
        print("\n" + "=" * 60)
        print(f"🎯 MATCHING POSTINGS ({len(matches)} FOUND)")
        print("=" * 60)
        for idx, m in enumerate(matches, 1):
            sal = f" | Sal: {m['salary_min']}-{m['salary_max']}" if m.get("salary_min") else ""
            print(f"[{idx}] {m['title']}")
            print(f"    Location: {m['location'] or 'Unspecified'} | ATS: {m['ats']}{sal}")
            print(f"    URL:      {m['url']}")
        print("=" * 60 + "\n")


if __name__ == "__main__":
    main()

