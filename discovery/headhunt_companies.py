#!/usr/bin/env python3
"""
headhunt_companies.py
~~~~~~~~~~~~~~~~~~~~~~
Utility that expands the master company list by asking a free‑tier OpenRouter model
for additional companies that match the industry pillars and functional sub‑domains
found in the existing `master_companies_mdm.json` file.

The script:
1. Loads the JSON source (the full authoritative catalogue).
2. Extracts the unique `domain_pillar` and `sub_domain` values – these are the
   "adject industry and functional areas" the user wants to cover.
3. Builds a concise prompt that asks the model to return **up to 200 companies**
   (including their career‑portal URL) that have a GCC/office in India and belong
   to any of the extracted domains/sub‑domains.
4. Sends the request via the repository’s `tools/openrouter.py` wrapper, which
   enforces the ``:free`` model policy.
5. Parses the JSON response (if possible) and writes a new CSV file
   `job_discovery/expanded_companies.csv` using the same column order as the
   master CSV.
6. Prints token usage for benchmarking.

If the LLM response cannot be parsed as JSON, the script falls back to writing a
plain‑text log so the user can manually inspect and correct it.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Repository‑root import setup – required for the OpenRouter wrapper.
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from intelligence.llm_clients.openrouter import ask_with_usage, DEFAULT_FREE_MODEL

# ---------------------------------------------------------------------------
# Paths & CSV schema
# ---------------------------------------------------------------------------
JSON_PATH = ROOT / "job_discovery" / "master_companies_mdm.json"
OUTPUT_CSV = ROOT / "job_discovery" / "expanded_companies.csv"

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

MAX_NEW_COMPANIES = 200

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


def extract_unique_domains(data: list[dict]) -> tuple[set[str], set[str]]:
    pillars = {row.get("domain_pillar", "").strip() for row in data}
    subs = {row.get("sub_domain", "").strip() for row in data}
    # Remove empty strings
    pillars.discard("")
    subs.discard("")
    return pillars, subs

# ---------------------------------------------------------------------------
# Main workflow
# ---------------------------------------------------------------------------

def main() -> None:
    if not JSON_PATH.exists():
        print(f"[headhunt] ERROR: JSON source not found at {JSON_PATH}")
        sys.exit(1)

    existing = load_json(JSON_PATH)
    pillars, subs = extract_unique_domains(existing)

    # Build a readable list for the prompt (limit length for token economy)
    pillar_list = ", ".join(sorted(pillars)[:1000])
    sub_list = ", ".join(sorted(subs)[:1000])

    prompt = (
        f"You are a career research assistant. Using the industry pillars and sub‑domains "
        f"provided below, generate a JSON array (max {MAX_NEW_COMPANIES} items) of Indian or global companies "
        f"that have a GCC/office in India and operate in **any** of those areas. "
        f"For each company, include the exact CSV columns used in the AI‑Job‑Search project: "
        f"{', '.join(CSV_HEADERS)}. "
        "If a field is unknown, use an empty string. Use the most recent public data (2024/2025).\n"
        f"\nIndustry pillars: {pillar_list}\n"
        f"Sub‑domains: {sub_list}"
    )

    print("[headhunt] Querying OpenRouter (free tier)…")
    response, usage = ask_with_usage(
        prompt,
        model=DEFAULT_FREE_MODEL,
        max_tokens=1200,
        json_mode=True,
    )
    print(
        f"[headhunt] Tokens – prompt:{usage.get('prompt_tokens')} "
        f"completion:{usage.get('completion_tokens')} total:{usage.get('total_tokens')}"
    )

    try:
        new_companies = json.loads(response)
        if not isinstance(new_companies, list):
            raise ValueError("Response is not a list")
    except Exception as e:
        print("[headhunt] Warning: could not parse LLM response as JSON.")
        print("Raw response:\n", response)
        sys.exit(1)

    # Deduplicate against existing master list (case‑insensitive name match)
    existing_names = {row.get("company_name", "").strip().lower() for row in existing}
    filtered = []
    for comp in new_companies:
        name = comp.get("company_name", "").strip().lower()
        if name and name not in existing_names:
            # Ensure all required keys exist (fill missing with empty string)
            full_entry = {key: comp.get(key, "") for key in CSV_HEADERS}
            filtered.append(full_entry)
            existing_names.add(name)

    total_added = len(filtered)
    print(f"[headhunt] Added {total_added} new companies after deduplication.")

    # Write the combined list (original + new) to the expanded CSV
    combined = existing + filtered
    write_csv(OUTPUT_CSV, combined)
    print(f"[headhunt] Expanded CSV written to {OUTPUT_CSV} with {len(combined)} rows (plus header).")

if __name__ == "__main__":
    main()
