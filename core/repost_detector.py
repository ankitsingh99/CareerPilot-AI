#!/usr/bin/env python3
"""
Repost & Ghost Job Detector
===========================
Deterministic heuristic engine to detect stale requisitions and ghost jobs
that companies repeatedly relist across multiple weeks without hiring.

Adapted from career-ops detect-reposts.mjs into CareerPilot AI Python 3.15+ architecture.
Enforces:
1. Exact Title Identity (token sets, ignoring word order, punctuation, and casing).
2. Distinct Scan Dates (at least 2 separate dates).
3. Minimum Span Window (>= 7 days span) to distinguish from concurrent parallel requisitions.
4. Maximum Recency Window (<= 90 days).
"""

import csv
import re
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple


_STOP_WORDS = {
    "and", "or", "the", "a", "an", "in", "for", "with", "at", "by", "from",
    "on", "to", "of", "full", "time", "part", "permanent", "contract"
}


def title_identity_key(title: str) -> str:
    """
    Derives a canonical title token key.
    Splits into alphanumeric tokens, filters noise stopwords, and sorts alphabetically.
    Tolerates word order churn (e.g. 'Data Engineer - Senior' vs 'Senior Data Engineer').
    Preserves seniority and domain tokens.
    """
    if not isinstance(title, str) or not title.strip():
        return ""
    
    clean = re.sub(r"[^\w\s]", " ", title.lower())
    tokens = [tok for tok in clean.split() if tok and tok not in _STOP_WORDS]
    return " ".join(sorted(set(tokens)))


def parse_date(date_str: str) -> Optional[date]:
    """Parses various date string formats into a datetime.date object."""
    if not date_str or not isinstance(date_str, str):
        return None
    date_str = date_str.strip()
    # Try ISO date YYYY-MM-DD
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(date_str.split()[0], fmt.split()[0]).date()
        except Exception:
            continue
    return None


class RepostDetector:
    """Detects repeated reposts and potential ghost jobs from tracker history."""

    def __init__(self, tracker_path: Optional[Path] = None):
        self.tracker_path = tracker_path or Path(__file__).resolve().parent.parent / "user_inputs" / "job_search_tracker.csv"

    def analyze_clusters(
        self,
        min_span_days: int = 7,
        max_window_days: int = 90,
        min_occurrences: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Scans tracker history and groups by (company, title_identity).
        Returns list of repost cluster diagnostics.
        """
        if not self.tracker_path.exists():
            return []

        records = []
        with open(self.tracker_path, mode="r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                company = (row.get("Company") or row.get("company") or "").strip()
                title = (row.get("Job Title") or row.get("job_title") or row.get("Title") or "").strip()
                url = (row.get("Job URL") or row.get("job_url") or row.get("URL") or "").strip()
                date_val = (row.get("Date Applied") or row.get("date_applied") or row.get("Date") or "").strip()
                parsed_d = parse_date(date_val)
                if company and title and parsed_d:
                    records.append({
                        "company": company,
                        "title": title,
                        "url": url,
                        "date": parsed_d,
                        "title_key": title_identity_key(title)
                    })

        # Group by (company_lower, title_key)
        groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
        for rec in records:
            if not rec["title_key"]:
                continue
            key = (rec["company"].lower(), rec["title_key"])
            groups.setdefault(key, []).append(rec)

        repost_clusters = []
        today = date.today()

        for (comp_key, t_key), items in groups.items():
            if len(items) < min_occurrences:
                continue

            # Check distinct scan dates
            dates = sorted(list(set(item["date"] for item in items)))
            if len(dates) < 2:
                # Parallel openings posted on the same single sweep, not reposts
                continue

            span_days = (dates[-1] - dates[0]).days
            if span_days < min_span_days:
                # Below minimum time span constraint
                continue

            # Check if within max_window_days
            days_since_latest = (today - dates[-1]).days
            if days_since_latest > max_window_days:
                continue

            urls = list(set(item["url"] for item in items if item["url"]))
            original_titles = list(set(item["title"] for item in items))
            company_name = items[0]["company"]

            repost_clusters.append({
                "company": company_name,
                "title_key": t_key,
                "titles": original_titles,
                "occurrences": len(items),
                "distinct_dates": [d.isoformat() for d in dates],
                "first_seen": dates[0].isoformat(),
                "latest_seen": dates[-1].isoformat(),
                "span_days": span_days,
                "urls": urls,
                "is_ghost_candidate": span_days >= 21 and len(items) >= 2
            })

        # Sort by span days descending
        repost_clusters.sort(key=lambda x: (x["span_days"], x["occurrences"]), reverse=True)
        return repost_clusters


if __name__ == "__main__":
    detector = RepostDetector()
    clusters = detector.analyze_clusters()
    print(f"\n[Repost & Ghost Job Audit] Found {len(clusters)} repost clusters:\n")
    for c in clusters:
        ghost_flag = " ⚠️ [POTENTIAL GHOST JOB]" if c["is_ghost_candidate"] else ""
        print(f"• {c['company']} - {c['titles'][0]}{ghost_flag}")
        print(f"    Occurrences: {c['occurrences']} | Span: {c['span_days']} days ({c['first_seen']} to {c['latest_seen']})")
        print(f"    Titles: {', '.join(c['titles'])}")
        print()
