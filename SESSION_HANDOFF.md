# AI Job Search: Session Handoff Document
**Last Updated:** 2026-10-03 19:11:00 IST
**Active Git Branch / Commit:** `master` @ `7d017b4`
**Model Context Status:** Ready for New Session (Clean Context Handoff)

---

## 1. Executive Summary & Session Accomplishments

### 1. Trinity Life Sciences Consultant Application (`JR100166`)
- **Parsed & Evaluated:** Extracted JD via Jina Reader. Excellent fit with candidate's Ex-ZS Associates healthcare commercial analytics, PySpark, and statistical modeling experience.
- **Tailored Assets & Tracker Sync:**
  - Generated humanized cover letter: `cover_letters/cover_trinity_life_sciences_consultant.md`.
  - Updated `job_search_tracker.csv` and executed `python tools/sync_tracker.py` (77 entries synced to `jobs.db`).
- **Autopilot Application Execution (Workday Portal):**
  - Autonomously registered candidate account (candidate email from `.env`) and uploaded master CV.
  - Completed all form fields: personal details (Noida address, phone), multi-card experience entries (Rush by Kira, ZS Associates, TresVista), and education (University of Delhi).
  - Advanced application all the way to the final pre-submission **Review** step.
  - **Browser State:** Left Chromium browser persistently open on screen per user directive.

### 2. Database Consolidation (`jobs.db`)
- Consolidated all research and company catalogs into local `jobs.db`:
  - `companies_mdm`: 590 records from master MDM catalog.
  - `analyst_job_tracker_excel`: 245 records from Excel tracker.
  - `gcc_raw`: 97 India GCC R&D hub entries.
  - `network_contacts`: 119 professional contact records.
  - `v_job_research_and_tracking`: Unified SQL view joining research intelligence with live tracking.

### 3. Security Policy & Complete Git Untracking of Data Files
- **Strict User Policy Enforced:** All company, job, and research data files are strictly excluded from git tracking.
- **Removed from Git Tracking (Kept on Local Filesystem):**
  - `Analyst job tracker.xlsx` & `*.xlsx`
  - `job_discovery/` (`master_companies_mdm.csv`, `master_companies_mdm.json`, etc.)
  - `company_research/` (`researched_opportunities.csv`, `researched_opportunities.md`, etc.)
  - `seeds/` (`all-verified.json`, `gh_companies.json`, `lever_companies.json`, etc.)
- **Updated `.gitignore`:** Added explicit rules covering `*.xlsx`, `job_discovery/`, `company_research/`, and `seeds/`.
- Committed and pushed commit `7d017b4` (`security: remove company, job, and research data files from git index and update .gitignore`).

---

## 2. Core Architecture & Single Sources of Truth
- **Guidelines & Candidate Profile:** [`AGENTS.md`](file:///Users/ashish/git/ai-job-search/AGENTS.md) (Unified single source of truth)
- **Token Lean Optimization Registry:** [`feedback.md`](file:///Users/ashish/git/ai-job-search/feedback.md)
- **Master Resume:** Dynamically resolved from [`cv/Ankit_Resume_v4.pdf`](file:///Users/ashish/git/ai-job-search/cv/Ankit_Resume_v4.pdf)
- **Local Database (Local Only):** `jobs.db` & `job_search_tracker.csv` (`tools/sync_tracker.py`)
- **Local Credentials & PII (Local Only):** `~/.config/job-agent/client_secret.json` & `~/.config/job-agent/profile.md`
- **Universal CLI Runner:** `python tools/apply.py --url "<url>" --role-name "<slug>" --mode review`

---

## 3. Strict Operating Directives (Active)
1. **NEVER Close the Browser (Zero-Tolerance):** Under NO circumstances must any browser window ever be closed automatically. Even on "stop", "abort", or script completion/errors, ONLY terminate the automation task and leave the browser permanently open on screen.
2. **Strict Data Privacy & Git Untracking Rule:** NEVER commit company research, job seed lists, Excel trackers, or candidate PII to git. All company and research data files must reside strictly on the local filesystem and be ignored by `.gitignore`.
3. **Single Persistent Browser Instance:** Bind Playwright automation scripts and Chrome DevTools MCP tools to a single persistent Chromium process (`--remote-debugging-port=9222`) to prevent dual browser window launches.
4. **Strict Zero-Cost OpenRouter Directive:** Strictly use free models (`:free` suffix). Never call paid models or incur financial cost. If free models fail, nudge the user.
5. **Git Commit & CI Verification Protocol (OpenRouter Free Tier Only):** Whenever committing to GitHub, exclusively use OpenRouter free tier models (`:free`). Always verify GitHub Actions CI status after pushing. If CI fails, diagnose and fix the failing run using OpenRouter free models and push again until CI passes.
6. **No Em Dashes (`—`):** Never use em dashes. Use standard hyphens (`-`), commas, colons, or parentheses.

---

## 4. Instructions for Next Session / Next Agent
1. Verify working directory with `git status`.
2. Read [`AGENTS.md`](file:///Users/ashish/git/ai-job-search/AGENTS.md), [`SESSION_HANDOFF.md`](file:///Users/ashish/git/ai-job-search/SESSION_HANDOFF.md), and [`feedback.md`](file:///Users/ashish/git/ai-job-search/feedback.md).
3. Resume directly on new job application URLs using `python tools/apply.py --url "<URL>" --role-name "<SLUG>" --mode review`.
