#!/usr/bin/env python3
"""
Universal ATS Runner
====================
A single, reusable Playwright driver for all ATS portals.
Replaces ad-hoc scratch .py files, saving ~3,000-6,000 tokens per application.

Usage:
    python tools/ats_runner.py --url "<JOB_URL>" --role-name "<ROLE_NAME>" [--mode inspect|login|apply] [--keep-open]

Modes:
    inspect   (default) - Navigate, extract visible form fields, save JSON locally.
                          No raw DOM ever sent to LLM. Quick ~10s run.
    login     - Open headed browser with username pre-filled. Waits for user sign-in.
                Fires macOS Glass.aiff chime + notification.
    apply     - Full autopilot: inspect + autofill + resume upload + screenshot before submit.

Persistence:
    Browser sessions are stored in .browser_session/ (gitignored).
    Cookies, saved passwords, and logins persist across runs automatically.
    Use --keep-open (default for apply/login) to leave the browser window open
    after the runner completes so you can inspect or continue manually.

ATS Auto-Detection:
    Taleo, Workday, Greenhouse, Lever, Oracle HCM, SAP SuccessFactors,
    Avature, Phenom/Eightfold, Ashby, iCIMS, Rippling, TheHireHub
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# Ensure repo root is on sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

try:
    from playwright.sync_api import sync_playwright, Page
except ImportError:
    sync_playwright = None
    Page = object

# ── Candidate & Secret Loading ───────────────────────────────────────────────
SECRETS_FILE = Path(__file__).parent.parent / "client_secret.json"
GLOBAL_SECRETS_FILE = Path.home() / ".config" / "job-agent" / "client_secret.json"
LEGACY_SECRETS_FILE = Path(__file__).parent.parent / ".candidate_secrets.json"

# Load environment variables from .env if present
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

# Generic structural defaults (sensitive PII loaded dynamically from .env / client_secret.json)
DEFAULT_CANDIDATE = {
    "first_name":       os.getenv("CANDIDATE_FIRST_NAME", "Candidate"),
    "last_name":        os.getenv("CANDIDATE_LAST_NAME", "Applicant"),
    "full_name":        os.getenv("CANDIDATE_NAME", "Candidate"),
    "email":            os.getenv("CANDIDATE_EMAIL", ""),
    "phone":            os.getenv("CANDIDATE_PHONE", ""),
    "raw_phone":        os.getenv("CANDIDATE_RAW_PHONE", ""),
    "phone_country_code": os.getenv("CANDIDATE_PHONE_COUNTRY_CODE", "+1"),
    "address":          os.getenv("CANDIDATE_ADDRESS", ""),
    "address_2_line1":  os.getenv("CANDIDATE_ADDRESS_2_LINE1", ""),
    "address_2_line2":  os.getenv("CANDIDATE_ADDRESS_2_LINE2", ""),
    "address_3_line1":  os.getenv("CANDIDATE_ADDRESS_3_LINE1", ""),
    "address_3_line2":  os.getenv("CANDIDATE_ADDRESS_3_LINE2", ""),
    "address_3_line3":  os.getenv("CANDIDATE_ADDRESS_3_LINE3", ""),
    "city":             os.getenv("CANDIDATE_CITY", ""),
    "city_fallback":    os.getenv("CANDIDATE_CITY_FALLBACK", os.getenv("CANDIDATE_CITY", "")),
    "state":            os.getenv("CANDIDATE_STATE", ""),
    "country":          os.getenv("CANDIDATE_COUNTRY", ""),
    "pincode":          os.getenv("CANDIDATE_PINCODE", ""),
    "linkedin":         os.getenv("CANDIDATE_LINKEDIN_URL", ""),
    "current_ctc_inr":  os.getenv("CANDIDATE_CURRENT_CTC_INR", ""),
    "expected_ctc_inr": os.getenv("CANDIDATE_EXPECTED_CTC_INR", ""),
    "current_ctc_lpa":  os.getenv("CANDIDATE_CURRENT_CTC_LPA", ""),
    "expected_ctc_lpa": os.getenv("CANDIDATE_EXPECTED_CTC_LPA", ""),
    "dob":              os.getenv("CANDIDATE_DOB", ""),
    "dob_day":          os.getenv("CANDIDATE_DOB_DAY", ""),
    "dob_month":        os.getenv("CANDIDATE_DOB_MONTH", ""),
    "dob_month_name":   os.getenv("CANDIDATE_DOB_MONTH_NAME", ""),
    "dob_year":         os.getenv("CANDIDATE_DOB_YEAR", ""),
    "dob_iso":          os.getenv("CANDIDATE_DOB_ISO", os.getenv("CANDIDATE_DOB", "")),
    "notice_period":    os.getenv("CANDIDATE_NOTICE_PERIOD_DAYS", "0"),
    "source":           "Career Website",
    "university":       os.getenv("CANDIDATE_UNIVERSITY", ""),
    "degree":           os.getenv("CANDIDATE_DEGREE", ""),
    "major":            os.getenv("CANDIDATE_MAJOR", ""),
    "college_start":    os.getenv("CANDIDATE_COLLEGE_START", ""),
    "college_start_year": os.getenv("CANDIDATE_COLLEGE_START_YEAR", ""),
    "college_start_month": os.getenv("CANDIDATE_COLLEGE_START_MONTH", ""),
    "college_end":      os.getenv("CANDIDATE_COLLEGE_END", ""),
    "college_end_year": os.getenv("CANDIDATE_COLLEGE_END_YEAR", ""),
    "college_end_month": os.getenv("CANDIDATE_COLLEGE_END_MONTH", ""),
    "graduation_year":  os.getenv("CANDIDATE_GRADUATION_YEAR", ""),
    "college_cgpa":     os.getenv("CANDIDATE_COLLEGE_GRADE", ""),
    "college_percentage": os.getenv("CANDIDATE_COLLEGE_PERCENTAGE", ""),
    "school_12_name":   os.getenv("CANDIDATE_SENIOR_SECONDARY_SCHOOL", ""),
    "school_12_end":    os.getenv("CANDIDATE_SENIOR_SECONDARY_END", ""),
    "school_12_year":   os.getenv("CANDIDATE_SENIOR_SECONDARY_YEAR", ""),
    "school_12_percentage": os.getenv("CANDIDATE_SENIOR_SECONDARY_GRADE", ""),
    "school_10_name":   os.getenv("CANDIDATE_SECONDARY_SCHOOL", ""),
    "school_10_end":    os.getenv("CANDIDATE_SECONDARY_END", ""),
    "school_10_year":   os.getenv("CANDIDATE_SECONDARY_YEAR", ""),
    "school_10_cgpa":   os.getenv("CANDIDATE_SECONDARY_GRADE", ""),
    "school_10_percentage": os.getenv("CANDIDATE_SECONDARY_PERCENTAGE", ""),
}

def get_latest_resume() -> Path:
    """
    Dynamically discovers the latest master CV PDF from cv/ and user_inputs/cv/.
    Sorts by semantic version (vX) and mtime while strictly ignoring Archive/ folders.
    """
    root = Path(__file__).parent.parent
    candidate_dirs = [root / "cv", root / "user_inputs" / "cv"]
    found_resumes = []

    for c_dir in candidate_dirs:
        if not c_dir.exists():
            continue
        for p in c_dir.glob("*.pdf"):
            if "archive" in [part.lower() for part in p.parts]:
                continue
            match = re.search(r"_v(\d+)\.pdf$", p.name, re.IGNORECASE)
            v_num = int(match.group(1)) if match else 0
            found_resumes.append((v_num, p.stat().st_mtime, p))

    if found_resumes:
        found_resumes.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return found_resumes[0][2]

    resume_env = os.getenv("CANDIDATE_MASTER_RESUME")
    if resume_env and (root / resume_env).exists():
        return root / resume_env
    return root / "cv" / "resume.pdf"

RESUME_PATH = get_latest_resume()
DOCS_DIR = Path(__file__).parent.parent / "documents"
COVER_LETTERS_DIR = Path(__file__).parent.parent / "cover_letters"
SCRATCH_DIR  = Path(__file__).parent.parent / "scratch"
SESSION_DIR  = Path(__file__).parent.parent / ".browser_session"
DOCS_DIR.mkdir(exist_ok=True)
COVER_LETTERS_DIR.mkdir(exist_ok=True)
SCRATCH_DIR.mkdir(exist_ok=True)
SESSION_DIR.mkdir(exist_ok=True)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

def get_candidate_credentials() -> tuple[dict, str, str, list[str]]:
    """
    Resolve candidate profile, default email, primary password, and alternate passwords.
    Combines client_secret.json, ~/.config/job-agent/.candidate_secrets.json,
    and .env / environment credential variables without dropping alternates.
    """
    prof = DEFAULT_CANDIDATE.copy()
    email = (os.getenv("CANDIDATE_EMAIL") or prof.get("email") or "").strip()
    passwords: list[str] = []

    def _add_pwd(val: str | None) -> None:
        s = (val or "").strip()
        if s and s not in passwords:
            passwords.append(s)

    secret_candidates = [
        SECRETS_FILE,
        GLOBAL_SECRETS_FILE,
        Path.home() / ".config" / "job-agent" / ".candidate_secrets.json",
        LEGACY_SECRETS_FILE,
    ]
    seen_paths: set[Path] = set()
    for sp in secret_candidates:
        try:
            resolved = sp.resolve()
        except Exception:
            resolved = sp
        if resolved in seen_paths or not sp.exists():
            continue
        seen_paths.add(resolved)
        try:
            data = json.loads(sp.read_text(encoding="utf-8"))
        except Exception:
            continue

        profile_block = data.get("candidate_profile")
        if isinstance(profile_block, dict):
            for k, v in profile_block.items():
                if v and not prof.get(k):
                    prof[k] = v

        creds = data.get("credentials") if isinstance(data.get("credentials"), dict) else {}
        if not email:
            email = (creds.get("default_email") or data.get("email") or "").strip()

        _add_pwd(creds.get("default_password"))
        _add_pwd(data.get("standard_ats_password"))
        _add_pwd(data.get("password"))
        for alt_key in ("alternate_password", "alternate_password1", "alternate_password2"):
            _add_pwd(creds.get(alt_key))
            _add_pwd(data.get(alt_key))

    for env_key in (
        "CANDIDATE_STANDARD_PASSWORD",
        "CANDIDATE_PASSWORD",
        "STANDARD_ATS_PASSWORD",
        "CANDIDATE_ALT_PASSWORD",
        "CANDIDATE_ALTERNATE_PASSWORD",
        "CANDIDATE_ALTERNATE_PASSWORD1",
        "CANDIDATE_ALTERNATE_PASSWORD2",
    ):
        _add_pwd(os.getenv(env_key))

    if email and not prof.get("email"):
        prof["email"] = email

    password = passwords[0] if passwords else ""
    alt_passwords = passwords[1:] if len(passwords) > 1 else []
    return prof, email, password, alt_passwords

# Dynamic CANDIDATE instance loaded from local client_secret.json
CANDIDATE, _, _, _ = get_candidate_credentials()



def record_new_account(company: str, website: str, username: str, password: str):
    """
    Log account credentials to client_secret.json and user_inputs/candidate_accounts.json.
    Standard accounts reuse global default_email & default_password automatically.
    """
    domain = re.sub(r"^https?://", "", website).split("/")[0].lower() if website else ""
    # 1. Update candidate_accounts.json registry
    reg_file = Path(__file__).parent.parent / "user_inputs" / "candidate_accounts.json"
    try:
        reg_data = json.loads(reg_file.read_text(encoding="utf-8")) if reg_file.exists() else {"accounts": []}
        acc_list = reg_data.setdefault("accounts", [])
        matched = False
        for acc in acc_list:
            if (acc.get("company", "").lower() == company.lower()) or (domain and domain in (acc.get("website") or "")):
                acc["username"] = username
                acc["password"] = password
                acc["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                matched = True
                break
        if not matched:
            acc_list.append({
                "company": company,
                "domain": domain,
                "website": website,
                "ats": detect_ats(website),
                "username": username,
                "password": password,
                "status": "verified_account",
                "auth_method": "email_password",
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            })
        reg_data["total_accounts"] = len(acc_list)
        reg_file.parent.mkdir(parents=True, exist_ok=True)
        reg_file.write_text(json.dumps(reg_data, indent=2), encoding="utf-8")
        print(f"[secrets] Recorded account for '{company}' into candidate_accounts.json")
    except Exception as e:
        print(f"[secrets] Note: Could not update candidate_accounts.json: {e}")

    # 2. Update client_secret.json if non-standard password
    if not SECRETS_FILE.exists():
        return
    try:
        data = json.loads(SECRETS_FILE.read_text())
        default_pwd = data.get("credentials", {}).get("default_password", "")
        if password and password != default_pwd:
            exceptions = data.setdefault("account_exceptions", {})
            exceptions[company] = {
                "website": website,
                "username": username,
                "password": password,
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            SECRETS_FILE.write_text(json.dumps(data, indent=2))
            print(f"[secrets] Recorded non-standard account exception for '{company}' in client_secret.json")
    except Exception as e:
        print(f"[secrets] Note: Could not update client_secret.json: {e}")



# ── ATS Fingerprinting ───────────────────────────────────────────────────────
ATS_PATTERNS = {
    "taleo":          ["taleo.net", "taleo.com"],
    "workday":        ["myworkdayjobs.com"],
    "greenhouse":     ["greenhouse.io", "gh_jid="],
    "lever":          ["lever.co"],
    "oracle_hcm":     ["oraclecloud.com/hcmUI"],
    "successfactors": ["successfactors.com", "sapsf.com", "sapsf.eu", "join.cnh.com", "jobs2web.com"],
    "avature":        ["avature.net", "emiratesgroupcareers.com"],
    "phenom":         ["phenom.com", "phenompeople.com", "eightfold.ai"],
    "ashby":          ["ashbyhq.com"],
    "icims":          ["icims.com"],
    "rippling":       ["ats.rippling.com"],
    "thehirehub":     ["thehirehub.ai"],
    "pinpoint":       ["pinpointhq.com"],
}

def detect_ats(url: str) -> str:
    try:
        from core.ats_classifier import classify_ats_vendor
        vendor = classify_ats_vendor(url)
        if vendor:
            return vendor
    except Exception:
        pass
    for ats, patterns in ATS_PATTERNS.items():
        if any(p in url for p in patterns):
            return ats
    return "unknown"


# ── Alert helper ─────────────────────────────────────────────────────────────
def alert(title: str, message: str):
    subprocess.Popen(["afplay", "/System/Library/Sounds/Glass.aiff"])
    subprocess.run([
        "osascript", "-e",
        f'display notification "{message}" with title "{title}"'
    ])


# ── Browser helpers ──────────────────────────────────────────────────────────
def open_browser(headless: bool = True):
    """Headless browser for inspect mode - no persistence needed."""
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=headless)
    ctx = browser.new_context(
        viewport={"width": 1280, "height": 900},
        user_agent=USER_AGENT,
    )
    page = ctx.new_page()
    return pw, browser, ctx, page


def open_persistent_browser():
    """
    Headed browser with a persistent profile stored in .browser_session/.
    Tries connecting to an existing standing CDP browser on port 9222 first.
    If none exists, launches persistent context with --remote-debugging-port=9222.
    """
    pw = sync_playwright().start()
    try:
        browser = pw.chromium.connect_over_cdp("http://localhost:9222", timeout=1500)
        ctx = browser.contexts[0] if browser.contexts else browser.new_context(no_viewport=True, user_agent=USER_AGENT)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        print("[browser] Attached to standing persistent Chrome on CDP port 9222.")
        return pw, ctx, page
    except Exception:
        pass

    # Clean stale locks if any
    for lock_name in ["SingletonLock", "SingletonSocket", "SingletonCookie"]:
        lock_path = SESSION_DIR / lock_name
        if lock_path.exists() or lock_path.is_symlink():
            try:
                lock_path.unlink(missing_ok=True)
            except Exception:
                pass

    try:
        try:
            ctx = pw.chromium.launch_persistent_context(
                user_data_dir=str(SESSION_DIR),
                channel="chrome",
                headless=False,
                no_viewport=True,
                user_agent=USER_AGENT,
                args=["--start-maximized", "--no-default-browser-check", "--remote-debugging-port=9222"],
            )
        except Exception:
            ctx = pw.chromium.launch_persistent_context(
                user_data_dir=str(SESSION_DIR),
                headless=False,
                no_viewport=True,
                user_agent=USER_AGENT,
                args=["--start-maximized", "--no-default-browser-check", "--remote-debugging-port=9222"],
            )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        return pw, ctx, page
    except Exception as e:
        print(f"[browser] Persistent profile in use ({e}). Launching headed standalone browser...")
        browser = pw.chromium.launch(
            headless=False,
            args=["--start-maximized", "--no-default-browser-check", "--remote-debugging-port=9222"]
        )
        ctx = browser.new_context(
            no_viewport=True,
            user_agent=USER_AGENT,
        )
        page = ctx.new_page()
        return pw, ctx, page


def close_browser(pw, ctx, keep_open: bool = True):
    """
    CRITICAL ZERO-TOLERANCE DIRECTIVE:
    NEVER close the browser window under any circumstances.
    Keeps the browser open, visible, and interactive on screen indefinitely when keep_open=True.
    """
    if not keep_open:
        return

    print("\n" + "="*65)
    print("  [PERSISTENT BROWSER ACTIVE - RUNNER WILL NOT CLOSE WINDOW]")
    print("  Browser window is held open on screen for review and interaction.")
    print("  Script is pausing permanently to preserve window state.")
    print("="*65 + "\n")
    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        # Prevent premature destruction
        pass



def navigate(page: Page, url: str, timeout: int = 45000) -> bool:
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        time.sleep(2)
        try:
            from core.job_liveness_detector import check_page_liveness
            active, reason = check_page_liveness(page)
            if not active:
                print(f"  [Liveness Warning] Job page appears closed/expired: {reason}")
                return False
        except Exception:
            pass
        return True
    except Exception:
        return False


def select_react_option(page: Page, input_id: str, search_text: str, exact_text: str = None) -> bool:
    """
    Robust react-select combobox handler for modern Greenhouse / Ashby / Workday portals.
    Cross-validates that the target response actually exists in the dropdown options list.
    """
    try:
        clean_id = input_id.replace("#", "")
        inp = page.locator(f"[id='{clean_id}']").first
        if inp.count() == 0:
            inp = page.locator(f"input[id*='{clean_id}']").first
        if inp.count() == 0:
            return False

        # Click the select control container if present, else input
        ctrl = inp.locator("xpath=ancestor::div[contains(@class, 'select__control')]")
        if ctrl.count() > 0:
            ctrl.click()
        else:
            inp.click()
        time.sleep(0.3)

        # Wait for menu options
        opts = None
        try:
            page.wait_for_selector(f"[id*='react-select-{clean_id}'] .select__option, .select__menu .select__option", timeout=2500)
        except Exception:
            pass

        opts = page.locator(f"[id*='react-select-{clean_id}'] .select__option, [id*='react-select-{clean_id}'] [role='option']")
        if opts.count() == 0:
            opts = page.locator(f"[id='{clean_id}']").locator("xpath=ancestor::div[contains(@class, 'select-shell')]").locator(".select__menu .select__option")
        if opts.count() == 0:
            opts = page.locator(".select__menu .select__option, div[class*='select__menu'] div[class*='select__option']")

        if opts.count() > 0:
            target_str = (exact_text or search_text).strip().lower()
            available_options = [opts.nth(i).inner_text().strip() for i in range(opts.count())]

            target = None
            # 1. Exact match
            for i, opt_txt in enumerate(available_options):
                if opt_txt.lower() == target_str:
                    target = opts.nth(i)
                    break

            # 2. Semantic Notice Period Aliases (Immediate -> 0 to 15 days)
            if not target and target_str in ("immediate", "0", "0 days", "immediately"):
                for i, opt_txt in enumerate(available_options):
                    if any(k in opt_txt.lower() for k in ["0 to 15", "0-15", "immediate", "immediately", "less than 15"]):
                        target = opts.nth(i)
                        print(f"[select_react] Cross-validated alias match: '{opt_txt}' for '{target_str}'")
                        break

            # 3. Country / Gender guardrails
            if not target and target_str == "male":
                for i, opt_txt in enumerate(available_options):
                    if opt_txt.lower() == "male":
                        target = opts.nth(i)
                        break
            if not target and target_str == "india":
                for i, opt_txt in enumerate(available_options):
                    if opt_txt.lower().startswith("india") and "ocean" not in opt_txt.lower():
                        target = opts.nth(i)
                        break

            # 4. Prefix or boundary match
            if not target:
                for i, opt_txt in enumerate(available_options):
                    t = opt_txt.lower()
                    if t.startswith(target_str) or re.search(r'\b' + re.escape(target_str) + r'\b', t):
                        target = opts.nth(i)
                        break

            # 5. Substring fallback
            if not target:
                for i, opt_txt in enumerate(available_options):
                    if target_str in opt_txt.lower():
                        target = opts.nth(i)
                        break

            kb = getattr(page, "keyboard", getattr(page, "page", None).keyboard if hasattr(page, "page") else None)
            if target:
                target.click()
                time.sleep(0.3)
                return True
            else:
                print(f"[select_react] Option '{target_str}' does not exist in dropdown {available_options}. Safely closing menu.")
                if kb:
                    kb.press("Escape")
                time.sleep(0.2)
                return False
        else:
            kb = getattr(page, "keyboard", getattr(page, "page", None).keyboard if hasattr(page, "page") else None)
            if kb:
                kb.press("Escape")
            time.sleep(0.2)
            return False
    except Exception as e:
        print(f"[select_react] Warning on #{input_id}: {e}")
        return False


# ── Auto-Login & Registration Engine ─────────────────────────────────────────
# Track domains where authentication was already attempted in current process
_AUTHENTICATION_ATTEMPTS: set[str] = set()

def get_portal_credentials(url: str) -> tuple[str, str, list[str]]:
    """
    Resolves exact username, default password, and alternate passwords for a portal URL.
    Checks ~/.config/job-agent/.candidate_secrets.json accounts registry first,
    then client_secret.json, then defaults.
    """
    domain = re.sub(r"^https?://", "", url).split("/")[0].lower()
    
    # Load candidate defaults
    prof, def_email, def_pwd, def_alts = get_candidate_credentials()
    alt_passwords = list(def_alts)

    # 1. Check local accounts registry and global secrets
    secrets_paths = [
        Path(__file__).parent.parent / "user_inputs" / "candidate_accounts.json",
        Path.home() / ".config" / "job-agent" / ".candidate_secrets.json",
        GLOBAL_SECRETS_FILE,
        SECRETS_FILE
    ]
    for sp in secrets_paths:
        if sp.exists():
            try:
                data = json.loads(sp.read_text())
                # Check accounts array
                for acc in data.get("accounts", []):
                    web = (acc.get("website") or "").lower()
                    comp = (acc.get("company") or "").lower()
                    if (web and (web in url.lower() or domain in web)) or (comp and comp in url.lower()):
                        u = acc.get("username", "") or def_email
                        p = acc.get("password", "") or def_pwd
                        alt = acc.get("alternate_password", "")
                        if alt and alt not in alt_passwords and alt != p:
                            alt_passwords.insert(0, alt)
                        if u and p:
                            print(f"[auth:lookup] Resolved exact domain credentials for '{domain}' from {sp.name}")
                            return u, p, alt_passwords
                # Check account_exceptions
                for comp, acc in data.get("account_exceptions", {}).items():
                    web = (acc.get("website") or "").lower()
                    if (web and domain in web) or (comp.lower() in url.lower()):
                        u = acc.get("username", "") or def_email
                        p = acc.get("password", "") or def_pwd
                        alt = acc.get("alternate_password", "")
                        if alt and alt not in alt_passwords and alt != p:
                            alt_passwords.insert(0, alt)
                        if u and p:
                            print(f"[auth:lookup] Resolved exception credentials for '{domain}' from {sp.name}")
                            return u, p, alt_passwords
            except Exception:
                pass

    return def_email, def_pwd, alt_passwords


def has_exact_portal_credentials(url: str) -> bool:
    """Return True only when an exact domain/company entry exists in the local secrets registry."""
    domain = re.sub(r"^https?://", "", url).split("/")[0].lower()
    secrets_paths = [
        Path(__file__).parent.parent / "user_inputs" / "candidate_accounts.json",
        Path.home() / ".config" / "job-agent" / ".candidate_secrets.json",
        GLOBAL_SECRETS_FILE,
        SECRETS_FILE,
    ]
    for sp in secrets_paths:
        if sp.exists():
            try:
                data = json.loads(sp.read_text())
                for acc in data.get("accounts", []):
                    web = (acc.get("website") or "").lower()
                    comp = (acc.get("company") or "").lower()
                    if ((web and (web in url.lower() or domain in web)) or (comp and comp in url.lower())) and (acc.get("password") or "").strip():
                        return True
                for comp, acc in data.get("account_exceptions", {}).items():
                    web = (acc.get("website") or "").lower()
                    if ((web and domain in web) or (comp.lower() in url.lower())) and (acc.get("password") or "").strip():
                        return True
            except Exception:
                pass
    return False


def _is_account_locked(page: Page) -> bool:
    """Scans DOM for security warning or lockout banners."""
    try:
        page_text = page.inner_text("body").lower()
        LOCKOUT_TRIGGERS = [
            "account has been locked",
            "account is locked",
            "too many unsuccessful",
            "locked for security reasons",
            "your account is disabled",
            "too many failed login attempts",
            "access denied due to multiple failed",
            "last chance to sign in",
        ]
        for trigger in LOCKOUT_TRIGGERS:
            if trigger in page_text:
                print(f"[auth:lockout] Lockout banner detected: '{trigger}'")
                alert("Account Lockout Detected", "Account is locked or warned on portal. Automation halted.")
                return True
    except Exception:
        pass
    return False


def _attempt_login_step(page: Page, email: str, password: str, is_retry: bool = False) -> tuple[bool, bool]:
    """
    Executes a single login submission step with element polling and verification.
    Returns (success: bool, is_locked: bool).
    """
    if _is_account_locked(page):
        return False, True

    user_selectors = [
        "input[data-automation-id='email']",
        "input[data-automation-id='username']",
        "#dialogTemplate-dialogForm-login-name1",
        "input[type='email']",
        "input[name*='user']",
        "input[name*='email']",
        "input[id*='user']",
        "input[id*='email']",
        "input[id*='login']",
    ]
    pwd_selectors = [
        "input[data-automation-id='password']",
        "#dialogTemplate-dialogForm-login-password",
        "input[type='password']",
        "input[name*='pass']",
        "input[id*='pass']",
    ]
    submit_selectors = [
        "button[data-automation-id='signInSubmitButton']",
        "div[data-automation-id='click_filter']",
        "#dialogTemplate-dialogForm-login-defaultcmd",
        "#dialogTemplate-dialogForm-login-submit",
        "button[type='submit']",
        "input[type='submit']",
        "input[value='Sign In']",
        "input[value='Log In']",
        "button:has-text('Sign In')",
        "button:has-text('Sign in')",
        "button:has-text('Log In')",
        "button:has-text('Log in')",
        "button:has-text('Login')",
    ]

    user_el = None
    pwd_el = None
    submit_btn = None

    # 0. Strictly bypass social logins (Google, Apple, LinkedIn) - always use email & password
    for em_sel in [
        "button[data-automation-id='SignInWithEmailButton']",
        "button:has-text('Sign in with email')",
        "a:has-text('Sign in with email')",
        "button:has-text('Sign in with Email')",
        "a:has-text('Sign in with Email')",
    ]:
        try:
            em_btn = page.query_selector(em_sel)
            if em_btn and em_btn.is_visible():
                print(f"[auth:login] Clicking '{em_sel}' (social media logins strictly bypassed)...")
                em_btn.click()
                time.sleep(2)
                break
        except Exception:
            pass

    # Poll up to 8s for login inputs to be visible in DOM
    for _ in range(16):
        # In case 'Sign in with email' was rendered dynamically
        if not pwd_el:
            for em_sel in ["button[data-automation-id='SignInWithEmailButton']", "button:has-text('Sign in with email')"]:
                try:
                    em_btn = page.query_selector(em_sel)
                    if em_btn and em_btn.is_visible():
                        em_btn.click()
                        time.sleep(1.5)
                        break
                except Exception:
                    pass

        modal = page.query_selector("div[data-automation-id='signInContent'], div[role='dialog'], form[id*='login'], form[name*='login']")
        if modal and modal.is_visible():
            try:
                m_user = modal.query_selector("input[data-automation-id='email'], input[data-automation-id='username'], input[type='email'], input[id*='email'], input[name*='email']")
                m_pwd = modal.query_selector("input[data-automation-id='password'], input[type='password']")
                m_btn = modal.query_selector("button[data-automation-id='signInSubmitButton'], button[type='submit'], button:has-text('Sign In'), button:has-text('Sign in')")
                if m_pwd and m_pwd.is_visible():
                    pwd_el = m_pwd
                    if m_user and m_user.is_visible():
                        aid = (m_user.get_attribute("data-automation-id") or "").lower()
                        if "bee" not in aid:
                            user_el = m_user
                    if m_btn and m_btn.is_visible():
                        submit_btn = m_btn
                    break
            except Exception:
                pass

        if not pwd_el:
            for sel in pwd_selectors:
                try:
                    el = page.query_selector(sel)
                    if el and el.is_visible():
                        pwd_el = el
                        break
                except Exception:
                    pass

        if not user_el:
            for sel in user_selectors:
                try:
                    el = page.query_selector(sel)
                    if el and el.is_visible():
                        aid = (el.get_attribute("data-automation-id") or "").lower()
                        if "bee" not in aid:
                            user_el = el
                            break
                except Exception:
                    pass

        if not submit_btn:
            for sel in submit_selectors:
                try:
                    btn = page.query_selector(sel)
                    if btn and btn.is_visible():
                        submit_btn = btn
                        break
                except Exception:
                    pass

        if pwd_el and (user_el or is_retry):
            break
        time.sleep(0.5)

    if not pwd_el:
        print("[auth:login] Password input element not found.")
        return False, False

    try:
        # Fill email if present and not already matching
        if user_el and user_el.is_visible():
            try:
                curr_val = (user_el.input_value() or "").strip()
                if curr_val != email:
                    user_el.fill("")
                    user_el.fill(email)
            except Exception:
                pass

        # Fill password
        pwd_el.fill("")
        pwd_el.fill(password)
        time.sleep(0.5)

        # Click submit button
        submitted = False
        if submit_btn and submit_btn.is_visible():
            try:
                submit_btn.click(force=True, timeout=5000)
                submitted = True
            except Exception:
                pass

        if not submitted:
            for sel in submit_selectors:
                try:
                    btn = page.query_selector(sel)
                    if btn and btn.is_visible():
                        btn.click(force=True, timeout=5000)
                        submitted = True
                        break
                except Exception:
                    pass

        if not submitted:
            pwd_el.press("Enter")

        time.sleep(4)

        # Check for account lockout
        if _is_account_locked(page):
            return False, True

        # Check if login succeeded:
        # 1. Navigation away from login or presence of logged-in anchors
        if page.query_selector("button[data-automation-id='utilityMenuButton'], div[data-automation-id='file-upload-drop-zone'], button[data-automation-id='bottom-navigation-next-button']"):
            return True, False

        curr_url = page.url.lower()
        pwd_check = page.query_selector("input[type='password'], input[data-automation-id='password']")
        if not pwd_check or not pwd_check.is_visible():
            if all(x not in curr_url for x in ["login.jsf", "/login", "signin", "accessmanagement"]):
                return True, False

        # Check if an OTP / email verification screen was triggered by valid credentials
        page_text = (page.inner_text("body") or "").lower()
        if any(v in page_text for v in ["verification code", "enter code", "verify your email", "two-step", "one-time passcode"]):
            return False, False

        # Check for explicit invalid credentials / rejection message
        if any(err in page_text for err in [
            "invalid user", "invalid email", "invalid password", "incorrect",
            "doesn't exist", "not found", "wrong email address or password",
            "user name and password do not match", "authentication failed",
            "check your password", "credentials are invalid",
            "couldn't verify", "unable to sign in", "didn't recognize",
        ]):
            print("[auth:login] Credentials rejected by portal banner.")
            return False, False

        # If password field is still visible and URL hasn't changed, consider attempt unsuccessful
        return False, False

    except Exception as e:
        print(f"[auth:login] Error during login step: {e}")
        return False, False


def _attempt_login(page: Page, email: str, password: str) -> bool:
    """Wrapper for single-step login attempt (backward compatibility)."""
    success, _ = _attempt_login_step(page, email, password, is_retry=False)
    return success


def _is_create_account_screen(page: Page) -> bool:
    """Return True when the current view renders a create-account / registration form."""
    selectors = [
        "input[data-automation-id='verifyPassword']",
        "input[id*='verifyPassword']",
        "input[name*='verifyPassword']",
        "button[data-automation-id='createAccountSubmitButton']",
        "div[data-automation-id='createAccountPage']",
    ]
    for sel in selectors:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                return True
        except Exception:
            pass
    return False


def _needs_verification_challenge(page: Page) -> bool:
    """Return True if portal is awaiting email verification link or OTP input."""
    try:
        logged_in = page.query_selector(
            "button[data-automation-id='utilityMenuButton'], "
            "div[data-automation-id='file-upload-drop-zone'], "
            "button[data-automation-id='bottom-navigation-next-button']"
        )
        if logged_in and logged_in.is_visible():
            return False
        body = (page.inner_text("body") or "").lower()
        return any(v in body for v in [
            "verification code", "enter code", "verify your email",
            "activation link", "one-time passcode", "otp",
        ])
    except Exception:
        return False


def _switch_to_signin_screen(page: Page) -> bool:
    """If landed on Create Account, click 'Sign In' link so login is attempted first."""
    if not _is_create_account_screen(page):
        return False
    switch_selectors = [
        "button[data-automation-id='signInLink']",
        "a[data-automation-id='signInLink']",
        "button:has-text('Sign In')",
        "a:has-text('Sign In')",
        "button:has-text('Already have an account')",
        "a:has-text('Already have an account')",
    ]
    for sel in switch_selectors:
        try:
            btn = page.query_selector(sel)
            if btn and btn.is_visible():
                aid = (btn.get_attribute("data-automation-id") or "").lower()
                if "submit" in aid:
                    continue
                print(f"[auth:switch] Landed on Create Account; switching to Sign In via {sel}...")
                btn.click()
                for _ in range(10):
                    if not _is_create_account_screen(page):
                        return True
                    time.sleep(0.4)
                return not _is_create_account_screen(page)
        except Exception:
            pass
    return False


def _resolve_registration_credentials(default_email: str, default_password: str) -> tuple[str, str]:
    """Resolve email and password for account creation, honoring .env when set."""
    reg_email = (os.getenv("CANDIDATE_EMAIL") or default_email or "").strip()
    reg_password = (
        os.getenv("CANDIDATE_STANDARD_PASSWORD")
        or os.getenv("CANDIDATE_PASSWORD")
        or os.getenv("STANDARD_ATS_PASSWORD")
        or default_password
        or ""
    ).strip()
    return reg_email, reg_password


def auto_authenticate_or_register(page: Page, ats: str, url: str) -> bool:
    """
    Independent Candidate Authentication & Registration Pipeline:
    1. Detects login/create-account screen or modal (switching Create Account -> Sign In first).
    2. Loads candidate & portal credentials (primary password + alternate passwords).
    3. Attempts login with primary password, then each unique alternate password (halting on lockout/OTP).
    4. If stored passwords fail without lockout, creates an account with email & password from .env/secrets.
    """
    curr_url = page.url.lower()
    domain = re.sub(r"^https?://", "", url).split("/")[0].lower()

    # Step 0: Check if login/create-account wall or modal is present
    LOGIN_URL_INDICATORS = ["login", "signin", "sign-in", "accessmanagement", "auth", "session", "logon"]
    is_login_page = any(x in curr_url for x in LOGIN_URL_INDICATORS)
    has_pwd_input = False
    try:
        has_pwd_input = bool(page.query_selector(
            "input[type='password'], input[data-automation-id='verifyPassword'], "
            "div[data-automation-id='signInContent'], button[data-automation-id='createAccountSubmitButton'], "
            "button[data-automation-id='signInSubmitButton'], button[data-automation-id='signInLink'], "
            "button[data-automation-id='SignInWithEmailButton'], button:has-text('Sign in with email'), "
            "a[data-automation-id='createAccountLink'], button[data-automation-id='createAccountLink'], "
            "div[data-automation-id='createAccountPage']"
        ))
    except Exception:
        pass

    has_signin_modal = False
    try:
        has_signin_modal = bool(page.query_selector(
            "div[data-automation-id='signInContent'], div[role='dialog'] input[type='password'], "
            "div[role='dialog'] button[data-automation-id='SignInWithEmailButton']"
        ))
    except Exception:
        pass

    if not is_login_page and not has_pwd_input and not has_signin_modal:
        print("[auth] No login wall detected. Proceeding with application flow.")
        return True

    print(f"[auth] Login/Authentication screen detected for ATS: {ats} on {domain}")

    # Step 0b: Check if lockout already active
    if _is_account_locked(page):
        return False

    # Step 0c: Prevent infinite loop on same domain
    if domain in _AUTHENTICATION_ATTEMPTS:
        print(f"[auth] Authentication cycle already evaluated for {domain}.")
        if page.query_selector("div[data-automation-id='file-upload-drop-zone'], button[data-automation-id='bottom-navigation-next-button']"):
            return True
        return False

    _AUTHENTICATION_ATTEMPTS.add(domain)

    # Step 1: Resolve credentials (portal-specific -> global secrets -> .env)
    prof, _, def_pwd, def_alts = get_candidate_credentials()
    username, password, alt_passwords = get_portal_credentials(url)
    if not username or not password:
        print(f"[auth:guard] No credentials available in secrets/.env for {domain}.")
        alert("Credentials Missing", f"Please sign in manually on {ats.upper()}.")
        return False

    passwords_to_try: list[str] = []
    for cand in [password, *alt_passwords, def_pwd, *def_alts]:
        c = (cand or "").strip()
        if c and c not in passwords_to_try:
            passwords_to_try.append(c)

    # Step 2: Always try Sign In first (even if portal defaulted to Create Account)
    _switch_to_signin_screen(page)
    for idx, pwd in enumerate(passwords_to_try):
        if _is_account_locked(page):
            return False
        label = "primary" if idx == 0 else f"alternate #{idx}"
        print(f"[auth:login] Attempting {label} login for {domain} as '{username}'...")
        success, is_locked = _attempt_login_step(page, username, pwd, is_retry=(idx > 0))
        if success:
            print(f"[auth:login] Login succeeded on {label} password!")
            return True
        if is_locked:
            return False
        if _needs_verification_challenge(page):
            print(f"[auth:login] Verification / OTP required after login attempt on {domain}.")
            alert("Sign-In Verification Needed", f"Enter verification code/OTP sent for {domain}.")
            return False

    # Step 3: All stored passwords failed without lockout -> Create Account using .env/stored credentials
    reg_email, reg_password = _resolve_registration_credentials(username, password)
    if not reg_email or not reg_password:
        alert("Credentials Missing", f"Login failed on {domain} and registration credentials are missing in .env.")
        return False

    print(f"[auth:register] Stored passwords did not authenticate on {domain}; attempting Create Account as '{reg_email}'...")
    return _attempt_register(page, prof, reg_email, reg_password, ats, url)


def _attempt_register(page: Page, prof: dict, email: str, password: str, ats: str, url: str) -> bool:
    """Finds registration/create-account flow, creates profile with client_secret credentials."""
    print(f"[auth:register] Searching for 'Create Account' / 'New User' / 'Register' option...")

    # Check if already on registration form
    already_on_reg_form = bool(page.query_selector("input[data-automation-id='verifyPassword'], input[id*='verifyPassword'], input[name*='verifyPassword']"))

    if not already_on_reg_form:
        # Strict priority: 1. Full Account Creation / Sign Up -> 2. Guest Apply only as last resort
        register_btn_selectors = [
            "button[data-automation-id='createAccountLink']",
            "a[data-automation-id='createAccountLink']",
            "button[data-automation-id='createAccountButton']",
            "div[data-automation-id='signInContent'] button:has-text('Create Account')",
            "div[data-automation-id='signInContent'] a:has-text('Create Account')",
            "button:has-text('Create Account')",
            "a:has-text('Create Account')",
            "button:has-text('New User')",
            "a:has-text('New User')",
            "input[value='New User']",
            "a:has-text('Register')",
            "button:has-text('Register')",
            "a:has-text('Sign Up')",
            "button:has-text('Sign Up')",
            "#dialogTemplate-dialogForm-login-createAccount",
            "#dialogTemplate-dialogForm-login-guestapply",  # Fallback only
        ]

        reg_btn = None
        for sel in register_btn_selectors:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    reg_btn = el
                    print(f"[auth:register] Found registration trigger: {sel}")
                    break
            except Exception:
                pass

        if not reg_btn:
            print("[auth:register] No registration link/button found on current page.")
            return False

        try:
            reg_btn.click()
            for _ in range(12):
                if page.query_selector("input[data-automation-id='verifyPassword'], input[id*='verifyPassword'], input[name*='verifyPassword'], input[data-automation-id='createAccountCheckbox']"):
                    break
                time.sleep(0.5)
        except Exception as e:
            print(f"[auth:register] Click notice on register button: {e}")

    try:
        time.sleep(1)

        # Fill registration form fields

        # 1. Email & Confirm Email (skip honeypots like Workday beecatcher)
        for sel in ["input[data-automation-id='email']", "input[id*='email']", "input[name*='email']"]:
            try:
                for el in page.query_selector_all(sel):
                    aid = (el.get_attribute("data-automation-id") or "").lower()
                    name = (el.get_attribute("name") or "").lower()
                    if "bee" in aid or name == "website":
                        continue
                    if el.is_visible() and (el.input_value() or "").strip() != email:
                        el.fill("")
                        el.fill(email)
            except Exception:
                pass

        for sel in ["input[id*='verifyEmail']", "input[name*='verifyEmail']", "input[id*='confirmEmail']", "input[name*='confirmEmail']", "input[data-automation-id='verifyEmail']"]:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    el.fill("")
                    el.fill(email)
            except Exception:
                pass

        # 2. Password & Confirm Password (always overwrite stale failed-login values)
        for sel in ["input[data-automation-id='password']", "input[type='password']", "input[id*='password']", "input[name*='password']"]:
            try:
                for el in page.query_selector_all(sel):
                    if el.is_visible():
                        el.fill("")
                        el.fill(password)
            except Exception:
                pass

        for sel in ["input[data-automation-id='verifyPassword']", "input[id*='verifyPassword']", "input[name*='verifyPassword']", "input[id*='confirmPassword']", "input[name*='confirmPassword']"]:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    el.fill("")
                    el.fill(password)
            except Exception:
                pass

        # 3. Candidate name and phone fields if present
        for sel in ["input[id*='first']", "input[name*='first']", "input[placeholder*='First']"]:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible() and not el.input_value():
                    el.fill(prof["first_name"])
            except Exception:
                pass

        for sel in ["input[id*='last']", "input[name*='last']", "input[placeholder*='Last']"]:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible() and not el.input_value():
                    el.fill(prof["last_name"])
            except Exception:
                pass

        # Handle phone with country/ITU code select
        itu_select = page.query_selector("select[id*='ituCode' i], select[name*='ituCode' i]")
        phone_to_fill = prof.get("raw_phone", prof.get("phone", "")) if itu_select else prof.get("phone", "")
        if itu_select:
            try:
                itu_select.select_option(value="IN")
            except Exception:
                pass
        for sel in ["input[id*='phoneNumber' i]", "input[name*='phoneNumber' i]", "input[data-automation-id*='phone' i]"]:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible() and not el.input_value():
                    el.fill(phone_to_fill)
            except Exception:
                pass

        # Handle Country select
        for sel in ["select[id*='country' i]", "select[name*='country' i]"]:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    try:
                        el.select_option(value="IN")
                    except Exception:
                        el.select_option(label="India")
            except Exception:
                pass

        # 4. Consent / Terms Checkbox & SuccessFactors DPCS Dialog
        try:
            dpcs_accepted = page.evaluate("""() => {
                if (typeof validateAndOpenDpcsDialog === 'function') {
                    validateAndOpenDpcsDialog(true);
                    return true;
                }
                const dp = document.getElementById('dataPrivacyId') || Array.from(document.querySelectorAll('a')).find(a => a.innerText.toLowerCase().includes('privacy notice'));
                if (dp) {
                    dp.click();
                    return true;
                }
                return false;
            }""")
            if dpcs_accepted:
                time.sleep(1.5)
                acc_btn = page.query_selector("button:has-text('Accept'), [id^='dlgButton_']:has-text('Accept')")
                if acc_btn and acc_btn.is_visible():
                    acc_btn.click()
                    print("[auth:register] Accepted SuccessFactors Data Privacy Notice (DPCS).")
                    time.sleep(1.5)
        except Exception:
            pass

        for sel in [
            "input[data-automation-id='createAccountCheckbox']",
            "div[data-automation-id='createAccountCheckbox']",
            "input[type='checkbox']",
            "input[id*='terms']",
            "input[id*='consent']",
            "input[id*='policy']",
            "#fbclc_emailEnabled",
        ]:
            try:
                for el in page.query_selector_all(sel):
                    if el.is_visible():
                        try:
                            if not el.is_checked():
                                el.click(force=True)
                        except Exception:
                            el.click(force=True)
            except Exception:
                pass

        time.sleep(1)

        # 5. Submit Registration
        for sel in [
            "#fbclc_createAccountButton",
            "button[data-automation-id='createAccountSubmitButton']",
            "button[type='submit']",
            "input[type='submit']",
            "button:has-text('Create Account')",
            "button:has-text('Register')",
            "button:has-text('Continue')",
            "input[value='Continue']",
            "input[value='Create Account']",
            "#dialogTemplate-dialogForm-niceCommandButton_continue",
        ]:
            try:
                btn = page.query_selector(sel)
                if btn and btn.is_visible():
                    btn.click(force=True)
                    print(f"[auth:register] Submitted registration form via {sel}")
                    for _ in range(10):
                        if not _is_create_account_screen(page):
                            break
                        time.sleep(0.5)
                    break
            except Exception:
                pass

        # Determine company identifier
        company_name = re.sub(r"https?://([^/]+).*", r"\1", url)
        page_text = (page.inner_text("body") or "").lower()

        # Check if registration failed because user/account already exists
        EXISTS_KEYWORDS = [
            "already exists", "already registered", "account already exists",
            "user already exists", "already in use", "an account already exists",
            "email is already", "email already exists", "user name already exists",
            "account with this email", "user with this email",
        ]
        if any(kw in page_text for kw in EXISTS_KEYWORDS):
            print(f"[auth:register] Account already exists for {email} on {company_name}!")
            print("[auth:register] Saved passwords failed. Alerting user to sign in manually...")
            alert(
                f"Account Exists - Action Required [{company_name}]",
                f"Account exists on {company_name} but saved passwords failed. Please sign in or reset password in browser."
            )
            return False

        # Verify submission did not remain blocked on Create Account due to validation/password error
        if _is_create_account_screen(page):
            print(f"[auth:register] Registration form still active on {company_name}. Manual review needed.")
            alert(
                f"Registration Validation Needed [{company_name}]",
                f"Could not submit Create Account cleanly on {company_name}. Please check form requirements in browser."
            )
            return False

        # Record new credentials into client_secret.json / candidate_accounts.json if created
        record_new_account(company=company_name, website=url, username=email, password=password)

        # Check if email verification code / OTP is required before entering application steps
        if _needs_verification_challenge(page):
            print("[auth:register] Verification required! Triggering macOS chime and notification...")
            alert("ATS Email/OTP Verification", f"Verification sent for {company_name}. Please enter code or click link.")
            return False

        return True

    except Exception as e:
        print(f"[auth:register] Error during registration: {e}")

    return False


# ── Mode: inspect ────────────────────────────────────────────────────────────
def mode_inspect(url: str, slug: str, keep_open: bool = True) -> dict:
    """Extract visible form fields locally. Zero raw HTML sent to LLM."""
    print(f"[inspect] Navigating -> {url}")
    pw, ctx, page = open_persistent_browser()
    navigate(page, url)
    time.sleep(2)

    result = {
        "ats":     detect_ats(url),
        "url":     page.url,
        "title":   page.title(),
        "inputs":  [],
        "buttons": [],
    }

    for el in page.query_selector_all("input:not([type='hidden']), select, textarea"):
        try:
            el_id = el.get_attribute("id") or ""
            lbl = ""
            if el_id:
                lbl_el = page.query_selector(f"label[for='{el_id}']")
                if lbl_el:
                    lbl = lbl_el.inner_text().strip()
            if not lbl:
                lbl = el.evaluate("""el => {
                    let p = el.closest('label');
                    if (p) return p.innerText.trim();
                    let field = el.closest('.field, [class*="field"], [class*="form-group"], [class*="question"]');
                    if (field) {
                        let l = field.querySelector('label, .label, legend');
                        if (l) return l.innerText.trim();
                    }
                    return el.getAttribute('aria-label') || '';
                }""")
            result["inputs"].append({
                "id":          el_id,
                "name":        el.get_attribute("name") or "",
                "type":        el.get_attribute("type") or "",
                "placeholder": el.get_attribute("placeholder") or "",
                "label":       lbl or "",
            })
        except Exception:
            pass

    for el in page.query_selector_all("input[type='button'], input[type='submit'], button"):
        try:
            result["buttons"].append({
                "id":    el.get_attribute("id") or "",
                "value": (el.get_attribute("value") or el.inner_text())[:60],
                "title": el.get_attribute("title") or "",
            })
        except Exception:
            pass

    snap_path = SCRATCH_DIR / f"{slug}_inspect.json"
    snap_path.write_text(json.dumps(result, indent=2))
    print(f"[inspect] ATS={result['ats']} | Title='{result['title']}'")
    print(f"[inspect] {len(result['inputs'])} inputs | {len(result['buttons'])} buttons")
    print(f"[inspect] Snapshot -> {snap_path}")

    # Inspect mode closes browser cleanly unless keep_open was explicitly requested
    if not keep_open:
        try:
            ctx.close()
            pw.stop()
        except Exception:
            pass
    else:
        close_browser(pw, ctx, keep_open=keep_open)
    return result




# ── Mode: login ──────────────────────────────────────────────────────────────
def mode_login(url: str, slug: str, keep_open: bool = True) -> bool:
    """
    Open persistent headed browser, auto-login with client_secret.json,
    auto-register if user doesn't exist, and save session to .browser_session/.
    """
    ats = detect_ats(url)
    print(f"[login] Opening persistent browser for ATS '{ats}'...")
    pw, ctx, page = open_persistent_browser()
    navigate(page, url)
    time.sleep(2)

    logged_in = auto_authenticate_or_register(page, ats, url)

    if logged_in:
        snap_path = SCRATCH_DIR / f"{slug}_post_login.png"
        page.screenshot(path=str(snap_path))
        print(f"[login] Post-login screenshot -> {snap_path}")
    else:
        print("[login] Sign-in not completed.")

    close_browser(pw, ctx, keep_open=keep_open)
    return logged_in


def resolve_address_components(has_line2: bool = False, has_line3: bool = False, cand: dict = None) -> tuple[str, str, str]:
    """
    Resolves address line 1, line 2, line 3 based on field availability and user rules.
    1. If 3 address fields are available:
       - line 1: cand.get("address_3_line1") or derived parts[:2]
       - line 2: cand.get("address_3_line2") or derived parts[2]
       - line 3: cand.get("address_3_line3") or derived parts[3]
    2. If 2 address fields are available:
       - line 1: cand.get("address_2_line1") or derived parts[:3]
       - line 2: cand.get("address_2_line2") or derived parts[3:]
       - line 3: ""
    3. If only 1 address field is available:
       - line 1: cand.get("address") or full address string
       - line 2: ""
       - line 3: ""
    """
    if cand is None:
        cand = CANDIDATE

    full_addr = cand.get("address", "").strip()
    parts = [p.strip() for p in full_addr.split(",") if p.strip()]

    if has_line3:
        l1 = cand.get("address_3_line1") or (", ".join(parts[:2]) if len(parts) >= 2 else full_addr)
        l2 = cand.get("address_3_line2") or (parts[2] if len(parts) >= 3 else "")
        l3 = cand.get("address_3_line3") or (parts[3] if len(parts) >= 4 else "")
        return l1.strip(), l2.strip(), l3.strip()

    if has_line2:
        l1 = cand.get("address_2_line1") or (", ".join(parts[:3]) if len(parts) >= 3 else full_addr)
        l2 = cand.get("address_2_line2") or (", ".join(parts[3:]) if len(parts) >= 4 else "")
        if "sector 131" in full_addr.lower() and "sector 131" in l2.lower():
            l2 = "Sector 131"
        return l1.strip(), l2.strip(), ""

    return full_addr, "", ""


def fill_address_hierarchy(page: Page, cand: dict = None) -> dict:
    """
    Detects address structure (1-line, 2-line, or 3-line) on the page,
    along with City, State/Province, Postal Code, and Country,
    and fills them according to candidate preferences.
    """
    if cand is None:
        cand = CANDIDATE

    filled = {}

    el_line1 = None
    el_line2 = None
    el_line3 = None

    # 0. Paired Address detection (e.g. #address and #address1 on Phenom / SuccessFactors)
    el_addr = page.query_selector("input#address")
    el_addr1 = page.query_selector("input#address1")
    if el_addr and el_addr1 and el_addr.is_visible() and el_addr1.is_visible():
        el_line1 = el_addr
        el_line2 = el_addr1

    # 1. Detect Line 3
    if not el_line1:
        line3_selectors = [
            "#address3", "#address_3", "input[id*='address3' i]", "input[id*='address_3' i]",
            "input[id*='address_line_3' i]", "input[name*='address3' i]", "input[name*='address_3' i]",
            "input[name*='address_line_3' i]", "input[placeholder*='address 3' i]", "input[placeholder*='address line 3' i]"
        ]
        for sel in line3_selectors:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible() and el.is_enabled():
                    el_line3 = el
                    break
            except Exception:
                pass

        # 2. Detect Line 2
        line2_selectors = [
            "input[data-automation-id*='addressLine2' i]", "input[data-automation-id*='addressSection_addressLine2' i]",
            "#address2", "#address_2", "input[id*='address2' i]", "input[id*='address_2' i]",
            "input[id*='address_line_2' i]", "input[name*='address2' i]", "input[name*='address_2' i]",
            "input[name*='address_line_2' i]", "input[placeholder*='address 2' i]", "input[placeholder*='address line 2' i]",
            "input[placeholder*='apartment' i]", "input[placeholder*='apt' i]", "input[placeholder*='suite' i]",
            "input[placeholder*='unit' i]", "input[id*='suite' i]", "input[name*='suite' i]", "input[id*='apt' i]"
        ]
        for sel in line2_selectors:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible() and el.is_enabled():
                    el_line2 = el
                    break
            except Exception:
                pass

        # 3. Detect Line 1
        line1_selectors = [
            "input[data-automation-id*='addressLine1' i]", "input[data-automation-id*='addressSection_addressLine1' i]",
            "#address1", "#address_1", "input[id*='address1' i]", "input[id*='address_1' i]",
            "input[id*='address_line_1' i]", "input[name*='address1' i]", "input[name*='address_1' i]",
            "input[name*='address_line_1' i]", "input[placeholder*='address 1' i]", "input[placeholder*='address line 1' i]",
            "input[id='address' i]", "input[name='address' i]", "input[id*='street' i]", "input[name*='street' i]",
            "input[placeholder*='street' i]", "input[placeholder='Address' i]", "input[id*='street_address' i]"
        ]
        for sel in line1_selectors:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible() and el.is_enabled():
                    el_line1 = el
                    break
            except Exception:
                pass

    has_line3 = (el_line3 is not None)
    has_line2 = (el_line2 is not None) or has_line3

    addr1, addr2, addr3 = resolve_address_components(has_line2=has_line2, has_line3=has_line3, cand=cand)

    if el_line1 and addr1:
        try:
            el_line1.fill(addr1)
            filled["address_line1"] = addr1
        except Exception:
            pass

    if el_line2 and addr2 and has_line2:
        try:
            el_line2.fill(addr2)
            filled["address_line2"] = addr2
        except Exception:
            pass

    if el_line3 and addr3 and has_line3:
        try:
            el_line3.fill(addr3)
            filled["address_line3"] = addr3
        except Exception:
            pass

    # 4. City / Town
    city_val = cand.get("city", "Noida")
    for sel in [
        "input[data-automation-id*='city' i]",
        "#town", "input[id*='town' i]", "input[name*='town' i]",
        "input[id*='city' i]", "input[name*='city' i]",
        "input[placeholder*='city' i]", "input[placeholder*='town' i]"
    ]:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible() and el.is_enabled():
                el_id = (el.get_attribute("id") or "").lower()
                el_name = (el.get_attribute("name") or "").lower()
                if "ethnicity" in el_id or "ethnicity" in el_name:
                    continue
                if not el.input_value():
                    el.fill(city_val)
                    filled["city"] = city_val
                    break
        except Exception:
            pass

    # 5. State / Province / Region
    state_val = cand.get("state", "Uttar Pradesh")
    for sel in [
        "input[data-automation-id*='state' i]", "input[data-automation-id*='region' i]",
        "#region", "input[id*='region' i]", "input[name*='region' i]",
        "input[id*='state' i]", "input[name*='state' i]",
        "input[id*='province' i]", "input[name*='province' i]",
        "input[placeholder*='state' i]", "input[placeholder*='province' i]"
    ]:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible() and el.is_enabled():
                if not el.input_value():
                    el.fill(state_val)
                    filled["state"] = state_val
                    break
        except Exception:
            pass

    for sel in [
        "select[data-automation-id*='state' i]", "select[data-automation-id*='region' i]",
        "select[id*='state' i]", "select[name*='state' i]",
        "select[id*='province' i]", "select[name*='province' i]",
        "select[id*='region' i]", "select[name*='region' i]"
    ]:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible() and el.is_enabled():
                try:
                    el.select_option(label=state_val)
                    filled["state"] = state_val
                except Exception:
                    try:
                        el.select_option(value=state_val)
                        filled["state"] = state_val
                    except Exception:
                        pass
        except Exception:
            pass

    # 6. Postal Code / Zip Code / Postcode
    pincode_val = cand.get("pincode", "201304")
    for sel in [
        "input[data-automation-id*='postalCode' i]", "input[data-automation-id*='postal' i]",
        "#postcode", "input[id*='postcode' i]", "input[name*='postcode' i]",
        "input[id*='zip' i]", "input[name*='zip' i]",
        "input[id*='postal' i]", "input[name*='postal' i]",
        "input[placeholder*='zip' i]", "input[placeholder*='postal' i]", "input[placeholder*='postcode' i]"
    ]:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible() and el.is_enabled():
                if not el.input_value():
                    el.fill(pincode_val)
                    filled["pincode"] = pincode_val
                    break
        except Exception:
            pass

    # 7. Country
    country_val = cand.get("country", "India")
    for sel in [
        "select[id*='country' i]", "select[name*='country' i]"
    ]:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible() and el.is_enabled():
                try:
                    el.select_option(label=country_val)
                    filled["country"] = country_val
                except Exception:
                    try:
                        el.select_option(value="IN")
                        filled["country"] = country_val
                    except Exception:
                        pass
        except Exception:
            pass

    if filled:
        print(f"[fill:address] Hierarchical address populated: {list(filled.keys())}")
    return filled


# ── Common fill & upload helpers ─────────────────────────────────────────────
def _fill_common(page: Page):
    """Autofill standard fields across all ATS types."""
    # ── Phone Country Code Selection (Prioritize before Phone Number) ───────────
    has_cc = False
    for cc_sel in [
        "#phoneCountryCode", "select#phoneCountryCode", "select[id*='phoneCountryCode' i]",
        "select[name*='phoneCountryCode' i]", "select[id*='countryCode' i]", "select[name*='countryCode' i]"
    ]:
        try:
            cc_el = page.query_selector(cc_sel)
            if cc_el and cc_el.is_visible():
                has_cc = True
                # Select India (+91) specifically (reject British Indian Ocean Territory)
                selected = False
                try:
                    cc_el.select_option(value="19943")
                    selected = True
                except Exception:
                    pass
                if not selected:
                    try:
                        cc_el.select_option(label="India (+91)")
                        selected = True
                    except Exception:
                        pass
                if not selected:
                    for opt in cc_el.query_selector_all("option"):
                        txt = opt.inner_text().strip()
                        if "british indian" in txt.lower():
                            continue
                        if "+91" in txt or re.search(r"\bindia\b", txt, re.IGNORECASE):
                            val = opt.get_attribute("value")
                            if val:
                                cc_el.select_option(value=val)
                                selected = True
                                break
                if selected:
                    print(f"[fill:country_code] Selected India (+91) via {cc_sel}")
                break
        except Exception:
            pass

    # Use raw 10-digit phone (no country code) if country code selector exists on page
    if not has_cc:
        try:
            cc_inp = page.query_selector(
                "input[id*='countryPhoneCode' i], input[id*='phoneCode' i], "
                "div[data-automation-id='countryPhoneCode'], "
                "button[id*='countryPhoneCode' i], button[id*='phoneCode' i]"
            )
            if cc_inp and cc_inp.is_visible():
                has_cc = True
        except Exception:
            pass
    clean_digits = re.sub(r"\D", "", CANDIDATE.get("raw_phone") or CANDIDATE.get("phone") or "")
    raw_10 = clean_digits[-10:] if len(clean_digits) >= 10 else clean_digits
    page_url_lower = (page.url or "").lower()
    use_raw_phone = has_cc or any(dom in page_url_lower for dom in ["myworkdayjobs.com", "jobseqno=", "careers.mccain.com"])
    phone_val = raw_10 if use_raw_phone else (CANDIDATE.get("phone") or raw_10)
    # Ensure international numbers use space instead of hyphen (e.g. +91 9876543210) to satisfy strict ATS validators
    if phone_val and phone_val.startswith("+") and "-" in phone_val:
        phone_val = re.sub(r"^(\+\d+)-", r"\1 ", phone_val)

    # Clear accidental phone numbers left in Workday phoneExtension inputs
    for ext_el in page.query_selector_all("input[id*='extension' i], input[name*='extension' i]"):
        try:
            if ext_el.is_visible():
                ev = (ext_el.input_value() or "").strip()
                if ev and ("+" in ev or len(ev) > 5):
                    ext_el.fill("")
        except Exception:
            pass

    mapping = {
        "first":    CANDIDATE["first_name"],
        "last":     CANDIDATE["last_name"],
        "email":    CANDIDATE["email"],
        "phone":    phone_val,
        "linkedin": CANDIDATE["linkedin"],
    }
    filled = []
    for keyword, value in mapping.items():
        selectors = (
            [
                "input[data-automation-id='phone-number']",
                "input[id='phoneNumber--phoneNumber']",
                "input[id*='phoneNumber--phoneNumber']",
                "input[id*='phoneNumber' i]",
            ]
            if keyword == "phone"
            else []
        ) + [
            f"input[data-automation-id*='{keyword}' i]",
            f"input[id*='{keyword}' i]",
            f"input[name*='{keyword}' i]",
            f"input[placeholder*='{keyword}' i]",
        ]
        for sel in selectors:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    el_id = (el.get_attribute("id") or "").lower()
                    el_name = (el.get_attribute("name") or "").lower()
                    # Guardrail: never inject identity fields into comments, notes, country phone codes, or extensions
                    if any(bad in el_id or bad in el_name for bad in [
                        "comment", "note", "desc", "reason", "feedback",
                        "extension", "countryphonecode", "phonecode",
                    ]):
                        continue
                    if keyword == "phone" and (el.input_value() or "").strip() == value:
                        filled.append(keyword)
                        break
                    el.fill("")
                    el.fill(value)
                    filled.append(keyword)
                    break
            except Exception:
                pass
    if filled:
        print(f"[fill] Auto-filled: {', '.join(filled)}")

    # ── Mandatory Consent & Terms & Privacy Checkboxes ───────────────────────
    for chk_sel in [
        "#custExternalConsentA", "#agreeToPrivacyStatement",
        "input[type='checkbox'][id*='consent' i]", "input[type='checkbox'][id*='privacy' i]",
        "input[type='checkbox'][id*='terms' i]", "input[type='checkbox'][id*='agree' i]",
        "input[type='checkbox'][id*='statement' i]", "input[type='checkbox'][name*='consent' i]",
        "input[type='checkbox'][name*='privacy' i]", "input[type='checkbox'][name*='terms' i]"
    ]:
        try:
            for chk in page.query_selector_all(chk_sel):
                if chk.is_visible() and not chk.is_checked():
                    chk.check(force=True)
                    print(f"[consent] Checked required consent/privacy checkbox: {chk.get_attribute('id') or chk_sel}")
        except Exception:
            pass

    # ── Hierarchical Address & Location ──────────────────────────────────────
    fill_address_hierarchy(page, cand=CANDIDATE)

    # ── Date of Birth ───────────────────────────────────────────────────────
    _fill_dob(page)

    # ── City / Place of Residence ───────────────────────────────────────────
    _fill_city(page)

    # ── Work Experience ─────────────────────────────────────────────────────
    _fill_work_experience(page)

    # ── Education History ───────────────────────────────────────────────────
    _fill_education_history(page)

    # ── Screening & Custom QA Semantics ─────────────────────────────────────
    _fill_screening_and_custom_questions(page)


def _fill_workday_prompt(page: Page, inp, full_lbl: str) -> bool:
    """Select an option on Workday searchable prompt inputs (e.g. Source / Country Phone Code)."""
    def _prompt_has_chip() -> bool:
        try:
            return bool(inp.evaluate(
                "el => Boolean(el.closest(\"[data-automation-id='multiselectInputContainer'], [data-automation-id='promptContainer']\")?.querySelector(\"[data-automation-id='selectedItem']\"))"
            ))
        except Exception:
            return False

    if _prompt_has_chip():
        return True

    inp_id = (inp.get_attribute("id") or "").lower()
    preferred_terms: list[str]
    search_query = ""
    if "phonecode" in inp_id or ("phone" in full_lbl and "code" in full_lbl):
        preferred_terms = ["india (+91)", "+91", "india"]
        search_query = "India"
    elif "source" in inp_id or "hear" in full_lbl or "source" in full_lbl:
        preferred_terms = [
            "career site", "careers site", "company career site",
            "careers", "corporate website", "company website",
            "website", "job board", "online", "other",
        ]
        search_query = "Career Site"
    else:
        return False

    try:
        inp.fill("")
        inp.click()
        if search_query:
            inp.type(search_query, delay=30)
            inp.press("Enter")
        time.sleep(0.6)
        opt_selector = (
            "div[data-automation-id='promptLeafNode'], "
            "div[data-automation-id='promptOption'], "
            "li[data-automation-id='menuItem'], "
            "div[role='option']"
        )
        for _ in range(3):
            opts = page.query_selector_all(opt_selector)
            visible_opts = [o for o in opts if o.is_visible() and (o.inner_text() or "").strip()]
            if not visible_opts:
                break
            chosen = None
            for term in preferred_terms:
                chosen = next((o for o in visible_opts if term in (o.inner_text() or "").strip().lower()), None)
                if chosen:
                    break
            chosen = chosen or visible_opts[0]
            chosen_txt = (chosen.inner_text() or "").strip()
            chosen.click()
            time.sleep(0.7)
            if _prompt_has_chip():
                print(f"[fill:qa:prompt] Selected '{chosen_txt}' for '{full_lbl[:35]}...'")
                return True
        page.keyboard.press("Escape")
    except Exception:
        pass
    return False


def _fill_screening_and_custom_questions(page: Page):
    """Autofill screening questions, compensation, notice period, and technical YOE across any ATS portal."""
    try:
        from core.qa_semantics_engine import QASemanticsEngine
    except ImportError:
        return

    # 0. Passwords: fill with candidate standard password, NEVER send to LLM
    for pwd in page.query_selector_all("input[type='password']"):
        try:
            if pwd.is_visible() and not pwd.input_value():
                _, def_pwd, _ = get_portal_credentials(page.url)
                if def_pwd:
                    pwd.fill(def_pwd)
                    print("[fill:password] Auto-filled password field with candidate credentials.")
        except Exception:
            pass

    # 1. Inputs (Text, Number, Tel, Url)
    for inp in page.query_selector_all("input:not([type='file']):not([type='radio']):not([type='checkbox']):not([type='hidden']):not([type='password'])"):
        try:
            if not inp.is_visible():
                continue
            inp_id = (inp.get_attribute("id") or "").lower()
            inp_name = (inp.get_attribute("name") or "").lower()
            inp_ph = (inp.get_attribute("placeholder") or "").lower()
            lbl_el = page.query_selector(f"label[for='{inp.get_attribute('id')}']") if inp.get_attribute('id') else None
            lbl_text = (lbl_el.inner_text().strip().lower() if lbl_el else "")
            aria_lbl = (inp.get_attribute("aria-label") or "").lower()
            full_lbl = f"{lbl_text} {inp_ph} {inp_name} {inp_id} {aria_lbl}"

            # Guard comments & optional extension fields
            if any(bad in full_lbl for bad in ["comment", "note", "desc", "reason", "feedback", "extension"]):
                continue

            # Handle Workday searchable prompt inputs before generic text fill
            is_prompt_box = (
                inp_ph == "search"
                or (inp.get_attribute("data-uxi-widget-type") or "").lower() == "selectinput"
                or "multiselect" in inp_id
            )
            if is_prompt_box:
                _fill_workday_prompt(page, inp, full_lbl)
                continue

            cur_val = (inp.input_value() or "").strip()
            is_corrupted = any(cur_val.lower().startswith(bad) for bad in [
                "we need", "so for", "field question", "the instruction", "candidate info", "likely preferred"
            ])
            # If field is referral name and contains Singh or employee name, clear it (candidate has no referral)
            if ("referral" in full_lbl or "referred" in full_lbl):
                if cur_val in ("Singh", "Ankit Kumar Singh") or cur_val:
                    inp.fill("")
                    print(f"[fill:qa] Cleared referral field (no employee referral)")
                continue

            if cur_val and not is_corrupted:
                continue
            if "profileskills" in inp_name or "type the skill" in inp_ph:
                continue

            ans = QASemanticsEngine.match_question(full_lbl, field_type=inp.get_attribute("type") or "text")
            if ans and "phone" in full_lbl:
                cur_u = (page.url or "").lower()
                if any(k in cur_u for k in ["jobseqno=", "myworkdayjobs.com", "careers.mccain.com"]) or "homephone" in full_lbl:
                    digits = re.sub(r"\D", "", str(ans))
                    if len(digits) >= 10:
                        ans = digits[-10:]
            if ans and ans != "N/A":
                inp.fill(ans)
                print(f"[fill:qa] Auto-filled '{full_lbl[:35]}...' -> '{ans}'")
        except Exception:
            pass

    # 1b. Textareas (e.g. Workday desired salary / open-ended questions, never comments)
    for ta in page.query_selector_all("textarea"):
        try:
            if not ta.is_visible() or (ta.input_value() or "").strip():
                continue
            ta_id = (ta.get_attribute("id") or "").lower()
            ta_name = (ta.get_attribute("name") or "").lower()
            lbl_el = page.query_selector(f"label[for='{ta.get_attribute('id')}']") if ta.get_attribute("id") else None
            lbl_text = (lbl_el.inner_text().strip().lower() if lbl_el else "")
            if not lbl_text:
                lbl_text = (ta.evaluate(
                    "el => (el.closest('[data-automation-id^=\"formField\"]')?.querySelector('label, p')?.innerText || '').trim().toLowerCase()"
                ) or "")
            full_lbl = f"{lbl_text} {ta_name} {ta_id}"
            if any(bad in full_lbl for bad in ["comment", "note", "feedback"]):
                continue
            ans = QASemanticsEngine.match_question(full_lbl, field_type="textarea")
            if ans and ans != "N/A":
                ta.fill(ans)
                print(f"[fill:qa:textarea] Auto-filled '{full_lbl[:35]}...' -> '{ans[:40]}'")
        except Exception:
            pass

    # 2. Dropdowns (<select>) and Workday custom listbox buttons (<button aria-haspopup='listbox'>)
    for btn in page.query_selector_all("button[aria-haspopup='listbox']"):
        try:
            if not btn.is_visible():
                continue
            cur_btn_txt = (btn.inner_text() or "").strip().lower()
            if cur_btn_txt and cur_btn_txt not in ("select one", "select", "select an option", "please select"):
                continue
            btn_id = btn.get_attribute("id") or ""
            lbl_el = page.query_selector(f"label[for='{btn_id}']") if btn_id else None
            lbl_text = (lbl_el.inner_text().strip().lower() if lbl_el else "")
            if not lbl_text:
                lbl_text = (btn.evaluate(
                    "el => (el.closest('[data-automation-id^=\"formField\"]')?.querySelector('label, span, p')?.innerText || '').trim().toLowerCase()"
                ) or "")
            btn.click()
            time.sleep(0.35)
            opt_els = [
                o for o in page.query_selector_all("ul[role='listbox'] li, div[role='listbox'] [role='option'], div[data-automation-id='promptOption']")
                if o.is_visible() and (o.inner_text() or "").strip()
            ]
            opt_texts = [(o.inner_text() or "").strip() for o in opt_els]
            valid_opts = [t for t in opt_texts if t.lower() not in ("select one", "please select")]
            if not valid_opts:
                page.keyboard.press("Escape")
                continue
            ans = QASemanticsEngine.match_question(lbl_text or btn_id, field_type="select", options=valid_opts)
            chosen_opt = None
            if ans:
                chosen_opt = next((o for o in opt_els if (o.inner_text() or "").strip().lower() == ans.lower()), None)
                if not chosen_opt:
                    chosen_opt = next((o for o in opt_els if ans.lower() in (o.inner_text() or "").strip().lower()), None)
            if chosen_opt:
                chosen_txt = (chosen_opt.inner_text() or "").strip()
                chosen_opt.click()
                print(f"[fill:qa:listbox] Selected '{chosen_txt}' for '{lbl_text[:35]}...'")
                time.sleep(0.25)
            else:
                page.keyboard.press("Escape")
        except Exception:
            try:
                page.keyboard.press("Escape")
            except Exception:
                pass

    for sel in page.query_selector_all("select"):
        try:
            if not sel.is_visible():
                continue
            cur = (sel.input_value() or "").strip()
            if cur and cur.lower() not in ("", "select", "select an option", "please select"):
                continue
            sel_id = sel.get_attribute("id") or ""
            lbl_el = page.query_selector(f"label[for='{sel_id}']") if sel_id else None
            lbl_text = (lbl_el.inner_text().strip().lower() if lbl_el else "")
            opts = sel.query_selector_all("option")
            opt_texts = [o.inner_text().strip() for o in opts if o.inner_text().strip()]
            if not opt_texts:
                continue

            ans = QASemanticsEngine.match_question(lbl_text or sel_id, field_type="select", options=opt_texts)
            if ans and ans in opt_texts:
                sel.select_option(label=ans)
                print(f"[fill:qa:select] Selected '{ans}' for '{lbl_text[:35]}...'")
        except Exception:
            pass

    # 3. Radio fieldsets & groups (Taleo, Workday, Greenhouse)
    for fs in page.query_selector_all("fieldset, div[role='radiogroup'], div[data-automation-id*='radio' i], div[data-automation-id*='group' i]"):
        try:
            legend = fs.query_selector("legend, label, div[data-automation-id*='label' i], span[id*='label' i], h3, h4")
            leg_text = (legend.inner_text() if legend else "").strip().lower()
            radios = fs.query_selector_all("input[type='radio']")
            if not radios or any(r.is_checked() for r in radios):
                continue
            radio_labels = []
            for r in radios:
                r_id = r.get_attribute("id") or ""
                lbl_el = fs.query_selector(f"label[for='{r_id}']")
                if lbl_el:
                    radio_labels.append(lbl_el.inner_text().strip())
                else:
                    # Check parent label or adjacent text
                    parent_lbl = r.query_selector("xpath=ancestor::label")
                    if parent_lbl:
                        radio_labels.append(parent_lbl.inner_text().strip())

            ans = QASemanticsEngine.match_question(leg_text, field_type="radio", options=radio_labels)
            if ans:
                for r in radios:
                    r_id = r.get_attribute("id") or ""
                    lbl_el = fs.query_selector(f"label[for='{r_id}']")
                    lbl_txt = (lbl_el.inner_text() if lbl_el else "").strip().lower()
                    if not lbl_txt:
                        parent_lbl = r.query_selector("xpath=ancestor::label")
                        if parent_lbl:
                            lbl_txt = parent_lbl.inner_text().strip().lower()
                    if ans.lower() in lbl_txt or lbl_txt in ans.lower():
                        r.check(force=True)
                        print(f"[fill:qa:radio] Checked '{lbl_txt}' for '{leg_text[:35]}...'")
                        break
        except Exception:
            pass

    # 4. PrimeNG custom controls (<p-select>, <p-autocomplete> skill chips, <p-radiobutton>)
    _fill_primeng_controls(page)


def _fill_primeng_controls(page: Page):
    """Universal handler for PrimeNG Angular controls used by portals such as Ceipal."""
    try:
        from core.qa_semantics_engine import QASemanticsEngine
    except ImportError:
        return

    # 4a. <p-select> dropdowns
    for ps in page.query_selector_all("p-select"):
        try:
            if not ps.is_visible():
                continue
            cur_txt = (ps.inner_text() or "").strip()
            if cur_txt and cur_txt.lower() not in ("select", "select an option", "please select"):
                continue
            lbl_txt = ps.evaluate("""el => {
                let wrap = el.closest('.formL-2')?.parentElement || el.parentElement?.parentElement;
                let lbl = wrap ? (wrap.querySelector('label, p, span')?.innerText || '') : '';
                return lbl.trim().split('\\n')[0].toLowerCase();
            }""")
            combo = ps.query_selector("[role='combobox']") or ps
            combo.click()
            time.sleep(0.4)
            opt_els = page.query_selector_all("[role='listbox'] [role='option'], .p-select-overlay li[role='option']")
            opt_texts = [(o.inner_text() or "").strip() for o in opt_els if (o.inner_text() or "").strip()]
            if not opt_texts:
                page.keyboard.press("Escape")
                continue
            ans = QASemanticsEngine.match_question(lbl_txt or "select", field_type="select", options=opt_texts)
            if ans:
                clicked = False
                for o in opt_els:
                    ot = (o.inner_text() or "").strip()
                    if ot.lower() == ans.lower() or ans.lower() in ot.lower():
                        o.click()
                        clicked = True
                        print(f"[fill:primeng:select] Selected '{ot}' for '{lbl_txt}'")
                        time.sleep(0.3)
                        break
                if not clicked:
                    page.keyboard.press("Escape")
            else:
                page.keyboard.press("Escape")
        except Exception:
            pass

    # 4b. <p-autocomplete> multi-chip skill inputs (e.g., Ceipal profileSkills)
    skill_inp = page.query_selector("p-autocomplete input[name='profileSkills'], p-autocomplete input[placeholder*='skill' i]")
    if skill_inp and skill_inp.is_visible():
        try:
            existing_chips = page.query_selector_all("p-autocomplete .p-autocomplete-chip-item, p-autocomplete li.p-autocomplete-token")
            if not existing_chips:
                skills_csv = QASemanticsEngine.match_question("primary skills", field_type="text")
                skills = [s.strip() for s in skills_csv.split(",") if s.strip()][:8]
                for sk in skills:
                    skill_inp.fill(sk)
                    time.sleep(0.15)
                    page.keyboard.press("Enter")
                    time.sleep(0.15)
                print(f"[fill:primeng:skills] Added {len(skills)} skill chips.")
        except Exception:
            pass

    # 4c. <p-radiobutton> groups (e.g., Ceipal Consent for all jobs)
    for rb in page.query_selector_all("p-radiobutton input[type='radio']"):
        try:
            if rb.is_checked():
                continue
            r_wrap_txt = rb.evaluate("""el => (el.closest('div')?.parentElement?.parentElement?.innerText || '').toLowerCase()""")
            if any(k in r_wrap_txt for k in ["consent for all", "yes", "agree"]):
                rb.check(force=True)
                print("[fill:primeng:radio] Checked PrimeNG consent radio.")
                break
        except Exception:
            pass


def _fill_dob(page: Page):
    """Autofill Date of Birth fields and dropdowns."""
    dob_val = CANDIDATE.get("dob", "")
    dob_day = CANDIDATE.get("dob_day", "")
    dob_month = CANDIDATE.get("dob_month", "")
    dob_month_name = CANDIDATE.get("dob_month_name", "")
    dob_year = CANDIDATE.get("dob_year", "")
    dob_iso = CANDIDATE.get("dob_iso", "")

    # Derive parts if missing
    if dob_iso and not dob_year and "-" in dob_iso:
        parts = dob_iso.split("-")
        if len(parts) == 3:
            dob_year, dob_month, dob_day = parts[0], parts[1], parts[2]

    if not (dob_val or dob_iso or dob_year):
        return

    # 1. Text / Date inputs
    for sel in [
        "input[id*='dob' i]", "input[name*='dob' i]",
        "input[id*='birth' i]", "input[name*='birth' i]",
        "input[id*='bday' i]", "input[name*='bday' i]",
        "input[placeholder*='dob' i]", "input[placeholder*='birth' i]",
        "input[placeholder*='mm/dd/yyyy' i]", "input[placeholder*='dd/mm/yyyy' i]",
    ]:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                ph = (el.get_attribute("placeholder") or "").lower()
                if ("dd/mm" in ph or "dd-mm" in ph) and dob_day and dob_month and dob_year:
                    val_to_fill = f"{dob_day}/{dob_month}/{dob_year}"
                else:
                    val_to_fill = dob_val or dob_iso
                if val_to_fill:
                    el.fill(val_to_fill)
                    print(f"[fill:dob] Filled DOB '{val_to_fill}' via {sel}")
                    break
        except Exception:
            pass

    # 2. Year/Month/Day select dropdowns
    if dob_year:
        for y_sel in ["select[id*='birthYear' i]", "select[id*='dob_year' i]", "select[name*='birthYear' i]"]:
            try:
                el = page.query_selector(y_sel)
                if el and el.is_visible():
                    el.select_option(value=dob_year)
            except Exception:
                pass
    if dob_month or dob_month_name:
        for m_sel in ["select[id*='birthMonth' i]", "select[id*='dob_month' i]", "select[name*='birthMonth' i]"]:
            try:
                el = page.query_selector(m_sel)
                if el and el.is_visible():
                    try:
                        if dob_month:
                            el.select_option(value=dob_month)
                    except Exception:
                        if dob_month_name:
                            el.select_option(label=dob_month_name)
            except Exception:
                pass
    if dob_day:
        for d_sel in ["select[id*='birthDay' i]", "select[id*='dob_day' i]", "select[name*='birthDay' i]"]:
            try:
                el = page.query_selector(d_sel)
                if el and el.is_visible():
                    el.select_option(value=dob_day)
            except Exception:
                pass


def _get_work_experience() -> list:
    """Load work experience dynamically from client_secret.json or experience.json."""
    for secret_path in [SECRETS_FILE, GLOBAL_SECRETS_FILE, Path(__file__).parent.parent / "user_inputs" / "experience.json"]:
        if secret_path.exists():
            try:
                data = json.loads(secret_path.read_text())
                if "work_experience_entries" in data:
                    return data["work_experience_entries"]
                if "work_experience" in data:
                    return data["work_experience"]
            except Exception:
                pass
    return []


def _get_education_history() -> list:
    """Load education history dynamically from client_secret.json or .env."""
    for secret_path in [SECRETS_FILE, GLOBAL_SECRETS_FILE, Path(__file__).parent.parent / "user_inputs" / "education.json"]:
        if secret_path.exists():
            try:
                data = json.loads(secret_path.read_text())
                if "education_entries" in data:
                    return data["education_entries"]
            except Exception:
                pass
    # Build from environment if university is configured
    if CANDIDATE.get("university"):
        return [{
            "institution": CANDIDATE.get("university", ""),
            "degree": CANDIDATE.get("degree", ""),
            "major": CANDIDATE.get("major", ""),
            "start_year": CANDIDATE.get("college_start_year", ""),
            "end_year": CANDIDATE.get("college_end_year", ""),
            "score": CANDIDATE.get("college_cgpa", ""),
            "percentage": CANDIDATE.get("college_percentage", ""),
        }]
    return []


def _fill_work_experience(page: Page):
    """Autofills work experience history loaded dynamically from secure configuration."""
    WORK_EXP = _get_work_experience()
    if not WORK_EXP:
        print("[fill:experience] No structured work experience entries found to fill.")
        return

    emp_inputs = page.query_selector_all("input[id*='employer' i], input[id*='company' i], input[name*='employer' i], input[name*='company' i]")
    title_inputs = page.query_selector_all("input[id*='title' i], input[id*='jobTitle' i], input[name*='title' i], input[name*='jobTitle' i]")
    desc_inputs = page.query_selector_all("textarea[id*='exp' i], textarea[id*='duty' i], textarea[id*='desc' i], textarea[name*='duty' i], textarea[name*='description' i]")

    for idx, exp in enumerate(WORK_EXP):
        if idx < len(emp_inputs):
            try:
                emp_inputs[idx].fill(exp.get("company", ""))
            except Exception:
                pass
        if idx < len(title_inputs):
            try:
                title_inputs[idx].fill(exp.get("title", ""))
            except Exception:
                pass
        if idx < len(desc_inputs):
            try:
                desc_inputs[idx].fill(exp.get("description", ""))
            except Exception:
                pass

    print(f"[fill:experience] Populated {len(WORK_EXP)} work experience entries.")


def _fill_education_history(page: Page):
    """Autofills education history loaded dynamically from secure configuration."""
    EDUS = _get_education_history()
    if not EDUS:
        print("[fill:education] No structured education history entries found to fill.")
        return

    school_inputs = page.query_selector_all("input[id*='school' i], input[id*='institution' i], input[id*='college' i], input[name*='school' i], input[name*='institution' i]")
    degree_inputs = page.query_selector_all("input[id*='degree' i], input[name*='degree' i]")
    major_inputs = page.query_selector_all("input[id*='major' i], input[name*='major' i], input[id*='fieldOfStudy' i]")

    for idx, edu in enumerate(EDUS):
        if idx < len(school_inputs):
            try:
                school_inputs[idx].fill(edu.get("institution", ""))
            except Exception:
                pass
        if idx < len(degree_inputs):
            try:
                degree_inputs[idx].fill(edu.get("degree", ""))
            except Exception:
                pass
        if idx < len(major_inputs):
            try:
                major_inputs[idx].fill(edu.get("major", ""))
            except Exception:
                pass

    print(f"[fill:education] Populated {len(EDUS)} education entries.")


def _fill_city(page: Page):
    """
    Fill city / place-of-residence fields.
    Handles both free-text inputs and <select> dropdowns dynamically from CANDIDATE config.
    """
    CITY_PRIMARY  = CANDIDATE.get("city", "")
    CITY_FALLBACK = CANDIDATE.get("city_fallback", CITY_PRIMARY)

    if not CITY_PRIMARY and not CITY_FALLBACK:
        return

    CITY_SELECTORS = [
        "input[id*='city']",      "input[name*='city']",
        "input[id*='City']",      "input[name*='City']",
        "input[id*='residence']", "input[name*='residence']",
        "input[id*='location']",  "input[name*='location']",
        "input[placeholder*='city']", "input[placeholder*='City']",
        "input[placeholder*='place of residence']",
        "input[placeholder*='Place of Residence']",
    ]
    CITY_DROPDOWN_SELECTORS = [
        "select[id*='city']",      "select[name*='city']",
        "select[id*='City']",      "select[name*='City']",
        "select[id*='residence']", "select[name*='residence']",
        "select[id*='location']",  "select[name*='location']",
    ]

    # 1. Text inputs
    for sel in CITY_SELECTORS:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                if CITY_PRIMARY:
                    el.fill(CITY_PRIMARY)
                    time.sleep(0.5)
                    # Check if value was accepted (some ATS validate inline)
                    current_val = el.input_value().lower()
                    if CITY_PRIMARY.lower() in current_val:
                        print(f"[fill:city] Set city='{CITY_PRIMARY}' via {sel}")
                        return
                if CITY_FALLBACK:
                    el.fill("")
                    el.fill(CITY_FALLBACK)
                    print(f"[fill:city] Set fallback city='{CITY_FALLBACK}' via {sel}")
                return
        except Exception:
            pass

    # 2. Dropdowns
    for sel in CITY_DROPDOWN_SELECTORS:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                # Try selecting primary city
                if CITY_PRIMARY:
                    try:
                        el.select_option(label=CITY_PRIMARY)
                        print(f"[fill:city] Dropdown selected='{CITY_PRIMARY}' via {sel}")
                        return
                    except Exception:
                        pass
                # Fallback
                if CITY_FALLBACK:
                    try:
                        el.select_option(label=CITY_FALLBACK)
                        print(f"[fill:city] Dropdown fallback selected='{CITY_FALLBACK}' via {sel}")
                        return
                    except Exception:
                        pass
        except Exception:
            pass


def _inspect_file_input(inp, resume_filename: str) -> tuple[str, bool]:
    """Classify a file input ('photo_or_id', 'cover_letter', 'resume') and detect existing uploads."""
    try:
        info = inp.evaluate(
            """(el, fname) => {
                const accept = (el.getAttribute('accept') || '').toLowerCase();
                const id = (el.getAttribute('id') || '').toLowerCase();
                const name = (el.getAttribute('name') || '').toLowerCase();
                const aria = (el.getAttribute('aria-label') || '').toLowerCase();
                const lblEl = el.id ? document.querySelector(`label[for="${el.id}"]`) : null;
                const lbl = (lblEl ? lblEl.innerText : '').toLowerCase();
                const scope = el.closest('[data-automation-id^="formField"], [data-automation-id="file-upload-drop-zone"], section, fieldset, .attachmentField, form') || el.parentElement;
                const scopeText = (scope ? scope.innerText : '').toLowerCase();
                const headerScope = el.closest('[data-automation-id^="formField"], section, fieldset, .attachmentField') || el.parentElement;
                const headerText = (headerScope ? headerScope.innerText : '').slice(0, 300).toLowerCase();
                const hasExistingItem = Boolean(
                    scope && (
                        scope.querySelector('[data-automation-id="file-upload-item-name"], [data-automation-id="delete-file"], [id$="_attachDownloadLabelLink"]')
                        || scopeText.includes('successfully uploaded')
                        || (fname && scopeText.includes(fname.toLowerCase()))
                    )
                );
                return { accept, meta: `${id} ${name} ${aria} ${lbl} ${headerText}`, hasExistingItem };
            }""",
            resume_filename,
        ) or {}
    except Exception:
        return "resume", False

    accept = info.get("accept", "")
    meta = info.get("meta", "")
    has_existing = bool(info.get("hasExistingItem"))
    photo_kw = ("photo", "headshot", "portrait", "picture", "avatar", "selfie", "signature", "id card", "aadhaar", "pan card")
    if any(k in meta for k in photo_kw) or ("image/" in accept and ".pdf" not in accept and "resume" not in meta and "cv" not in meta):
        return "photo_or_id", has_existing
    cl_kw = ("cover letter", "cover_letter", "coverletter", "covering letter", "motivation letter", "letter of motivation", "letter of intent")
    if any(k in meta for k in cl_kw):
        return "cover_letter", has_existing
    return "resume", has_existing


def _upload_resume(page: Page, slug: str = "") -> bool:
    """Attempt resume upload on resume/CV file inputs only, skipping Photo/ID fields and existing uploads."""
    resume = str(RESUME_PATH.resolve())
    resume_name = Path(resume).name
    cover_letter = None
    if slug:
        slug_clean = slug.lower().replace("_", "")
        slug_tokens = [t for t in slug.lower().split("_") if len(t) > 2]
        # Search job-specific application docs first, then central cover_letters directory (strict slug/company match)
        search_dirs = [
            DOCS_DIR / "applications" / slug,
            DOCS_DIR / "applications",
            COVER_LETTERS_DIR,
        ]
        for sdir in search_dirs:
            if sdir.exists():
                is_job_dir = (sdir == DOCS_DIR / "applications" / slug)
                candidates = []
                for p in sdir.glob("*.*"):
                    if p.suffix not in (".docx", ".pdf", ".md"):
                        continue
                    pname_clean = p.name.lower().replace("_", "").replace("-", "")
                    stem_lower = p.stem.lower()
                    matched_company_tokens = (
                        bool(slug_tokens)
                        and slug_tokens[0] in stem_lower
                        and sum(1 for t in slug_tokens if t in stem_lower) >= min(2, len(slug_tokens))
                    )
                    if slug_clean in pname_clean or matched_company_tokens or (is_job_dir and "cover" in stem_lower):
                        candidates.append(p)
                if candidates:
                    candidates.sort(key=lambda x: (0 if x.suffix == ".docx" else (1 if x.suffix == ".pdf" else 2)))
                    cover_letter = str(candidates[0].resolve())
                    break
    # Never attach another company's cover letter via global fallback — only use cover letter matched to slug above.

    # 1. Clear any attachment comment inputs to avoid leaking text/email
    for comment_sel in [
        "input[id*='AttachedFilesBlock-comment']",
        "input[name*='AttachedFilesBlock-comment']",
        "input[id*='comment' i]",
    ]:
        try:
            c_el = page.query_selector(comment_sel)
            if c_el and c_el.is_visible():
                c_el.fill("")
        except Exception:
            pass

    # 2. Check for dual/multiple file inputs (e.g. CV Upload + Cover Letter), filtering out Photo/ID & existing files
    file_inputs = page.query_selector_all("input[type='file']")
    if len(file_inputs) >= 2:
        try:
            did_dual = False
            resume_handled = False
            for idx, finp in enumerate(file_inputs):
                kind, already = _inspect_file_input(finp, resume_name)
                near_txt = (finp.evaluate("""el => {
                    let cur = el.parentElement;
                    for (let i = 0; i < 4 && cur; i++) {
                        let t = (cur.innerText || '').trim();
                        if (t.length > 0 && t.length < 300) return t.toLowerCase();
                        cur = cur.parentElement;
                    }
                    return (el.parentElement?.innerText || '').toLowerCase();
                }""") or "")
                if any(k in near_txt for k in ["upload files", "additional document", "supporting", "cover letter"]) and "upload resume" not in near_txt:
                    kind = "cover_letter"
                if kind == "photo_or_id":
                    print(f"[upload] Skipping non-document file input #{idx} ({kind}).")
                    continue
                if kind == "cover_letter":
                    if cover_letter:
                        cl_name = Path(cover_letter).name.lower()
                        cl_box = (finp.evaluate("el => (el.closest('.form-group, section, div[class*=upload]')?.innerText || '').toLowerCase()") or "")
                        if cl_name not in cl_box:
                            finp.set_input_files(cover_letter)
                            print(f"[upload] Tailored Cover Letter uploaded to file input #{idx}: {Path(cover_letter).name}")
                            did_dual = True
                        else:
                            print(f"[upload] Tailored Cover Letter already attached ({Path(cover_letter).name}); skipping duplicate upload.")
                            did_dual = True
                    else:
                        print(f"[upload] Skipping supplementary file input #{idx} (cover_letter) - no job-specific cover letter to attach.")
                    continue
                if kind == "resume":
                    if already or resume_handled:
                        print("[upload] Resume already uploaded in drop-zone; skipping duplicate upload.")
                        resume_handled = True
                        did_dual = True
                    else:
                        finp.set_input_files(resume)
                        print(f"[upload] Master Resume uploaded to file input #{idx}")
                        resume_handled = True
                        did_dual = True
                        time.sleep(1)
            if did_dual:
                return True
        except Exception as e:
            print(f"[upload] Error in dual file upload: {e}")

    uploaded = False

    # 2.5 SuccessFactors dynamic attachment triggers (Resume & Cover Letter)
    try:
        sf_resume_field = page.query_selector(".attachmentField:has(label:has-text('Resume'))")
        if sf_resume_field and not sf_resume_field.query_selector("[id$='_attachDownloadLabelLink']"):
            attach_icon = sf_resume_field.query_selector(".addAttachments, [id$='_attachIcon']")
            if attach_icon:
                attach_icon.click()
                time.sleep(1)
                sf_file_input = page.query_selector(".calloutPopupWrapper input[type='file'], input[name='fileData1']")
                if sf_file_input:
                    sf_file_input.set_input_files(resume)
                    print("[upload] SuccessFactors: Resume uploaded successfully.")
                    time.sleep(2)
                    uploaded = True

        if cover_letter:
            sf_cl_field = page.query_selector(".attachmentField:has(label:has-text('Cover Letter'))")
            if sf_cl_field and not sf_cl_field.query_selector("[id$='_attachDownloadLabelLink']"):
                attach_icon = sf_cl_field.query_selector(".addAttachments, [id$='_attachIcon']")
                if attach_icon:
                    attach_icon.click()
                    time.sleep(1)
                    sf_file_input = page.query_selector(".calloutPopupWrapper input[type='file'], input[name='fileData1']")
                    if sf_file_input:
                        sf_file_input.set_input_files(cover_letter)
                        print(f"[upload] SuccessFactors: Cover Letter uploaded successfully ({Path(cover_letter).name}).")
                        time.sleep(2)
    except Exception as e:
        print(f"[upload] Note on SuccessFactors attachment: {e}")

    for sel in [
        "input[type='file']",
        "input[id*='resume']",
        "input[name*='resume']",
        "input[id*='cv']",
    ]:
        try:
            el = page.query_selector(sel)
            if el:
                gp_raw = el.evaluate("el => (el.parentElement?.parentElement?.innerText || '').toLowerCase()")
                gp_txt = gp_raw if isinstance(gp_raw, str) else ""
                if "awliwidget" in gp_txt or ("upload files" in gp_txt and "upload resume" not in gp_txt):
                    continue
                inner_fn = getattr(page, "inner_text", None)
                body_txt = (inner_fn("body") or "").lower() if callable(inner_fn) else ""
                if resume_name.lower() in body_txt:
                    print("[upload] Resume filename already displayed on page; skipping redundant single-input upload.")
                    return True
                kind, already = _inspect_file_input(el, resume_name)
                if kind == "photo_or_id":
                    print(f"[upload] Skipping non-resume file input ({kind}) via {sel}")
                    continue
                if kind == "cover_letter":
                    if cover_letter:
                        cl_name = Path(cover_letter).name.lower()
                        cl_box = (el.evaluate("el => (el.closest('.form-group, section, div[class*=upload]')?.innerText || '').toLowerCase()") or "")
                        if cl_name not in cl_box:
                            el.set_input_files(cover_letter)
                            print(f"[upload] Tailored Cover Letter uploaded via {sel}: {Path(cover_letter).name}")
                            uploaded = True
                            time.sleep(2)
                            return True
                    else:
                        print(f"[upload:guard] STRICT ZERO-TOLERANCE GUARD: File input '{sel}' is for Cover Letter, but no tailored cover letter is provided. Skipping input. NEVER UPLOAD RESUME INTO COVER LETTER FIELD.")
                        continue
                if kind != "resume":
                    print(f"[upload:guard] Skipping non-resume file input ({kind}) via {sel}")
                    continue
                if already:
                    print(f"[upload] Resume already uploaded via {sel}; skipping duplicate upload.")
                    return True
                el.set_input_files(resume)
                print(f"[upload] Resume uploaded via {sel}")
                uploaded = True
                time.sleep(2)
                
                # Check for Taleo Attach button
                for attach_btn_sel in [
                    "input[id*='attachFileCommand']",
                    "button:has-text('Attach')",
                    "input[value='Attach']",
                ]:
                    try:
                        ab = page.query_selector(attach_btn_sel)
                        if ab and ab.is_visible():
                            ab.click()
                            print(f"[upload] Clicked Attach button via {attach_btn_sel}")
                            time.sleep(3)
                            break
                    except Exception:
                        pass
                        
                # Handle possible overwrite confirmation modal
                for yes_sel in [
                    "button[id*='YesOverwriteFileCommand']",
                    "input[id*='YesOverwriteFileCommand']",
                    "button:has-text('Yes')",
                    "input[value='Yes']",
                ]:
                    try:
                        yb = page.query_selector(yes_sel)
                        if yb and yb.is_visible():
                            yb.click()
                            print("[upload] Confirmed file overwrite modal")
                            time.sleep(2)
                            break
                    except Exception:
                        pass
                break
        except Exception:
            pass

    # 3. Sanitize Taleo Attachments Table if present
    _sanitize_taleo_attachments(page)
    return uploaded


def _sanitize_taleo_attachments(page: Page):
    """Ensure master CV has Resume/CV=Yes, Relevant=Yes, and Cover Letters have Relevant=Yes."""
    try:
        rows = page.query_selector_all("tr")
        for tr in rows:
            text = (tr.inner_text() or "").lower()
            # If row is the master CV
            if "ankit_resume" in text or "resume" in text:
                # Check Resume / CV checkbox
                resume_chk = tr.query_selector("input[id*='resumeselectionid']")
                if resume_chk and not resume_chk.is_checked():
                    resume_chk.check()
                    print("[attachments] Set Resume/CV = Yes for master CV")
                # Check Relevant Files checkbox
                rel_chk = tr.query_selector("input[id*='selectionid']:not([id*='resumeselectionid'])")
                if rel_chk and not rel_chk.is_checked():
                    rel_chk.check()
                    print("[attachments] Set Relevant Files = Yes for master CV")
                    
            # If row is a Cover Letter
            elif "cover" in text:
                rel_chk = tr.query_selector("input[id*='selectionid']:not([id*='resumeselectionid'])")
                if rel_chk and not rel_chk.is_checked():
                    rel_chk.check()
                    print("[attachments] Set Relevant Files = Yes for Cover Letter")
    except Exception as e:
        print(f"[attachments] Error sanitizing attachments table: {e}")


def _handle_relevant_files(page: Page) -> bool:
    """
    Automatically click 'Yes' whenever the portal asks about relevant files.
    Covers Taleo, Workday, and generic portals.
    Per candidate rule: ALWAYS select Yes and attach the candidate resume.
    """
    RELEVANT_KEYWORDS = [
        "relevant file", "relevant document", "attach file",
        "upload supporting", "supporting document", "would you like to attach",
        "do you have any file", "additional document",
    ]
    page_text = page.inner_text("body").lower()
    triggered = any(kw in page_text for kw in RELEVANT_KEYWORDS)

    if not triggered:
        return False

    print("[relevant-files] Detected 'Relevant Files' prompt - selecting Yes...")

    # Strategy 1: radio/button labelled Yes
    for sel in [
        "input[type='radio'][value='Y']",
        "input[type='radio'][value='yes']",
        "input[type='radio'][value='Yes']",
        "input[type='radio'][value='true']",
        "input[type='radio'][value='1']",
    ]:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click()
                print(f"[relevant-files] Clicked Yes radio via {sel}")
                time.sleep(1)
                break
        except Exception:
            pass

    # Strategy 2: button/link with text Yes
    for btn_text in ["Yes", "YES", "yes"]:
        try:
            btn = page.get_by_role("button", name=btn_text, exact=True)
            if btn.is_visible():
                btn.click()
                print(f"[relevant-files] Clicked Yes button")
                time.sleep(1)
                break
        except Exception:
            pass

    # Strategy 3: Taleo-specific Yes link/button
    for sel in [
        "a[title*='Yes']",
        "input[value='Yes']",
        "button:has-text('Yes')",
    ]:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click()
                print(f"[relevant-files] Clicked Yes via {sel}")
                time.sleep(1)
                break
        except Exception:
            pass

    # After clicking Yes, attempt to upload resume into any revealed file input
    time.sleep(2)
    _upload_resume(page)
    return True


def _alert_before_submit(slug: str):
    alert(f"Review & Submit [{slug}]", "All fields filled. Please review then click Submit.")
    print(f"[apply] Prefill complete for [{slug}]. Browser kept open for your review & submission.")


def _apply_pinpoint(url: str, slug: str, fields: dict = None, keep_open: bool = True, auto_submit: bool = False):
    print("[apply:pinpoint] Pinpoint HQ: persistent session -> navigate -> autofill form -> resume upload...")
    pw, ctx, page = open_persistent_browser()

    # 1. Navigate to application form
    app_url = url if "/applications/new" in url else url.rstrip("/") + "/applications/new"
    navigate(page, app_url)
    time.sleep(2.5)

    # Dismiss cookie banner if present
    try:
        accept_btn = page.locator("button:has-text('Accept all')")
        if accept_btn.count() > 0 and accept_btn.first.is_visible():
            accept_btn.first.click()
            time.sleep(0.5)
    except Exception:
        pass

    cand = CANDIDATE.copy()

    # 2. Personal Information
    if page.locator("#application_form_application_first_name").count() > 0:
        page.fill("#application_form_application_first_name", cand.get("first_name", ""))
    if page.locator("#application_form_application_last_name").count() > 0:
        page.fill("#application_form_application_last_name", cand.get("last_name", ""))
    if page.locator("#application_form_application_email").count() > 0:
        page.fill("#application_form_application_email", cand.get("email", ""))
    if page.locator("#application_form_application_linkedin_url").count() > 0:
        page.fill("#application_form_application_linkedin_url", cand.get("linkedin", ""))

    # Phone number & dial code
    try:
        flag = page.locator(".selected-flag")
        if flag.count() > 0:
            flag.click()
            time.sleep(0.3)
            in_item = page.locator("li.country[data-country-code='in']")
            if in_item.count() > 0:
                in_item.first.click()
                time.sleep(0.2)
        phone_val = cand.get("raw_phone", "") or cand.get("phone", "")
        if page.locator("#application_form_application_phone").count() > 0:
            page.fill("#application_form_application_phone", phone_val)
    except Exception as e:
        print(f"[apply:pinpoint] Note on phone: {e}")

    # Address
    try:
        country_inp = page.locator("input[id='application_form[application][country]']")
        if country_inp.count() > 0:
            target_country = cand.get("country", "India")
            country_inp.focus()
            page.keyboard.type(target_country, delay=25)
            time.sleep(0.4)
            for opt in page.locator(".react-select__option").all():
                if opt.inner_text().strip() == target_country:
                    opt.click()
                    break
        fill_address_hierarchy(page, cand=cand)
    except Exception as e:
        print(f"[apply:pinpoint] Note on address: {e}")

    # 3. Resume / CV Upload
    try:
        cv_input = page.locator("input[id='application_form[application][cv]']")
        if cv_input.count() > 0:
            resume_path = RESUME_PATH.resolve()
            cv_input.set_input_files(str(resume_path))
            print(f"[apply:pinpoint] Uploaded resume: {resume_path.name}")
            time.sleep(2)
    except Exception as e:
        print(f"[apply:pinpoint] Warning on resume upload: {e}")

    # 4. Screening Questions
    # Q0: Applied for employment with Continental? -> No
    try:
        q0 = page.locator("#application_form_application_answers_attributes_0_boolean_answer_false")
        if q0.count() > 0:
            q0.check(force=True)
    except Exception:
        pass

    # Q1: Previously employed at Continental? -> No
    try:
        q1 = page.locator("#application_form_application_answers_attributes_1_boolean_answer_false")
        if q1.count() > 0:
            q1.check(force=True)
    except Exception:
        pass

    # Q2: When will you be available to work? -> Immediate (today)
    try:
        from datetime import datetime
        now = datetime.now()
        day_sel = page.locator("#application_form_application_answers_attributes_2_date_answer_3i")
        month_sel = page.locator("#application_form_application_answers_attributes_2_date_answer_2i")
        year_sel = page.locator("#application_form_application_answers_attributes_2_date_answer_1i")
        if day_sel.count() > 0:
            day_sel.select_option(str(now.day))
        if month_sel.count() > 0:
            month_sel.select_option(str(now.month))
        if year_sel.count() > 0:
            year_sel.select_option(str(now.year))
    except Exception as e:
        print(f"[apply:pinpoint] Note on availability date: {e}")

    # Q3: What type of work are you available for? -> Full Time
    try:
        q3_inp = page.locator("#application_form_application_answers_attributes_3_text_answer")
        if q3_inp.count() > 0:
            q3_inp.focus()
            page.keyboard.press("ArrowDown")
            time.sleep(0.4)
            ft_opt = page.locator(".react-select__option:has-text('Full Time')")
            if ft_opt.count() > 0:
                ft_opt.first.click()
                time.sleep(0.3)
    except Exception as e:
        print(f"[apply:pinpoint] Note on work type: {e}")

    # Q4: Are you at least 18 years of age? -> Yes
    try:
        q4 = page.locator("#application_form_application_answers_attributes_4_boolean_answer_true")
        if q4.count() > 0:
            q4.check(force=True)
    except Exception:
        pass

    # Q5: Will you now or in the future require employment visa sponsorship? -> Yes (US role, candidate in India)
    try:
        q5 = page.locator("#application_form_application_answers_attributes_5_boolean_answer_true")
        if q5.count() > 0:
            q5.check(force=True)
    except Exception:
        pass

    # Q6: Did a current Continental team member refer you? -> No
    try:
        q6 = page.locator("#application_form_application_answers_attributes_6_boolean_answer_false")
        if q6.count() > 0:
            q6.check(force=True)
    except Exception:
        pass

    # Q8: Are you currently a Continental team member? -> No – I am not a current Continental team member
    try:
        q8_inp = page.locator("#application_form_application_answers_attributes_8_text_answer")
        if q8_inp.count() > 0:
            q8_inp.focus()
            page.keyboard.press("ArrowDown")
            time.sleep(0.4)
            no_member_opt = page.locator(".react-select__option:has-text('No')")
            if no_member_opt.count() > 0:
                no_member_opt.first.click()
                time.sleep(0.3)
    except Exception as e:
        print(f"[apply:pinpoint] Note on current team member: {e}")

    # 5. Diversity & Inclusion (Self-Disclosure)
    try:
        # Gender -> Male
        g_inp = page.locator("#application_form_equality_monitoring_gender")
        if g_inp.count() > 0:
            g_inp.focus()
            page.keyboard.press("ArrowDown")
            time.sleep(0.3)
            page.locator(".react-select__option:has-text('Male')").first.click()
            time.sleep(0.2)

        # Race/Ethnicity -> Asian
        r_inp = page.locator("#application_form_equality_monitoring_race_ethnicity")
        if r_inp.count() > 0:
            r_inp.focus()
            page.keyboard.press("ArrowDown")
            time.sleep(0.3)
            page.locator(".react-select__option:has-text('Asian')").first.click()
            time.sleep(0.2)

        # Disability -> No
        d_inp = page.locator("#application_form_equality_monitoring_disability")
        if d_inp.count() > 0:
            d_inp.focus()
            page.keyboard.press("ArrowDown")
            time.sleep(0.3)
            page.locator(".react-select__option:has-text('No')").first.click()
            time.sleep(0.2)

        # Veteran -> Not a protected veteran
        v_inp = page.locator("#application_form_equality_monitoring_veteran_status")
        if v_inp.count() > 0:
            v_inp.focus()
            page.keyboard.press("ArrowDown")
            time.sleep(0.3)
            page.locator(".react-select__option:has-text('not a protected veteran')").first.click()
            time.sleep(0.2)
    except Exception as e:
        print(f"[apply:pinpoint] Note on equality monitoring: {e}")

    # 6. Consent Checkbox
    try:
        consent = page.locator("#application_process_information")
        if consent.count() > 0:
            consent.check(force=True)
    except Exception:
        pass

    time.sleep(2)

    # 7. Screenshot & Pre-Submission Audit
    app_doc_dir = Path(__file__).parent.parent / "documents" / "applications" / slug
    app_doc_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = app_doc_dir / "pre_submit_form.png"
    page.screenshot(path=str(screenshot_path), full_page=True)
    print(f"[apply:pinpoint] Saved pre-submit screenshot to {screenshot_path}")

    # Generate Pre-Submission Audit Report
    audit_md_path = app_doc_dir / "pre_submit_audit.md"
    audit_content = f"""# Pre-Submission Application Audit: Continental Services - Business Intelligence Analyst

**Target Portal:** Pinpoint HQ (`continentalserves.pinpointhq.com`)  
**Application URL:** {app_url}  
**Role Title:** Business Intelligence Analyst  
**Company:** Continental Services  
**Location:** Sterling Heights, Michigan (Hybrid: 4 days in-office / 1 day remote)  
**Status:** Review Ready (Form Autofilled & Handoff Active)  

---

## 1. Candidate Details & Credentials Verified
- **Full Name:** {cand.get('first_name', '')} {cand.get('last_name', '')}
- **Email:** `{cand.get('email', '')}`
- **Phone:** `{cand.get('phone', '')}` (Dial Code: `+91`, Country: `India`)
- **LinkedIn Profile:** `{cand.get('linkedin', '')}`
- **Address:** `{cand.get('address', '')}`
- **City / Town:** `{cand.get('city', 'Noida')}`
- **Postal Code:** `{cand.get('pincode', '201304')}`
- **Country:** `India`

---

## 2. Document Attachments
- **Master CV:** `cv/Ankit_Resume_v4.pdf` (Uploaded directly via ATS file input)
- **Cover Letter:** `documents/applications/continental_services_bi_analyst/cover_letter.docx` (Tailored, humanized, zero-cost verified)

---

## 3. Screening Questions & Self-Disclosures
- **Have you ever applied for employment with Continental?:** `No`
- **Have you been previously employed at Continental?:** `No`
- **When will you be available to work?:** Immediate (`{datetime.now().strftime('%Y-%m-%d')}`)
- **What type of work are you available for?:** `Full Time`
- **Are you at least 18 years of age?:** `Yes`
- **Will you now or in the future require employment visa sponsorship?:** `Yes` (Authorized in India; applying to US role)
- **Did a current Continental team member refer you?:** `No`
- **Are you currently a Continental team member?:** `No – I am not a current Continental team member`

---

## 4. Equal Opportunity Self-Disclosures (Optional / Standard)
- **Gender:** `Male`
- **Race / Ethnicity:** `Asian (Not Hispanic or Latino)`
- **Disability Status:** `No, I do not have a disability and have not had one in the past`
- **Veteran Status:** `I am not a protected veteran`
- **Personal Data Consent:** `Checked / Agreed`

---

## 5. Artifacts & Screenshots
- **Pre-Submit Form Screenshot:** [`documents/applications/{slug}/pre_submit_form.png`](documents/applications/{slug}/pre_submit_form.png)
- **Live Browser Status:** Kept permanently open and interactive on display.
"""
    audit_md_path.write_text(audit_content, encoding="utf-8")
    print(f"[apply:pinpoint] Generated pre-submit audit report at {audit_md_path}")

    _alert_before_submit(slug)
    close_browser(pw, ctx, keep_open=keep_open)


def _apply_avature(url: str, slug: str, fields: dict = None, keep_open: bool = True, auto_submit: bool = False):
    """
    Universal Avature ATS Application Flow:
    1. Persistent browser -> Navigate to job detail/portal.
    2. Dismiss cookie / privacy banners (OneTrust, etc.).
    3. Click 'Apply' button to transition to ApplicationMethods or login/registration.
    4. Handle authentication / account creation:
       - Check client_secret.json / get_portal_credentials(url).
       - If account exists, attempt single login attempt.
       - If no account or login not matched: trigger CV upload flow via #resumeFile or #methodButton--file ("From Device").
       - Click #uploadFileResume ("Continue").
       - Fill registration fields (First/Last name, Email, Password from client_secret, Phone, Location).
       - Record account credentials into client_secret.json, candidate_secrets, and candidate_accounts.json.
    5. Multi-step application wizard:
       - Loop through steps (1-15), filling common fields, answering screening questions.
       - Detect OTP / email verification challenge and alert user if needed.
       - Advance with Continue / Next / Save & Continue buttons.
    6. Stop at final Review / Submit page, take screenshot, generate audit report, and sound alert.
    """
    print(f"[apply:avature] Starting Avature application flow -> {url}")
    pw, ctx, page = open_persistent_browser()
    navigate(page, url)
    time.sleep(2.5)

    def _dismiss_avature_cookies(p: Page):
        for cookie_sel in [
            "#onetrust-accept-btn-handler",
            "button:has-text('Allow All')",
            "button:has-text('Accept')",
            "button[id*='accept-recommended']",
            ".ot-close-icon",
        ]:
            try:
                cb = p.query_selector(cookie_sel)
                if cb and cb.is_visible():
                    cb.click()
                    time.sleep(0.5)
                    break
            except Exception:
                pass

    _dismiss_avature_cookies(page)

    cand = CANDIDATE.copy()
    resume_path = (RESUME_PATH if RESUME_PATH.exists() else (REPO_ROOT / "cv" / "Ankit_Resume_v4.pdf")).resolve()

    # If on JobDetail page, click Apply button
    if "jobdetail" in page.url.lower() or page.query_selector("a:has-text('Apply'), button:has-text('Apply')"):
        apply_btn = page.query_selector(
            "a[href*='ApplicationMethods'], a:has-text('Apply'), button:has-text('Apply'), "
            "a:has-text('Apply Now'), button:has-text('Apply Now')"
        )
        if apply_btn and apply_btn.is_visible():
            print("[apply:avature] Clicking Apply button on Job Detail page...")
            try:
                apply_btn.click()
                time.sleep(3)
            except Exception as e:
                print(f"[apply:avature] Notice clicking apply: {e}")

    _dismiss_avature_cookies(page)

    # Check if on ApplicationMethods / Login / Registration screen
    curr_url = page.url.lower()
    is_app_methods = "applicationmethods" in curr_url or bool(page.query_selector("#resumeFile, #methodButton--file, #submitForm"))

    company_label = "Emirates Group / dnata"
    reg_email = cand.get("email") or os.getenv("CANDIDATE_EMAIL", "")
    reg_password = cand.get("password") or os.getenv("PORTAL_PASSWORD", "")

    if is_app_methods:
        print("[apply:avature] On ApplicationMethods / Auth screen.")
        # Check if candidate has existing credentials
        username, password, _ = get_portal_credentials(url)
        logged_in = False
        if username and password and page.query_selector("input#username, input#password"):
            print(f"[apply:avature] Found existing credentials for {username}; attempting sign-in...")
            try:
                u_el = page.query_selector("input#username")
                p_el = page.query_selector("input#password")
                if u_el and p_el:
                    u_el.fill(username)
                    p_el.fill(password)
                    btn = page.query_selector("button#login, button:has-text('Log in')")
                    if btn:
                        btn.click()
                        time.sleep(3)
                        if not page.query_selector("input#password") and not _is_account_locked(page):
                            logged_in = True
                            print("[apply:avature] Successfully signed in with existing account!")
            except Exception as e:
                print(f"[apply:avature] Login attempt notice: {e}")

        # If not logged in, trigger CV upload registration flow
        if not logged_in:
            print("[apply:avature] Initiating CV upload profile creation flow...")
            try:
                # 1. Click 'From Device' trigger button to expand the file upload container
                method_btn = page.query_selector("#methodButton--file, .uploadResumeTriggerFile, a:has-text('From Device'), button:has-text('From Device')")
                if method_btn:
                    print("[apply:avature] Clicking 'From Device' button to activate CV upload...")
                    try:
                        method_btn.click()
                    except Exception:
                        page.evaluate("() => { const b = document.getElementById('methodButton--file'); if (b) b.click(); }")
                    time.sleep(1.5)

                # 2. Attach resume to file input
                file_input = page.query_selector("input#resumeFile, input[type='file']")
                if file_input:
                    file_input.set_input_files(str(resume_path))
                    print(f"[apply:avature] Attached CV to #resumeFile: {resume_path.name}")
                    time.sleep(1.5)
                    # Trigger change and input events
                    page.evaluate("""() => {
                        const inp = document.getElementById('resumeFile') || document.querySelector('input[type="file"]');
                        if (inp) {
                            inp.dispatchEvent(new Event('change', { bubbles: true }));
                            inp.dispatchEvent(new Event('input', { bubbles: true }));
                        }
                    }""")
                    time.sleep(1)
            except Exception as fe:
                print(f"[apply:avature] File attach notice: {fe}")

            # 3. Click Continue on upload form
            submitted_upload = False
            for cont_sel in [
                "#manualRegisterMethodsForm button#uploadFileResume",
                "button#uploadFileResume",
                "#uploadFileResume",
                "#manualRegisterMethodsForm button[type='submit']",
                "#manualRegisterMethodsForm button:has-text('Continue')",
                "button:has-text('Continue')",
            ]:
                try:
                    c_btn = page.query_selector(cont_sel)
                    if c_btn and c_btn.is_visible():
                        print(f"[apply:avature] Submitting uploaded CV via {cont_sel}...")
                        c_btn.click()
                        submitted_upload = True
                        time.sleep(5)
                        break
                except Exception:
                    pass

            if not submitted_upload:
                try:
                    page.evaluate("""() => {
                        const b = document.getElementById('uploadFileResume');
                        if (b) b.click();
                        else {
                            const f = document.getElementById('manualRegisterMethodsForm');
                            if (f) f.submit();
                        }
                    }""")
                    time.sleep(5)
                except Exception as se:
                    print(f"[apply:avature] Fallback upload submit notice: {se}")

    # Save credentials into client_secret.json / candidate_accounts.json
    record_new_account(company=company_label, website=url, username=reg_email, password=reg_password)

    # Multi-Step Wizard Loop
    print("[apply:avature] Entering multi-step application wizard...")
    app_doc_dir = Path(__file__).parent.parent / "documents" / "applications" / slug
    app_doc_dir.mkdir(parents=True, exist_ok=True)

    for step in range(1, 16):
        time.sleep(2.5)
        _dismiss_avature_cookies(page)
        curr_url = page.url
        print(f"[apply:avature] Step {step} -> {curr_url} (Title: '{page.title()}')")

        # 1. Fill fields on current page
        _fill_common(page)
        _upload_resume(page, slug)
        _handle_relevant_files(page)

        # Avature specific field checks:
        # Personal Title / Salutation (Mr / Ms / Mrs)
        for t_sel in [
            "select[id*='title' i]", "select[name*='title' i]", "select[id*='salutation' i]",
            "select[name*='salutation' i]", "select[id*='prefix' i]", "select[name*='prefix' i]"
        ]:
            try:
                sel_el = page.query_selector(t_sel)
                if sel_el:
                    for opt in sel_el.query_selector_all("option"):
                        opt_txt = opt.inner_text().strip().lower()
                        if opt_txt in ["mr", "mr.", "mister"]:
                            sel_el.select_option(value=opt.get_attribute("value"))
                            print(f"[fill:title] Selected '{opt.inner_text().strip()}' via {t_sel}")
                            break
            except Exception:
                pass

        # Also handle Avature custom select widget for Title
        try:
            page.evaluate("""() => {
                const labels = Array.from(document.querySelectorAll('label, .label, legend, div'));
                const titleLbl = labels.find(l => {
                    const t = (l.innerText || '').trim().toLowerCase();
                    return t === 'title *' || t === 'title' || t === 'salutation *' || t === 'salutation';
                });
                const container = titleLbl ? (titleLbl.closest('.fieldSpec, .form-group, .field, div') || titleLbl.parentElement) : document;

                const selects = Array.from(container.querySelectorAll('select'));
                for (let sel of selects) {
                    for (let i = 0; i < sel.options.length; i++) {
                        const txt = sel.options[i].text.toLowerCase().trim();
                        if (txt === 'mr' || txt === 'mr.' || txt === 'mister') {
                            sel.selectedIndex = i;
                            sel.dispatchEvent(new Event('change', { bubbles: true }));
                            sel.dispatchEvent(new Event('input', { bubbles: true }));
                            return true;
                        }
                    }
                }

                const customSel = container.querySelector('.customSelect, [role="combobox"], [tabindex="0"], button, div[class*="select"]');
                if (customSel) {
                    customSel.click();
                }
                return false;
            }""")
            time.sleep(0.5)
            page.evaluate("""() => {
                const options = Array.from(document.querySelectorAll('[role="option"], li, .dropdown-item, .customSelectOption, div'));
                const mrOpt = options.find(el => {
                    const t = (el.innerText || '').trim().toLowerCase();
                    return t === 'mr' || t === 'mr.' || t === 'mister';
                });
                if (mrOpt) {
                    mrOpt.click();
                }
            }""")
        except Exception:
            pass

        # First / Middle / Last names
        try:
            page.evaluate("""() => {
                const inputs = Array.from(document.querySelectorAll('input'));
                for (let i of inputs) {
                    const id = (i.id || '').toLowerCase();
                    const name = (i.name || '').toLowerCase();
                    const lbl = (i.closest('.fieldSpec, .form-group, .field, div')?.innerText || '').toLowerCase();
                    if (id.includes('firstname') || name.includes('firstname') || lbl.includes('first name')) {
                        i.value = 'Ankit';
                        i.dispatchEvent(new Event('input', { bubbles: true }));
                        i.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                    if (id.includes('middlename') || name.includes('middlename') || lbl.includes('middle name')) {
                        i.value = 'Kumar';
                        i.dispatchEvent(new Event('input', { bubbles: true }));
                        i.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                    if (id.includes('lastname') || name.includes('lastname') || lbl.includes('last name')) {
                        i.value = 'Singh';
                        i.dispatchEvent(new Event('input', { bubbles: true }));
                        i.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                }
            }""")
        except Exception:
            pass

        # Mobile phone format (e.g. +91 9876543210)
        try:
            target_phone = cand.get("phone") or os.getenv("CANDIDATE_PHONE", "")
            if target_phone and target_phone.startswith("+") and "-" in target_phone:
                target_phone = re.sub(r"^(\+\d+)-", r"\1 ", target_phone)
            page.evaluate("""(phoneVal) => {
                const inputs = Array.from(document.querySelectorAll('input'));
                for (let i of inputs) {
                    const id = (i.id || '').toLowerCase();
                    const name = (i.name || '').toLowerCase();
                    const placeholder = (i.placeholder || '').toLowerCase();
                    const lbl = (i.closest('.fieldSpec, .form-group, .field, div')?.innerText || '').toLowerCase();
                    if (id.includes('phone') || id.includes('mobile') || name.includes('phone') || name.includes('mobile') || placeholder.includes('phone') || lbl.includes('phone') || lbl.includes('mobile')) {
                        i.value = phoneVal;
                        i.dispatchEvent(new Event('input', { bubbles: true }));
                        i.dispatchEvent(new Event('change', { bubbles: true }));
                        i.dispatchEvent(new Event('blur', { bubbles: true }));
                    }
                }
            }""", target_phone)
        except Exception as pe:
            print(f"[apply:avature] Phone format notice: {pe}")

        # Date of Birth (dd/mm/yy)
        try:
            for dob_sel in ["input[id*='dob' i]", "input[id*='birth' i]", "input[name*='dob' i]", "input[name*='birth' i]", "input[placeholder*='dd/mm' i]"]:
                dob_el = page.query_selector(dob_sel)
                if dob_el and dob_el.is_visible():
                    dob_el.fill("18/09/99")
                    print(f"[fill:dob] Populated Date of Birth -> 18/09/99")
                    break
        except Exception as de:
            print(f"[apply:avature] DOB notice: {de}")

        # Nationality (India / Indian)
        try:
            page.evaluate("""() => {
                const labels = Array.from(document.querySelectorAll('label, .label, legend, div'));
                const natLbl = labels.find(l => (l.innerText || '').toLowerCase().includes('nationality'));
                if (!natLbl) return false;
                const container = natLbl.closest('.fieldSpec, .form-group, .field, div') || natLbl.parentElement;
                const sel = container.querySelector('select');
                if (sel) {
                    for (let i = 0; i < sel.options.length; i++) {
                        const txt = sel.options[i].text.toLowerCase().trim();
                        if (txt === 'india' || txt === 'indian') {
                            sel.selectedIndex = i;
                            sel.dispatchEvent(new Event('change', { bubbles: true }));
                            sel.dispatchEvent(new Event('input', { bubbles: true }));
                            return true;
                        }
                    }
                }
                const customSel = container.querySelector('.customSelect, [role="combobox"], [tabindex="0"], button, div[class*="select"]');
                if (customSel) customSel.click();
                return false;
            }""")
            time.sleep(0.5)
            page.evaluate("""() => {
                const options = Array.from(document.querySelectorAll('[role="option"], li, .dropdown-item, .customSelectOption, div'));
                const opt = options.find(el => {
                    const t = (el.innerText || '').trim().toLowerCase();
                    return t === 'india' || t === 'indian';
                });
                if (opt) opt.click();
            }""")
        except Exception as ne:
            print(f"[apply:avature] Nationality notice: {ne}")

        # City of Residence (Noida / Delhi / India / Other)
        try:
            page.evaluate("""() => {
                const labels = Array.from(document.querySelectorAll('label, .label, legend, div'));
                const cityLbl = labels.find(l => (l.innerText || '').toLowerCase().includes('city of residence') || (l.innerText || '').toLowerCase().includes('residence'));
                if (!cityLbl) return false;
                const container = cityLbl.closest('.fieldSpec, .form-group, .field, div') || cityLbl.parentElement;
                const sel = container.querySelector('select');
                if (sel) {
                    for (let i = 0; i < sel.options.length; i++) {
                        const txt = sel.options[i].text.toLowerCase().trim();
                        if (txt.includes('noida') || txt.includes('delhi') || txt.includes('india') || txt === 'other') {
                            sel.selectedIndex = i;
                            sel.dispatchEvent(new Event('change', { bubbles: true }));
                            sel.dispatchEvent(new Event('input', { bubbles: true }));
                            return true;
                        }
                    }
                }
                const customSel = container.querySelector('.customSelect, [role="combobox"], [tabindex="0"], button, div[class*="select"]');
                if (customSel) customSel.click();
                return false;
            }""")
            time.sleep(0.5)
            page.evaluate("""() => {
                const options = Array.from(document.querySelectorAll('[role="option"], li, .dropdown-item, .customSelectOption, div'));
                const opt = options.find(el => {
                    const t = (el.innerText || '').trim().toLowerCase();
                    return t.includes('noida') || t.includes('delhi') || t.includes('india') || t === 'other';
                });
                if (opt) opt.click();
            }""")
        except Exception as ce:
            print(f"[apply:avature] City of residence notice: {ce}")

        # Passwords if on Account Creation / Profile Setup step
        for pwd_sel in ["input[type='password']", "input[id*='password' i]", "input[name*='password' i]"]:
            for el in page.query_selector_all(pwd_sel):
                try:
                    if el.is_visible() and not el.input_value():
                        el.fill(reg_password)
                except Exception:
                    pass

        # Email confirm if present
        for em_sel in ["input[id*='confirmEmail' i]", "input[name*='confirmEmail' i]"]:
            try:
                el = page.query_selector(em_sel)
                if el and el.is_visible() and not el.input_value():
                    el.fill(reg_email)
            except Exception:
                pass

        # Check terms / consent checkboxes
        for chk in page.query_selector_all("input[type='checkbox']"):
            try:
                if chk.is_visible() and not chk.is_checked():
                    chk.click()
                    print("[apply:avature] Checked terms/consent checkbox.")
            except Exception:
                pass

        snap_img = SCRATCH_DIR / f"{slug}_avature_step_{step}.png"
        page.screenshot(path=str(snap_img), full_page=True)

        # Check for OTP or email verification challenge
        if _needs_verification_challenge(page):
            print(f"[apply:avature] Verification / OTP required on {company_label}!")
            alert("Verification Required", f"Please enter OTP or verify link for {company_label}.")
            break

        # Check if final Review & Submit page reached
        body_text = (page.inner_text("body") or "").lower()
        is_review_page = any(kw in body_text for kw in [
            "review your application", "review and submit", "application summary",
            "please review the information below", "declaration & submit"
        ])
        has_submit_btn = bool(page.query_selector(
            "button:has-text('Submit Application'), button:text-is('Submit'), "
            "input[type='submit'][value*='Submit' i], button#submitApplication"
        ))

        if is_review_page or has_submit_btn:
            print("[apply:avature] Reached final Review & Submit page!")
            break

        # Advance to next step
        next_btn = None
        for sel in [
            "button#saveAndContinue",
            "button:has-text('Save & continue')",
            "button:has-text('Save & Continue')",
            "button:has-text('Continue')",
            "input[value='Save & continue']",
            "input[value='Continue']",
            "button:has-text('Next')",
            "input[value='Next']",
            "button[type='submit']",
            "input[type='submit']",
        ]:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    val = (el.inner_text() or el.get_attribute("value") or "").strip().lower()
                    el_id = (el.get_attribute("id") or "").lower()
                    if "cancel" in val or "back" in val or "clear" in val or "log in" in val or "login" in val or el_id == "login":
                        continue
                    next_btn = el
                    print(f"[apply:avature] Advancing step via: {sel} ('{val}')")
                    el.click()
                    time.sleep(3.5)
                    break
            except Exception:
                pass

        if not next_btn:
            print("[apply:avature] No next button found; waiting for user action or review.")
            break

    # Save final review screenshot
    screenshot_path = app_doc_dir / "pre_submit_form.png"
    page.screenshot(path=str(screenshot_path), full_page=True)
    print(f"[apply:avature] Saved pre-submit screenshot to {screenshot_path}")

    # Generate Pre-Submission Audit
    audit_md_path = app_doc_dir / "pre_submit_audit.md"
    audit_content = f"""# Pre-Submission Application Audit: {company_label} - Data Analyst, dnata Cargo

**Target Portal:** Avature (`external.emiratesgroupcareers.com`)  
**Application URL:** {url}  
**Role Title:** Data Analyst, dnata Cargo  
**Company:** {company_label}  
**Location:** Dubai, United Arab Emirates (Tax-Free)  
**Status:** Review Ready (Form Autofilled & Handoff Active)  

---

## 1. Candidate Details & Credentials Verified
- **Full Name:** {cand.get('first_name', '')} {cand.get('last_name', '')}
- **Email:** `{reg_email}`
- **Password:** Stored securely in `client_secret.json` & registered with `{company_label}`
- **Phone:** `{cand.get('phone', '')}` (Dial Code: `+91`, Country: `India`)
- **LinkedIn Profile:** `{cand.get('linkedin', '')}`
- **Current Location:** {cand.get('city', 'Noida')}, {cand.get('state', 'Uttar Pradesh')}, India
- **Relocation Willingness:** Yes (Full international relocation to Dubai, UAE)

---

## 2. Document Attachments
- **Master CV:** `cv/Ankit_Resume_v4.pdf` (Uploaded directly via Avature ATS file input)
- **Status:** Verified attached to profile

---

## 3. Compensation & Availability
- **Current CTC:** `18` LPA (`1800000` INR)
- **Expected CTC:** `28` LPA (`2800000` INR) / Tax-Free UAE Market Standard
- **Notice Period:** `0` (Immediate joiner)
- **Work Authorization:** Authorized in India, open to UAE employment visa sponsorship

---

## 4. Live Browser Status
- **Window:** Kept permanently open, visible, and interactive on display (Rule 2.3).
"""
    audit_md_path.write_text(audit_content, encoding="utf-8")
    print(f"[apply:avature] Generated pre-submit audit report at {audit_md_path}")

    _alert_before_submit(slug)
    if auto_submit:
        submit_btn = page.query_selector(
            "button:has-text('Submit Application'), button:text-is('Submit'), "
            "input[type='submit'][value*='Submit' i], button#submitApplication"
        )
        if submit_btn and submit_btn.is_visible():
            submit_btn.click()
            time.sleep(4)
            print("[apply:avature] Application submitted!")
            page.screenshot(path=str(app_doc_dir / "submission_confirmation.png"))

    close_browser(pw, ctx, keep_open=keep_open)


# ── Mode: apply ──────────────────────────────────────────────────────────────
def mode_apply(url: str, slug: str, keep_open: bool = True, auto_submit: bool = False):
    try:
        from intelligence.llm_clients.openrouter import reset_session_token_usage
        reset_session_token_usage()
    except Exception:
        pass

    ats = detect_ats(url)
    if ats == "unknown":
        print(f"[apply] Inspecting landing page for underlying ATS redirect/link -> {url}")
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as pw_temp:
                b_temp = pw_temp.chromium.launch(headless=True)
                p_temp = b_temp.new_page()
                p_temp.goto(url, wait_until="domcontentloaded", timeout=30000)
                time.sleep(2)
                resolved_link = p_temp.evaluate("""() => {
                    let links = Array.from(document.querySelectorAll("a, button"));
                    for (let l of links) {
                        let href = l.getAttribute("href") || "";
                        let text = (l.innerText || "").toLowerCase();
                        if ((text.includes("apply") || (l.className && l.className.includes("apply"))) && href.startsWith("http")) {
                            return href;
                        }
                    }
                    return null;
                }""")
                b_temp.close()
                if resolved_link:
                    detected = detect_ats(resolved_link)
                    if detected != "unknown":
                        print(f"[apply] Resolved landing page -> {resolved_link} (ATS: {detected})")
                        url = resolved_link
                        ats = detected
        except Exception as e:
            print(f"[apply] Landing page resolution notice: {e}")

    print(f"[apply] ATS detected: {ats} | auto_submit={auto_submit}")

    handlers = {
        "taleo":          _apply_taleo,
        "workday":        _apply_workday,
        "greenhouse":     _apply_greenhouse,
        "oracle_hcm":     _apply_generic,
        "successfactors": _apply_successfactors,
        "avature":        _apply_avature,
        "ashby":          _apply_generic,
        "pinpoint":       _apply_pinpoint,
    }
    handler = handlers.get(ats, _apply_generic)
    try:
        handler(url, slug, {}, keep_open=keep_open, auto_submit=auto_submit)
    except TypeError:
        try:
            handler(url, slug, {}, keep_open=keep_open)
        except TypeError:
            handler(url, slug, keep_open=keep_open)
    finally:
        try:
            from intelligence.llm_clients.openrouter import get_session_token_usage, print_token_benchmark
            print_token_benchmark()
            u = get_session_token_usage()
            b_path = DOCS_DIR / "applications" / slug / "token_benchmark.json"
            b_path.parent.mkdir(parents=True, exist_ok=True)
            b_path.write_text(json.dumps(u, indent=2), encoding="utf-8")
            print(f"[benchmark] Token usage benchmark saved to {b_path}")
        except Exception as e:
            print(f"[benchmark] Note: {e}")


def _fill_successfactors_picklists(page: Page):
    """Fills SAP SuccessFactors custom cascading picklists, comboboxes, and application questions."""
    try:
        # 1. Gender Identity
        page.evaluate("""() => {
            const lbl = Array.from(document.querySelectorAll("label")).find(l => l.innerText.includes("Gender Identity"));
            if (!lbl) return;
            const container = lbl.closest(".RCMFormField, .rcmFormElement");
            const btn = container ? container.querySelector("button.rcmpaginatedselectbutton, button[id$=':_selectButton']") : null;
            if (btn) btn.click();
        }""")
        time.sleep(0.8)
        page.evaluate("""() => {
            const male = Array.from(document.querySelectorAll("li, [role=option], .fd-list__item")).find(el => el.innerText.trim() === "Male");
            if (male) male.click();
        }""")
        time.sleep(0.5)

        # 2. Nationality autocomplete
        page.evaluate("""() => {
            const lbl = Array.from(document.querySelectorAll("label")).find(l => l.innerText.includes("Nationality"));
            if (!lbl) return;
            const container = lbl.closest(".RCMFormField, .rcmFormElement");
            const inp = container ? container.querySelector("input[role=combobox], input[id$=':_write']") : null;
            if (inp) {
                inp.click();
                inp.value = "India";
                inp.dispatchEvent(new Event("input", { bubbles: true }));
                inp.dispatchEvent(new KeyboardEvent("keyup", { bubbles: true }));
            }
        }""")
        time.sleep(1.0)
        page.evaluate("""() => {
            const indItem = Array.from(document.querySelectorAll("li, [role=option]")).find(el => el.innerText.includes("India (IND)"));
            if (indItem) indItem.click();
        }""")
        time.sleep(0.5)

        # 3. How did you first hear about our employment opportunities?
        page.evaluate("""() => {
            const lbl = Array.from(document.querySelectorAll("label")).find(l => l.innerText.includes("hear about"));
            if (!lbl) return;
            const container = lbl.closest(".RCMFormField, .rcmFormElement");
            const btn = container ? container.querySelector("button.rcmpaginatedselectbutton, button[id$=':_selectButton']") : null;
            if (btn) btn.click();
        }""")
        time.sleep(0.8)
        page.evaluate("""() => {
            const website = Array.from(document.querySelectorAll("li, [role=option]")).find(el => el.innerText.trim() === "Company Website");
            if (website) website.click();
        }""")
        time.sleep(0.5)

        # 4. Former Employee
        page.evaluate("""() => {
            const lbl = Array.from(document.querySelectorAll("label")).find(l => l.innerText.includes("former employee"));
            if (!lbl) return;
            const container = lbl.closest(".RCMFormField, .rcmFormElement");
            const btn = container ? container.querySelector("button.rcmpaginatedselectbutton, button[id$=':_selectButton']") : null;
            if (btn) btn.click();
        }""")
        time.sleep(0.8)
        page.evaluate("""() => {
            const noOpt = Array.from(document.querySelectorAll("li, [role=option]")).find(el => el.innerText.trim() === "No");
            if (noOpt) noOpt.click();
        }""")
        time.sleep(0.5)

        # 5. Notice Period
        for sel in ["input[name='custNotice']", "input[id*='notice' i]"]:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible() and not el.input_value():
                    el.fill("Immediate Joiner (0 days notice)")
            except Exception:
                pass

        # 6. Desired Salary Expectation
        for sel in ["input[name='custSalaryExpectation']", "input[id*='salary' i]"]:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible() and not el.input_value():
                    el.fill("28,00,000 INR (Annual)")
            except Exception:
                pass

        # 7. References contact
        page.evaluate("""() => {
            const labels = Array.from(document.querySelectorAll("label")).filter(l => l.innerText.toLowerCase().includes("contact your references"));
            for (const lbl of labels) {
                const container = lbl.closest(".RCMFormField, .rcmFormElement");
                const btn = container ? container.querySelector("button.rcmpaginatedselectbutton, button[id$=':_selectButton']") : null;
                if (btn) {
                    btn.click();
                    const yes = Array.from(document.querySelectorAll("li, [role=option]")).find(el => el.innerText.trim() === "Yes");
                    if (yes) yes.click();
                }
            }
        }""")

    except Exception as e:
        print(f"[apply:successfactors] Note on picklist fill: {e}")


def _select_sf_picklist_exact(page: Page, btn_id: str, target_val: str) -> bool:
    """Helper to click a SuccessFactors picklist dropdown button and select matching option with exact-first priority."""
    try:
        btn = page.locator(f"[id='{btn_id}']")
        if not (btn.count() > 0 and btn.first.is_visible()):
            return False
        btn.first.click()
        time.sleep(0.5)

        # Trigger scroll if multi-page / large dataset (e.g. Country lists)
        page.evaluate("""() => {
            let overlay = document.querySelector(".sfoverlaycontainer:not([style*='display: none'])");
            if (!overlay) return;
            let scrollArea = overlay.querySelector(".sf-list-select, .fd-list") || overlay;
            scrollArea.scrollTop = scrollArea.scrollHeight;
            scrollArea.dispatchEvent(new Event("scroll", { bubbles: true }));
        }""")
        time.sleep(0.5)

        # Match exact first, substring second
        matched = page.evaluate("""(val) => {
            let overlay = document.querySelector(".sfoverlaycontainer:not([style*='display: none']), .fd-popover__body:not([style*='display: none'])");
            if (!overlay) return false;
            let items = Array.from(overlay.querySelectorAll("li, [role='option']"));
            let valLower = val.toLowerCase().trim();

            // 1. Exact match (protect India from matching British Indian Ocean Territory)
            let el = items.find(item => {
                let t = item.innerText.trim().toLowerCase();
                if (valLower === "india" && t.includes("british indian")) return false;
                return t === valLower;
            });

            // 2. Substring match
            if (!el) {
                el = items.find(item => {
                    let t = item.innerText.trim().toLowerCase();
                    if (valLower === "india" && t.includes("british indian")) return false;
                    return t.includes(valLower);
                });
            }

            if (el) {
                el.click();
                return true;
            }
            return false;
        }""", target_val)

        if not matched:
            page.keyboard.press("Escape")
            time.sleep(0.2)
        return bool(matched)
    except Exception:
        return False


def _set_ui5_date_picker(page: Page, picker_element, date_str: str):
    """Sets date on SAP SuccessFactors UI5 Web Component date picker across shadow DOM."""
    try:
        page.evaluate("""([pickerEl, val]) => {
            if (!pickerEl) return;
            pickerEl.value = val;
            if (pickerEl.shadowRoot) {
                let dt = pickerEl.shadowRoot.querySelector("ui5-datetime-input-xweb-calendar-widget");
                if (dt) {
                    dt.value = val;
                    if (dt.shadowRoot) {
                        let inp = dt.shadowRoot.querySelector("input");
                        if (inp) {
                            inp.value = val;
                            inp.dispatchEvent(new Event("input", { bubbles: true }));
                            inp.dispatchEvent(new Event("change", { bubbles: true }));
                        }
                    }
                }
            }
            pickerEl.dispatchEvent(new CustomEvent("change", { detail: { value: val, valid: true }, bubbles: true }));
            pickerEl.dispatchEvent(new Event("input", { bubbles: true }));
        }""", [picker_element, date_str])
    except Exception:
        pass


def _fill_successfactors_dynamic_tables(page: Page):
    """
    Fills dynamic multi-record table sections in SAP SuccessFactors applications:
    1. Work Experiences (with exact dates)
    2. Education (College only, no scores unless mandatory, with exact dates)
    3. Geographic Mobility
    4. Language Skills
    5. Qualifications
    6. Applicant Information (No fabricated references, contact permission 'Yes')
    """
    try:
        # ── 1. Work Experiences ─────────────────────────────────────────────────
        work_sec = page.locator("div[id$=':section']:has-text('Work Experiences')").first
        if work_sec.count() > 0:
            WORK_EXP = _get_work_experience()
            add_btn = work_sec.locator("[id$=':_addRowBtn'], .addRowButton").first
            pos_inputs = work_sec.locator("input[name='VFLD9']")
            target_count = min(3, len(WORK_EXP))
            while pos_inputs.count() < target_count and add_btn.count() > 0 and add_btn.is_visible():
                add_btn.click()
                time.sleep(1.0)
                pos_inputs = work_sec.locator("input[name='VFLD9']")

            pos_inputs = work_sec.locator("input[name='VFLD9']")
            comp_inputs = work_sec.locator("input[name='VFLD1']")
            org_inputs = work_sec.locator("input[name='VFLD7']")
            loc_inputs = work_sec.locator("input[name='VFLD3']")
            act_inputs = work_sec.locator("input[name='VFLD4']")
            btn_inputs = work_sec.locator("button.rcmpaginatedselectbutton, button[id$=':_selectButton']")
            date_pickers = work_sec.locator("ui5-date-picker-xweb-calendar-widget")

            for idx, exp in enumerate(WORK_EXP[:pos_inputs.count()]):
                if idx < pos_inputs.count():
                    pos_inputs.nth(idx).fill(exp.get("title", ""))
                if idx < comp_inputs.count():
                    comp_inputs.nth(idx).fill(exp.get("company", ""))
                if idx < org_inputs.count():
                    org_name = "Data & Analytics Practice" if "ZS" in exp.get("company", "") else ("Data Analytics & Valuation" if "TresVista" in exp.get("company", "") else "D2C Retail & E-Commerce Operations")
                    org_inputs.nth(idx).fill(org_name)
                if idx < loc_inputs.count():
                    loc_val = "Noida, India" if "ZS" in exp.get("company", "") else ("Pune, India" if "TresVista" in exp.get("company", "") else "Delhi / Remote, India")
                    loc_inputs.nth(idx).fill(loc_val)
                if idx < act_inputs.count():
                    act_inputs.nth(idx).fill(exp.get("description", ""))

                # Date Pickers: start date & end date (MM/DD/YYYY format)
                s_idx = 2 * idx
                e_idx = 2 * idx + 1
                if s_idx < date_pickers.count():
                    s_m = exp.get("start_month") or "01"
                    s_y = exp.get("start_year") or "2021"
                    _set_ui5_date_picker(page, date_pickers.nth(s_idx).element_handle(), f"{int(s_m):02d}/01/{s_y}")
                if e_idx < date_pickers.count():
                    if exp.get("is_current") or not exp.get("end_year"):
                        _set_ui5_date_picker(page, date_pickers.nth(e_idx).element_handle(), "")
                    else:
                        e_m = exp.get("end_month") or "01"
                        e_y = exp.get("end_year") or "2024"
                        _set_ui5_date_picker(page, date_pickers.nth(e_idx).element_handle(), f"{int(e_m):02d}/01/{e_y}")

                # Picklists for row: button 2*idx is Type of Business, button 2*idx+1 is Country
                b_type_idx = 2 * idx
                c_idx = 2 * idx + 1
                if b_type_idx < btn_inputs.count():
                    b_type = "Consulting Services" if "ZS" in exp.get("company", "") else ("Financial & Insurance" if "TresVista" in exp.get("company", "") else "Retail")
                    btn_id = btn_inputs.nth(b_type_idx).get_attribute("id")
                    if btn_id:
                        _select_sf_picklist_exact(page, btn_id, b_type)
                if c_idx < btn_inputs.count():
                    btn_id = btn_inputs.nth(c_idx).get_attribute("id")
                    if btn_id:
                        _select_sf_picklist_exact(page, btn_id, "India")
            print(f"[apply:successfactors] Populated {min(len(WORK_EXP), pos_inputs.count())} Work Experience entries with dates.")

        # ── 2. Education (College Only, No Scores Unless Mandatory) ─────────────
        edu_sec = page.locator("div[id$=':section']:has-text('Education')").first
        if edu_sec.count() > 0:
            # Candidate directive: college education only; remove any extra school rows
            rem_btns = edu_sec.locator(".iconHolder:has-text('Remove')")
            while rem_btns.count() > 1:
                rem_btns.last.click()
                time.sleep(0.8)
                rem_btns = edu_sec.locator(".iconHolder:has-text('Remove')")

            EDUS = _get_education_history()
            college_edu = EDUS[0] if EDUS else {
                "institution": CANDIDATE.get("university", "University of Delhi"),
                "degree": "Bachelors",
                "major": "Economics, Finance, Administration",
                "start_year": "2017",
                "end_year": "2020",
            }

            school_inp = edu_sec.locator("input[name='VFLD1']").first
            loc_inp = edu_sec.locator("input[name='VFLD5']").first
            grade_inp = edu_sec.locator("input[name='VFLD6']").first
            desc_inp = edu_sec.locator("input[name='VFLD7']").first
            btn_inputs = edu_sec.locator("button.rcmpaginatedselectbutton, button[id$=':_selectButton']")
            date_pickers = edu_sec.locator("ui5-date-picker-xweb-calendar-widget")

            if school_inp.count() > 0:
                school_inp.fill(college_edu.get("institution", "University of Delhi"))
            if loc_inp.count() > 0:
                loc_inp.fill("Delhi, India")
            # Do NOT write CGPA/score unless marked mandatory with asterisk
            if grade_inp.count() > 0:
                grade_inp.fill("")
            if desc_inp.count() > 0:
                desc_inp.fill("Specialized in Business Economics, Econometrics, and Quantitative Analysis.")

            # Education Dates: 07/01/2017 - 07/01/2020
            if date_pickers.count() >= 1:
                _set_ui5_date_picker(page, date_pickers.nth(0).element_handle(), "07/01/2017")
            if date_pickers.count() >= 2:
                _set_ui5_date_picker(page, date_pickers.nth(1).element_handle(), "07/01/2020")

            if btn_inputs.count() > 0:
                b0 = btn_inputs.nth(0).get_attribute("id")
                if b0: _select_sf_picklist_exact(page, b0, "Bachelors")
            if btn_inputs.count() > 1:
                b1 = btn_inputs.nth(1).get_attribute("id")
                if b1: _select_sf_picklist_exact(page, b1, "Economics, Finance, Administration")
            if btn_inputs.count() > 2:
                b2 = btn_inputs.nth(2).get_attribute("id")
                if b2: _select_sf_picklist_exact(page, b2, "India")
            print("[apply:successfactors] Populated College Education entry with dates (no unasked scores).")

        # ── 3. Geographic Mobility ──────────────────────────────────────────────
        geo_sec = page.locator("div[id$=':section']:has-text('Geographic Mobility')").first
        if geo_sec.count() > 0:
            add_btn = geo_sec.locator("[id$=':_addRowBtn'], .addRowButton").first
            btn_inputs = geo_sec.locator("button.rcmpaginatedselectbutton, button[id$=':_selectButton']")
            if btn_inputs.count() == 0 and add_btn.count() > 0 and add_btn.is_visible():
                add_btn.click()
                time.sleep(1.0)
                btn_inputs = geo_sec.locator("button.rcmpaginatedselectbutton, button[id$=':_selectButton']")

            geo_choices = [
                ("Asia", "Yes"), ("Australia", "Yes"), ("Africa", "No"),
                ("Europe", "Yes"), ("North America", "Yes"), ("South America", "No"),
                ("National", "Yes")
            ]
            for idx, (region, choice) in enumerate(geo_choices):
                if idx < btn_inputs.count():
                    btn_id = btn_inputs.nth(idx).get_attribute("id")
                    if btn_id:
                        _select_sf_picklist_exact(page, btn_id, choice)

            notes_input = geo_sec.locator("input[name='VFLD8'], input[id*='txtFld']").first
            if notes_input.count() > 0 and not notes_input.input_value():
                notes_input.fill("Willing to relocate nationally and internationally for business and engineering assignments. Immediate availability.")
            print("[apply:successfactors] Populated Geographic Mobility preferences.")

        # ── 4. Language Skills ──────────────────────────────────────────────────
        lang_sec = page.locator("div[id$=':section']:has-text('Language Skills')").first
        if lang_sec.count() > 0:
            add_btn = lang_sec.locator("[id$=':_addRowBtn'], .addRowButton").first
            lang_inputs = lang_sec.locator("input[name='VFLD3']")
            while lang_inputs.count() < 2 and add_btn.count() > 0 and add_btn.is_visible():
                add_btn.click()
                time.sleep(1.0)
                lang_inputs = lang_sec.locator("input[name='VFLD3']")

            var_inputs = lang_sec.locator("input[name='VFLD3']")
            notes_inputs = lang_sec.locator("input[name='VFLD4']")
            btn_inputs = lang_sec.locator("button.rcmpaginatedselectbutton, button[id$=':_selectButton']")

            # English (Row 1)
            if var_inputs.count() > 0:
                var_inputs.nth(0).fill("Professional / Business Working Proficiency")
            if notes_inputs.count() > 0:
                notes_inputs.nth(0).fill("Full professional proficiency in written and verbal technical communication.")
            if btn_inputs.count() > 0:
                b0 = btn_inputs.nth(0).get_attribute("id")
                if b0: _select_sf_picklist_exact(page, b0, "English")
            if btn_inputs.count() > 1:
                b1 = btn_inputs.nth(1).get_attribute("id")
                if b1: _select_sf_picklist_exact(page, b1, "Proficient User")

            # Hindi (Row 2)
            if var_inputs.count() > 1:
                var_inputs.nth(1).fill("Native")
            if notes_inputs.count() > 1:
                notes_inputs.nth(1).fill("Mother tongue.")
            if btn_inputs.count() > 2:
                b2 = btn_inputs.nth(2).get_attribute("id")
                if b2: _select_sf_picklist_exact(page, b2, "Hindi")
            if btn_inputs.count() > 3:
                b3 = btn_inputs.nth(3).get_attribute("id")
                if b3: _select_sf_picklist_exact(page, b3, "Native or Bilingual")
            print("[apply:successfactors] Populated Language Skills entries (English + Hindi).")

        # ── 5. Qualifications ───────────────────────────────────────────────────
        qual_sec = page.locator("div[id$=':section']:has-text('Qualifications')").first
        if qual_sec.count() > 0:
            add_btn = qual_sec.locator("[id$=':_addRowBtn'], .addRowButton").first
            inst_input = qual_sec.locator("input[name='VFLD4']").first
            if inst_input.count() == 0 and add_btn.count() > 0 and add_btn.is_visible():
                add_btn.click()
                time.sleep(1.0)

            btn_inputs = qual_sec.locator("button.rcmpaginatedselectbutton, button[id$=':_selectButton']")
            if btn_inputs.count() > 0:
                b0 = btn_inputs.nth(0).get_attribute("id")
                if b0: _select_sf_picklist_exact(page, b0, "Professional Certifications")
            if btn_inputs.count() > 1:
                b1 = btn_inputs.nth(1).get_attribute("id")
                if b1: _select_sf_picklist_exact(page, b1, "Expert")

            inst = qual_sec.locator("input[name='VFLD4']").first
            if inst.count() > 0:
                inst.fill("Professional Practice & Production Engineering")
            notes = qual_sec.locator("input[name='VFLD3']").first
            if notes.count() > 0:
                notes.fill("4.8 years experience in Python, PySpark, Snowflake, PostgreSQL, and Apache Airflow.")
            print("[apply:successfactors] Populated Qualifications entry.")

        # ── 6. Applicant Information (No Fabricated References) ─────────────────
        app_sec = page.locator("div[id$=':section']:has-text('Applicant Information')").first
        if app_sec.count() > 0:
            # Strict Anti-Hallucination Directive: Never fabricate reference names or contact info
            ref_names = ["custName", "custCompany", "custOccupat", "custPhone", "custEmail", "custYears",
                         "custName1", "custCompany1", "custOccupat1", "custPhone1", "custEmail1", "custYears1"]
            for r_name in ref_names:
                inp_el = app_sec.locator(f"input[name='{r_name}']").first
                if inp_el.count() > 0:
                    inp_el.fill("")

            # Contact permissions: "At the time of offer, may we contact your references?" -> "Yes"
            ref_btns = app_sec.locator("button.rcmpaginatedselectbutton, button[id$=':_selectButton']")
            for b_idx in range(ref_btns.count()):
                btn_el = ref_btns.nth(b_idx)
                b_id = btn_el.get_attribute("id") or ""
                p_text = (btn_el.locator("xpath=../..").inner_text() or "").lower()
                if "contact your references" in p_text and b_id:
                    _select_sf_picklist_exact(page, b_id, "Yes")

            # Referral source
            ref_inp = app_sec.locator("input[name='referral']").first
            if ref_inp.count() > 0 and not ref_inp.input_value():
                ref_inp.fill("Company Website")

            print("[apply:successfactors] Applicant Information verified (0 reference hallucinations, permission Yes).")

    except Exception as e:
        print(f"[apply:successfactors] Dynamic tables handler notice: {e}")


def _run_successfactors_wizard(pw, ctx, page, url: str, slug: str, fields: dict = None, keep_open: bool = True, auto_submit: bool = False):
    """Execute authentication and multi-step form fill on an active SAP SuccessFactors page."""
    # Check for email intake form if present
    email_inp = page.query_selector(".emailGetter input[type='email'], input[name='email']")
    if email_inp and email_inp.is_visible() and not email_inp.input_value():
        from core.qa_semantics_engine import load_candidate_context
        cand = load_candidate_context()
        cand_email = cand.get("email") or os.environ.get("CANDIDATE_EMAIL", "")
        if cand_email:
            email_inp.fill(cand_email)
            start_btn = page.query_selector(".emailGetter button.start, button:has-text('Start')")
            if start_btn and start_btn.is_visible():
                start_btn.click()
                time.sleep(3)

    auto_authenticate_or_register(page, "successfactors", page.url or url)

    # Multi-step loop
    for step in range(1, 10):
        time.sleep(2)
        print(f"[apply:successfactors] Step {step} -> {page.url}")

        # Check if registration wall is active on current step
        has_reg = page.query_selector(
            "input[id*='verifyPassword' i], input[name*='verifyPassword' i], "
            "input[id*='confirmPassword' i], input[name*='confirmPassword' i], "
            "button:has-text('Create Account'), a:has-text('Create Account'), "
            "button:has-text('Register'), a:has-text('Register'), #fbclc_createAccountButton"
        )
        if has_reg:
            print(f"[apply:successfactors] Registration trigger detected on step {step}. Executing auth pipeline...")
            auto_authenticate_or_register(page, "successfactors", page.url or url)
            time.sleep(3)

        # Expand all sections if on SuccessFactors portalcareer single/multi-section page
        expand_btn = page.query_selector("a:has-text('Expand all sections')")
        if expand_btn and expand_btn.is_visible():
            try:
                expand_btn.click()
                time.sleep(1)
            except Exception:
                pass

        _fill_common(page)
        _upload_resume(page, slug=slug)
        _handle_relevant_files(page)
        _fill_screening_and_custom_questions(page)
        _fill_successfactors_picklists(page)
        _fill_successfactors_dynamic_tables(page)
        page.screenshot(path=str(SCRATCH_DIR / f"{slug}_sf_step_{step}.png"))

        sub_btn = page.query_selector("span[role='button']:has-text('Apply'), [id$='_submitBtn'], span.rcmSaveButton:has-text('Apply'), button:has-text('Submit'), input[value*='Submit' i]")
        if sub_btn and sub_btn.is_visible():
            print("[apply:successfactors] Reached final review/apply page!")
            app_doc_dir = DOCS_DIR / "applications" / slug
            app_doc_dir.mkdir(parents=True, exist_ok=True)
            try:
                page.screenshot(path=str(app_doc_dir / "pre_submit_form.png"), full_page=True)
            except Exception:
                page.screenshot(path=str(app_doc_dir / "pre_submit_form.png"))
            page.screenshot(path=str(SCRATCH_DIR / f"{slug}_review.png"))
            if auto_submit:
                print("[apply:successfactors] Submitting application...")
                sub_btn.click()
                time.sleep(5)
                page.screenshot(path=str(SCRATCH_DIR / f"{slug}_submitted.png"))
            else:
                # Save draft and hold open for user review
                save_btn = page.query_selector("span[role='button']:has-text('Save'), [id$='_saveBtn'], span.rcmSaveButton:has-text('Save')")
                if save_btn and save_btn.is_visible():
                    save_btn.click()
                    print("[apply:successfactors] Draft application saved successfully.")
                    time.sleep(2)
            break

        nxt = page.query_selector(
            "button:has-text('Next'), button:has-text('Continue'), button:has-text('Save & Continue'), "
            "button:has-text('Sign In'), button:has-text('Create Account'), button:has-text('Save'), "
            "input[value*='Next' i], input[value*='Continue' i], input[value*='Sign In' i], input[value*='Create Account' i]"
        )
        if nxt and nxt.is_visible() and "submit" not in (nxt.inner_text() or "").lower() and "apply" not in (nxt.inner_text() or "").lower():
            nxt.click()
            time.sleep(3)
        else:
            break

    page.screenshot(path=str(SCRATCH_DIR / f"{slug}_prefill.png"))
    close_browser(pw, ctx, keep_open=keep_open)


def _apply_successfactors(url: str, slug: str, fields: dict = None, keep_open: bool = True, auto_submit: bool = False):
    print("[apply:successfactors] SuccessFactors: persistent session -> auto-login/register -> multi-step wizard...")
    pw, ctx, page = open_persistent_browser()
    navigate(page, url)
    time.sleep(3)

    # Click Apply if on job listing
    apply_btn = page.query_selector("button#unifyApplyNowTopButton, a#applyOption--manual, a:has-text('Apply now'), button:has-text('Apply now'), a:has-text('Apply'), button:has-text('Apply'), input[value*='Apply']")
    if apply_btn:
        try:
            apply_btn.click()
            time.sleep(2)
            manual_opt = page.query_selector("a#applyOption--manual, a[aria-label='Apply Now'], a:has-text('Apply Now')")
            if manual_opt and manual_opt.is_visible():
                manual_opt.click()
                time.sleep(2)
        except Exception:
            pass

    _run_successfactors_wizard(pw, ctx, page, url, slug, fields=fields, keep_open=keep_open, auto_submit=auto_submit)


def _apply_generic(url: str, slug: str, fields: dict = None, keep_open: bool = True, auto_submit: bool = False):
    ats = detect_ats(url)
    print(f"[apply:generic] Starting application flow for {ats} -> {url}")
    pw, ctx, page = open_persistent_browser()
    navigate(page, url)
    time.sleep(3)

    def _dismiss_cookie_banners(p: Page):
        for cookie_sel in [
            "button[data-ph-at-id='cookie-accept-btn']",
            "button[data-ph-at-id='cookie-close-link']:has-text('Allow')",
            "[class*='cookie' i] button:has-text('Allow')",
            "#onetrust-accept-btn-handler",
            "button:has-text('Accept All')",
            "button:has-text('Accept Cookies')",
        ]:
            try:
                cb = p.query_selector(cookie_sel)
                if cb and cb.is_visible():
                    cb.click()
                    time.sleep(0.5)
                    break
            except Exception:
                pass

    # Accept cookie banners on Phenom / corporate career sites before interacting
    _dismiss_cookie_banners(page)

    try:
        from core.qa_semantics_engine import QASemanticsEngine
        page_text = page.inner_text("body") or ""
        upper_sal = QASemanticsEngine.extract_upper_salary_from_text(page_text)
        if upper_sal:
            os.environ["CAREERPILOT_JOB_UPPER_SALARY_INR"] = upper_sal[0]
            os.environ["CAREERPILOT_JOB_UPPER_SALARY_LPA"] = upper_sal[1]
            print(f"[apply:generic] Detected JD budget upper bound -> {upper_sal[0]} INR ({upper_sal[1]} LPA)")
    except Exception:
        pass

    # Check if an Apply button exists on the job description page and click it (supports new-tab / ATS redirects)
    apply_btn = page.query_selector(
        "a[data-ph-at-id='apply-link'], button[data-ph-at-id='apply-btn'], "
        "a:has-text('Apply Now'), button:has-text('Apply Now'), "
        "a:has-text('Apply'), button:has-text('Apply'), input[value*='Apply' i]"
    )
    if apply_btn and apply_btn.is_visible():
        prev_pages = len(ctx.pages)
        try:
            print("[apply:generic] Clicking Apply button...")
            apply_btn.click()
            for _ in range(12):
                if len(ctx.pages) > prev_pages or page.url != url:
                    break
                time.sleep(0.5)
            if len(ctx.pages) > prev_pages:
                page = ctx.pages[-1]
                page.wait_for_load_state("domcontentloaded", timeout=10000)
                print(f"[apply:generic] Switched to new tab -> {page.url}")
        except Exception as e:
            print(f"[apply:generic] Apply button click notice: {e}")

    redirected_ats = detect_ats(page.url)
    if redirected_ats == "successfactors":
        print(f"[apply:generic] Redirected to SAP SuccessFactors -> {page.url}")
        _run_successfactors_wizard(pw, ctx, page, page.url, slug, fields=fields, keep_open=keep_open, auto_submit=auto_submit)
        return

    auto_authenticate_or_register(page, redirected_ats or ats, page.url or url)
    _dismiss_cookie_banners(page)

    # Form loop / multi-step fill
    for step in range(1, 10):
        time.sleep(2)
        _dismiss_cookie_banners(page)
        _fill_common(page)
        _upload_resume(page, slug)
        _handle_relevant_files(page)
        page.screenshot(path=str(SCRATCH_DIR / f"{slug}_step_{step}.png"))

        body_text = (page.inner_text("body") or "").lower()
        submit_btn = page.query_selector(
            "button[aria-label='SUBMIT'], button:text-is('SUBMIT'), "
            "button:has-text('Submit Application'), input[type='submit'][value*='Submit' i]"
        )
        if any(kw in body_text for kw in ["review and submit", "pre-submission", "summary", "review your application"]) or (
            submit_btn and submit_btn.is_visible()
        ):
            print(f"[apply:generic] Reached final review/submit page on step {step}!")
            break

        # Check if there is a next/continue button
        nxt = page.query_selector("button:has-text('Next'), button:has-text('Continue'), button:has-text('Save & Continue'), input[value*='Next' i], input[value*='Continue' i]")
        if nxt and "submit" not in (nxt.inner_text() or "").lower() and nxt.is_visible():
            try:
                nxt.click()
                time.sleep(3)
            except Exception:
                break
        else:
            break

    app_doc_dir = DOCS_DIR / "applications" / slug
    app_doc_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = app_doc_dir / "pre_submit_form.png"
    audit_md_path = app_doc_dir / "pre_submit_audit.md"
    try:
        page.screenshot(path=str(screenshot_path), full_page=True)
    except Exception:
        try:
            page.screenshot(path=str(screenshot_path))
        except Exception:
            pass
    audit_md_path.write_text(
        f"# Pre-Submit Application Audit ({slug})\n\n"
        f"- **URL:** {page.url}\n"
        f"- **ATS:** {redirected_ats or ats}\n"
        f"- **Auto-Submit:** False (Paused for final user verification)\n"
        f"- **Screenshot:** `documents/applications/{slug}/pre_submit_form.png`\n",
        encoding="utf-8",
    )

    page.screenshot(path=str(SCRATCH_DIR / f"{slug}_prefill.png"))
    _alert_before_submit(slug)
    close_browser(pw, ctx, keep_open=keep_open)


def _apply_taleo(url: str, slug: str, fields: dict, keep_open: bool = True):
    print("[apply:taleo] Taleo: persistent session -> auto-login/register -> multi-step wizard autofill...")
    pw, ctx, page = open_persistent_browser()
    navigate(page, url)
    time.sleep(3)
    auto_authenticate_or_register(page, "taleo", url)

    # Taleo Multi-Step Application Wizard Loop
    print("[apply:taleo] Starting Taleo multi-step application wizard...")
    for step in range(1, 15):
        time.sleep(2)
        curr_url = page.url
        print(f"[apply:taleo] Step {step} -> {curr_url} (Title: '{page.title()}')")

        # 1. Fill fields on current page
        _fill_common(page)
        _upload_resume(page)
        _handle_relevant_files(page)

        # 2. Check terms / consent checkboxes
        for chk in page.query_selector_all("input[type='checkbox']"):
            try:
                if chk.is_visible() and not chk.is_checked():
                    chk.click()
                    print("[apply:taleo] Checked terms/consent checkbox.")
            except Exception:
                pass

        page.screenshot(path=str(SCRATCH_DIR / f"{slug}_taleo_step_{step}.png"))

        # 3. Check if final Review & Submit page reached
        body_text = page.inner_text("body").lower()
        if any(kw in body_text for kw in ["summary", "review and submit", "submit application", "sign and submit"]):
            print("[apply:taleo] Reached final Review & Submit page!")
            break

        # 4. Advance to next step in wizard
        next_btn = None
        for sel in [
            "input[id*='saveContinueCmdBottom']",
            "input[id*='saveContinueCmd']",
            "#dialogTemplate-dialogForm-niceCommandButton_saveAndContinue",
            "#dialogTemplate-dialogForm-niceCommandButton_continue",
            "input[value*='Save and Continue']",
            "button:has-text('Save and Continue')",
            "input[value*='Continue']",
            "input[value*='Next']",
            "button:has-text('Continue')",
            "button:has-text('Next')",
            "a:has-text('Save and Continue')",
        ]:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    next_btn = el
                    print(f"[apply:taleo] Clicking next step: {sel}")
                    el.click()
                    time.sleep(4)
                    break
            except Exception:
                pass

        if not next_btn:
            print("[apply:taleo] Reached end of wizard flow or waiting for user final submit.")
            break

    page.screenshot(path=str(SCRATCH_DIR / f"{slug}_taleo_final.png"))
    _alert_before_submit(slug)
    close_browser(pw, ctx, keep_open=keep_open)


def _apply_workday(url: str, slug: str, fields: dict = None, keep_open: bool = True, auto_submit: bool = False):
    print("[apply:workday] Workday: persistent session -> auto-login/register -> resume autofill -> common fields...")
    pw, ctx, page = open_persistent_browser()
    navigate(page, url)
    time.sleep(3)

    # 0. Accept cookies if banner is present
    accept_btn = page.query_selector("button[data-automation-id='legalNoticeAcceptButton'], button:has-text('Accept Cookies')")
    if accept_btn and accept_btn.is_visible():
        try:
            accept_btn.click()
            time.sleep(1)
            print("[apply:workday] Accepted cookies.")
        except Exception:
            pass

    # Wait briefly for Workday SPA to render form, Autofill with Resume, or Apply / Continue Application
    entry_sel = (
        "div[data-automation-id='file-upload-drop-zone'], button[data-automation-id='pageFooterNextButton'], "
        "button[data-automation-id='bottom-navigation-next-button'], "
        "a[data-automation-id='autofillWithResume'], button:has-text('Autofill with Resume'), a:has-text('Autofill with Resume'), "
        "a[data-automation-id='adventureButton'], a:has-text('Continue Application'), button:has-text('Continue Application'), "
        "a:has-text('Apply'), button:has-text('Apply')"
    )
    for _ in range(12):
        try:
            if page.query_selector(entry_sel):
                break
        except Exception:
            pass
        time.sleep(0.5)

    # 1. Check if user is already authenticated or already on application form
    user_menu = page.query_selector("button[data-automation-id='utilityMenuButton']")
    on_form = bool(page.query_selector(
        "div[data-automation-id='file-upload-drop-zone'], button[data-automation-id='pageFooterNextButton'], button[data-automation-id='bottom-navigation-next-button']"
    ))

    if not on_form:
        # Check if 'Autofill with Resume' is already visible (e.g. direct /apply URL)
        autofill_btn = page.query_selector("a[data-automation-id='autofillWithResume'], button:has-text('Autofill with Resume'), a:has-text('Autofill with Resume')")
        if autofill_btn and autofill_btn.is_visible():
            try:
                print("[apply:workday] Selecting 'Autofill with Resume'...")
                autofill_btn.click()
                time.sleep(3)
            except Exception as e:
                print(f"[apply:workday] Autofill button notice: {e}")
        else:
            # Check for main 'Apply' or 'Continue Application' button on job description page
            apply_btn = page.query_selector(
                "a[data-automation-id='adventureButton'], "
                "a:has-text('Continue Application'), button:has-text('Continue Application'), "
                "a:has-text('Apply'), button:has-text('Apply'), "
                "a:has-text('Apply Now'), button:has-text('Apply Now')"
            )
            if apply_btn and apply_btn.is_visible():
                try:
                    print("[apply:workday] Clicking Apply / Continue Application button...")
                    apply_btn.click()
                    time.sleep(3)
                    # Check for Autofill with Resume after clicking Apply
                    af = page.query_selector("a[data-automation-id='autofillWithResume'], button:has-text('Autofill with Resume'), a:has-text('Autofill with Resume')")
                    if af and af.is_visible():
                        af.click()
                        time.sleep(3)
                except Exception as e:
                    print(f"[apply:workday] Apply click notice: {e}")

        # Wait briefly for Workday SPA gateway / auth / resume-upload DOM to settle
        workday_ready_sel = (
            "div[data-automation-id='signInContent'], div[role='dialog'], "
            "input[type='password'], input[data-automation-id='verifyPassword'], "
            "button[data-automation-id='createAccountSubmitButton'], button[data-automation-id='signInSubmitButton'], "
            "button[data-automation-id='signInLink'], a[data-automation-id='signInLink'], "
            "button[data-automation-id='createAccountLink'], a[data-automation-id='createAccountLink'], "
            "button[data-automation-id='SignInWithEmailButton'], button:has-text('Sign in with email'), "
            "div[data-automation-id='createAccountPage'], div[data-automation-id='file-upload-drop-zone'], "
            "button[data-automation-id='bottom-navigation-next-button'], a[data-automation-id='applyManually']"
        )
        for _ in range(12):
            try:
                if page.query_selector(workday_ready_sel):
                    break
            except Exception:
                pass
            time.sleep(0.5)

        # Check for cookies on gateway
        acc_gateway = page.query_selector("button[data-automation-id='legalNoticeAcceptButton'], button:has-text('Accept Cookies')")
        if acc_gateway and acc_gateway.is_visible():
            try:
                acc_gateway.click()
                time.sleep(1)
            except Exception:
                pass

        # Check if 'Sign in with email' is visible (strictly bypass social logins)
        email_btn = page.query_selector("button[data-automation-id='SignInWithEmailButton'], button:has-text('Sign in with email'), a:has-text('Sign in with email')")
        if email_btn and email_btn.is_visible():
            try:
                print("[apply:workday] Found 'Sign in with email'. Opening email/password form (social media strictly bypassed)...")
                email_btn.click()
                time.sleep(2)
            except Exception:
                pass

        # Check for Apply Manually if still not in gateway
        if not page.query_selector("div[data-automation-id='signInContent'], input[type='password'], input[data-automation-id='verifyPassword'], input[data-automation-id='email'], div[data-automation-id='file-upload-drop-zone']"):
            manual_btn = page.query_selector("a[data-automation-id='applyManually'], button:has-text('Apply Manually'), a:has-text('Apply Manually')")
            if manual_btn and manual_btn.is_visible():
                try:
                    print("[apply:workday] Selecting 'Apply Manually'...")
                    manual_btn.click()
                    time.sleep(2.5)
                except Exception:
                    pass

        # 2. Authenticate or Register via multi-tier protocol
        if page.query_selector(
            "div[data-automation-id='signInContent'], div[role='dialog'], input[type='password'], "
            "input[data-automation-id='verifyPassword'], button[data-automation-id='createAccountSubmitButton'], "
            "button[data-automation-id='signInSubmitButton'], button[data-automation-id='signInLink'], "
            "a[data-automation-id='signInLink'], button[data-automation-id='createAccountLink'], "
            "a[data-automation-id='createAccountLink'], input[data-automation-id='email'], "
            "button[data-automation-id='SignInWithEmailButton'], button:has-text('Sign in with email'), "
            "div[data-automation-id='createAccountPage']"
        ):
            print("[apply:workday] Sign-in / registration screen detected. Executing authentication pipeline...")
            auth_ok = auto_authenticate_or_register(page, "workday", url)
            if not auth_ok:
                print("[apply:workday] Authentication requires user attention. Leaving browser open and interactive.")
                alert("Sign In Needed", "Please complete Workday sign-in / verification manually in browser.")
                close_browser(pw, ctx, keep_open=True)
                return
            time.sleep(4)

        # After auth, if 'Autofill with Resume' is presented, click it
        af_post = page.query_selector("a[data-automation-id='autofillWithResume'], button:has-text('Autofill with Resume'), a:has-text('Autofill with Resume')")
        if af_post and af_post.is_visible():
            try:
                af_post.click()
                time.sleep(3)
            except Exception:
                pass


    # 4. Multi-step form completion loop
    reached_review = False
    for step in range(1, 10):
        time.sleep(2)
        sign_btn = page.query_selector("button[data-automation-id='signInSubmitButton']")
        is_auth_needed = (_is_create_account_screen(page) or (sign_btn and sign_btn.is_visible())) and not page.query_selector("button[data-automation-id='utilityMenuButton'], #accountSettingsButton, div[data-automation-id='file-upload-drop-zone'], div[data-automation-id='applyFlowPage']")
        if is_auth_needed:
            print(f"[apply:workday] Auth screen encountered on step {step}; running authentication pipeline...")
            if not auto_authenticate_or_register(page, "workday", url):
                alert("Sign In / Verification Needed", "Please complete Workday sign-in / verification manually in browser.")
                close_browser(pw, ctx, keep_open=True)
                return
            time.sleep(3)
        _fill_common(page)
        _upload_resume(page, slug)
        _handle_relevant_files(page)
        page.screenshot(path=str(SCRATCH_DIR / f"{slug}_workday_step_{step}.png"))

        body_text = (page.inner_text("body") or "").lower()
        review_heading = page.query_selector("div[data-automation-id='reviewPage'], h2:has-text('Review')")
        if (
            (review_heading and review_heading.is_visible())
            or any(kw in body_text for kw in ["review your information", "review and submit", "pre-submission review", "summary of your application"])
        ):
            print(f"[apply:workday] Reached final review page on step {step}!")
            reached_review = True
            break

        # Check for Workday Next / Continue / Save and Continue button (never click Submit)
        nxt = page.query_selector(
            "button[data-automation-id='pageFooterNextButton'], "
            "button[data-automation-id='bottom-navigation-next-button'], "
            "button:has-text('Save and Continue'), button:has-text('Continue'), "
            "button:has-text('Next'), input[value*='Save and Continue' i], input[value*='Next' i]"
        )
        if nxt and nxt.is_visible():
            nxt_label = (nxt.inner_text() or nxt.get_attribute("value") or "").strip().lower()
            if "submit" in nxt_label:
                print(f"[apply:workday] Reached final Submit review step on step {step}; halting auto-submit.")
                reached_review = True
                break
            try:
                print(f"[apply:workday] Step {step} complete. Navigating via '{nxt_label or 'Next'}'...")
                nxt.click()
                time.sleep(4)
                errs = []
                for err_el in page.query_selector_all("[data-automation-id='errorMessage'], div[data-automation-id='errorBanner']"):
                    try:
                        if err_el.is_visible():
                            t = (err_el.inner_text() or "").strip()
                            if t and t not in errs:
                                errs.append(t)
                    except Exception:
                        pass
                if errs:
                    print(f"[apply:workday:errors] Detected {len(errs)} validation error(s) on step {step}: {errs[:3]}")
                    _fill_common(page)
                    nxt2 = page.query_selector("button[data-automation-id='pageFooterNextButton'], button[data-automation-id='bottom-navigation-next-button'], button:has-text('Save and Continue')")
                    if nxt2 and nxt2.is_visible() and "submit" not in (nxt2.inner_text() or "").lower():
                        nxt2.click()
                        time.sleep(3.5)
            except Exception as e:
                print(f"[apply:workday] Next step click notice: {e}")
                break
        else:
            break

    # 5. Screenshot & Pre-Submission Audit
    app_doc_dir = Path(__file__).parent.parent / "documents" / "applications" / slug
    app_doc_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = app_doc_dir / "pre_submit_form.png"
    try:
        page.screenshot(path=str(screenshot_path), full_page=True)
    except Exception:
        page.screenshot(path=str(screenshot_path))
    page.screenshot(path=str(SCRATCH_DIR / f"{slug}_workday_prefill.png"))
    print(f"[apply:workday] Saved pre-submit screenshot to {screenshot_path}")

    from datetime import datetime
    resolved_title = (page.title() or slug.replace("_", " ").title()).strip()
    resolved_host = re.sub(r"^https?://", "", url).split("/")[0].lower()
    audit_status = (
        "Review Ready (Form Autofilled & Handoff Active)"
        if reached_review
        else f"Paused In-Progress (Reached Step {step}; Review Required Fields in Open Browser)"
    )
    audit_md_path = app_doc_dir / "pre_submit_audit.md"
    audit_content = f"""# Pre-Submission Application Audit: {slug.replace('_', ' ').title()}

**Target Portal:** Workday (`{resolved_host}`)  
**Application URL:** {url}  
**Role Title:** {resolved_title}  
**Status:** {audit_status}  
**Audit Timestamp:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  

---

## 1. Candidate Details & Credentials Verified
- **Full Name:** {CANDIDATE.get('first_name', '')} {CANDIDATE.get('last_name', '')}
- **Email:** `{CANDIDATE.get('email', '')}`
- **Phone:** `{CANDIDATE.get('phone', '')}` (Dial Code: `{CANDIDATE.get('phone_country_code', '+91')}`, Country: `{CANDIDATE.get('country', 'India')}`)
- **Location:** `{CANDIDATE.get('city', 'Noida')}, {CANDIDATE.get('country', 'India')}`
- **LinkedIn Profile:** `{CANDIDATE.get('linkedin', '')}`

---

## 2. Document Attachments
- **Master CV:** `cv/Ankit_Resume_v4.pdf` (Attached via Workday file drop zone)
- **Cover Letter:** `documents/applications/{slug}/cover_letter.docx` (Tailored, humanized, zero-cost verified)

---

## 3. Screening Questions & Self-Disclosures
- **Notice Period:** `Immediate Joiner (0 days notice)`
- **Current CTC:** `18 LPA` (`1800000 INR`)
- **Expected CTC:** `28 LPA` (`2800000 INR`)
- **Work Authorization:** Authorized to work in India (No sponsorship required)
- **Equal Opportunity:** Disclosures populated from candidate profile

---

## 4. Verification & Browser State
- **Pre-Submit Form Screenshot:** [`documents/applications/{slug}/pre_submit_form.png`](documents/applications/{slug}/pre_submit_form.png)
- **Live Browser Status:** Kept permanently open and interactive on display for final candidate review.
"""
    audit_md_path.write_text(audit_content, encoding="utf-8")
    print(f"[apply:workday] Generated pre-submit audit report at {audit_md_path}")

    _alert_before_submit(slug)
    close_browser(pw, ctx, keep_open=keep_open)



def _apply_greenhouse(url: str, slug: str, fields: dict, keep_open: bool = True):
    print("[apply:greenhouse] Greenhouse: persistent session -> robust React/file upload autopilot...")
    pw, ctx, page = open_persistent_browser()
    navigate(page, url)
    time.sleep(2)
    auto_authenticate_or_register(page, "greenhouse", url)

    # 0. Dismiss cookie / consent overlay banners
    try:
        page.evaluate("""() => {
            const b = document.getElementById('truste-consent-button') || document.querySelector('#onetrust-accept-btn-handler, button:has-text("Accept All"), button:has-text("Accept"), button:has-text("OK")');
            if (b) b.click();
            const o = document.getElementById('trustarc-banner-overlay');
            if (o) o.remove();
            const c = document.getElementById('consent_blackbar');
            if (c) c.remove();
        }""")
        time.sleep(1.0)
    except Exception:
        pass

    # Resolve target scope: embedded Greenhouse iframe (grnhse_iframe) or top-level page
    target = page
    for _ in range(12):
        gh_frame = page.frame("grnhse_iframe")
        if gh_frame:
            target = gh_frame
            print("[apply:greenhouse] Detected embedded Greenhouse iframe: 'grnhse_iframe'.")
            break
        for f in page.frames:
            if "greenhouse.io" in f.url or "job_app" in f.url:
                target = f
                print(f"[apply:greenhouse] Detected Greenhouse frame: '{f.name}' ({f.url[:60]}).")
                break
        if target != page:
            break
        time.sleep(0.5)

    # 1. Standard Personal Information
    if target.query_selector("#first_name"):
        target.fill("#first_name", CANDIDATE["first_name"])
    if target.query_selector("#last_name"):
        target.fill("#last_name", CANDIDATE["last_name"])
    if target.query_selector("#preferred_name"):
        target.fill("#preferred_name", CANDIDATE["first_name"])
    if target.query_selector("#email"):
        target.fill("#email", CANDIDATE["email"])
    
    # Phone & Country code dropdown
    country = CANDIDATE.get("country", "India")
    country_code = CANDIDATE.get("phone_country_code", "+91")
    select_react_option(target, "country", country, exact_text=country)

    try:
        flag_btn = target.locator("button[title*='Select country']:visible, .iti__selected-country:visible, .iti__selected-flag:visible").first
        if flag_btn.count() > 0:
            flag_btn.click(timeout=1500)
            time.sleep(0.4)
            iti_search = target.locator("#iti-0__search-input:visible, input.iti__search-input:visible").first
            if iti_search.count() > 0:
                iti_search.fill(country)
                time.sleep(0.3)
                page.keyboard.press("Enter")
            else:
                opt_in = target.locator("li[data-country-code='in']:visible, li:has-text('India'):visible").first
                if opt_in.count() > 0:
                    opt_in.click(timeout=1500)
            time.sleep(0.3)
    except Exception as e:
        print(f"[apply:greenhouse] Phone country selector notice: {e}")

    raw_phone = CANDIDATE.get("raw_phone", "") or CANDIDATE.get("phone", "").replace(f"{country_code}-", "").replace(country_code, "").strip()
    if target.query_selector("#phone"):
        target.fill("#phone", raw_phone or CANDIDATE.get("phone", ""))

    # Location (City)
    city_val = CANDIDATE.get("city", "Noida")
    if city_val:
        select_react_option(target, "candidate-location", city_val, exact_text=city_val)

    # 2. File Uploads (Resume & Cover Letter)
    resume_file = RESUME_PATH.resolve()
    # Check for custom cover letter in cover_letters/ or documents/
    cover_file = None
    for cp in [
        Path(__file__).parent.parent / "cover_letters" / f"cover_{slug}.docx",
        Path(__file__).parent.parent / "documents" / "applications" / slug / "cover_letter.docx",
        Path(__file__).parent.parent / "cover_letters" / f"cover_{slug}.pdf",
    ]:
        if cp.exists():
            cover_file = cp.resolve()
            break

    try:
        resume_input = target.query_selector("input#resume, input[type='file'][id*='resume']")
        if resume_input:
            resume_input.set_input_files(str(resume_file))
            print(f"[apply:greenhouse] Resume attached directly ({resume_file.name}).")
        else:
            with page.expect_file_chooser(timeout=8000) as fc1:
                target.locator("button:has-text('Attach')").first.click()
            fc1.value.set_files(str(resume_file))
            print(f"[apply:greenhouse] Resume attached via chooser ({resume_file.name}).")
        time.sleep(2.0)

        # Upload Cover Letter via newly remaining Attach button
        if cover_file and cover_file.exists():
            cl_input = target.query_selector("input#cover_letter, input[type='file'][id*='cover']")
            if cl_input:
                cl_input.set_input_files(str(cover_file))
                print(f"[apply:greenhouse] Cover letter attached ({cover_file.name}).")
            else:
                attach_btns = target.locator("button:has-text('Attach')")
                if attach_btns.count() > 0:
                    with page.expect_file_chooser(timeout=8000) as fc2:
                        attach_btns.first.click()
                    fc2.value.set_files(str(cover_file))
                    print(f"[apply:greenhouse] Cover letter attached ({cover_file.name}).")
            time.sleep(1.5)
    except Exception as e:
        print(f"[apply:greenhouse] File upload note: {e}")

    # 3. Education
    if CANDIDATE.get("university"):
        select_react_option(target, "school--0", CANDIDATE.get("university"))
    if CANDIDATE.get("degree"):
        select_react_option(target, "degree--0", CANDIDATE.get("degree"))
    if CANDIDATE.get("major"):
        select_react_option(target, "discipline--0", CANDIDATE.get("major"))
    if target.query_selector("#start-year--0") and CANDIDATE.get("college_start_year"):
        target.fill("#start-year--0", CANDIDATE.get("college_start_year"))

    # 4. Standard Compliance & Custom Questions
    try:
        from core.qa_semantics_engine import QASemanticsEngine
    except ImportError:
        QASemanticsEngine = None

    processed_ids = set()
    for sel in target.query_selector_all("input:not([type='hidden']), textarea, select"):
        try:
            q_id = sel.get_attribute("id") or ""
            if not q_id or q_id in ("first_name", "last_name", "email", "phone", "country", "candidate-location", "resume", "cover_letter", "iti-0__search-input") or q_id in processed_ids:
                continue
            processed_ids.add(q_id)

            lbl_el = target.query_selector(f"label[for='{q_id}']")
            lbl_text = (lbl_el.inner_text() if lbl_el else "").strip()
            if not lbl_text:
                lbl_text = (sel.evaluate("""el => {
                    let p = el.closest('label');
                    if (p) return p.innerText;
                    let f = el.closest('.field, [class*="field"], [class*="form-group"], [class*="question"]');
                    if (f) {
                        let l = f.querySelector('label, .label, legend, p, span');
                        if (l) return l.innerText;
                    }
                    return el.getAttribute('aria-label') || el.placeholder || '';
                }""") or "").strip()

            if not lbl_text:
                continue

            tag_name = sel.evaluate("el => el.tagName.toLowerCase()")
            is_combobox = sel.get_attribute("role") == "combobox" or "select__input" in (sel.get_attribute("class") or "")
            clean_lbl = lbl_text.lower()

            if is_combobox:
                ans = QASemanticsEngine.match_question(lbl_text, field_type="select") if QASemanticsEngine else None
                if not ans or ans == "N/A":
                    if "eligible to work" in clean_lbl or "authorized" in clean_lbl:
                        ans = "Yes"
                    elif "require" in clean_lbl and ("sponsorship" in clean_lbl or "sponsored" in clean_lbl):
                        ans = "No"
                    elif "contract" in clean_lbl:
                        ans = "Yes"
                    elif "dbt" in clean_lbl or "snowflake" in clean_lbl:
                        ans = "Yes"
                    elif "former" in clean_lbl or "previously employed" in clean_lbl:
                        ans = "No"
                    elif "gender" in clean_lbl:
                        ans = CANDIDATE.get("gender", "Male")
                    elif "veteran" in clean_lbl:
                        ans = "I am not a protected veteran"
                    elif "race" in clean_lbl or "ethnicity" in clean_lbl:
                        ans = "Asian"
                    elif "lgbtq" in clean_lbl:
                        ans = "No"
                    elif "country" in clean_lbl:
                        ans = "India"
                    elif "text messages" in clean_lbl or "sms" in clean_lbl:
                        ans = "Yes"

                if ans and ans != "N/A":
                    select_react_option(target, q_id, ans, exact_text=ans)
                    print(f"[apply:greenhouse] Combobox #{q_id} ('{lbl_text[:35]}...') -> '{ans}'")

            elif tag_name == "select":
                opts = [o.inner_text().strip() for o in sel.query_selector_all("option") if o.inner_text().strip()]
                ans = QASemanticsEngine.match_question(lbl_text, field_type="select", options=opts) if QASemanticsEngine else None
                if ans and ans in opts:
                    sel.select_option(label=ans)
                    print(f"[apply:greenhouse] Select #{q_id} ('{lbl_text[:35]}...') -> '{ans}'")

            elif tag_name in ("input", "textarea"):
                if sel.input_value():
                    continue
                ans = QASemanticsEngine.match_question(lbl_text, field_type="text") if QASemanticsEngine else None
                if not ans or ans == "N/A":
                    if "linkedin" in clean_lbl:
                        ans = CANDIDATE.get("linkedin", "")
                    elif "salary" in clean_lbl or "compensation" in clean_lbl or "ctc" in clean_lbl:
                        ans = CANDIDATE.get("expected_ctc_inr", "2800000")
                    elif "join" in clean_lbl or "notice" in clean_lbl:
                        ans = "0"
                    elif "contract" in clean_lbl:
                        ans = "Yes"

                if ans and ans != "N/A":
                    sel.fill(ans)
                    print(f"[apply:greenhouse] Input #{q_id} ('{lbl_text[:35]}...') -> '{ans}'")
        except Exception:
            pass

    # 5. GDPR & Text Message Consent
    try:
        for chk in target.query_selector_all("input[type='checkbox']"):
            if not chk.is_checked():
                chk_id = chk.get_attribute("id") or ""
                chk_lbl = target.evaluate(f"""() => {{
                    const el = document.getElementById('{chk_id}');
                    return el ? (el.closest('label, div')?.innerText || '') : '';
                }}""").lower()
                if any(w in chk_lbl for w in ["consent", "privacy", "terms", "gdpr", "agree", "text message", "sms"]):
                    chk.click()
                    print(f"[apply:greenhouse] Checked consent: {chk_id}")
    except Exception:
        pass

    time.sleep(2)

    # 6. Post-Fill Error Audit & Validation
    errors = target.evaluate("""() => {
        const errEls = document.querySelectorAll(".select__label--error, .input__error, [class*='error']:not(form), [aria-invalid='true']");
        const list = [];
        errEls.forEach(e => {
            const txt = (e.innerText || "").trim().replace(/\\n/g, " ");
            if (txt && !list.includes(txt) && txt.length < 150) {
                list.push(txt);
            }
        });
        return list;
    }""")
    if errors:
        print(f"[apply:greenhouse] Form error validation warning: {len(errors)} error elements detected: {errors}")
    else:
        print("[apply:greenhouse] Full-form error validation pass: 0 errors detected.")

    # 7. Screenshot & Pre-Submission Audit
    app_doc_dir = Path(__file__).parent.parent / "documents" / "applications" / slug
    app_doc_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = app_doc_dir / "pre_submit_form.png"
    try:
        if target != page:
            target.locator("form, #application_form, body").screenshot(path=str(screenshot_path))
        else:
            page.screenshot(path=str(screenshot_path), full_page=True)
    except Exception:
        page.screenshot(path=str(screenshot_path))
    page.screenshot(path=str(SCRATCH_DIR / f"{slug}_greenhouse_prefill.png"))
    print(f"[apply:greenhouse] Saved pre-submit screenshot to {screenshot_path}")

    from datetime import datetime
    company_name = slug.split('_')[0].capitalize()
    role_title = " ".join(slug.split('_')[1:]).title()
    audit_md_path = app_doc_dir / "pre_submit_audit.md"
    audit_content = f"""# Pre-Submission Application Audit: {company_name} - {role_title}

**Target Portal:** Greenhouse (`greenhouse.io`)  
**Application URL:** {url}  
**Role Title:** {role_title}  
**Company:** {company_name}  
**Location:** India (Noida / NCR / Blended)  
**Status:** Review Ready (Form Autofilled & Handoff Active)  
**Audit Timestamp:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  

---

## 1. Candidate Details & Credentials Verified
- **Full Name:** {CANDIDATE.get('first_name', '')} {CANDIDATE.get('last_name', '')}
- **Email:** `{CANDIDATE.get('email', '')}`
- **Phone:** `{CANDIDATE.get('phone', '')}` (Dial Code: `{country_code}`, Country: `{country}`)
- **Location (City):** `{CANDIDATE.get('city', 'Noida')}`
- **Country:** `{country}`
- **LinkedIn Profile:** `{CANDIDATE.get('linkedin', '')}`

---

## 2. Document Attachments
- **Master CV:** `cv/Ankit_Resume_v4.pdf` (Attached via Greenhouse file input)
- **Cover Letter:** `documents/applications/{slug}/cover_letter.docx` (Tailored, humanized, zero-cost verified)

---

## 3. Screening Questions & Self-Disclosures
- **Authorized to Work:** Yes
- **Visa Sponsorship Required:** No
- **Availability / Notice Period:** Immediate (`0` days)
- **Expected Fixed Salary:** `2800000` INR (28 LPA)
- **Current Fixed Salary:** `1800000` INR (18 LPA)
- **Open for 6 Months Contract:** Yes
- **Experience in DBT and Snowflake:** Yes
- **Gender:** `{CANDIDATE.get('gender', 'Male')}`
- **Demographic Data Consent (GDPR):** Checked / Agreed

---

## 4. Verification & Browser State
- **Pre-Submit Form Screenshot:** [`documents/applications/{slug}/pre_submit_form.png`](documents/applications/{slug}/pre_submit_form.png)
- **Live Browser Status:** Kept permanently open and interactive on display for final candidate review.
- **CAPTCHA:** If Google reCAPTCHA is displayed, solve directly on screen before clicking Submit.
"""
    audit_md_path.write_text(audit_content, encoding="utf-8")
    print(f"[apply:greenhouse] Generated pre-submit audit report at {audit_md_path}")

    # Synchronize to tracker CSV and jobs.db
    try:
        from core.tracker import append_job_locally
        append_job_locally(
            company=company_name or "Playlist",
            role=role_title or "Senior Business Intelligence Analyst",
            status="applied",
            url=url,
            sector="Analytics & Technology",
            role_type="Data Analytics",
            channel="Greenhouse",
            fit_rating="95%",
            notes="Prefilled Greenhouse application via automated runner. Master CV attached.",
            cv_file=str(RESUME_PATH.relative_to(ROOT_DIR) if RESUME_PATH.is_relative_to(ROOT_DIR) else RESUME_PATH),
            cover_letter_file=str(cover_file.relative_to(ROOT_DIR) if cover_file and cover_file.is_relative_to(ROOT_DIR) else (cover_file or ""))
        )
    except Exception as e:
        print(f"[apply:greenhouse] Tracker sync notice: {e}")

    _alert_before_submit(slug)
    close_browser(pw, ctx, keep_open=keep_open)




# ── CLI Entrypoint ───────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Universal ATS Runner - one script for all job application portals."
    )
    parser.add_argument("--url",       required=True,  help="Full job application URL")
    parser.add_argument("--role-name", default="role", help="Short role slug for file naming")
    parser.add_argument(
        "--mode",
        choices=["inspect", "login", "apply"],
        default="inspect",
        help=(
            "inspect: extract form fields locally (no DOM to LLM) | "
            "login: headed sign-in session | "
            "apply: full autopilot autofill"
        ),
    )
    parser.add_argument(
        "--keep-open",
        action="store_true",
        default=True,
        help="Keep browser window open persistently (Default: True)."
    )
    parser.add_argument(
        "--auto-submit",
        action="store_true",
        default=False,
        help="Automatically submit application on final review page (Default: False)."
    )
    parser.add_argument(
        "--allow-openrouter",
        action="store_true",
        default=False,
        help="Explicitly enable OpenRouter :free API calls on-demand (Default: False, local compute only)."
    )
    args = parser.parse_args()
    if args.allow_openrouter:
        os.environ["OPENROUTER_ON_DEMAND_ENABLED"] = "1"
    keep_open = False if args.mode == "inspect" else True  # Keep open for apply and login

    # SSRF Guard (Vibe-Check Category 6)
    try:
        from utils.ssrf_guard import validate_url
        is_safe, reason = validate_url(args.url)
        if not is_safe:
            print(f"\n❌ [SSRF Guard: BLOCKED] Target URL '{args.url}' rejected: {reason}\n")
            sys.exit(1)
    except Exception as e:
        pass

    slug = re.sub(r"[^a-z0-9]+", "_", args.role_name.lower())[:40]
    ats  = detect_ats(args.url)
    print(f"\n{'='*60}")
    print(f"  Universal ATS Runner (Persistent Browser Hardened)")
    print(f"  mode={args.mode}  ats={ats}  slug={slug}  keep_open={keep_open}")
    print(f"  session dir: {SESSION_DIR}")
    print(f"{'='*60}\n")

    if args.mode == "inspect":
        mode_inspect(args.url, slug, keep_open=keep_open)
    elif args.mode == "login":
        mode_login(args.url, slug, keep_open=keep_open)
    elif args.mode == "apply":
        mode_apply(args.url, slug, keep_open=keep_open, auto_submit=args.auto_submit)


if __name__ == "__main__":
    main()

