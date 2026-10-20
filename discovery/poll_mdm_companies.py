#!/usr/bin/env python3
"""
High-Speed ATS Poller for Master Target Companies (MDM)

Polls public ATS APIs (Greenhouse, Lever, Ashby, SmartRecruiters) for companies
defined in `job_discovery/master_companies_mdm.csv` and ingests matching roles
into SQLite `jobs.db` and `job_search_tracker.csv`.

Author: Ankit Kumar Singh
Rule: Zero em dashes permitted. Zero paid API tokens.
"""

import os
import sys
import csv
import json
import re
import sqlite3
import argparse
from pathlib import Path
from typing import List, Dict, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add tools to path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(REPO_ROOT / "tools"))

from ats_discovery.boards import POLLERS
from ats_discovery.filters import evaluate_posting
from sync_tracker import generate_recruiter_search_link, ensure_db_schema

SEEDS_DIR = REPO_ROOT / "seeds"
MDM_PATH = REPO_ROOT / "job_discovery" / "master_companies_mdm.csv"
DB_PATH = REPO_ROOT / "jobs.db"
CSV_PATH = REPO_ROOT / "job_search_tracker.csv"


def norm(name: str) -> str:
    """Normalize string for fuzzy matching."""
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def load_seed_map() -> Dict[str, Tuple[str, str]]:
    """Build lookup map from normalized names to (ats, slug)."""
    seed_map = {}
    
    # 1. Load from all-verified.json
    all_ver = SEEDS_DIR / "all-verified.json"
    if all_ver.exists():
        with open(all_ver, "r", encoding="utf-8") as f:
            for item in json.load(f):
                slug = item.get("token") or item.get("slug")
                ats = item.get("ats")
                cname = item.get("company") or slug
                if ats and slug:
                    seed_map[norm(cname)] = (ats, slug)
                    seed_map[norm(slug)] = (ats, slug)
                    
    # 2. Fallbacks from specific JSON files
    for fn, ats in [("gh_companies.json", "greenhouse"), ("lever_companies.json", "lever"), ("ashby_companies.json", "ashby")]:
        p = SEEDS_DIR / fn
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                for slug in json.load(f):
                    seed_map[norm(slug)] = (ats, slug)
                    
    return seed_map


def load_mdm_targets() -> List[Dict[str, Any]]:
    """Load and match MDM companies to verified ATS endpoints."""
    if not MDM_PATH.exists():
        print(f"Error: MDM file not found at {MDM_PATH}")
        return []

    seed_map = load_seed_map()
    targets = []

    with open(MDM_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            comp_name = (row.get("company_name") or "").strip()
            if not comp_name:
                continue

            n = norm(comp_name)
            seed = seed_map.get(n)
            if not seed:
                cleaned = re.sub(r"\b(technologies|inc|corp|labs|hub|analytics|software|health|india|solutions|pharma|therapeutics)\b", "", comp_name, flags=re.I)
                c_norm = norm(cleaned)
                if c_norm and c_norm in seed_map:
                    seed = seed_map[c_norm]

            if seed:
                ats, slug = seed
                row["ats"] = ats
                row["ats_slug"] = slug
                targets.append(row)

    return targets


def poll_target(target: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Poll public ATS for a single MDM target."""
    comp_name = target["company_name"]
    ats = target["ats"]
    slug = target["ats_slug"]
    poller = POLLERS.get(ats)
    if not poller:
        return []

    matches = []
    try:
        for job in poller(slug, timeout=12):
            ev = evaluate_posting(job)
            if ev["passed"]:
                job["company"] = comp_name
                job["sector"] = target.get("domain_pillar", "")
                base_fit = float(target.get("candidate_fit_score", 90))
                # Adjust score slightly based on location tier
                tier = ev["location_tier"]
                job["location_tier"] = tier
                if tier == "100% Remote" or "NCR" in tier:
                    job["score"] = base_fit
                elif "Bangalore" in tier or "Hyderabad" in tier:
                    job["score"] = max(80.0, base_fit - 2)
                else:
                    job["score"] = max(75.0, base_fit - 5)
                matches.append(job)
    except Exception:
        pass
    return matches


def ingest_into_db(jobs: List[Dict[str, Any]]) -> int:
    """Ingest discovered jobs into SQLite jobs.db."""
    if not jobs:
        return 0

    conn = sqlite3.connect(DB_PATH)
    ensure_db_schema(conn)
    cursor = conn.cursor()

    inserted = 0
    for j in jobs:
        url = j.get("url")
        if not url:
            continue
        
        comp = j.get("company", "Unknown")
        title = j.get("title", "Unknown")
        loc = j.get("location", "")
        sector = j.get("sector", "")
        score = j.get("score", 85.0)
        jd_text = j.get("jd_text", "")
        recruiter_link = generate_recruiter_search_link(comp)
        
        try:
            cursor.execute("""
                INSERT INTO jobs (company, sector, title, url, location, jd_text, score, status, recruiter_search_link)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'discovered', ?)
                ON CONFLICT(url) DO UPDATE SET
                    score = excluded.score,
                    location = excluded.location,
                    recruiter_search_link = excluded.recruiter_search_link
            """, (comp, sector, title, url, loc, jd_text, score, recruiter_link))
            if cursor.rowcount > 0:
                inserted += 1
        except Exception as e:
            print(f"Error inserting {url}: {e}")

    conn.commit()
    conn.close()
    return inserted


def main():
    parser = argparse.ArgumentParser(description="Poll ATS boards for master companies (MDM).")
    parser.add_argument("--workers", type=int, default=25, help="Concurrent worker threads")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of companies to poll")
    parser.add_argument("--ingest", action="store_true", default=True, help="Ingest into SQLite jobs.db")
    args = parser.parse_args()

    targets = load_mdm_targets()
    if args.limit:
        targets = targets[:args.limit]

    print(f"Polling {len(targets)} MDM Target Companies with {args.workers} workers...")

    all_matches = []
    completed = 0
    total = len(targets)

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(poll_target, t): t for t in targets}
        for future in as_completed(futures):
            completed += 1
            if completed % 10 == 0 or completed == total:
                sys.stdout.write(f"\rProgress: {completed}/{total} companies scanned | {len(all_matches)} matching roles found")
                sys.stdout.flush()
            try:
                res = future.result()
                if res:
                    all_matches.extend(res)
            except Exception:
                pass

    print(f"\n\nDiscovery Complete! Found {len(all_matches)} matching roles across {total} MDM target companies.")

    # Sort by score descending
    all_matches.sort(key=lambda x: x.get("score", 0), reverse=True)

    if args.ingest:
        count = ingest_into_db(all_matches)
        print(f"Successfully ingested / updated {count} jobs in {DB_PATH}")

    print("\n" + "=" * 100)
    print(f"{'Company':<25} | {'Title':<35} | {'Fit':<6} | {'Location':<20}")
    print("-" * 100)
    for j in all_matches[:30]:
        comp = j.get("company", "")[:24]
        title = j.get("title", "")[:34]
        fit = f"{j.get('score', 0):.0f}%"
        loc = (j.get("location_tier", "") or j.get("location", ""))[:19]
        print(f"{comp:<25} | {title:<35} | {fit:<6} | {loc:<20}")
    print("=" * 100)


if __name__ == "__main__":
    main()
