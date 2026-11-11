#!/usr/bin/env python3
"""Iterate over career site accounts and determine whether each is a known
site or a new one.

Evaluates URLs deterministically first (0 tokens), then via local Ollama if
running offline, and finally via OpenRouter `:free` (chore tier) only when
explicitly opted in (`--allow-openrouter` or `OPENROUTER_ON_DEMAND_ENABLED=1`).
"""
import argparse
import json
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
ACCOUNTS_PATH = BASE_DIR / "user_inputs" / "candidate_accounts.json"
KNOWN_PATH = BASE_DIR / "user_inputs" / "known_career_sites.json"

KNOWN_CAREER_DOMAIN_HINTS = (
    "greenhouse.io", "lever.co", "myworkdayjobs.com", "smartrecruiters.com",
    "ashbyhq.com", "taleo.net", "successfactors", "icims.com",
    "bamboohr.com", "workable.com", "jobs.", "careers.", "apply.", "hire.",
)

def load_known():
    if KNOWN_PATH.is_file():
        return set(json.loads(KNOWN_PATH.read_text()))
    return set()

def save_known(domains):
    KNOWN_PATH.write_text(json.dumps(sorted(list(domains)), indent=2))

def query_model(domain: str) -> bool:
    """Classify domain locally first, then Ollama, then gated OpenRouter :free chore tier."""
    dom_l = (domain or "").strip().lower()
    if any(hint in dom_l for hint in KNOWN_CAREER_DOMAIN_HINTS):
        return True

    from intelligence.llm_clients.openrouter import (
        ask,
        ask_local_ollama_if_online,
        is_on_demand_enabled,
    )

    prompt = f"Is the website https://{domain} a career or job application portal? Respond with only yes or no."
    local_ans = ask_local_ollama_if_online(prompt, max_tokens=10, temperature=0.0)
    if local_ans:
        return local_ans.strip().lower().startswith("yes")

    if not is_on_demand_enabled():
        raise PermissionError("OpenRouter disabled (pass --allow-openrouter to classify unknown domain).")

    answer = ask(
        prompt,
        system="Respond strictly with 'yes' or 'no'.",
        model="auto",
        task_tier="chore",
        temperature=0.0,
        max_tokens=10,
    ).strip().lower()
    return answer.startswith("yes")

def main():
    parser = argparse.ArgumentParser(description="Classify career-site domains locally or via gated :free tier")
    parser.add_argument("--allow-openrouter", action="store_true", help="Enable OpenRouter :free chore classification for unknown domains")
    args = parser.parse_args()
    if args.allow_openrouter:
        os.environ["OPENROUTER_ON_DEMAND_ENABLED"] = "1"

    if not ACCOUNTS_PATH.is_file():
        raise FileNotFoundError(f"Accounts file not found: {ACCOUNTS_PATH}")
    data = json.loads(ACCOUNTS_PATH.read_text())
    accounts = data.get("accounts", [])
    known_domains = load_known()
    new_domains = set()

    for acct in accounts:
        domain = acct.get("domain")
        if not domain:
            continue
        if domain in known_domains:
            status = "known"
        else:
            print(f"Checking domain: {domain} ...")
            try:
                is_career = query_model(domain)
                status = "career_site" if is_career else "non_career"
                if is_career:
                    new_domains.add(domain)
            except Exception as e:
                status = f"error: {e}"
        print(f"{domain}: {status}")

    if new_domains:
        known_domains.update(new_domains)
        save_known(known_domains)
        print(f"Added {len(new_domains)} new career domains to known list.")

if __name__ == "__main__":
    main()
