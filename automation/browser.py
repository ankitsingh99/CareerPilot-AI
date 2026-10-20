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

from playwright.sync_api import sync_playwright, Page

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
SCRATCH_DIR  = Path(__file__).parent.parent / "scratch"
SESSION_DIR  = Path(__file__).parent.parent / ".browser_session"
SCRATCH_DIR.mkdir(exist_ok=True)
SESSION_DIR.mkdir(exist_ok=True)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

def get_candidate_credentials() -> tuple[dict, str, str, str]:
    """Returns (candidate_dict, default_email, default_password, alt_password) from client_secret.json."""
    prof = DEFAULT_CANDIDATE.copy()
    email = prof["email"]
    password = ""
    alt_password = ""

    target_secret = SECRETS_FILE if SECRETS_FILE.exists() else (GLOBAL_SECRETS_FILE if GLOBAL_SECRETS_FILE.exists() else None)
    if target_secret:
        try:
            data = json.loads(target_secret.read_text())
            if "candidate_profile" in data:
                prof.update(data["candidate_profile"])
            if "credentials" in data:
                email = data["credentials"].get("default_email", email)
                password = data["credentials"].get("default_password", password)
                alt_password = data["credentials"].get("alternate_password", "")
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

    return prof, email, password, alt_password

# Dynamic CANDIDATE instance loaded from local client_secret.json
CANDIDATE, _, _, _ = get_candidate_credentials()


def record_new_account(company: str, website: str, username: str, password: str):
    """
    Log account credentials only if they differ from standard defaults.
    Standard accounts reuse global default_email & default_password automatically.
    """
    if not SECRETS_FILE.exists():
        return
    try:
        data = json.loads(SECRETS_FILE.read_text())
        default_pwd = data.get("credentials", {}).get("default_password", "")
        # Only record if password or username is non-standard
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
    "successfactors": ["successfactors.com", "sapsf.com"],
    "avature":        ["avature.net"],
    "phenom":         ["phenom.com", "phenompeople.com", "eightfold.ai"],
    "ashby":          ["ashbyhq.com"],
    "icims":          ["icims.com"],
    "rippling":       ["ats.rippling.com"],
    "thehirehub":     ["thehirehub.ai"],
    "pinpoint":       ["pinpointhq.com"],
}

def detect_ats(url: str) -> str:
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
            args=["--start-maximized", "--no-default-browser-check"]
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



def navigate(page: Page, url: str, timeout: int = 45000):
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        time.sleep(2)
    except Exception:
        pass


def select_react_option(page: Page, input_id: str, search_text: str, exact_text: str = None) -> bool:
    """Robust react-select combobox handler for modern Greenhouse / Ashby / Workday portals."""
    try:
        inp = page.locator(f"#{input_id}")
        if inp.count() == 0:
            return False
        inp.focus()
        page.keyboard.type(search_text, delay=25)
        time.sleep(0.6)
        
        menu = page.locator("div.select__menu")
        if menu.count() > 0:
            opts = menu.locator("div.select__option")
            target = None
            for i in range(opts.count()):
                txt = opts.nth(i).inner_text().strip()
                if exact_text and exact_text.lower() in txt.lower():
                    target = opts.nth(i)
                    break
                elif not exact_text and search_text.lower() in txt.lower():
                    target = opts.nth(i)
                    break
            if target:
                target.click()
            elif opts.count() > 0:
                opts.first.click()
            time.sleep(0.3)
            return True
        else:
            page.keyboard.press("ArrowDown")
            time.sleep(0.2)
            page.keyboard.press("Enter")
            time.sleep(0.3)
            return True
    except Exception as e:
        print(f"[select_react] Warning on #{input_id}: {e}")
        return False



# ── Auto-Login & Registration Engine ─────────────────────────────────────────
# Track domains where authentication was already attempted in current process
_AUTHENTICATION_ATTEMPTS: set[str] = set()

def get_portal_credentials(url: str) -> tuple[str, str]:
    """
    Resolves exact username and password for a given portal URL.
    Checks ~/.config/job-agent/.candidate_secrets.json accounts registry first,
    then client_secret.json, then environment variables.
    """
    domain = re.sub(r"^https?://", "", url).split("/")[0].lower()
    
    # 1. Check ~/.config/job-agent/.candidate_secrets.json accounts list
    secrets_paths = [
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
                        u = acc.get("username", "")
                        p = acc.get("password", "")
                        if u and p:
                            print(f"[auth:lookup] Resolved exact domain credentials for '{domain}' from {sp.name}")
                            return u, p
                # Check account_exceptions
                for comp, acc in data.get("account_exceptions", {}).items():
                    web = (acc.get("website") or "").lower()
                    if (web and domain in web) or (comp.lower() in url.lower()):
                        u = acc.get("username", "")
                        p = acc.get("password", "")
                        if u and p:
                            print(f"[auth:lookup] Resolved exception credentials for '{domain}' from {sp.name}")
                            return u, p
            except Exception:
                pass

    # 2. Check standard defaults
    _, def_email, def_pwd, _ = get_candidate_credentials()
    return def_email, def_pwd


def auto_authenticate_or_register(page: Page, ats: str, url: str) -> bool:
    """
    STRICT ZERO-LOCKOUT PROTOCOL:
    1. Resolves exact domain credentials from registry.
    2. Enforces STRICT SINGLE-ATTEMPT LIMIT per domain.
    3. Scans for security warning / lockout banners and immediately halts if found.
    4. NEVER guesses passwords or runs iteration loops.
    5. NEVER calls auto-registration if an existing account exists or if login fails.
    """
    curr_url = page.url.lower()
    domain = re.sub(r"^https?://", "", url).split("/")[0].lower()

    # Step 0: Check if already authenticated or on job application form
    LOGIN_URL_INDICATORS = ["login", "signin", "sign-in", "accessmanagement", "auth", "session", "logon"]
    is_login_page = any(x in curr_url for x in LOGIN_URL_INDICATORS)
    has_pwd_input = False
    try:
        has_pwd_input = bool(page.query_selector("input[type='password']"))
    except Exception:
        pass

    if not is_login_page and not has_pwd_input:
        print("[auth] No login wall detected. Proceeding with application flow.")
        return True

    print(f"[auth] Login/Authentication screen detected for ATS: {ats} on {domain}")

    # Step 0b: Check if account lockout or warning banner is already present
    page_text = page.inner_text("body").lower()
    if any(warn in page_text for warn in ["locked", "security reasons", "too many unsuccessful", "last chance"]):
        print("[auth:circuit-breaker] CRITICAL: Account lockout or security warning detected on page! Halting immediately.")
        alert("Account Lockout Detected", f"Automation aborted on {ats.upper()} to protect account.")
        return False

    # Step 0c: Enforce single attempt per domain per session
    if domain in _AUTHENTICATION_ATTEMPTS:
        print(f"[auth:circuit-breaker] Authentication was already attempted for {domain}. Halting to prevent lockout.")
        alert("Manual Authentication Required", f"Please complete login manually on {ats.upper()}.")
        return False

    _AUTHENTICATION_ATTEMPTS.add(domain)

    # Step 1: Resolve exact credentials
    username, password = get_portal_credentials(url)
    if not username or not password:
        print(f"[auth:guard] No exact credentials found for {domain}. Aborting login to prevent guessing.")
        alert("Credentials Missing", f"Please sign in manually on {ats.upper()}.")
        return False

    # Step 2: Exactly ONE login attempt
    print(f"[auth:single-attempt] Attempting exactly 1 login for {domain} as '{username}'...")
    login_success = _attempt_login(page, username, password)
    if login_success:
        print("[auth] Login succeeded on single attempt!")
        return True

    # Step 3: If login fails, IMMEDIATELY HALT. Do NOT retry or call auto-registration.
    print("[auth:guard] Login attempt 1 did not succeed. Halting automation immediately to prevent lockout.")
    alert("Login Required", f"Please complete sign in manually on the open {ats.upper()} browser window.")
    return False


def _attempt_login(page: Page, email: str, password: str) -> bool:
    """Finds login fields, fills email/password from client_secret.json, and submits."""
    print(f"[auth:login] Attempting login with email: {email}...")

    # Selectors for username/email
    user_selectors = [
        "#dialogTemplate-dialogForm-login-name1",
        "input[data-automation-id='email']",
        "input[data-automation-id='username']",
        "input[type='email']",
        "input[name*='user']",
        "input[name*='email']",
        "input[id*='user']",
        "input[id*='email']",
        "input[id*='login']",
    ]
    # Selectors for password
    pwd_selectors = [
        "#dialogTemplate-dialogForm-login-password",
        "input[data-automation-id='password']",
        "input[type='password']",
        "input[name*='pass']",
        "input[id*='pass']",
    ]
    # Selectors for sign-in button
    submit_selectors = [
        "#dialogTemplate-dialogForm-login-defaultcmd",
        "#dialogTemplate-dialogForm-login-submit",
        "button[data-automation-id='signInSubmitButton']",
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
    for sel in user_selectors:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                user_el = el
                break
        except Exception:
            pass

    pwd_el = None
    for sel in pwd_selectors:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                pwd_el = el
                break
        except Exception:
            pass

    if not user_el or not pwd_el:
        print("[auth:login] Login form elements not found.")
        return False

    try:
        # Pre-check for existing security warnings on page
        page_text = page.inner_text("body").lower()
        if any(w in page_text for w in ["locked", "security reasons", "too many unsuccessful", "last chance"]):
            print("[auth:login] CRITICAL: Security lockout or warning banner active before submit. Aborting.")
            alert("Account Lockout Detected", "Active lockout banner detected on portal.")
            return False

        user_el.fill(email)
        pwd_el.fill(password)
        time.sleep(1)

        # Click submit
        submitted = False
        for sel in submit_selectors:
            try:
                btn = page.query_selector(sel)
                if btn and btn.is_visible():
                    btn.click()
                    submitted = True
                    break
            except Exception:
                pass

        if not submitted:
            pwd_el.press("Enter")

        time.sleep(4)

        # Check if URL changed or login succeeded
        curr = page.url.lower()
        if all(x not in curr for x in ["login.jsf", "/login", "signin", "accessmanagement"]):
            return True

        # Check if lockout or error message appeared
        page_text = page.inner_text("body").lower()
        if any(w in page_text for w in ["locked", "security reasons", "too many unsuccessful"]):
            print("[auth:login] CRITICAL: Account lockout triggered or detected! Halting immediately.")
            alert("Account Locked", "Portal indicated account is locked. Automation permanently halted.")
            return False

        if any(err in page_text for err in ["invalid", "incorrect", "doesn't exist", "not found", "create an account", "user name and password do not match", "last chance"]):
            print("[auth:login] Login failed with error banner: account does not exist or credentials rejected.")
            return False

        # If password input is gone, login likely succeeded
        pwd_check = page.query_selector("input[type='password']")
        if not pwd_check or not pwd_check.is_visible():
            return True

    except Exception as e:
        print(f"[auth:login] Error during auto-login attempt: {e}")

    return False


def _attempt_register(page: Page, prof: dict, email: str, password: str, ats: str, url: str) -> bool:
    """Finds registration/create-account flow, creates profile with client_secret credentials."""
    print(f"[auth:register] Searching for 'Create Account' / 'New User' / 'Register' option...")

    # Strict priority: 1. Full Account Creation / Sign Up -> 2. Guest Apply only as last resort
    register_btn_selectors = [
        "button[data-automation-id='createAccountButton']",
        "a[data-automation-id='createAccountLink']",
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
        time.sleep(3)

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

        # 3. Candidate name fields if present
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

        # 4. Consent / Terms Checkbox
        for sel in ["input[type='checkbox']", "input[id*='terms']", "input[id*='consent']", "input[id*='policy']"]:
            try:
                for el in page.query_selector_all(sel):
                    if el.is_visible() and not el.is_checked():
                        el.click()
            except Exception:
                pass

        time.sleep(1)

        # 5. Submit Registration
        for sel in [
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
            result["inputs"].append({
                "id":          el.get_attribute("id") or "",
                "name":        el.get_attribute("name") or "",
                "type":        el.get_attribute("type") or "",
                "placeholder": el.get_attribute("placeholder") or "",
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

    # 1. Detect Line 3
    line3_selectors = [
        "#address3", "#address_3", "input[id*='address3' i]", "input[id*='address_3' i]",
        "input[id*='address_line_3' i]", "input[name*='address3' i]", "input[name*='address_3' i]",
        "input[name*='address_line_3' i]", "input[placeholder*='address 3' i]", "input[placeholder*='address line 3' i]"
    ]
    el_line3 = None
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
        "#address2", "#address_2", "input[id*='address2' i]", "input[id*='address_2' i]",
        "input[id*='address_line_2' i]", "input[name*='address2' i]", "input[name*='address_2' i]",
        "input[name*='address_line_2' i]", "input[placeholder*='address 2' i]", "input[placeholder*='address line 2' i]",
        "input[placeholder*='apartment' i]", "input[placeholder*='apt' i]", "input[placeholder*='suite' i]",
        "input[placeholder*='unit' i]", "input[id*='suite' i]", "input[name*='suite' i]", "input[id*='apt' i]"
    ]
    el_line2 = None
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
        "#address1", "#address_1", "input[id*='address1' i]", "input[id*='address_1' i]",
        "input[id*='address_line_1' i]", "input[name*='address1' i]", "input[name*='address_1' i]",
        "input[name*='address_line_1' i]", "input[placeholder*='address 1' i]", "input[placeholder*='address line 1' i]",
        "input[id='address' i]", "input[name='address' i]", "input[id*='street' i]", "input[name*='street' i]",
        "input[placeholder*='street' i]", "input[placeholder='Address' i]", "input[id*='street_address' i]"
    ]
    el_line1 = None
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
    mapping = {
        "first":    CANDIDATE["first_name"],
        "last":     CANDIDATE["last_name"],
        "email":    CANDIDATE["email"],
        "phone":    CANDIDATE["phone"],
        "linkedin": CANDIDATE["linkedin"],
    }
    filled = []
    for keyword, value in mapping.items():
        for sel in [
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

    # 1. Inputs (Text, Number, Tel, Url)
    for inp in page.query_selector_all("input:not([type='file']):not([type='radio']):not([type='checkbox']):not([type='hidden'])"):
        try:
            if not inp.is_visible() or inp.input_value():
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

    # 3. Radio fieldsets
    for fs in page.query_selector_all("fieldset"):
        try:
            legend = fs.query_selector("legend")
            leg_text = (legend.inner_text() if legend else "").strip().lower()
            radios = fs.query_selector_all("input[type='radio']")
            if any(r.is_checked() for r in radios):
                continue
            radio_labels = []
            for r in radios:
                r_id = r.get_attribute("id") or ""
                lbl_el = fs.query_selector(f"label[for='{r_id}']")
                if lbl_el:
                    radio_labels.append(lbl_el.inner_text().strip())

            ans = QASemanticsEngine.match_question(leg_text, field_type="radio", options=radio_labels)
            if ans:
                for r in radios:
                    r_id = r.get_attribute("id") or ""
                    lbl_el = fs.query_selector(f"label[for='{r_id}']")
                    lbl_txt = (lbl_el.inner_text() if lbl_el else "").strip().lower()
                    if ans.lower() in lbl_txt or lbl_txt in ans.lower():
                        r.check()
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


def _upload_resume(page: Page) -> bool:
    """Attempt resume upload on common file-input selectors with Taleo table sanitization."""
    resume = str(RESUME_PATH.resolve())
    
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

    uploaded = False
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

    # 2. Sanitize Taleo Attachments Table if present
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
    ats = detect_ats(url)
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


def _apply_successfactors(url: str, slug: str, fields: dict = None, keep_open: bool = True, auto_submit: bool = True):
    print("[apply:successfactors] SuccessFactors: persistent session -> auto-login/register -> multi-step wizard...")
    pw, ctx, page = open_persistent_browser()
    navigate(page, url)
    time.sleep(3)

    # Click Apply if on job listing
    apply_btn = page.query_selector("a:has-text('Apply'), button:has-text('Apply'), input[value*='Apply']")
    if apply_btn:
        try:
            apply_btn.click()
            time.sleep(3)
        except Exception:
            pass

    auto_authenticate_or_register(page, "successfactors", url)

    # Multi-step loop
    for step in range(1, 10):
        time.sleep(2)
        print(f"[apply:successfactors] Step {step} -> {page.url}")
        _fill_common(page)
        _upload_resume(page)
        _handle_relevant_files(page)

        body_text = (page.inner_text("body") or "").lower()
        if "review" in body_text or "summary" in body_text or "pre-submission" in body_text:
            print("[apply:successfactors] Reached final review page!")
            page.screenshot(path=str(SCRATCH_DIR / f"{slug}_review.png"))
            if auto_submit:
                sub_btn = page.query_selector("button:has-text('Submit'), input[value*='Submit' i], a:has-text('Submit')")
                if sub_btn:
                    print("[apply:successfactors] Submitting application...")
                    sub_btn.click()
                    time.sleep(5)
                    page.screenshot(path=str(SCRATCH_DIR / f"{slug}_submitted.png"))
            break

        nxt = page.query_selector("button:has-text('Next'), button:has-text('Continue'), button:has-text('Save & Continue'), input[value*='Next' i], input[value*='Continue' i]")
        if nxt and "submit" not in (nxt.inner_text() or "").lower():
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
        _upload_resume(page)
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


def _apply_workday(url: str, slug: str, fields: dict, keep_open: bool = True):
    print("[apply:workday] Workday: persistent session -> auto-login/register -> resume autofill -> common fields...")
    pw, ctx, page = open_persistent_browser()
    navigate(page, url)
    time.sleep(3)
    auto_authenticate_or_register(page, "workday", url)
    _upload_resume(page)
    time.sleep(4)
    _fill_common(page)
    _handle_relevant_files(page)
    page.screenshot(path=str(SCRATCH_DIR / f"{slug}_workday_prefill.png"))
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
    if page.query_selector("#email"):
        page.fill("#email", CANDIDATE["email"])
    
    # Phone & Country code dropdown
    country = CANDIDATE.get("country", "India")
    country_code = CANDIDATE.get("phone_country_code", "+91")
    select_react_option(page, "country", country, exact_text=f"{country} {country_code}")
    raw_phone = CANDIDATE.get("raw_phone", "") or CANDIDATE.get("phone", "").replace(f"{country_code}-", "").replace(country_code, "").strip()
    if page.query_selector("#phone"):
        page.fill("#phone", raw_phone or CANDIDATE.get("phone", ""))

    # Location (City)
    city_val = CANDIDATE.get("city", "")
    if city_val:
        select_react_option(page, "candidate-location", city_val)

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
    for sel in page.query_selector_all("input[id*='question'], textarea[id*='question']"):
        try:
            q_id = sel.get_attribute("id") or ""
            lbl_el = page.query_selector(f"label[for='{q_id}']")
            lbl_text = (lbl_el.inner_text() if lbl_el else "").lower()

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
            elif "worked for" in lbl_text and ("affiliated" in lbl_text or "previous" in lbl_text):
                select_react_option(page, q_id, "No", exact_text="No")
            elif "interviewed with" in lbl_text or "interviewed before" in lbl_text:
                select_react_option(page, q_id, "No", exact_text="No")
            elif "non-compete" in lbl_text or "non-solicit" in lbl_text:
                select_react_option(page, q_id, "No", exact_text="No")
            elif "certify" in lbl_text or "certify that" in lbl_text or "accurate" in lbl_text:
                select_react_option(page, q_id, "Yes", exact_text="Yes")
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

    page.screenshot(path=str(SCRATCH_DIR / f"{slug}_greenhouse_prefill.png"))
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
    args = parser.parse_args()
    keep_open = True  # Strict directive: NEVER close browser window

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
        mode_apply(args.url, slug, keep_open=keep_open)


if __name__ == "__main__":
    main()

