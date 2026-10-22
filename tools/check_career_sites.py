#!/usr/bin/env python3
"""Iterate over career site accounts and determine whether each is a known
site or a new one.

The script reads `user_inputs/candidate_accounts.json` and optionally a file
`user_inputs/known_career_sites.json` (a simple JSON list of domain strings).
For any account whose domain is not present in the known list, the script calls
the free OpenRouter model `google/gemma-2-9b-it:free` to ask the model if the
URL is a career‑site / job‑application portal. The result is printed and the
new domain is added to the known list for future runs.

Credentials (usernames / passwords) are **not** sent – only the domain is
used. The OpenRouter API key must be stored in an environment variable
`OPENROUTER_API_KEY` (git‑ignored `.env`).
"""
import json
import os
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ACCOUNTS_PATH = BASE_DIR / "user_inputs" / "candidate_accounts.json"
KNOWN_PATH = BASE_DIR / "user_inputs" / "known_career_sites.json"

OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "google/gemma-2-9b-it:free"

def load_known():
    if KNOWN_PATH.is_file():
        return set(json.loads(KNOWN_PATH.read_text()))
    return set()

def save_known(domains):
    KNOWN_PATH.write_text(json.dumps(sorted(list(domains)), indent=2))

def query_model(domain):
    prompt = f"Is the website https://{domain} a career or job application portal? Respond with only ""yes"" or ""no""."
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": 10
    }
    # Use curl to avoid adding external dependencies
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENROUTER_API_KEY not set in environment")
    curl_cmd = [
        "curl", "-s", "-X", "POST", OPENROUTER_ENDPOINT,
        "-H", f"Authorization: Bearer {api_key}",
        "-H", "Content-Type: application/json",
        "-d", json.dumps(payload)
    ]
    result = subprocess.run(curl_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Curl failed: {result.stderr}")
    try:
        resp = json.loads(result.stdout)
        answer = resp["choices"][0]["message"]["content"].strip().lower()
        return answer.startswith("yes")
    except Exception as e:
        raise RuntimeError(f"Failed to parse OpenRouter response: {e}")

def main():
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
