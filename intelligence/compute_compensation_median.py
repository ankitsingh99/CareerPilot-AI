#!/usr/bin/env python3
"""
Compute median compensation LPA for master_companies_mdm.csv.
The script reads the CSV, extracts numeric ranges from the "Target Band" column (e.g., "₹20-28 LPA"),
calculates the midpoint (treated as median) and appends a new column `compensation_median_lpa`.
It overwrites the original CSV in‑place.
"""
import csv, re, sys
from pathlib import Path

CSV_PATH = Path("/Users/ashish/git/ai-job-search/job_discovery/master_companies_mdm.csv")
if not CSV_PATH.exists():
    print(f"CSV not found: {CSV_PATH}")
    sys.exit(1)

range_pat = re.compile(r"₹\s*([0-9]+)\s*(?:-\s*([0-9]+))?\s*LPA", re.IGNORECASE)

rows = []
with CSV_PATH.open(newline="", encoding="utf-8") as f:
    reader = csv.reader(f)
    header = next(reader)
    # locate compensation benchmark column (case‑insensitive)
    target_idx = next((i for i, h in enumerate(header) if "compensation" in h.lower()), None)
    if target_idx is None:
        print("Compensation benchmark column not found")
        sys.exit(1)
    header.append("compensation_median_lpa")
    for row in reader:
        cell = row[target_idx] if len(row) > target_idx else ""
        m = range_pat.search(cell)
        if m:
            low = float(m.group(1))
            high = float(m.group(2)) if m.group(2) else low
            median = round((low + high) / 2, 1)
        else:
            median = ""
        row.append(str(median))
        rows.append(row)

with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(header)
    writer.writerows(rows)

print(f"Added compensation_median_lpa to {CSV_PATH} (rows: {len(rows)})")
