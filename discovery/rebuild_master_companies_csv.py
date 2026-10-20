#!/usr/bin/env python3
"""
rebuild_master_companies_csv.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Utility to reconstruct `master_companies_mdm.csv` from the authoritative
`master_companies_mdm.json` file. It:
1. Loads the JSON (which contains the full company catalogue).
2. Ensures an entry for **EXL Service** exists – it asks a free‑tier OpenRouter
   model for a complete JSON record matching the CSV schema.
3. De‑duplicates rows based on the `company_name` column (case‑insensitive).
4. Writes the data back to the CSV using the exact column order required by the
   rest of the project.
5. Prints token usage for the LLM call so you can benchmark the cost.

The script is safe to run repeatedly – it will not create duplicate rows.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Repository‑root import setup – needed for the OpenRouter wrapper.
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from intelligence.llm_clients.openrouter import ask_with_usage, DEFAULT_FREE_MODEL

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
JSON_PATH = ROOT / "job_discovery" / "master_companies_mdm.json"
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

EXL_COMPANY_NAME = "EXL Service"

EXL_PROMPT = (
    "Provide a JSON object describing EXL Service (an Indian data & consulting firm) "
    "with the exact keys as in the project's CSV: "
    + ", ".join(CSV_HEADERS)
    + ". Use empty strings for any field you do not know."
)

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def load_json(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerows(rows)


def dedupe(rows: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for r in rows:
        name = r.get("company_name", "").strip().lower()
        if name and name not in seen:
            seen.add(name)
            out.append(r)
    return out


def fetch_exl() -> dict:
    print("[rebuild] Querying OpenRouter for EXL Service details (free tier)…")
    response, usage = ask_with_usage(
        EXL_PROMPT,
        model=DEFAULT_FREE_MODEL,
        max_tokens=800,
        json_mode=True,
    )
    print(
        f"[rebuild] Tokens – prompt:{usage.get('prompt_tokens')} "
        f"completion:{usage.get('completion_tokens')} total:{usage.get('total_tokens')}"
    )
    try:
        data = json.loads(response)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    # Fallback – a minimal placeholder (same as earlier script used)
    print("[rebuild] Warning: could not parse LLM response as JSON – using fallback entry.")
    return {
        "company_name": EXL_COMPANY_NAME,
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

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not JSON_PATH.exists():
        print(f"[rebuild] ERROR: JSON source not found at {JSON_PATH}")
        sys.exit(1)

    companies = load_json(JSON_PATH)
    # Ensure EXL entry exists
    if not any(c.get("company_name", "").strip().lower() == EXL_COMPANY_NAME.lower() for c in companies):
        companies.append(fetch_exl())
        print("[rebuild] Added EXL Service entry via LLM.")
    else:
        print("[rebuild] EXL Service already present in JSON.")

    # Deduplicate and write CSV
    clean = dedupe(companies)
    write_csv(CSV_PATH, clean)
    print(f"[rebuild] CSV written with {len(clean)} rows (plus header).")

if __name__ == "__main__":
    main()
