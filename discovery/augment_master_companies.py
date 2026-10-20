#!/usr/bin/env python3
"""
augment_master_companies.py
~~~~~~~~~~~~~~~~~~~~~~~~~~
Utility script to:
1. De‑duplicate entries in `job_discovery/master_companies_mdm.csv` (case‑insensitive).
2. Append an entry for **EXL Service**.
3. Use OpenRouter (free‑tier) to suggest adjacent Indian companies based on existing domains/sub‑domains.
4. Log token usage for each LLM call for benchmarking.

Run from the repository root:
    python tools/augment_master_companies.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import List, Dict, Set, Tuple

# Import the zero‑cost OpenRouter wrapper (enforces :free models).
import sys
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from intelligence.llm_clients.openrouter import ask_with_usage, DEFAULT_FREE_MODEL

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "job_discovery" / "master_companies_mdm.csv"

EXL_ENTRY = {
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
    "company_overview": ""
}

ADJACENT_PROMPT = (
    "Based on the following company metadata (JSON list), suggest up to 5 additional Indian "
    "companies that operate in the same domains/sub‑domains. Return a JSON array with keys: "
    "company, gcc, domain, sub, loc, focus, portal. Only include companies that have a presence "
    "in India."
)

def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def write_csv(path: Path, rows: List[Dict[str, str]], headers: List[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)

def dedupe(rows: List[Dict[str, str]]) -> Tuple[List[Dict[str, str]], Set[str]]:
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
    payload = [{"company_name": r.get("company_name", ""), "domain_pillar": r.get("domain_pillar", ""), "sub_domain": r.get("sub_domain", "")} for r in existing]
    prompt = ADJACENT_PROMPT + "\n\nCurrent entries (JSON):\n" + json.dumps(payload, ensure_ascii=False)
    print("[augment] Querying OpenRouter (free tier)…")
    resp, usage = ask_with_usage(prompt, model=DEFAULT_FREE_MODEL, max_tokens=800, json_mode=True)
    print(f"[augment] Tokens – prompt:{usage.get('prompt_tokens')} completion:{usage.get('completion_tokens')} total:{usage.get('total_tokens')}")
    try:
        data = json.loads(resp)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        print("[augment] Warning: could not parse LLM response as JSON.")
        return []

def main() -> None:
    if not CSV_PATH.exists():
        print(f"[augment] ERROR: {CSV_PATH} not found")
        sys.exit(1)
    rows = read_csv(CSV_PATH)
    headers = ["company_name","gcc_india_hub","domain_pillar","sub_domain","persona_match_rationale","recommended_target_roles","candidate_fit_score","india_locations","core_functional_focus","compensation_benchmark","network_contacts","career_portal_url","company_overview"]

    # 1. Remove duplicates
    rows, dupes = dedupe(rows)
    if dupes:
        print(f"[augment] Removed {len(dupes)} duplicates: {', '.join(dupes)}")
    else:
        print("[augment] No duplicates found.")

    # 2. Add EXL if missing
    names = {r.get("company_name", "").strip().lower() for r in rows}
    if EXL_ENTRY["company_name"].lower() not in names:
        rows.append(EXL_ENTRY)
        print("[augment] Added EXL Service entry.")
    else:
        print("[augment] EXL Service already present.")

    # 3. Get adjacent companies via LLM
    new_companies = fetch_adjacent(rows)
    added = 0
    existing_names = {r.get("company_name", "").strip().lower() for r in rows}
    for comp in new_companies:
        cname = comp.get("company_name", comp.get("company", "")).strip().lower()
        if cname and cname not in existing_names:
            rows.append(comp)
            existing_names.add(cname)
            added += 1
    print(f"[augment] Added {added} adjacent companies from LLM.")

    # 4. Write back
    write_csv(CSV_PATH, rows, list(headers))
    print(f"[augment] CSV updated – total rows: {len(rows)}")

if __name__ == "__main__":
    main()
