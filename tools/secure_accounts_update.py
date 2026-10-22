#!/usr/bin/env python3
"""Generate a secure version of `candidate_accounts.json` where credentials are referenced
via environment variables instead of being stored in plain text.

The script reads `user_inputs/candidate_accounts.json`, constructs placeholder keys for
each account (e.g., `GOOGLE_USERNAME`, `GOOGLE_PASSWORD`), and writes a new JSON file
`user_inputs/secure_candidate_accounts.json` containing those placeholders.

It also prints suggested entries for `.env.example` so you can add the actual secrets
to a git‑ignored `.env` file.

The script uses only the standard library.
"""
import json
import os
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_PATH = BASE_DIR / "user_inputs" / "candidate_accounts.json"
OUTPUT_PATH = BASE_DIR / "user_inputs" / "secure_candidate_accounts.json"

def sanitize_name(name: str) -> str:
    """Create a safe environment variable prefix from the company name."""
    return re.sub(r"[^A-Z0-9]", "_", name.upper())

def main():
    if not INPUT_PATH.is_file():
        raise FileNotFoundError(f"Input file not found: {INPUT_PATH}")
    data = json.loads(INPUT_PATH.read_text())
    accounts = data.get("accounts", [])
    env_suggestions = []
    for acct in accounts:
        prefix = sanitize_name(acct.get("company", "UNKNOWN"))
        user_var = f"{prefix}_USERNAME"
        pass_var = f"{prefix}_PASSWORD"
        acct["username"] = f"${{{user_var}}}"
        acct["password"] = f"${{{pass_var}}}"
        env_suggestions.append(f"# {acct.get('company')} credentials")
        env_suggestions.append(f"{user_var}=your_username_here")
        env_suggestions.append(f"{pass_var}=your_password_here")
        env_suggestions.append("")
    OUTPUT_PATH.write_text(json.dumps(data, indent=2))
    print(f"Secure account file written to {OUTPUT_PATH}")
    print("\nAdd the following entries to your .env (git‑ignored) file:\n")
    print("\n".join(env_suggestions))

if __name__ == "__main__":
    main()
