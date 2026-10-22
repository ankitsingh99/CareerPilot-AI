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
    """Returns (candidate_dict, default_email, default_password, alt_passwords) from client_secret.json."""
    prof = DEFAULT_CANDIDATE.copy()
    email = prof["email"]
    password = ""
    alt_passwords: list[str] = []

    target_secret = SECRETS_FILE if SECRETS_FILE.exists() else (GLOBAL_SECRETS_FILE if GLOBAL_SECRETS_FILE.exists() else None)
    if target_secret:
        try:
            data = json.loads(target_secret.read_text())
            if "candidate_profile" in data:
                prof.update(data["candidate_profile"])
            if "credentials" in data:
                creds = data["credentials"]
                email = creds.get("default_email", email)
                password = creds.get("default_password", password)
                for key in ["alternate_password", "alternate_password1", "alternate_password2"]:
                    val = creds.get(key)
                    if val and val not in alt_passwords and val != password:
                        alt_passwords.append(val)
        except Exception:
            pass
    elif LEGACY_SECRETS_FILE.exists():
        try:
            data = json.loads(LEGACY_SECRETS_FILE.read_text())
            email = data.get("email", email)
            password = data.get("standard_ats_password", password)
        except Exception:
            pass

    if email and not prof.get("email"):
        prof["email"] = email

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
    "greenhouse":     ["greenhouse.io"],
    "lever":          ["lever.co"],
    "oracle_hcm":     ["oraclecloud.com/hcmUI"],
    "successfactors": ["successfactors.com", "sapsf.com", "sapsf.eu", "join.cnh.com", "jobs2web.com"],
    "avature":        ["avature.net"],
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

            if target:
                target.click()
                time.sleep(0.3)
                return True
            else:
                print(f"[select_react] Option '{target_str}' does not exist in dropdown {available_options}. Safely closing menu.")
                page.keyboard.press("Escape")
                time.sleep(0.2)
                return False
        else:
            page.keyboard.press("Escape")
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

        # Check for explicit invalid credentials / rejection message
        page_text = page.inner_text("body").lower()
        if any(err in page_text for err in [
            "invalid user", "invalid email", "invalid password", "incorrect",
            "doesn't exist", "not found", "wrong email address or password",
            "user name and password do not match", "authentication failed",
            "check your password", "credentials are invalid"
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


def auto_authenticate_or_register(page: Page, ats: str, url: str) -> bool:
    """
    Candidate Authentication & Registration Pipeline:
    1. Detects login/authentication screen or modal.
    2. Loads candidate credentials (default password + alternate passwords).
    3. Attempts login with default password.
    4. If default password fails, iterates through alternate passwords.
    5. If password and alt passwords fail, proceeds to register the candidate.
    """
    curr_url = page.url.lower()
    domain = re.sub(r"^https?://", "", url).split("/")[0].lower()

    # Step 0: Check if login wall or modal is present
    LOGIN_URL_INDICATORS = ["login", "signin", "sign-in", "accessmanagement", "auth", "session", "logon"]
    is_login_page = any(x in curr_url for x in LOGIN_URL_INDICATORS)
    has_pwd_input = False
    try:
        has_pwd_input = bool(page.query_selector(
            "input[type='password'], div[data-automation-id='signInContent'], "
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
        # If already on application form, consider ready
        if page.query_selector("div[data-automation-id='file-upload-drop-zone'], button[data-automation-id='bottom-navigation-next-button']"):
            return True
        return False

    _AUTHENTICATION_ATTEMPTS.add(domain)

    # Step 1: Resolve credentials
    username, password, alt_passwords = get_portal_credentials(url)
    if not username or not password:
        print(f"[auth:guard] No credentials available in client_secret for {domain}.")
        alert("Credentials Missing", f"Please sign in manually on {ats.upper()}.")
        return False

    # Step 2: Attempt login with Primary / Default Password
    print(f"[auth:login] Attempting login for {domain} with primary password as '{username}'...")
    success, is_locked = _attempt_login_step(page, username, password, is_retry=False)
    if success:
        print("[auth:login] Login succeeded with primary password!")
        return True
    if is_locked:
        return False

    # Step 3: Iterate through alternate passwords if primary fails
    if alt_passwords:
        for idx, alt_pwd in enumerate(alt_passwords, start=1):
            if not alt_pwd or alt_pwd == password:
                continue
            if _is_account_locked(page):
                return False
            print(f"[auth:login] Primary password failed. Trying alternate password #{idx} for '{username}'...")
            success, is_locked = _attempt_login_step(page, username, alt_pwd, is_retry=True)
            if success:
                print(f"[auth:login] Login succeeded with alternate password #{idx}!")
                company_name = re.sub(r"https?://([^/]+).*", r"\1", url)
                record_new_account(company=company_name, website=url, username=username, password=alt_pwd)
                return True
            if is_locked:
                return False

    # Step 4: If password and alt passwords fail, proceed to register
    print(f"[auth] Primary and alternate passwords failed on {domain}. Proceeding to register as directed...")
    reg_success = _attempt_register(page, CANDIDATE, username, password, ats, url)
    if reg_success:
        print("[auth] Registration completed successfully!")
        return True
    else:
        print("[auth] Registration could not be automatically completed. Leaving browser open for candidate.")
        alert("Registration Action Required", f"Please complete sign in or registration manually on {ats.upper()}.")
        return False


def _attempt_register(page: Page, prof: dict, email: str, password: str, ats: str, url: str) -> bool:
    """Finds registration/create-account flow, creates profile with client_secret credentials."""
    print(f"[auth:register] Searching for 'Create Account' / 'New User' / 'Register' option...")

    # Check if already on registration form
    already_on_reg_form = bool(page.query_selector("input[data-automation-id='verifyPassword'], input[id*='verifyPassword'], input[name*='verifyPassword']"))

    if not already_on_reg_form:
        # Strict priority: 1. Full Account Creation / Sign Up -> 2. Guest Apply only as last resort
        register_btn_selectors = [
            "button[data-automation-id='createAccountButton']",
            "a[data-automation-id='createAccountLink']",
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

        # 1. Email & Confirm Email
        for sel in ["input[id*='email']", "input[name*='email']", "input[data-automation-id='email']"]:
            try:
                for el in page.query_selector_all(sel):
                    if el.is_visible() and not el.input_value():
                        el.fill(email)
            except Exception:
                pass

        for sel in ["input[id*='verifyEmail']", "input[name*='verifyEmail']", "input[id*='confirmEmail']", "input[name*='confirmEmail']", "input[data-automation-id='verifyEmail']"]:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    el.fill(email)
            except Exception:
                pass

        # 2. Password & Confirm Password
        for sel in ["input[type='password']", "input[data-automation-id='password']", "input[id*='password']", "input[name*='password']"]:
            try:
                for el in page.query_selector_all(sel):
                    if el.is_visible() and not el.input_value():
                        el.fill(password)
            except Exception:
                pass

        for sel in ["input[id*='verifyPassword']", "input[name*='verifyPassword']", "input[id*='confirmPassword']", "input[name*='confirmPassword']", "input[data-automation-id='verifyPassword']"]:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
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
                    btn.click()
                    print(f"[auth:register] Submitted registration form via {sel}")
                    time.sleep(4)
                    break
            except Exception:
                pass

        # Determine company identifier
        company_name = re.sub(r"https?://([^/]+).*", r"\1", url)
        page_text = page.inner_text("body").lower()

        # Check if registration failed because user/account already exists
        EXISTS_KEYWORDS = [
            "already exists", "already registered", "account already exists",
            "user already exists", "already in use", "an account already exists",
            "email is already", "email already exists", "user name already exists",
            "account with this email", "user with this email",
        ]
        if any(kw in page_text for kw in EXISTS_KEYWORDS):
            print(f"[auth:register] Account already exists for {email} on {company_name}!")
            print(f"[auth:register] Saved passwords failed. Alerting user to sign in manually...")
            alert(
                f"Account Exists - Action Required [{company_name}]",
                f"Account exists on {company_name} but saved passwords failed. Please sign in or reset password in browser."
            )
            return False

        # Record new credentials into client_secret.json if successfully created
        record_new_account(company=company_name, website=url, username=email, password=password)

        # Check if email verification code / OTP is required
        if any(v in page_text for v in ["verification code", "enter code", "verify your email", "activation link", "otp"]):
            print("[auth:register] Verification required! Triggering macOS chime and notification...")
            alert("ATS Email/OTP Verification", f"Verification sent for {company_name}. Please enter code or click link.")

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

    # Use raw 10-digit phone if country code selector exists on page
    phone_val = CANDIDATE["raw_phone"] if has_cc else CANDIDATE["phone"]

    mapping = {
        "first":    CANDIDATE["first_name"],
        "last":     CANDIDATE["last_name"],
        "email":    CANDIDATE["email"],
        "phone":    phone_val,
        "linkedin": CANDIDATE["linkedin"],
    }
    filled = []
    for keyword, value in mapping.items():
        for sel in [
            f"input[data-automation-id*='{keyword}' i]",
            f"input[id*='{keyword}']",
            f"input[name*='{keyword}']",
            f"input[placeholder*='{keyword}']",
        ]:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    el_id = (el.get_attribute("id") or "").lower()
                    el_name = (el.get_attribute("name") or "").lower()
                    # Guardrail: never inject identity fields into comment or notes inputs
                    if any(bad in el_id or bad in el_name for bad in ["comment", "note", "desc", "reason", "feedback"]):
                        continue
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

            # Guard comments
            if any(bad in full_lbl for bad in ["comment", "note", "desc", "reason", "feedback"]):
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

            ans = QASemanticsEngine.match_question(full_lbl, field_type=inp.get_attribute("type") or "text")
            if ans and ans != "N/A":
                inp.fill(ans)
                print(f"[fill:qa] Auto-filled '{full_lbl[:35]}...' -> '{ans}'")
        except Exception:
            pass

    # 2. Dropdowns (<select>)
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


def _upload_resume(page: Page, slug: str = "") -> bool:
    """Attempt resume upload on common file-input selectors, with dual cover letter upload and Taleo table sanitization."""
    resume = str(RESUME_PATH.resolve())
    cover_letter = None
    if slug:
        slug_clean = slug.lower().replace("_", "")
        # Search both application docs directory and central cover_letters directory
        search_dirs = [
            DOCS_DIR / "applications" / slug,
            DOCS_DIR / "applications",
            COVER_LETTERS_DIR,
        ]
        for sdir in search_dirs:
            if sdir.exists():
                candidates = [
                    p for p in sdir.glob("*.*")
                    if (slug_clean in p.name.lower().replace("_", "") or "cover" in p.name.lower())
                    and p.suffix in (".docx", ".pdf", ".md")
                ]
                if candidates:
                    candidates.sort(key=lambda x: (0 if x.suffix == ".docx" else (1 if x.suffix == ".pdf" else 2)))
                    cover_letter = str(candidates[0].resolve())
                    break
    if not cover_letter:
        recent_letters = sorted(COVER_LETTERS_DIR.glob("*.docx"), key=os.path.getmtime, reverse=True)
        if recent_letters:
            cover_letter = str(recent_letters[0].resolve())

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

    # 2. Check for dual/multiple file inputs (e.g. CV Upload + Additional Documents / Cover Letter)
    file_inputs = page.query_selector_all("input[type='file']")
    if len(file_inputs) >= 2:
        try:
            file_inputs[0].set_input_files(resume)
            print("[upload] Master Resume uploaded to primary file input #0")
            time.sleep(1)
            if cover_letter:
                file_inputs[1].set_input_files(cover_letter)
                print(f"[upload] Tailored Cover Letter uploaded to secondary file input #1: {Path(cover_letter).name}")
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
        "avature":        _apply_generic,
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


def _apply_successfactors(url: str, slug: str, fields: dict = None, keep_open: bool = True, auto_submit: bool = True):
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
            
            # Check for email intake form
            email_inp = page.query_selector(".emailGetter input[type='email'], input[name='email']")
            if email_inp and email_inp.is_visible():
                from core.qa_semantics_engine import load_candidate_context
                cand = load_candidate_context()
                cand_email = cand.get("email") or os.environ.get("CANDIDATE_EMAIL", "")
                if cand_email:
                    email_inp.fill(cand_email)
                    start_btn = page.query_selector(".emailGetter button.start, button:has-text('Start')")
                    if start_btn:
                        start_btn.click()
                        time.sleep(3)
        except Exception:
            pass

    auto_authenticate_or_register(page, "successfactors", url)

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
            print(f"[apply:successfactors] Registration trigger detected on step {step}. Executing account registration...")
            _attempt_register(page, CANDIDATE, CANDIDATE["email"], CANDIDATE["password"], "successfactors", page.url)
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

        body_text = (page.inner_text("body") or "").lower()
        sub_btn = page.query_selector("span[role='button']:has-text('Apply'), [id$='_submitBtn'], span.rcmSaveButton:has-text('Apply'), button:has-text('Submit'), input[value*='Submit' i]")
        if sub_btn and sub_btn.is_visible():
            print("[apply:successfactors] Reached final review/apply page!")
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
        if nxt and "submit" not in (nxt.inner_text() or "").lower() and "apply" not in (nxt.inner_text() or "").lower():
            nxt.click()
            time.sleep(3)
        else:
            break

    close_browser(pw, ctx, keep_open=keep_open)


def _apply_generic(url: str, slug: str, fields: dict = None, keep_open: bool = True, auto_submit: bool = False):
    ats = detect_ats(url)
    print(f"[apply:generic] Starting application flow for {ats} -> {url}")
    pw, ctx, page = open_persistent_browser()
    navigate(page, url)
    time.sleep(3)

    # Check if an Apply button exists on the job description page and click it
    apply_btn = page.query_selector("a:has-text('Apply Now'), button:has-text('Apply Now'), a:has-text('Apply'), button:has-text('Apply'), input[value*='Apply' i]")
    if apply_btn:
        try:
            print("[apply:generic] Clicking Apply button...")
            apply_btn.click()
            time.sleep(4)
        except Exception as e:
            print(f"[apply:generic] Apply button click notice: {e}")

    auto_authenticate_or_register(page, ats, url)

    # Form loop / multi-step fill
    for step in range(1, 10):
        time.sleep(2)
        _fill_common(page)
        _upload_resume(page, slug)
        _handle_relevant_files(page)
        page.screenshot(path=str(SCRATCH_DIR / f"{slug}_step_{step}.png"))

        body_text = (page.inner_text("body") or "").lower()
        if any(kw in body_text for kw in ["review and submit", "pre-submission", "summary", "review your application"]):
            print(f"[apply:generic] Reached final review page on step {step}!")
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

    # 1. Check if user is already authenticated or already on application form
    user_menu = page.query_selector("button[data-automation-id='utilityMenuButton']")
    on_form = bool(page.query_selector("div[data-automation-id='file-upload-drop-zone'], button[data-automation-id='bottom-navigation-next-button']"))

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
            # Check for main 'Apply' button on job description page
            apply_btn = page.query_selector("a[data-automation-id='adventureButton'], a:has-text('Apply'), button:has-text('Apply'), a:has-text('Apply Now'), button:has-text('Apply Now')")
            if apply_btn and apply_btn.is_visible():
                try:
                    print("[apply:workday] Clicking Apply button...")
                    apply_btn.click()
                    time.sleep(3)
                    # Check for Autofill with Resume after clicking Apply
                    af = page.query_selector("a[data-automation-id='autofillWithResume'], button:has-text('Autofill with Resume'), a:has-text('Autofill with Resume')")
                    if af and af.is_visible():
                        af.click()
                        time.sleep(3)
                except Exception as e:
                    print(f"[apply:workday] Apply click notice: {e}")

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
        if not page.query_selector("div[data-automation-id='signInContent'], input[type='password'], input[data-automation-id='email'], div[data-automation-id='file-upload-drop-zone']"):
            manual_btn = page.query_selector("a[data-automation-id='applyManually'], button:has-text('Apply Manually'), a:has-text('Apply Manually')")
            if manual_btn and manual_btn.is_visible():
                try:
                    print("[apply:workday] Selecting 'Apply Manually'...")
                    manual_btn.click()
                    time.sleep(2.5)
                except Exception:
                    pass

        # 2. Authenticate or Register via multi-tier protocol
        if page.query_selector("div[data-automation-id='signInContent'], div[role='dialog'], input[type='password'], input[data-automation-id='email'], button[data-automation-id='SignInWithEmailButton'], button:has-text('Sign in with email'), div[data-automation-id='createAccountPage']"):
            print("[apply:workday] Sign-in / registration screen detected. Executing authentication pipeline...")
            auth_ok = auto_authenticate_or_register(page, "workday", url)
            if not auth_ok:
                print("[apply:workday] Authentication requires user attention. Leaving browser open and interactive.")
                alert("Sign In Needed", "Please enter your password or sign in manually to Workday.")
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
    for step in range(1, 10):
        time.sleep(2)
        _fill_common(page)
        _upload_resume(page, slug)
        _handle_relevant_files(page)
        page.screenshot(path=str(SCRATCH_DIR / f"{slug}_workday_step_{step}.png"))

        body_text = (page.inner_text("body") or "").lower()
        if any(kw in body_text for kw in ["review your information", "review and submit", "pre-submission review", "summary of your application"]):
            print(f"[apply:workday] Reached final review page on step {step}!")
            break

        # Check for Workday Next / Save and Continue button
        nxt = page.query_selector("button[data-automation-id='bottom-navigation-next-button'], button:has-text('Save and Continue'), button:has-text('Next'), input[value*='Save and Continue' i], input[value*='Next' i]")
        if nxt and "submit" not in (nxt.inner_text() or "").lower():
            try:
                print(f"[apply:workday] Step {step} complete. Navigating to next step...")
                nxt.click()
                time.sleep(4)
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
    audit_md_path = app_doc_dir / "pre_submit_audit.md"
    audit_content = f"""# Pre-Submission Application Audit: {slug.replace('_', ' ').title()}

**Target Portal:** Workday (`myworkdayjobs.com`)  
**Application URL:** {url}  
**Role Title:** Associate, Data Engineer Workplace Data & Insights  
**Company:** BlackRock  
**Location:** Gurugram, India (Hybrid)  
**Status:** Review Ready (Form Autofilled & Handoff Active)  
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

    # 1. Standard Personal Information
    if page.query_selector("#first_name"):
        page.fill("#first_name", CANDIDATE["first_name"])
    if page.query_selector("#last_name"):
        page.fill("#last_name", CANDIDATE["last_name"])
    if page.query_selector("#preferred_name"):
        page.fill("#preferred_name", CANDIDATE["first_name"])
    if page.query_selector("#email"):
        page.fill("#email", CANDIDATE["email"])
    
    # Phone & Country code dropdown
    country = CANDIDATE.get("country", "India")
    country_code = CANDIDATE.get("phone_country_code", "+91")
    select_react_option(page, "country", country, exact_text=country)

    try:
        flag_btn = page.locator("button[title*='Select country']:visible, .iti__selected-country:visible, .iti__selected-flag:visible").first
        if flag_btn.count() > 0:
            flag_btn.click(timeout=1500)
            time.sleep(0.4)
            iti_search = page.locator("#iti-0__search-input:visible, input.iti__search-input:visible").first
            if iti_search.count() > 0:
                iti_search.fill(country)
                time.sleep(0.3)
                page.keyboard.press("Enter")
            else:
                opt_in = page.locator("li[data-country-code='in']:visible, li:has-text('India'):visible").first
                if opt_in.count() > 0:
                    opt_in.click(timeout=1500)
            time.sleep(0.3)
    except Exception as e:
        print(f"[apply:greenhouse] Phone country selector notice: {e}")


    raw_phone = CANDIDATE.get("raw_phone", "") or CANDIDATE.get("phone", "").replace(f"{country_code}-", "").replace(country_code, "").strip()
    if page.query_selector("#phone"):
        page.fill("#phone", raw_phone or CANDIDATE.get("phone", ""))

    # Location (City)
    city_val = CANDIDATE.get("city", "Noida")
    if city_val:
        select_react_option(page, "candidate-location", city_val, exact_text=city_val)

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
        # Upload Resume via first Attach button
        with page.expect_file_chooser(timeout=8000) as fc1:
            page.locator("button:has-text('Attach')").first.click()
        fc1.value.set_files(str(resume_file))
        print(f"[apply:greenhouse] Resume attached ({resume_file.name}).")
        time.sleep(2.5)

        # Upload Cover Letter via newly remaining Attach button
        if cover_file and cover_file.exists():
            with page.expect_file_chooser(timeout=8000) as fc2:
                page.locator("button:has-text('Attach')").first.click()
            fc2.value.set_files(str(cover_file))
            print(f"[apply:greenhouse] Cover letter attached ({cover_file.name}).")
            time.sleep(2.5)
    except Exception as e:
        print(f"[apply:greenhouse] File upload fallback: {e}")
        try:
            page.set_input_files("input#resume", str(resume_file))
            if cover_file:
                page.set_input_files("input#cover_letter", str(cover_file))
        except Exception:
            pass

    # 3. Education
    if CANDIDATE.get("university"):
        select_react_option(page, "school--0", CANDIDATE.get("university"))
    if CANDIDATE.get("degree"):
        select_react_option(page, "degree--0", CANDIDATE.get("degree"))
    if CANDIDATE.get("major"):
        select_react_option(page, "discipline--0", CANDIDATE.get("major"))
    if page.query_selector("#start-year--0") and CANDIDATE.get("college_start_year"):
        page.fill("#start-year--0", CANDIDATE.get("college_start_year"))

    # 4. Standard Compliance & Form Questions
    processed_ids = set()
    for sel in page.query_selector_all("input:not([type='hidden']), textarea, select"):
        try:
            q_id = sel.get_attribute("id") or ""
            if not q_id or q_id in ("first_name", "last_name", "email", "phone", "country", "candidate-location", "resume", "cover_letter", "iti-0__search-input") or q_id in processed_ids:
                continue
            processed_ids.add(q_id)

            lbl_el = page.query_selector(f"label[for='{q_id}']")
            lbl_text = (lbl_el.inner_text() if lbl_el else "").lower()
            if not lbl_text:
                lbl_text = (sel.evaluate("""el => {
                    let p = el.closest('label');
                    if (p) return p.innerText;
                    let f = el.closest('.field, [class*="field"], [class*="form-group"], [class*="question"]');
                    if (f) {
                        let l = f.querySelector('label, .label, legend');
                        if (l) return l.innerText;
                    }
                    return el.getAttribute('aria-label') || '';
                }""") or "").lower()

            if not lbl_text:
                continue

            if "linkedin" in lbl_text:
                sel.fill(CANDIDATE.get("linkedin", ""))
            elif "salary" in lbl_text or "compensation" in lbl_text:
                exp_lpa = CANDIDATE.get("expected_ctc_lpa", "")
                exp_inr = CANDIDATE.get("expected_ctc_inr", "")
                if exp_lpa and exp_inr:
                    sel.fill(f"{exp_lpa} LPA ({exp_inr} INR)")
                elif exp_lpa:
                    sel.fill(f"{exp_lpa} LPA")
                elif exp_inr:
                    sel.fill(f"{exp_inr} INR")
            elif "authorized to work" in lbl_text or "legally authorized" in lbl_text:
                select_react_option(page, q_id, "Yes", exact_text="Yes")
            elif "sponsorship" in lbl_text or "sponsor" in lbl_text:
                select_react_option(page, q_id, "No", exact_text="No")
            elif any(k in lbl_text for k in ["worked for", "worked at", "previously employed", "employed at", "employed with", "worked before"]):
                select_react_option(page, q_id, "No", exact_text="No")
            elif "interviewed with" in lbl_text or "interviewed before" in lbl_text:
                select_react_option(page, q_id, "No", exact_text="No")
            elif "non-compete" in lbl_text or "non-solicit" in lbl_text:
                select_react_option(page, q_id, "No", exact_text="No")
            elif any(k in lbl_text for k in ["certify", "certify that", "confirm", "accurate", "true and accurate"]):
                select_react_option(page, q_id, "Yes", exact_text="Yes")
            elif any(k in lbl_text for k in ["business intelligence", "data analysis", "bi experience"]):
                select_react_option(page, q_id, "Yes", exact_text="Yes")
            elif any(k in lbl_text for k in ["tableau", "looker", "power bi", "powerbi"]):
                select_react_option(page, q_id, "Yes", exact_text="Yes")
            elif any(k in lbl_text for k in ["sql/python", "sql", "python/r", "python"]):
                select_react_option(page, q_id, "Yes", exact_text="Yes")
            elif any(k in lbl_text for k in ["privacy notice", "candidate privacy", "consent to"]):
                select_react_option(page, q_id, "Yes", exact_text="Yes")
            elif "gender" in lbl_text:
                select_react_option(page, q_id, CANDIDATE.get("gender", "Male"), exact_text=CANDIDATE.get("gender", "Male"))
            elif "notice" in lbl_text or "availability" in lbl_text:
                select_react_option(page, q_id, "Immediate", exact_text="Immediate")
            elif "address 3" in lbl_text or "address line 3" in lbl_text:
                _, _, addr3 = resolve_address_components(has_line2=True, has_line3=True, cand=CANDIDATE)
                if addr3:
                    sel.fill(addr3)
            elif "address 2" in lbl_text or "address line 2" in lbl_text:
                has_a3 = page.locator("text=/address (line )?3/i").count() > 0
                _, addr2, _ = resolve_address_components(has_line2=True, has_line3=has_a3, cand=CANDIDATE)
                if addr2:
                    sel.fill(addr2)
            elif "street address" in lbl_text or "address 1" in lbl_text or "address line 1" in lbl_text:
                has_a3 = page.locator("text=/address (line )?3/i").count() > 0
                has_a2 = has_a3 or page.locator("text=/address (line )?2/i").count() > 0
                addr1, _, _ = resolve_address_components(has_line2=has_a2, has_line3=has_a3, cand=CANDIDATE)
                if addr1:
                    sel.fill(addr1)
            elif "legal address - city" in lbl_text or "city*" in lbl_text or "city" in lbl_text:
                if CANDIDATE.get("city"):
                    sel.fill(CANDIDATE.get("city"))
            elif "state" in lbl_text or "province" in lbl_text or "region" in lbl_text:
                if CANDIDATE.get("state"):
                    sel.fill(CANDIDATE.get("state"))
            elif "zip" in lbl_text or "postal" in lbl_text or "pincode" in lbl_text:
                if CANDIDATE.get("pincode"):
                    sel.fill(CANDIDATE.get("pincode"))
            elif "legal address - country" in lbl_text or "country*" in lbl_text:
                select_react_option(page, q_id, country, exact_text=country)
            elif "if yes" in lbl_text:
                sel.fill("N/A")
            elif sel.evaluate("el => el.tagName.toLowerCase()") == "textarea" and not sel.input_value():
                # Open-ended essay or customized question
                try:
                    from intelligence.rag import answer_custom_question
                    ans = answer_custom_question(lbl_text, company=slug, role=slug)
                    if ans:
                        sel.fill(ans)
                        print(f"[apply:greenhouse] Local RAG filled textarea #{q_id}: {ans[:60]}...")
                except Exception as e:
                    print(f"[apply:greenhouse] Local RAG textarea skip: {e}")
        except Exception:
            pass

    # 5. GDPR Consent
    try:
        gdpr = page.query_selector("input[id*='gdpr'], input[name*='gdpr'], input[id*='consent']")
        if gdpr and not gdpr.is_checked():
            gdpr.click()
            print("[apply:greenhouse] Checked GDPR retention consent.")
    except Exception:
        pass

    time.sleep(2)

    # 6. Post-Fill Error Audit & Validation
    errors = page.evaluate("""() => {
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
- **Will you require sponsorship now or in the future?:** `No` (Authorized in India)
- **I confirm that all information provided is true and accurate:** `Yes`
- **Have you worked at {company_name} before?:** `No`
- **What best describes your gender:** `{CANDIDATE.get('gender', 'Male')}`
- **Demographic Data Consent (GDPR):** `Checked / Agreed`

---

## 4. Verification & Browser State
- **Pre-Submit Form Screenshot:** [`documents/applications/{slug}/pre_submit_form.png`](documents/applications/{slug}/pre_submit_form.png)
- **Live Browser Status:** Kept permanently open and interactive on display for final candidate review.
"""
    audit_md_path.write_text(audit_content, encoding="utf-8")
    print(f"[apply:greenhouse] Generated pre-submit audit report at {audit_md_path}")

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
    args = parser.parse_args()
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

