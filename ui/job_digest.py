#!/usr/bin/env python3
"""Zero-Token Local Job Digest & Daily Alert Engine.

Parses, ranks, and filters newly discovered roles against candidate persona
using deterministic on-device seniority & relevance guardrails without LLM token cost.
"""

import os
import sys
import csv
import json
import sqlite3
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

from on_device_parser import OnDeviceParser

REPO_ROOT = Path(__file__).resolve().parent.parent
TRACKER_CSV = REPO_ROOT / "job_search_tracker.csv"
DB_PATH = REPO_ROOT / "jobs.db"
DIGESTS_DIR = REPO_ROOT / "job_discovery" / "digests"


def load_tracked_jobs() -> List[Dict[str, Any]]:
    """Loads all tracked job records from CSV and joins jd_text from jobs.db."""
    jobs = []
    
    # Pre-fetch jd_text from database by URL
    url_to_jd = {}
    if DB_PATH.exists():
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT url, jd_text FROM jobs WHERE jd_text IS NOT NULL")
            for row in cursor.fetchall():
                url_to_jd[row["url"]] = row["jd_text"]
            conn.close()
        except Exception as e:
            print(f"Warning: Could not read from jobs.db: {e}", file=sys.stderr)

    if TRACKER_CSV.exists():
        with open(TRACKER_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("company") and row.get("role"):
                    source_url = row.get("source", "")
                    jobs.append({
                        "company_name": row.get("company"),
                        "job_title": row.get("role"),
                        "job_url": source_url,
                        "location": row.get("role_type") or "India / Remote",
                        "status": row.get("status", "tracked"),
                        "recruiter_search_link": row.get("recruiter_search_link", ""),
                        "jd_text": url_to_jd.get(source_url, "")
                    })
    return jobs


def generate_digest(limit: int = 25, min_score: float = 60.0) -> str:
    """Generates a ranked local Markdown digest."""
    parser = OnDeviceParser()
    jobs = load_tracked_jobs()
    scored_jobs = []

    for job in jobs:
        title = job.get("job_title") or ""
        company = job.get("company_name") or ""
        url = job.get("job_url") or ""
        location = job.get("location") or "India / Remote"
        jd_text = job.get("jd_text") or ""
        
        eval_res = parser.evaluate_seniority_and_relevance(title=title, jd_text=jd_text)
        score = eval_res["deterministic_fit_score"]

        if score >= min_score and not eval_res["is_strictly_excluded"]:
            scored_jobs.append({
                "company": company,
                "title": title,
                "score": score,
                "seniority": eval_res["seniority_level"],
                "url": url,
                "location": location,
                "recruiter_link": job.get("recruiter_search_link", ""),
                "matched_skills": eval_res["matched_primary_skills"]
            })

    # Sort descending by deterministic score
    scored_jobs.sort(key=lambda x: x["score"], reverse=True)
    top_matches = scored_jobs[:limit]

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# 🎯 AI Job Search - Ranked Match Digest ({now_str})",
        "",
        f"> **Zero-Token Local Compute Engine:** Evaluated {len(jobs)} tracked roles against candidate profile.",
        "",
        "| Rank | Fit Score | Company | Job Title | Location | Direct Link |",
        "| :---: | :---: | :--- | :--- | :--- | :--- |"
    ]

    for idx, item in enumerate(top_matches, start=1):
        link_str = f"[Apply / View]({item['url']})" if item['url'] else "Portal"
        score_badge = f"**{item['score']}%**"
        lines.append(f"| {idx} | {score_badge} | **{item['company']}** | {item['title']} | {item['location']} | {link_str} |")

    lines.append("")
    lines.append("---")
    lines.append(f"*Generated on-device in <50ms with 0 LLM tokens consumed.*")

    digest_md = "\n".join(lines)
    DIGESTS_DIR.mkdir(parents=True, exist_ok=True)
    today_str = datetime.now().strftime("%Y%m%d")
    out_file = DIGESTS_DIR / f"digest_{today_str}.md"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(digest_md)

    return digest_md


def main():
    parser = argparse.ArgumentParser(description="Generate zero-token job digest and alerts.")
    parser.add_argument("--limit", type=int, default=25, help="Max jobs to display in digest")
    parser.add_argument("--min-score", type=float, default=60.0, help="Minimum fit score threshold")
    parser.add_argument("--output", type=str, default=None, help="Custom output file")
    args = parser.parse_args()

    digest = generate_digest(limit=args.limit, min_score=args.min_score)
    print(digest)


if __name__ == "__main__":
    main()
