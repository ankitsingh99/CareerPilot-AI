#!/usr/bin/env python3
"""
fetch_exl_info.py
~~~~~~~~~~~~~~~~~~
Utility that asks a free‑tier OpenRouter model for a structured JSON record about
EXL Service. The record matches the column layout of `master_companies_mdm.csv`
so the result can be merged back into the CSV if desired.
"""

import json
import sys
from pathlib import Path

# Ensure repository root is on the import path for the openrouter wrapper
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from intelligence.llm_clients.openrouter import ask_with_usage, DEFAULT_FREE_MODEL

# ---------------------------------------------------------------------------
# Prompt – we ask the model to fill every column. Empty strings are acceptable
# for unknown fields.
# ---------------------------------------------------------------------------
prompt = (
    "Provide a JSON object describing EXL Service (an Indian data & consulting firm) "
    "with the following keys exactly as they appear in the CSV used by the "
    "AI‑Job‑Search project: company_name, gcc_india_hub, domain_pillar, sub_domain, "
    "persona_match_rationale, recommended_target_roles, candidate_fit_score, "
    "india_locations, core_functional_focus, compensation_benchmark, "
    "network_contacts, career_portal_url, company_overview. Use empty strings for any "
    "field you do not know."
)

print("[exl] Querying OpenRouter (free tier)…")
response, usage = ask_with_usage(
    prompt,
    model=DEFAULT_FREE_MODEL,
    max_tokens=800,
    json_mode=True,
)
print(f"[exl] Tokens – prompt:{usage.get('prompt_tokens')} completion:{usage.get('completion_tokens')} total:{usage.get('total_tokens')}")

try:
    data = json.loads(response)
    print("[exl] Parsed JSON response:")
    print(json.dumps(data, indent=2, ensure_ascii=False))
except json.JSONDecodeError:
    print("[exl] Warning: could not parse LLM response as JSON.")
    print("Raw response:")
    print(response)

if __name__ == "__main__":
    sys.exit(0)
