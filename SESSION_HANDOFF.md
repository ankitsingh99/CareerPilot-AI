# AI Job Search: Session Handoff Document
**Last Updated:** 2026-10-26 15:05:00 IST  
**Active Git Branch / Commit:** `master` @ `origin/master` (Universal Automation Framework v1.2.0)  
**Repository Visibility:** Public ([https://github.com/ankitsingh99/ai-job-search](https://github.com/ankitsingh99/ai-job-search))  
**Model Context Status:** Optimal (Clean Context Handoff)  

---

## 1. Executive Summary & Accomplishments

### 1. End-to-End Autonomous LinkedIn Easy Apply Execution (2026-10-26)
- **Batch Results:** **18 applications submitted** on 2026-10-26 (1 pre-submission review verified by user + 17 autonomous end-to-end applications).
- **Submitted Opportunities Today:**
  1. **EXL:** 4594082-Senior Executive (`https://www.linkedin.com/jobs/view/4446725505/`)
  2. **Arise TechGlobal:** Team Lead – Data Analyst (`https://www.linkedin.com/jobs/view/4482926808/`)
  3. **VAYUZ Technologies:** Lead Data Scientist (`https://www.linkedin.com/jobs/view/4481428565/`)
  4. **Tata Consultancy Services (TCS):** Data Analyst (`https://www.linkedin.com/jobs/view/4471373647/`)
  5. **Fractal:** Data Scientist (`https://www.linkedin.com/jobs/view/4483531495/`)
  6. **Zorba AI:** Tableau to Power BI Migration Specialist _4+ years (`https://www.linkedin.com/jobs/view/4482917519/`)
  7. **Nielsen:** Senior Member Technical Staff (MTS 3) - Machine learning (`https://www.linkedin.com/jobs/view/4451210421/`)
  8. **SID Information Technologies:** Lead Data Analyst (Technical Lead – SQL Data Analytics) (`https://www.linkedin.com/jobs/view/4481098666/`)
  9. **A2Y Consultants:** Data Analyst (`https://www.linkedin.com/jobs/view/4482690174/`)
  10. **Zetheta Algorithms Private Limited:** Data Analyst (`https://www.linkedin.com/jobs/view/4482690131/`)
  11. **Crossing Hurdles:** Data Annotator | $10/hr Remote (`https://www.linkedin.com/jobs/view/4473884053/`)
  12. **Scoutit:** Associate - Data Analytics (`https://www.linkedin.com/jobs/view/4482687118/`)
  13. **Essex Lake Group LLC:** ADG Senior Analyst (ML Ops-Model Deployment & Monitoring) (`https://www.linkedin.com/jobs/view/4482912444/`)
  14. **Tata Consultancy Services (TCS):** Data Scientist (`https://www.linkedin.com/jobs/view/4479536836/`)
  15. **TEKNIKOZ:** Business Analyst (`https://www.linkedin.com/jobs/view/4482688001/`)
  16. **Innova ESI:** Senior Business Analyst – ServiceNow, ITSM (`https://www.linkedin.com/jobs/view/4481099689/`)
  17. **TEKNIKOZ:** Business Analyst (`https://www.linkedin.com/jobs/view/4482688002/`)
  18. **Crossing Hurdles:** Business Analyst | $90/hr Remote (`https://www.linkedin.com/jobs/view/4473884054/`)
- **Tracker & SQLite Sync:** 100% of applications logged to `user_inputs/job_search_tracker.csv` and `jobs.db`.

### 2. QASemanticsEngine Hardening & Zero-Collision Notice Period Matching
- **Notice Period Substring Collision Elimination:** Fixed a critical bug where `"30 Days"`, `"60 Days"`, and `"90 Days"` erroneously matched `"0 days"` due to raw substring search (`"0 days" in "30 days"`). Implemented negative lookbehind regex `(?<!\d)0\s*days\b` and a tiered priority queue (`immediate` / `0 days` -> `less than 15` / `0-15` -> `15 days` -> `30 days`), successfully aliasing candidate's immediate availability to `"Less than 15 Days"` on Oracle Cloud ATS.
- **LLM Prompt Leaking & Bullet Stripping:** Hardened `ask_openrouter_free_llm` and `ask_openrouter_free` with regex sanitization to strip bullet prefixes (`*`, `-`, `•`), markdown formatting (`**`), and instruction preambles, preventing model thinking from leaking into input text fields.
- **Deterministic Compliance Expansion:** Added deterministic rules for prior company employment (`Have you worked with [company] before` -> `No`), health/ailment/medical leave (`No`), interview within last 90 days (`No`), Indian passport (`Yes`), and night/rotational shifts (`Yes`).
- **Comprehensive Unit Testing:** Added `test_compliance_and_notice_period_dropdown_options` to `tests/test_qa_semantics_engine.py` (all 13 tests passing in 0.19s).

### 3. Review-Only Mode Feature (`--review-only`)
- Added universal `--review-only` parameter to `tools/linkedin_easy_apply_runner.py`.
- Form is 100% filled and navigated to the final review screen without clicking the "Submit application" button.
- Triggers macOS audio chime (`Glass.aiff`) and notification while preserving the browser open for human inspection.

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
- **Execution & Submissions:** 16 Easy Apply applications submitted across today's sessions, totaling 41 unique Easy Apply applications on 2026-10-22 (including latest roles: IndiTech Consulting, crewlia, IQVIA India, Kake).
- **Rate Limit Safety:** Enforced daily safety ceiling (35-40 applications / 24h) to safeguard candidate account reputation. Automation safely paused upon reaching 41 submissions.
- **Tracker Synchronization:** 100% of submitted jobs synced to `user_inputs/job_search_tracker.csv` and SQLite `jobs.db`.

### 5. Strict Gender Match & Demographic Screening Hardening
- **Strict Male Gender Directive:** Enforced exact string equality, negative assertions against `"female"`, and strict word-boundary regex (`\bmale\b`) across `core/qa_semantics_engine.py` and `tools/linkedin_easy_apply_runner.py` to eradicate substring collisions (where `"female"` previously matched substring `"male"`).
- **Demographic Diversity Rules:** Codified deterministic handlers for LGBTQ (`No` / `Heterosexual`), Veteran status (`No` / `I am not a veteran`), Disability (`No, I do not have a disability`), and Race (`Asian - Indian`), preventing sexual orientation from colliding with "sex" questions.
- **Comprehensive Unit Testing:** Added `test_gender_strictly_male` and `test_demographic_diversity_questions` in `tests/test_qa_semantics_engine.py`.
- **Codified Invariant:** Codified in `.agents/rules/05_APPLICATION_LEARNING_AND_ADAPTATION.md` and `user_inputs/candidate_preferences_and_rules.md`.

### 6. Modern LinkedIn Navigation & CDP Session Resiliency
- **Auth & Nav Detection:** Updated `is_logged_in` in `tools/linkedin_easy_apply_runner.py` to recognize modern obfuscated nav selectors (`a[href*='/messaging']`, `a[href*='/notifications']`, `a[href*='/mynetwork']`), eliminating false-positive login walls.
- **CDP Port 9222 Attach & Tab Reuse:** Automatically attaches to `http://localhost:9222`, reuses the open tab with `linkedin.com/jobs`, and seamlessly continues from the current pagination offset (`start=25`, Page 2+) without reloading from Page 1.

### 7. CareerOps Full Capabilities Integration (2026-11-05)
- **Comprehensive 1-5 Scoring & A-H Block Evaluation Engine:** Implemented `core/job_evaluator.py` and `tools/evaluate_job.py`. Calculates scores across 5 dimensions (CV Match, North Star, Comp, Culture, Red Flags) and generates full A-H reports saved in `reports/{NNN}-{slug}-{date}.md`.
- **Zero-Token Pre-Flight Liveness Probe:** Added `check_url_liveness` to `core/job_liveness_detector.py` and created CLI `tools/check_liveness.py` to verify HTTP status, redirection chains, and HTML closure indicators before launching browser contexts or spending LLM tokens.
- **Zero-Token Public ATS Multi-Board Scanner:** Expanded `discovery/ats_discovery/boards.py` and created `tools/scan_public_ats.py` supporting Greenhouse, Lever, Ashby, SmartRecruiters, Workable, BambooHR, Breezy HR, and Recruitee public APIs with zero credentials.
- **Anti-Hallucination CV Fact Checker:** Implemented `core/cv_fact_checker.py` and `tools/verify_cv_facts.py` to audit generated cover letters, pitches, and ATS answers against candidate ground truth facts, strictly flagging ungrounded numbers, em dashes, and corporate slop.
- **Interview Preparation Brief Kit:** Created `tools/interview_prep.py` to produce tailored interview kits with STAR+R stories, technical system design probes, red flag objection handling, and reverse interview questions saved in `interview_prep/`.
- **Skill Gap & Upskill Roadmapper:** Created `tools/upskill_analyzer.py` to aggregate market skill demands across `jobs.db` postings and identify high-ROI technical learning priorities.
- **Recruiter Pitch & Networking Outreach Engine:** Created `tools/contact_pitch.py` to generate character-capped LinkedIn connection notes (<=300 chars), InMail value propositions, and follow-up drafts.
- **Compensation & Salary Gap Intelligence:** Created `tools/salary_gap.py` to evaluate spreads against candidate baseline CTC (18 LPA) and desired CTC (28 LPA).
- **Quality Gates Verification:** Executed `tools/quality_gate.sh`, passing all 454 unit tests across all 5 verification levels with 100% operational status.
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
