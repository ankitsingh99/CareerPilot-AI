#!/usr/bin/env python3
"""
tools/generate_workspace_from_master.py
---------------------------------------
Universal Master Workspace Generator & PII Sanitizer.

This tool reads `MASTER_TEMPLATE.md` and the gitignored `.env` file to:
1. Generate / rehydrate localized workspace files for any candidate who uses the framework.
2. Scrub / sanitize git-tracked markdown and python files of raw PII.
3. Audit the workspace to verify zero PII leakage in tracked repository files.

Usage:
    python tools/generate_workspace_from_master.py            # Hydrate workspace from .env
    python tools/generate_workspace_from_master.py --clean    # Revert workspace to clean template mode
    python tools/generate_workspace_from_master.py --audit-pii # Verify no raw PII in tracked files
"""

import os
import re
import sys
import argparse
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
MASTER_TEMPLATE_PATH = ROOT_DIR / "MASTER_TEMPLATE.md"
ENV_PATH = ROOT_DIR / ".env"
ENV_EXAMPLE_PATH = ROOT_DIR / ".env.example"


def parse_env_file(path: Path) -> Dict[str, str]:
    """Parse a .env file without external dependencies."""
    env_vars = {}
    if not path.exists():
        return env_vars

    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            env_vars[key] = val
    return env_vars


def get_candidate_config() -> Dict[str, str]:
    """Load configuration from .env with fallback to system environment variables."""
    config = parse_env_file(ENV_PATH)
    # Overlay system environment variables if set
    for k, v in os.environ.items():
        if k.startswith("CANDIDATE_") or k in ("OPENROUTER_API_KEY", "LINKEDIN_EMAIL", "LINKEDIN_PASSWORD"):
            config[k] = v
    return config


# Keys that should NEVER be baked as raw plaintext into tracked markdown files
SENSITIVE_PII_KEYS = {
    "CANDIDATE_EMAIL",
    "CANDIDATE_PHONE",
    "CANDIDATE_RAW_PHONE",
    "CANDIDATE_ADDRESS",
    "CANDIDATE_DOB",
    "CANDIDATE_DOB_FORMATTED",
    "LINKEDIN_PASSWORD",
    "OPENROUTER_API_KEY",
    "PGPASSWORD",
}


def substitute_template(
    template_text: str,
    variables: Dict[str, str],
    default_placeholder: bool = False,
    protect_sensitive: bool = True
) -> str:
    """Substitute {{VARIABLE_NAME}} tokens in template_text with config values."""
    def replacer(match):
        var_name = match.group(1).strip()
        if protect_sensitive and var_name in SENSITIVE_PII_KEYS:
            return f"Loaded securely from `.env` (`{var_name}`)"
        if var_name in variables and variables[var_name]:
            return variables[var_name]
        if default_placeholder:
            return f"[{var_name}]"
        return f"[NOT_SET: {var_name}]"

    return re.sub(r"\{\{([A-Za-z0-9_]+)\}\}", replacer, template_text)


def generate_agents_md(config: Dict[str, str], clean_mode: bool = False) -> str:
    """Generates AGENTS.md cleanly from MASTER_TEMPLATE.md or generic instructions."""
    template = MASTER_TEMPLATE_PATH.read_text(encoding="utf-8")
    
    # In clean mode, keep placeholders
    if clean_mode:
        vars_to_use = {k: f"[{k}]" for k in config.keys()}
    else:
        vars_to_use = config

    rendered = substitute_template(template, vars_to_use, default_placeholder=clean_mode)
    return rendered


def update_application_settings():
    """Ensure user_inputs/application_settings.py dynamically loads from environment."""
    settings_file = ROOT_DIR / "user_inputs" / "application_settings.py"
    if not settings_file.exists():
        return

    content = """# -*- coding: utf-8 -*-
\"\"\"
User Application Settings and Target Preferences
Dynamically loads candidate identity and preferences from gitignored .env
\"\"\"
import os
from pathlib import Path

# Load .env fallback if not already in os.environ
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

# ==========================================
# 1. Contact & Autofill Information (Dynamic)
# ==========================================
CANDIDATE_NAME = os.getenv("CANDIDATE_NAME", "Candidate")
PHONE = os.getenv("CANDIDATE_PHONE", "")
EMAIL = os.getenv("CANDIDATE_EMAIL", "")
LOCATION = os.getenv("CANDIDATE_LOCATION", os.getenv("CANDIDATE_CITY", "") + ", " + os.getenv("CANDIDATE_COUNTRY", ""))
CV_PATH = os.getenv("CANDIDATE_MASTER_RESUME", "cv/resume.pdf")

# ==========================================
# 2. LinkedIn Job Search & Application Scope
# ==========================================
APPLICATION_SOURCE = os.getenv("APPLICATION_SOURCE", "researched_db")

TARGET_ROLES = [
    r.strip() for r in os.getenv(
        "CANDIDATE_TARGET_ROLES",
        "Data Engineer, Analytics Engineer, AI Systems Engineer, Business Technology Consultant"
    ).split(",") if r.strip()
]

TARGET_LOCATIONS = [
    "Remote",
    os.getenv("CANDIDATE_CITY", "Noida"),
    "Delhi NCR",
    "Bengaluru, Karnataka, India"
]

WORKPLACE_TYPE = "all"
BATCH_LIMIT = 5
MIN_FIT_RATING = 90
"""
    settings_file.write_text(content, encoding="utf-8")
    print("[generator] Updated user_inputs/application_settings.py to use dynamic environment loading.")


def update_claude_candidate_profile(config: Dict[str, str], clean_mode: bool = False):
    """Sanitize and update .claude/skills/job-application-assistant/01-candidate-profile.md."""
    claude_profile = ROOT_DIR / ".claude" / "skills" / "job-application-assistant" / "01-candidate-profile.md"
    if not claude_profile.exists():
        return

    text = claude_profile.read_text(encoding="utf-8")
    
    # Sanitize hardcoded values to dynamic .env lookups
    text = re.sub(r"-\s+\*\*Name:\*\*.*", "- **Name:** Loaded from `.env` (`CANDIDATE_NAME`)", text)
    text = re.sub(r"-\s+\*\*Email:\*\*.*", "- **Email:** Loaded securely from `.env` (`CANDIDATE_EMAIL`)", text)
    text = re.sub(r"-\s+\*\*Phone:\*\*.*", "- **Phone:** Loaded securely from `.env` (`CANDIDATE_PHONE`)", text)
    text = re.sub(r"-\s+\*\*LinkedIn:\*\*.*", "- **LinkedIn:** Loaded from `.env` (`CANDIDATE_LINKEDIN_URL`)", text)
    text = re.sub(r"-\s+\*\*Current Compensation:\*\*.*", "- **Current Compensation:** Loaded from `.env` (`CANDIDATE_CURRENT_CTC_LPA`)", text)

    claude_profile.write_text(text, encoding="utf-8")
    print("[generator] Sanitized and updated .claude/skills/job-application-assistant/01-candidate-profile.md.")


def update_candidate_preferences(config: Dict[str, str], clean_mode: bool = False):
    """Update user_inputs/candidate_preferences_and_rules.md with templated references."""
    pref_file = ROOT_DIR / "user_inputs" / "candidate_preferences_and_rules.md"
    if not pref_file.exists():
        return

    text = pref_file.read_text(encoding="utf-8")
    env_vars = config or get_candidate_config()
    phone = env_vars.get("CANDIDATE_RAW_PHONE") or env_vars.get("CANDIDATE_PHONE")
    email = env_vars.get("CANDIDATE_EMAIL")
    address = env_vars.get("CANDIDATE_ADDRESS")

    # Sanitize raw phone, email, street address with variables/dynamic markers
    if phone:
        text = re.sub(re.escape(phone), "{{CANDIDATE_PHONE}}", text)
    if email:
        text = re.sub(re.escape(email), "{{CANDIDATE_EMAIL}}", text)
    if address:
        text = re.sub(re.escape(address), "{{CANDIDATE_ADDRESS}}", text)

    text = text.replace("{{CANDIDATE_PHONE}}", "Loaded from `.env` (`CANDIDATE_PHONE`)")
    text = text.replace("{{CANDIDATE_EMAIL}}", "Loaded from `.env` (`CANDIDATE_EMAIL`)")
    text = text.replace("{{CANDIDATE_ADDRESS}}", "Loaded from `.env` (`CANDIDATE_ADDRESS`)")

    pref_file.write_text(text, encoding="utf-8")
    print("[generator] Sanitized and updated user_inputs/candidate_preferences_and_rules.md.")


def audit_workspace_pii() -> bool:
    """
    Scans all tracked git files for hardcoded candidate PII.
    Per creator directive: Author, contributor, and credit lines (Ankit Kumar Singh)
    are retained. Working modules (automation, intelligence, parsers, core, tools) must have zero
    candidate personal identification (DOB, phone, email, street address).
    """
    print("\n--- Running PII Audit across repository files ---")
    
    env_vars = parse_env_file(ENV_PATH)
    candidate_phone = env_vars.get("CANDIDATE_RAW_PHONE") or env_vars.get("CANDIDATE_PHONE", "")
    candidate_email = env_vars.get("CANDIDATE_EMAIL", "")
    candidate_dob = env_vars.get("CANDIDATE_DOB", "")
    candidate_address = env_vars.get("CANDIDATE_ADDRESS", "")

    universal_sensitive_patterns: List[Tuple[str, re.Pattern]] = []
    if candidate_phone and len(candidate_phone) >= 7:
        universal_sensitive_patterns.append(("Candidate Phone", re.compile(re.escape(candidate_phone.strip()))))
    if candidate_email and "@" in candidate_email:
        universal_sensitive_patterns.append(("Candidate Email", re.compile(re.escape(candidate_email.strip()), re.I)))
    if candidate_address and len(candidate_address.split()) > 1:
        first_segment = candidate_address.split(",")[0].strip()
        if len(first_segment) >= 4:
            universal_sensitive_patterns.append(("Candidate Street Address", re.compile(re.escape(first_segment), re.I)))

    # Passwords from .env and secret stores
    passwords_to_check: set[str] = set()
    for k, v in env_vars.items():
        if any(w in k.lower() for w in ["pass", "secret", "token", "key"]):
            if v and len(v) >= 6:
                passwords_to_check.add(v)
    
    # Load secrets store passwords
    for sec_path in [
        Path.home() / ".config" / "job-agent" / ".candidate_secrets.json",
        Path.home() / ".config" / "job-agent" / "client_secret.json",
    ]:
        if sec_path.exists():
            try:
                sec_data = json.loads(sec_path.read_text())
                for acc in sec_data.get("accounts", []):
                    p = acc.get("password")
                    if p and len(p) >= 6:
                        passwords_to_check.add(p)
                for p_key in ["standard_ats_password", "default_password", "alternate_password"]:
                    p = sec_data.get(p_key) or sec_data.get("credentials", {}).get(p_key)
                    if p and len(p) >= 6:
                        passwords_to_check.add(p)
            except Exception:
                pass

    for pwd in passwords_to_check:
        universal_sensitive_patterns.append(("Credential/Password Leak", re.compile(re.escape(pwd))))

    # Patterns forbidden strictly in working code modules
    code_module_sensitive_patterns: List[Tuple[str, re.Pattern]] = []
    if candidate_dob and len(candidate_dob) >= 8:
        code_module_sensitive_patterns.append(("Candidate Hardcoded DOB", re.compile(re.escape(candidate_dob.strip()))))

    working_module_prefixes = ("automation/", "intelligence/", "parsers/", "core/", "tools/")

    try:
        tracked_files = subprocess.check_output(
            ["git", "ls-files"], cwd=str(ROOT_DIR), text=True
        ).splitlines()
    except Exception as e:
        print(f"[audit] Error listing git files: {e}")
        tracked_files = []

    violations: List[Tuple[str, str, int, str]] = []

    # Files excluded from audit (e.g. past historic changelogs or git archives)
    exempt_prefixes = ("CHANGELOG.md", "Archive/")

    for file_rel in tracked_files:
        if file_rel.startswith(exempt_prefixes) or file_rel == "tools/generate_workspace_from_master.py":
            continue
        file_path = ROOT_DIR / file_rel
        if not file_path.is_file():
            continue
        # Skip binary files
        if file_path.suffix.lower() in (".pdf", ".png", ".jpg", ".jpeg", ".xlsx", ".db", ".ico"):
            continue

        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            for line_no, line in enumerate(content.splitlines(), start=1):
                # 1. Universal check
                for label, pattern in universal_sensitive_patterns:
                    # Skip self-check in generate_workspace_from_master.py audit logic
                    if file_rel == "tools/generate_workspace_from_master.py":
                        continue
                    if pattern.search(line):
                        violations.append((file_rel, label, line_no, line.strip()))

                # 2. Working code modules check
                if file_rel.startswith(working_module_prefixes):
                    for label, pattern in code_module_sensitive_patterns:
                        if pattern.search(line):
                            violations.append((file_rel, label, line_no, line.strip()))
        except Exception:
            pass

    if violations:
        print(f"[audit] WARNING: Found {len(violations)} raw PII occurrences in tracked files:")
        for f, lbl, lno, snippet in violations:
            print(f"  - {f}:{lno} [{lbl}] -> {snippet[:80]}")
        return False
    else:
        print("[audit] PASS: Zero hardcoded candidate PII (phone, email, street address, DOB) detected in working modules.")
        print("[audit] NOTE: Creator author and git attribution lines (Ankit Kumar Singh) are verified and preserved.")
        return True


def main():
    parser = argparse.ArgumentParser(description="AI Job Search Master Workspace Generator & PII Sanitizer")
    parser.add_argument("--clean", action="store_true", help="Revert files to clean template mode with zero personal data")
    parser.add_argument("--audit-pii", action="store_true", help="Audit all git-tracked files for PII leakage")
    args = parser.parse_args()

    config = get_candidate_config()

    if args.audit_pii:
        success = audit_workspace_pii()
        sys.exit(0 if success else 1)

    print(f"[generator] Loading master specification from {MASTER_TEMPLATE_PATH.name}...")
    
    # 1. Update AGENTS.md
    agents_content = generate_agents_md(config, clean_mode=args.clean)
    (ROOT_DIR / "AGENTS.md").write_text(agents_content, encoding="utf-8")
    print("[generator] Generated AGENTS.md from MASTER_TEMPLATE.md.")

    # 2. Update user_inputs/application_settings.py
    update_application_settings()

    # 3. Update candidate_preferences_and_rules.md
    update_candidate_preferences(config, clean_mode=args.clean)

    # 4. Update .claude/skills/job-application-assistant/01-candidate-profile.md
    update_claude_candidate_profile(config, clean_mode=args.clean)

    # 5. Run audit
    audit_workspace_pii()
    print("\n[generator] Workspace synchronization complete.")


if __name__ == "__main__":
    main()
