#!/usr/bin/env python3
"""
adjacent_companies_query.py
~~~~~~~~~~~~~~~~~~~~~~~~~~
A tiny helper that asks a free‑tier OpenRouter model for a few Indian companies
matching a specific domain/sub‑domain. The prompt is deliberately simple so the
LLM response can be parsed reliably as JSON.
"""

import json
import sys
from pathlib import Path

# Ensure repo root on sys.path for the openrouter wrapper
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from intelligence.llm_clients.openrouter import ask_with_usage, DEFAULT_FREE_MODEL

# ---------------------------------------------------------------------------
# Configuration – adjust as needed
# ---------------------------------------------------------------------------
DOMAIN = "Data Governance & Engineering"
SUB_DOMAIN = "Analytics, Consulting, AI Agent Development"
MAX_COMPANIES = 5

prompt = (
    f"List up to {MAX_COMPANIES} Indian companies (with career site URLs) that operate in the "
    f"domain '{DOMAIN}' and sub‑domain '{SUB_DOMAIN}'. Return the result as a JSON array, "
    "where each object has the keys: company_name, gcc_india_hub, domain_pillar, "
    "sub_domain, career_portal_url. If you do not know a field, use an empty string."
)

print("[adjacent] Querying OpenRouter (free tier)…")
response, usage = ask_with_usage(
    prompt,
    model=DEFAULT_FREE_MODEL,
    max_tokens=500,
    json_mode=True,
)
print(f"[adjacent] Tokens – prompt:{usage.get('prompt_tokens')} completion:{usage.get('completion_tokens')} total:{usage.get('total_tokens')}")

try:
    data = json.loads(response)
    print("[adjacent] Parsed JSON response:")
    print(json.dumps(data, indent=2, ensure_ascii=False))
except json.JSONDecodeError:
    print("[adjacent] Warning: could not parse LLM response as JSON.")
    print("Raw response:")
    print(response)

if __name__ == "__main__":
    sys.exit(0)
