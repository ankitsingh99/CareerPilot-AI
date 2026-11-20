# AI Job Search: Session Handoff Document
**Last Updated:** 2026-11-20 14:35:00 IST  
**Active Git Branch / Commit:** `master` (Universal Automation Framework v1.2.0)  
**Repository Visibility:** Public (https://github.com/ankitsingh99/ai-job-search)  
**Model Context Status:** Optimal (Clean Context Handoff - Ready for New Session)  

---

## 1. Executive Summary & Current Accomplishments

### 0. Cost-Intelligent Model Architecture & Adaptive Task Promotion (2026-11-20)
- **Token-Lean Two-Tier Routing (`core/model_router.py`):**
  - Evolved model philosophy: use cheaper/free models (Local Ollama, fast OpenRouter free tier) for low-reasoning chore tasks (regex extraction, text trimming, deduplication, simple screening).
  - Reserve high-reasoning **Gemini** for complex tasks (nuanced cover letter drafting, executive outreach pitches, complex ATS questionnaires, debugging).
- **FreeLLMAPI Best Patterns Integration:**
  - **Tool-Call / JSON Output Rescue:** Intercepts markdown fences and conversational chatter, repairing malformed text into valid JSON schemas.
  - **429 / 5xx Sliding-Window Cooldown Ledger:** Automatically cools down throttled endpoints (60s) and fails over seamlessly without crashing.
  - **Real-Time Token Conservation:** Tracks tokens saved by offloading chore tasks to local/free models.
- **User Correction & Mistake Ledger (`core/user_corrections_engine.py`):**
  - Persistent JSON ledger in `user_inputs/user_corrections_log.json` tracking where the user has halted, corrected, or guided the agent.
  - **Adaptive Escalation:** When user corrections or mistakes in a task category rise (critical $\ge 1$ or recurrence $\ge 2$), the router dynamically escalates and promotes that entire task category to Gemini.
  - Active Promoted Tasks: `phone_formatting`, `notice_period_formatting`, `compensation_input`, `experience_duration`, `company_outreach_emphasis`, and `workday_auth_loop`.
- **Real-Time Analytics CLI (`tools/model_analytics.py`):**
  - Inspect live routing metrics, model usage, token conservation, active cooldowns, and promoted categories via `python tools/model_analytics.py --status`.

### 1. LinkedIn Easy Apply & Outbound Outreach Assets (2026-11-19)
1. **Digits-Only Phone Input Normalization:**
   - Fixed LinkedIn Easy Apply modal getting stuck on formatted phone strings (`+91-XXXXX`).
   - Wired `CANDIDATE_RAW_PHONE` (digits only) into `core/qa_semantics_engine.py` and `tools/linkedin_easy_apply_runner.py` to auto-clear and refill raw 10 digits whenever digits-only validation is required.
2. **Outbound Pitches Drafted & Verified:**
   - **Amgen (Senior Associate, IC Contest Reporting, Hyderabad):** Outreach DM to Utkarsh Verma (Manager at Amgen | ex ZS), heavily emphasizing 3+ years at ZS Associates in data management, ingestion, and QC feeding quota and IC inputs ([documents/Amgen_Utkarsh_Verma_IC_Contest_Reporting_Outreach.md](file:///Users/ashish/git/ai-job-search/documents/Amgen_Utkarsh_Verma_IC_Contest_Reporting_Outreach.md)).
   - **Crescendo Group (Data Solutions Analyst, Gurugram):** Outbound email to Pooja Prasad highlighting ZS Associates consulting, Snowflake curation, 15+ Airflow DAGs, alongside Rush by Kira tracking and TresVista financial modeling ([documents/Crescendo_Data_Solutions_Analyst_Gurugram_Outreach.md](file:///Users/ashish/git/ai-job-search/documents/Crescendo_Data_Solutions_Analyst_Gurugram_Outreach.md)).
   - **Genpact (Business Systems Analyst / Data Analyst):** Outbound email to Pinki Chhetri ([documents/Genpact_Business_Systems_Analyst_Outreach.md](file:///Users/ashish/git/ai-job-search/documents/Genpact_Business_Systems_Analyst_Outreach.md)).
   - **Apidel Technologies (Data Engineer - Pharma Domain):** Outbound email to Piyusha R ([documents/Apidel_Technologies_Data_Engineer_Pharma_Outreach.md](file:///Users/ashish/git/ai-job-search/documents/Apidel_Technologies_Data_Engineer_Pharma_Outreach.md)).

### 2. GitHub Maintenance & Dependency Hygiene
1. **GitHub Issue #1 Resolved:** Audited upstream commits from `MadsLorentzen/ai-job-search`, populated `.github/upstream-wontport.txt`, enhanced `.github/workflows/upstream-watch.yml`, and closed Issue #1.
2. **GitHub PR #2 Merged:** Bumped `zod` to v4.6.7 across 4 CLI directories and fast-forwarded `master`.
3. **Quality Gates 100% Passed:** Level 1 (PII audit), Level 2 (SSRF guard), Level 3 (linter integrity), Level 4 (Python 3.15 lazy imports), Level 5 (495 passed unit tests in pytest).

---

## 2. Key Architecture & Single Sources of Truth

- **Master Blueprint:** `MASTER_TEMPLATE.md` (universal person-agnostic instructions)
- **Candidate Profile & Rules:** `AGENTS.md` & `user_inputs/candidate_preferences_and_rules.md`
- **Secrets & Credentials (Local Only):** `.env` & `~/.config/job-agent/.candidate_secrets.json` (gitignored)
- **Universal ATS Automation Engine:** `tools/ats_runner.py` & `tools/linkedin_easy_apply_runner.py` (headed Playwright with persistent browser)
- **Deterministic Q&A Semantics:** `core/qa_semantics_engine.py`
- **Application Tracker & Local DB:** `user_inputs/job_search_tracker.csv` & `jobs.db` via `tools/sync_tracker.py` (448 total synchronized applications)
- **Zero-Cost LLM Engine:** Strictly free OpenRouter models (`google/gemma-4-31b-it:free`, `cohere/north-mini-code:free`)

---

## 3. Active Candidate Ground Truth

- **Name:** Ankit Kumar Singh
- **Target Roles:** Data Analyst, Analytics Consultant, Business Analyst, Data Engineer, Data Governance, Consultant
- **Location:** India (Noida / Delhi NCR / Pan-India). Residence: `Noida, Uttar Pradesh, India`.
- **Education:** University of Delhi (BA Hons. Business Economics), 07/2017 - 07/2020. **Graduation Year:** Strictly `2020`.
- **Total Experience:** 5 Years / 60 Months (Strictly `5` years or `60` months when integer requested)
- **Database & SQL Experience:** Strictly `4` Years (DB, database, datalake, SQL, PostgreSQL, any database tool)
- **Current Compensation:** 18 LPA (`1800000` INR / `150000` Monthly)
- **Expected Compensation:** 28 LPA (`2800000` INR / `233333` Monthly)
- **Notice Period:** Strictly `0` (Immediate joiner)
- **Earliest / Future Start Date:** Next business day (`MM/DD/YYYY` or `YYYY-MM-DD`)
- **Daily Easy Apply Safety Ceiling:** 40 applications per rolling 24h.

---

## 4. Operational Directives & Invariants

1. **NEVER Close the Browser Window:** When automation finishes or pauses, leave the browser open and interactive on display.
2. **Token-Lean Architecture:** Never create throwaway or single-job scripts (`apply_xyz.py`). All automation must use parameterized reusable engines.
3. **Zero Em Dashes:** Never use em dashes (Unicode U+2014) in prose or code. Use standard hyphens (`-`), commas, or parentheses.
4. **Strict Resume and Cover Letter Separation:** Under NO circumstances should a resume be uploaded into a cover letter field, or vice versa.
5. **Zero-Cost OpenRouter Models:** Use only models ending with `:free`. Never incur billable spend. Do not use OpenRouter until explicitly asked for.
6. **Gemini-Exclusive Writing:** Use active Gemini exclusively for drafting and humanizing cover letters.

---

## 5. Next Steps for Upcoming Session

1. **Monitor Inbound Responses:** Track recruiter replies from Yatin Saini (Evalueserve) and Kanchan (Spectral Consultants).
2. **LinkedIn Easy Apply Batch Execution:** If initiating the next daily batch of Easy Apply jobs in India (Non-Remote):
   ```bash
   PYTHONUNBUFFERED=1 .venv/bin/python tools/linkedin_easy_apply_runner.py \
     --keywords "Data Analyst" "Analytics Consultant" "Business Analyst" \
     --location "India" \
     --time-filter "r86400" \
     --sort DD \
     --no-remote \
     --experience-level "3,4" \
     --max-yoe 8 \
     --target 40
   ```
3. **Custom Portal Applications:** Run candidate portal submissions via `tools/ats_runner.py` with verified credentials stored in `user_inputs/candidate_accounts.json`.
