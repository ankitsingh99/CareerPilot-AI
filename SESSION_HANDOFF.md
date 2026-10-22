# AI Job Search: Session Handoff Document
**Last Updated:** 2026-10-22 11:47:00 IST  
**Active Git Branch / Commit:** `master` @ `origin/master` (Universal Automation Framework v1.2.0)  
**Repository Visibility:** Public ([https://github.com/ankitsingh99/ai-job-search](https://github.com/ankitsingh99/ai-job-search))  
**Model Context Status:** Optimal (Clean Context Handoff)  

---

## 1. Executive Summary & Accomplishments

### 1. AlphaSense - Business Analyst II Application (Greenhouse ATS)
- **Role & Company:** Business Analyst II, Content Strategy, Planning & Analysis team at AlphaSense.
- **Application URL:** `https://job-boards.greenhouse.io/alphasense/jobs/8857586002?gh_src=8a5751f62us`.
- **Form Automation & Autofill:**
  - Standard candidate details populated from local `.env` (First Name, Last Name, Preferred Name `Ankit`, Email, Country `India +91`, Phone, Location `Noida, Uttar Pradesh, India`).
  - Dual document attachments uploaded: Master CV (`cv/Ankit_Resume_v4.pdf`) and tailored Cover Letter (`cover_letters/cover_alphasense_business_analyst_ii.docx` and `.md`).
  - Screening questions cross-validated against actual options dynamically loaded in the portal dropdowns:
    - *BI & Data Analysis Experience:* `Yes` (options `['Yes', 'No']`).
    - *Tableau / Looker / Power BI Experience:* `Yes` (options `['Yes', 'No']`).
    - *SQL / Python / R Experience:* `Yes` (options `['Yes', 'No']`).
    - *Notice Period:* `0 to 15 days` (options `['0 to 15 days', '30 days', '45 days', '60 days', '90 days']` aliased to candidate's immediate availability).
    - *Candidate Privacy Notice Consent:* `Yes` (options `['Yes']`).
  - **Full-Form Error Verification:** 0 error elements remaining (`.select__label--error: 0`, `.input__error: 0`, `[aria-invalid='true']: 0`).
  - **Artifacts:** Pre-submit audit report at `documents/applications/alphasense_business_analyst_ii/pre_submit_audit.md` and screenshot at `pre_submit_form.png`.
  - **Live Browser Status:** Headed browser preserved open and interactive on display.

### 2. Universal Automation Engine Hardening (`automation/browser.py`)
- **Dropdown Option Cross-Validation & Safe Menu Dismissal:** Upgraded `select_react_option` to query actual available options in the active menu, perform exact and semantic alias matching (e.g. `immediate` -> `0 to 15 days`), and dismiss with `Escape` rather than pressing `Enter` into the form, preventing premature submission and unintended validation errors.
- **Preferred Name & Technical Question Ingestion:** Added automatic support for `#preferred_name`, BI due diligence, BI visualization, SQL/Python/R querying, and privacy consent across modern Greenhouse / React-Select forms.
- **Post-Fill Error Audit:** Integrated automated full-page error scanning into `_apply_greenhouse` to verify clean form state before human review.

### 3. Self-Learning & Adaptive Evaluator Engine & Skill
- Registered skill: `.agents/skills/self-learning-adaptive-evaluator/SKILL.md`.
- Implemented core evaluator engine: `core/adaptive_evaluator.py`.
- Automated invariant unit tests: `tests/test_adaptive_evaluator.py`.
- Five permanent learned directives codified across `.agents/rules/05_APPLICATION_LEARNING_AND_ADAPTATION.md` and `user_inputs/candidate_preferences_and_rules.md`:
  1. *Zero Reference Person Fabrication:* Leave reference person fields empty unless provided; permission to contact is `Yes`.
  2. *College-Only Education Default:* Prune to single university degree; do not add 10th or 12th schooling unasked.
  3. *Omit Scores / CGPA Unless Mandatory:* Leave grade fields blank unless explicitly marked mandatory (`*`).
  4. *Mandatory Date Population:* Enforce start and end dates for all roles and degrees (including UI5 shadow DOM web components).
  5. *Rush by Kira Domain Spec:* Strictly classified as `Retail` / `D2C Retail & E-Commerce Operations`.

### 4. LinkedIn Easy Apply Automation & Daily Safety Ceiling
- **Search Parameters:** Data Analyst positions in India posted in the last 24 hours (`f_TPR=r86400`, Date Descending).
- **Execution & Submissions:** 12 Easy Apply applications completed and recorded in this cycle, reaching today's total of 41 Easy Apply applications.
- **Rate Limit Safety:** Enforced daily safety ceiling (35-40 applications / 24h) to safeguard candidate account reputation. Easy Apply automation safely paused until the rolling 24h reset.
- **Tracker Synchronization:** 100% of submitted jobs synced to `user_inputs/job_search_tracker.csv` and SQLite `jobs.db`.

### 5. Strict Gender Match & Semantics Engine Hardening
- **Strict Male Gender Directive:** Enforced exact string equality, negative assertions against `"female"`, and strict word-boundary regex (`\bmale\b`) across `core/qa_semantics_engine.py` and `tools/linkedin_easy_apply_runner.py` to eradicate substring collisions (where `"female"` previously matched substring `"male"`).
- **Comprehensive Unit Testing:** Added `test_gender_strictly_male` in `tests/test_qa_semantics_engine.py`, ensuring `Male` is accurately matched across radio options and dropdowns.
- **Codified Invariant:** Codified in `.agents/rules/05_APPLICATION_LEARNING_AND_ADAPTATION.md` and `user_inputs/candidate_preferences_and_rules.md`.

### 6. Modern LinkedIn Navigation & CDP Session Resiliency
- **Auth & Nav Detection:** Updated `is_logged_in` in `tools/linkedin_easy_apply_runner.py` to recognize modern obfuscated nav selectors (`a[href*='/messaging']`, `a[href*='/notifications']`, `a[href*='/mynetwork']`), eliminating false-positive login walls.
- **CDP Port 9222 Attach:** Added automatic fallback to connect via `connect_over_cdp("http://localhost:9222")`, allowing scripts to seamlessly share the existing interactive browser session without profile lock conflicts.
- **Zero-Cost OpenRouter Free Tier:** Utilized zero-cost free models (`google/gemma-4-31b-it:free`, `cohere/north-mini-code:free`) with zero financial spend.

---

## 2. Core Architecture & Single Sources of Truth

- **Master Blueprint:** `MASTER_TEMPLATE.md`
- **Unified Agent Instructions:** `AGENTS.md`
- **Candidate Preferences & Rules:** `user_inputs/candidate_preferences_and_rules.md`
- **Universal Automation Runner:** `tools/ats_runner.py` (headed Playwright with persistent browser)
- **Universal Browser Modules:** `automation/browser.py` & `core/qa_semantics_engine.py`
- **Adaptive Evaluator Engine:** `core/adaptive_evaluator.py`
- **Tracker & Local Database:** `user_inputs/job_search_tracker.csv` & `jobs.db` via `tools/sync_tracker.py`

---

## 3. Strict Operating Directives (Active)

1. **NEVER Close the Browser Window:** Under no circumstances must automation close the browser. Always leave the browser open and interactive for human verification.
2. **Zero PII in Git:** Never commit candidate phone numbers, email addresses, dates of birth, or street addresses to git. Verify before pushing with `bash tools/quality_gate.sh`.
3. **Strict Zero-Cost OpenRouter Directive:** Exclusively use free-tier models ending in `:free`. Never incur billable API costs.
4. **No Em Dashes (`—`):** Never use em dashes. Use standard hyphens (`-`), commas, colons, or parentheses.
5. **Python 3.15 Native Lazy Imports:** Maintain `PYTHON_LAZY_IMPORTS=all` in `.env` and `utils/lazy_bootstrap.py`.
6. **Token-Lean Architecture:** All code must be reusable; no single-use scripts.
7. **Cover Letter Pairing in `cover_letters/`:** Maintain paired `.md` and `.docx` files with matching names (`cover_<company>_<role>.md` and `cover_<company>_<role>.docx`).

---

## 4. Instructions for Resuming

1. Live headed browser remains active on port 9222 on the AlphaSense Business Analyst II application review page with 0 errors.
2. Candidate can review final fields and click **Submit application** on screen whenever ready.
3. Next application can be initiated cleanly via `python tools/ats_runner.py --url "<URL>" --mode apply`.
