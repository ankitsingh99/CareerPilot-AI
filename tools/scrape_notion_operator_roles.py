#!/usr/bin/env python3
"""
tools/scrape_notion_operator_roles.py
--------------------------------------
Fetches and ingests roles from Rohan Surana's Startup Operator Roles Tracker
(Notion database) into the local jobs SQLite database (jobs.db).

Features:
- Queries public Notion collection view API directly (no browser or tokens needed).
- Deduplicates records against `jobs.db` using job_key based on URL / Role + Company.
- Inserts new opportunities with structured attributes:
    title, company, location, url, notes (experience, pay range, apply link), source.
- Can be scheduled as a daily cron job.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sqlite3
import sys
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("notion_scraper")

NOTION_PAGE_ID = "3ad900b1-07b2-8025-b057-c5b90f7bfe63"
COLLECTION_ID = "3ad900b1-07b2-80ab-aecd-000b0ad98d90"
COLLECTION_VIEW_ID = "3ad900b1-07b2-8047-ab00-000c8f430b48"

DEFAULT_DB_PATH = Path("/Users/ashish/git/ai-job-search/jobs.db")


def extract_prop_text(prop_val: Optional[List[Any]]) -> str:
    """Extracts text content or link target from Notion property representation."""
    if not prop_val or not isinstance(prop_val, list):
        return ""
    text_pieces = []
    for piece in prop_val:
        if isinstance(piece, list) and len(piece) > 0:
            val = piece[0]
            if val == "‣" and len(piece) > 1:
                # Date or mention
                for meta in piece[1]:
                    if isinstance(meta, list) and len(meta) > 1 and meta[0] == "d":
                        d_info = meta[1]
                        if isinstance(d_info, dict) and "start_date" in d_info:
                            text_pieces.append(d_info["start_date"])
            elif isinstance(val, str):
                text_pieces.append(val)
    return "".join(text_pieces).strip()


def extract_prop_url(prop_val: Optional[List[Any]]) -> str:
    """Extracts URL from link metadata or text."""
    if not prop_val or not isinstance(prop_val, list):
        return ""
    for piece in prop_val:
        if isinstance(piece, list) and len(piece) > 1:
            for meta in piece[1]:
                if isinstance(meta, list) and len(meta) > 1 and meta[0] == "a":
                    return meta[1]
    # Fallback to plain text
    return extract_prop_text(prop_val)


def fetch_notion_roles(limit: int = 5000) -> List[Dict[str, Any]]:
    """Fetches records from the Notion collection view endpoint."""
    url = "https://www.notion.so/api/v3/queryCollection"
    payload = {
        "collection": {"id": COLLECTION_ID},
        "collectionView": {"id": COLLECTION_VIEW_ID},
        "loader": {
            "type": "reducer",
            "reducers": {
                "collection_group_results": {
                    "type": "results",
                    "limit": limit
                }
            },
            "userTimeZone": "Asia/Kolkata"
        }
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko)"
        }
    )

    logger.info("Connecting to Notion public collection endpoint...")
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    record_map = data.get("recordMap", {})
    blocks = record_map.get("block", {})
    logger.info("Received %d block records from Notion.", len(blocks))

    # Schema mapping:
    # title: Startup Name
    # ;G@T: Role
    # =<T}: Location
    # CKu?: Apply Link
    # Eodb: Pay Range
    # sr`K: Date Posted
    # vuYV: Experience
    # ybYy: Job Link
    items = []
    for bid, bval in blocks.items():
        val = bval.get("value", {})
        if "value" in val:
            val = val["value"]
        if val.get("type") != "page":
            continue

        props = val.get("properties", {})
        if not props:
            continue

        company = extract_prop_text(props.get("title"))
        role = extract_prop_text(props.get(";G@T"))
        location = extract_prop_text(props.get("=<T}"))
        apply_link = extract_prop_url(props.get("CKu?"))
        pay_range = extract_prop_text(props.get("Eodb"))
        date_posted = extract_prop_text(props.get("sr`K"))
        experience = extract_prop_text(props.get("vuYV"))
        job_link = extract_prop_url(props.get("ybYy"))

        # Primary link
        target_url = job_link if (job_link and job_link.startswith("http")) else apply_link

        if not role and not company:
            continue

        items.append({
            "notion_id": bid,
            "company": company or "Unknown Startup",
            "title": role or "Operator Role",
            "location": location or "India / Remote",
            "url": target_url or f"https://rohansurana.notion.site/{bid.replace('-', '')}",
            "apply_link": apply_link,
            "pay_range": pay_range,
            "date_posted": date_posted,
            "experience": experience,
            "created_time": val.get("created_time")
        })

    logger.info("Successfully extracted %d job rows.", len(items))
    return items


def make_job_key(company: str, title: str, url: str) -> str:
    """Computes a stable hash key for deduplication."""
    norm = f"{company.strip().lower()}|{title.strip().lower()}|{url.strip().lower()}"
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:24]


def ingest_into_jobs_db(jobs: List[Dict[str, Any]], db_path: Path) -> Tuple[int, int]:
    """Inserts new jobs into sqlite database, skipping duplicates."""
    if not db_path.exists():
        logger.error("Database %s does not exist.", db_path)
        return 0, 0

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    inserted = 0
    skipped = 0
    now_iso = datetime.now().isoformat()

    for j in jobs:
        key = make_job_key(j["company"], j["title"], j["url"])
        
        # Check if already present
        cur.execute("SELECT 1 FROM jobs WHERE job_key = ? OR url = ?", (key, j["url"]))
        if cur.fetchone():
            skipped += 1
            continue

        notes_parts = []
        if j.get("experience"):
            notes_parts.append(f"Exp: {j['experience']}")
        if j.get("pay_range"):
            notes_parts.append(f"Pay: {j['pay_range']}")
        if j.get("apply_link") and j["apply_link"] != j["url"]:
            notes_parts.append(f"Apply: {j['apply_link']}")
        if j.get("date_posted"):
            notes_parts.append(f"Posted: {j['date_posted']}")

        notes_text = " | ".join(notes_parts)
        jd_summary = f"{j['title']} at {j['company']}. Location: {j['location']}. {notes_text}"

        cur.execute(
            """
            INSERT INTO jobs (
                job_key, source, company, sector, title, role_type,
                url, location, department, salary, jd_text,
                fit_rating, score, status, notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                key,
                "notion_startup_operators",
                j["company"],
                "Startups / Tech",
                j["title"],
                "Full-time",
                j["url"],
                j["location"],
                "Founder's Office / Strategy / Growth",
                j.get("pay_range") or None,
                jd_summary,
                None,
                None,
                "discovered",
                notes_text,
                now_iso,
                now_iso
            )
        )
        inserted += 1

    conn.commit()
    conn.close()
    return inserted, skipped


def main():
    parser = argparse.ArgumentParser(description="Scrape Rohan Surana Startup Operator Roles Tracker into jobs.db")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Path to jobs.db SQLite database")
    parser.add_argument("--limit", type=int, default=5000, help="Max records to fetch from Notion")
    args = parser.parse_args()

    jobs = fetch_notion_roles(limit=args.limit)
    if not jobs:
        logger.warning("No jobs fetched.")
        return

    inserted, skipped = ingest_into_jobs_db(jobs, args.db)
    logger.info("Done. %d new jobs inserted, %d existing jobs skipped in %s.", inserted, skipped, args.db)


if __name__ == "__main__":
    main()

