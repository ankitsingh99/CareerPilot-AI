# Root Cause Analysis (RCA) & Permanent Prevention Protocol: Taleo Account Lockout

- **Incident Date:** 2026-10-20
- **Target Portal:** Oracle Taleo Enterprise (`uhg.taleo.net`) / UnitedHealth Group (Optum)
- **Impact Severity:** **CRITICAL** - Candidate account temporarily locked for 24 hours.
- **Affected User:** Sourced dynamically from local `.env` (`CANDIDATE_EMAIL`)
- **Root Cause Classification:** Automated Credential Guessing / Uncontrolled Authentication Loop & Fallback Misbehavior.

---

## 1. Executive Summary

During an automated benchmark run on UnitedHealth Group's Taleo job application portal (`https://uhg.taleo.net/careersection/10780/jobapply.ftl?job=2393655`), the automation script triggered a 24-hour security lockout on the candidate's account.

This occurred because the automation script executed an automated trial loop across multiple potential usernames and multiple passwords against the live authentication endpoint, and subsequently attempted an auto-registration fallback ("New User") when an active account already existed.

**Taleo enterprise IAM policy strictly locks accounts after 3 consecutive failed login attempts.** By attempting combinations in rapid succession without a single-attempt circuit breaker, the account was automatically locked.

---

## 2. Comprehensive Root Cause Analysis (5 Whys)

1. **Why was the candidate account locked?**
   Because Oracle Taleo received 3+ consecutive incorrect login attempts for the candidate account within a few seconds, triggering its automated brute-force protection policy.

2. **Why did the automation submit multiple incorrect credentials?**
   The benchmark script launched an ad-hoc authentication helper that iterated through a matrix of potential usernames and generic fallback passwords retrieved from local config rather than using a single attempt.

3. **Why did the script use generic fallback passwords instead of the exact portal password?**
   The exact password for the enterprise portal was stored in an existing domain-specific accounts registry inside `~/.config/job-agent/.candidate_secrets.json`, but the authentication function in `automation/browser.py` did not check domain-specific account mappings before attempting login. It only referenced generic fallback keys.

4. **Why did the script attempt "New User" registration after login failed?**
   `automation/browser.py` contained an unconstrained fallback routine: `if not logged_in: attempt auto_registration()`. Clicking "New User" on an identity provider where the candidate is already registered generates conflicts, confuses the session state, and violates user expectations.

5. **Why was there no automated circuit breaker to prevent multiple failed attempts?**
   The automation framework lacked a strict, zero-tolerance single-attempt authentication safety protocol. It permitted unbounded retry loops against live authentication gateways instead of halting immediately upon the first failure.

---

## 3. Systematic Defects Identified

| Defect ID | Defect Description | Mechanism | Severity |
| :--- | :--- | :--- | :---: |
| **DEF-AUTH-01** | **Unbounded Credential Guessing / Looping** | A nested loop executed against live HTTP endpoints without a rate limit or attempt counter. | **CRITICAL** |
| **DEF-AUTH-02** | **Absence of Single-Attempt Circuit Breaker** | No programmatic enforcement limiting authentication attempts to exactly ONE attempt per domain per session. | **CRITICAL** |
| **DEF-AUTH-03** | **Unconstrained Registration Fallback** | Automated clicking of "New User" / "Create Account" when authentication fails, causing unwanted secondary registration flows. | **HIGH** |
| **DEF-AUTH-04** | **Fragmented Credential Storage Lookup** | Failure to query the domain-specific `accounts` array in `~/.config/job-agent/.candidate_secrets.json` before falling back to generic defaults. | **HIGH** |
| **DEF-AUTH-05** | **Failure to Abort on Warning / Threat Banners** | Taleo warned *"This is your last chance to sign in"* on attempt #2, but the script did not parse warning strings to immediately abort. | **HIGH** |

---

## 4. Permanent Behavioral & Architectural Safeguards (Never Repeat)

To guarantee that this incident can **NEVER** happen again on any portal, the following rules are permanently embedded into the framework and code:

### Rule 1: Zero Guessing / Strict Single-Attempt Rule (ZERO-TOLERANCE)
- Automation is permitted **AT MOST ONE (1)** login attempt per portal domain.
- **NEVER** iterate through password arrays, username guesses, or variations.
- If attempt #1 fails or yields an error, the automation MUST **IMMEDIATELY HALT**.
- It must play a macOS alert chime (`Glass.aiff`), trigger a notification, and hand off control to the human user:
  ```bash
  afplay /System/Library/Sounds/Glass.aiff && osascript -e 'display notification "Login failed on attempt 1. Automation halted to prevent lockout." with title "Manual Authentication Required"'
  ```

### Rule 2: Strict Ban on Auto-Registration When Existing Account Exists
- Automation must **NEVER** click "New User", "Create Account", "Register", or "Sign Up" if the user has an existing account or if a login attempt failed.
- Auto-registration is ONLY permitted if explicitly instructed by the user via `--mode register` or user prompt.

### Rule 3: Unified Exact-Domain Credential Resolution
- Before attempting any authentication, the runner must resolve credentials in strict priority order:
  1. Exact domain match in `~/.config/job-agent/.candidate_secrets.json` -> `accounts` list.
  2. Domain-specific environment variables in local gitignored `.env`.
  3. If no exact match is found, **DO NOT GUESS**. Stop and ask the user or leave the login fields for manual entry.

### Rule 4: Warning & Lockout Pattern Interceptor
- Before submitting any authentication form, scan the DOM for security warning phrases:
  - `"last chance to sign in"`
  - `"too many unsuccessful login attempts"`
  - `"account has been locked"`
  - `"invalid credentials"`
- If any warning banner is present on the page, the automation must **REFUSE TO SUBMIT** and immediately terminate.

---

## 5. Verification Checklist for All Future Portal Automations

- [x] No password testing loops exist anywhere in the codebase.
- [x] `auto_authenticate_or_register()` refactored to single-attempt only.
- [x] Auto-registration fallback removed from default application flows.
- [x] Immediate macOS notification dispatched on any auth failure.
- [x] Master framework directives updated in `MASTER_TEMPLATE.md` and `AGENTS.md`.
- [x] Zero raw credentials or email addresses committed or tracked in repo documents.
