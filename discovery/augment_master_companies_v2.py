#!/usr/bin/env python3
"""
augment_master_companies_v2.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Utility script to:
1. De‑duplicate rows in `job_discovery/master_companies_mdm.csv` based on the
   `company_name` column (case‑insensitive, keep the first occurrence).
2. Append a correctly‑formatted entry for **EXL Service** if it is not already
   present.
3. Query an OpenRouter free‑tier model for up to five *adjacent* Indian companies
   that share the same domain/sub‑domain as the existing rows. The model is asked
   to return a JSON array where each object uses the exact CSV column names.
4. Append any new companies returned by the model (skip duplicates).
5. Write the enriched CSV back to disk while preserving the original column order.
6. Log token usage for the LLM call for benchmarking.

All OpenRouter calls use the repository‑provided `tools/openrouter.py` wrapper,
which enforces the ``:free`` model policy (see AGENTS.md). The script is safe to
run repeatedly – it will not create duplicate rows.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import List, Dict, Set, Tuple

# ---------------------------------------------------------------------------
# Ensure the repository root is on the Python path so we can import the wrapper.
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from intelligence.llm_clients.openrouter import ask_with_usage, DEFAULT_FREE_MODEL

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
CSV_PATH = ROOT / "job_discovery" / "master_companies_mdm.csv"

CSV_HEADERS = [
    "company_name",
    "gcc_india_hub",
    "domain_pillar",
    "sub_domain",
    "persona_match_rationale",
    "recommended_target_roles",
    "candidate_fit_score",
    "india_locations",
    "core_functional_focus",
    "compensation_benchmark",
    "network_contacts",
    "career_portal_url",
    "company_overview",
]

EXL_ENTRY: Dict[str, str] = {
    "company_name": "EXL Service",
    "gcc_india_hub": "EXL Analytics & Consulting Hub",
    "domain_pillar": "Data Governance & Engineering",
    "sub_domain": "Analytics, Consulting, AI Agent Development",
    "persona_match_rationale": "",
    "recommended_target_roles": "",
    "candidate_fit_score": "",
    "india_locations": "Noida, Delhi NCR (Remote/Hybrid)",
    "core_functional_focus": "Data Engineering pipelines, AI agent automation, consulting services",
    "compensation_benchmark": "",
    "network_contacts": "",
    "career_portal_url": "https://www.exlservice.com/careers",
    "company_overview": "",
}

ADJACENT_PROMPT = (
    "You are an AI assistant helping a data engineer build a target‑company list. "
    "Given the existing company entries (a JSON list where each object contains the keys "
    "'company_name', 'gcc_india_hub', 'domain_pillar', 'sub_domain'), suggest up to 5 "
    "additional Indian companies that operate in the same domains/sub‑domains. "
    "Return the result **exactly** as a JSON array where each object contains **all** "
    "CSV columns: company_name, gcc_india_hub, domain_pillar, sub_domain, "
    "persona_match_rationale, recommended_target_roles, candidate_fit_score, "
    "india_locations, core_functional_focus, compensation_benchmark, "
    "network_contacts, career_portal_url, company_overview. "
    "If a field is unknown, use an empty string."
)

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def read_csv(path: Path) -> List[Dict[str, str]]:
    """Read the CSV and return a list of dictionaries preserving order."""
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    """Write rows back to the CSV using the predefined header order."""
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerows(rows)


def dedupe_rows(rows: List[Dict[str, str]]) -> Tuple[List[Dict[str, str]], Set[str]]:
    """Remove duplicate company_name entries (case‑insensitive)."""
    seen: Set[str] = set()
    cleaned: List[Dict[str, str]] = []
    dupes: Set[str] = set()
    for r in rows:
        name = r.get("company_name", "").strip().lower()
        if name and name not in seen:
            seen.add(name)
            cleaned.append(r)
        else:
            dupes.add(r.get("company_name", ""))
    return cleaned, dupes


def fetch_adjacent(existing: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Ask OpenRouter for adjacent companies.

    Returns a list of dictionaries matching CSV_HEADERS (or a subset). The caller
    will merge the result while avoiding duplicates.
    """
    payload = [
        {
            "company_name": r.get("company_name", ""),
            "domain_pillar": r.get("domain_pillar", ""),
            "sub_domain": r.get("sub_domain", ""),
        }
        for r in existing
    ]
    prompt = (
        ADJACENT_PROMPT
        + "\n\nCurrent entries (JSON):\n"
        + json.dumps(payload, ensure_ascii=False)
    )
    print("[augment] Querying OpenRouter (free tier)…")
    response, usage = ask_with_usage(
        prompt, model=DEFAULT_FREE_MODEL, max_tokens=800, json_mode=True
    )
    print(
        f"[augment] Tokens – prompt:{usage.get('prompt_tokens')} "
        f"completion:{usage.get('completion_tokens')} total:{usage.get('total_tokens')}"
    )
    try:
        data = json.loads(response)
        if isinstance(data, list):
            return data
        else:
            print("[augment] Warning: LLM returned JSON that is not a list.")
    except json.JSONDecodeError:
        print("[augment] Warning: could not parse LLM response as JSON.")
    return []

# ---------------------------------------------------------------------------
# Main workflow
# ---------------------------------------------------------------------------

def main() -> None:
    if not CSV_PATH.exists():
        print(f"[augment] ERROR: CSV not found at {CSV_PATH}")
        sys.exit(1)

    rows = read_csv(CSV_PATH)
    # 1. De‑duplicate
    rows, dupes = dedupe_rows(rows)
    if dupes:
        print(f"[augment] Removed {len(dupes)} duplicate company_name entries: {', '.join(dupes)}")
    else:
        print("[augment] No duplicate company_name entries found.")

    # 2. Ensure EXL entry exists
    existing_names = {r.get("company_name", "").strip().lower() for r in rows}
    if EXL_ENTRY["company_name"].lower() not in existing_names:
        rows.append(EXL_ENTRY)
        print("[augment] Added EXL Service entry.")
    else:
        print("[augment] EXL Service already present.")

    # 3. Fetch adjacent companies via LLM
    new_companies = fetch_adjacent(rows)
    added = 0
    for comp in new_companies:
        cname = comp.get("company_name", "").strip().lower()
        if cname and cname not in existing_names:
            full_entry = {key: comp.get(key, "") for key in CSV_HEADERS}
            rows.append(full_entry)
            existing_names.add(cname)
            added += 1
    print(f"[augment] Added {added} adjacent companies from LLM.")

    # 4. Write back to CSV
    write_csv(CSV_PATH, rows)
    print(f"[augment] CSV updated – total rows (including header): {len(rows) + 1}")

if __name__ == "__main__":
    main()
