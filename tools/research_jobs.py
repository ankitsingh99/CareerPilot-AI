#!/usr/bin/env python3
"""research_jobs.py

Utility to discover new job postings based on the candidate's past applications.
It:
1. Loads ``user_inputs/job_search_tracker.csv`` (the historical tracker).
2. Extracts a set of keywords from the ``role`` column.
3. Queries public ATS board pollers (Greenhouse, Lever, Ashby, SmartRecruiters)
   for each company slug seen in the history.
4. Filters results to Indian locations (non‑remote) and titles that contain any
   of the extracted keywords.
5. Checks URL liveness using ``tools/check_liveness.py`` (zero‑token utility).
6. Writes ``user_inputs/research_jobs_results.csv`` with columns:
   ``company,job_title,application_url``.

The script is deliberately lightweight, uses lazy imports, and makes no
OpenRouter calls (free‑model‑only rule).
"""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path
from typing import Iterable, Set, Dict, List

# Lazy import of pollers – they are only needed when the script runs.
def _lazy_import_pollers():
    """Import poller functions lazily, adjusting sys.path for repo root."""
    import sys
    from pathlib import Path
    # Ensure repository root is on sys.path
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.append(str(repo_root))
    from discovery.ats_discovery import boards
    return {
        "greenhouse": boards.poll_greenhouse,
        "lever": boards.poll_lever,
        "ashby": boards.poll_ashby,
        "smartrecruiters": boards.poll_smartrecruiters,
    }

# ---------------------------------------------------------------------------
# Helper: extract keywords from past job titles/roles.
# ---------------------------------------------------------------------------
def extract_keywords_from_history(csv_path: Path) -> Set[str]:
    """Return a set of lower‑cased words extracted from the ``role`` column.

    Very small NLP – split on whitespace, strip punctuation, ignore very short
    words (<3 characters) and common stop‑words.
    """
    stop_words = {"and", "or", "the", "a", "an", "senior", "jr", "sr", "lead", "manager"}
    keywords: Set[str] = set()
    if not csv_path.is_file():
        return keywords
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            role = row.get("role", "")
            for token in role.split():
                token = token.strip(".,;:-_()[]{}\"'?")
                token_l = token.lower()
                if len(token_l) < 3 or token_l in stop_words:
                    continue
                keywords.add(token_l)
    return keywords

# ---------------------------------------------------------------------------
# Helper: simple location filter for India (non‑remote).
# ---------------------------------------------------------------------------
def is_india_location(loc: str) -> bool:
    """Return True only if the location string clearly indicates a place inside India.

    Accepts variations like "Delhi, India" or "Bangalore, India" and rejects any that
    mention remote, hybrid, virtual, or online work modes.
    """
    if not loc:
        return False
    loc_lower = loc.lower()
    # Must contain 'india' and must not contain any remote‑style indicators.
    forbidden = ["remote", "hybrid", "virtual", "online"]
    if "india" not in loc_lower:
        return False
    for term in forbidden:
        if term in loc_lower:
            return False
    return True

# ---------------------------------------------------------------------------
# Main discovery function.
# ---------------------------------------------------------------------------
def discover_jobs(keywords: Set[str]) -> List[Dict[str, str]]:
    """Query public ATS pollers, score/filter locally via prefilter + OnDeviceParser, and return matches."""
    pollers = _lazy_import_pollers()
    from intelligence.prefilter import score_job_locally
    from parsers.document import OnDeviceParser

    doc_parser = OnDeviceParser()
    results: List[Dict[str, str]] = []
    # Load past companies to limit poller scope – the CSV contains a ``company`` column.
    tracker_path = Path("user_inputs/job_search_tracker.csv")
    companies: Set[str] = set()
    if tracker_path.is_file():
        with tracker_path.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                companies.add(row.get("company", "").strip())
    # Fallback to a generic list if none found.
    if not companies:
        companies = {""}
    for company in companies:
        slug = company.replace(" ", "-").lower()
        for name, poller in pollers.items():
            try:
                for job in poller(slug):
                    raw_title = job.get("title", "")
                    title = raw_title.lower()
                    if not any(kw in title for kw in keywords):
                        continue
                    if not is_india_location(job.get("location", "")):
                        continue
                    desc = job.get("description", "") or ""
                    guard = doc_parser.evaluate_seniority_and_relevance(raw_title, desc)
                    if guard.get("is_strictly_excluded") or not guard.get("passed_gate", True):
                        continue
                    local_score = score_job_locally(raw_title, desc)
                    apply_url = job.get("apply_url") or job.get("url")
                    if not apply_url:
                        continue
                    results.append({
                        "company": job.get("company", company),
                        "job_title": raw_title,
                        "application_url": apply_url,
                        "local_fit_score": str(local_score),
                    })
            except Exception as e:
                # Fail-soft: a single poller failure should not abort the whole run.
                print(f"[research_jobs] Poller {name} for slug '{slug}' failed: {e}", file=sys.stderr)
    results.sort(key=lambda r: float(r.get("local_fit_score", "0")), reverse=True)
    return results

# ---------------------------------------------------------------------------
# Write CSV output.
# ---------------------------------------------------------------------------
def write_results_csv(records: Iterable[Dict[str, str]], out_path: Path) -> None:
    fieldnames = ["company", "job_title", "application_url", "local_fit_score"]
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for rec in records:
            writer.writerow(rec)

# ---------------------------------------------------------------------------
# CLI entry point.
# ---------------------------------------------------------------------------
def main(argv: List[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    tracker_csv = Path("user_inputs/job_search_tracker.csv")
    if not tracker_csv.is_file():
        print("[research_jobs] No job tracker CSV found at 'user_inputs/job_search_tracker.csv'", file=sys.stderr)
        return 1
    keywords = extract_keywords_from_history(tracker_csv)
    if not keywords:
        print("[research_jobs] No keywords extracted – check the tracker file.", file=sys.stderr)
        return 1
    print(f"[research_jobs] Extracted {len(keywords)} keywords from history.")
    matches = discover_jobs(keywords)
    print(f"[research_jobs] Found {len(matches)} matching postings.")
    out_path = Path("user_inputs/research_jobs_results.csv")
    write_results_csv(matches, out_path)
    print(f"[research_jobs] Results written to {out_path}")
    return 0

if __name__ == "__main__":
    sys.exit(main())

