#!/usr/bin/env python3
"""Local TF-IDF & Keyword Pre-filter for Zero-Token Job Filtering.

Filters raw job listings against candidate target skills and excluded titles locally
on CPU before sending candidate postings to LLM APIs.
"""

import json
import re
import argparse
from pathlib import Path

# Exclusion patterns (Java backend, internships, student roles, senior executive)
EXCLUDE_REGEX = re.compile(
    r"\b(java|spring boot|j2ee|intern|internship|trainee|working student|director|vp|vice president)\b",
    re.IGNORECASE,
)

TARGET_SKILLS = [
    "python", "pyspark", "sql", "snowflake", "postgresql", "trino", "oracle",
    "apache airflow", "airflow", "etl", "elt", "data governance", "data engineering",
    "data quality", "data observability", "ai agent", "llm", "tableau", "aws",
    "business technology consultant", "analytics engineer", "solutions architect"
]

def score_job_locally(title: str, description: str) -> float:
    text = f"{title} {description}".lower()
    if EXCLUDE_REGEX.search(title):
        return 0.0
    
    matches = sum(1 for skill in TARGET_SKILLS if skill in text)
    score = min(100.0, (matches / 5.0) * 100.0)
    return round(score, 1)

def main():
    parser = argparse.ArgumentParser(description="Pre-filter job listings locally")
    parser.add_argument("--input", required=True, help="Input JSON file containing raw jobs")
    parser.add_argument("--output", required=True, help="Output JSON file for qualified jobs")
    parser.add_argument("--min-score", type=float, default=40.0, help="Minimum local match score (0-100)")
    args = parser.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        print(f"Error: input file {in_path} not found.")
        return

    with open(in_path, "r", encoding="utf-8") as f:
        jobs = json.load(f)

    qualified = []
    for job in jobs:
        title = job.get("title", "")
        desc = job.get("description", "")
        local_score = score_job_locally(title, desc)
        if local_score >= args.min_score:
            job["local_fit_score"] = local_score
            qualified.append(job)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(qualified, f, indent=2)

    print(f"Local Pre-filter Complete: {len(jobs)} raw jobs -> {len(qualified)} qualified jobs (0 tokens used).")

if __name__ == "__main__":
    main()
