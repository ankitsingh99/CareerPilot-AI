# AI Job Search: Session Handoff Document
**Last Updated:** 2026-11-11 11:32:00 IST  
**Active Git Branch / Commit:** `master` @ `origin/master` (Universal Automation Framework v1.2.0)  
**Repository Visibility:** Public ([https://github.com/ankitsingh99/ai-job-search](https://github.com/ankitsingh99/ai-job-search))  
**Model Context Status:** Optimal (Clean Context Handoff - Ready for New Session)  

---

## 1. Executive Summary & Current Accomplishments

### 0. Token-Lean Routing, Outreach Engine & Cost Hardening (2026-11-11)
- **Tiered Free Model Routing & On-Demand Gate:** Updated `intelligence/llm_clients/openrouter.py` with `CHORE_FREE_MODELS` vs `HEAVY_FREE_MODELS` routing (`--tier chore|heavy`), local Ollama offline fallback (`ask_local_ollama_if_online`), explicit `OPENROUTER_ON_DEMAND_ENABLED` (`--allow-openrouter`) gate, and extracted `extract_cover_letter_text()` out of generic `ask()`.
- **Billable Endpoint Hardening:** Disabled `api.deepseek.com` fallback in `intelligence/llm_clients/deepseek.py`, replaced raw `curl` in `tools/check_career_sites.py` with deterministic domain matching + gated `:free` client, and wired `--allow-openrouter` across `automation/browser.py`, `tools/linkedin_easy_apply_runner.py`, `tools/dl_humanizer_prefilter.py`, and `parsers/linter.py`.
- **Local Job Filtering & QA Deduplication:** Wired `score_job_locally` and `OnDeviceParser.evaluate_seniority_and_relevance` into `tools/research_jobs.py` (removing unreachable blocks), and unified `ask_openrouter_free` into `core/qa_semantics_engine.py`.
- **JD-Matched Outreach Engine & Greenhouse Fixes:** Added reusable `tools/contact_pitch.py`, `.agents/skills/linkedin-and-email-outreach/`, `tests/test_contact_pitch.py`, `gh_jid` / iframe handling in `core/ats_classifier.py` and `automation/browser.py`, and direct CSV append sync in `core/tracker.py`.

### 1. Integration of Best-of-Breed LinkedIn Open-Source Capabilities
Integrated verified patterns from `nicolomantini/LinkedIn-Easy-Apply-Bot` and `GodsScion/Auto_job_applier_linkedIn` directly into universal framework modules (`tools/linkedin_easy_apply_runner.py` and `core/qa_semantics_engine.py`):
1. **Seniority Experience Ceiling Guard:** Added `extract_min_yoe_requirement()` and CLI option `--max-yoe-ceiling 8` to automatically skip senior postings (e.g. 10+ YOE) before applying, preventing disqualification.
2. **Pre-Click Company & Title Blacklisting:** Added active company and title blacklist filters (`--company-blacklist`, `--title-blacklist`) with automatic skipping of excluded titles (Java, DevOps, Intern, Sales).
3. **LinkedIn Experience Level URL Parameters:** Integrated native parameter `&f_E=3,4` (Associate, Mid-Senior) to target relevant seniority tiers.
4. **Unit-Aware CTC & Notice Period Normalization:**
   - "Per month" / "monthly": Expected CTC returns `233333` (`2800000 / 12`), Current CTC returns `150000` (`1800000 / 12`).
   - "In lakhs" / "lpa": Expected returns `28`, Current returns `18`.
   - Notice period in months, weeks, or days returns strictly `0` (immediate joiner).
5. **Automatic "Follow Company" Opt-Out:** On Review and Submit screens, automatically unchecks `input[type='checkbox'][id*='follow-company']` to protect candidate feed.
6. **Two-Pass Deadlock Detection:** Detects identical unresolved signatures between step $N$ and $N+1$, preventing timeout loops.
7. **Structured Failed Application Logging:** Appends skipped or blocked applications to `user_inputs/failed_applications.csv` for transparent auditing.

### 2. Candidate Education Graduation Year Codification (Graduation Year: 2020)
- Explicit user confirmation: College completion year is strictly `2020` (University of Delhi, 07/2017 to 07/2020).
- Updated `core/qa_semantics_engine.py` to deterministically return `"2020"` for all variations of graduation year, completion year, passing year, and passout year.
- Added comprehensive unit tests in `tests/test_qa_semantics_engine.py`.
- Verified 100% pass across all 456 unit tests (`pytest tests/`).

### 3. Modern LinkedIn SDUI Form Handling & Interactive Prompts
- Added group resolution for modern LinkedIn SDUI radio buttons lacking `<fieldset>` containers.
- Implemented `ask_user_for_answer()`: Triggers macOS chime (`Glass.aiff`), push notification, and native dialog if an unknown question requires candidate input, automatically caching the response into `user_inputs/application_qa_knowledge_base.json`.

---

## 2. Key Architecture & Single Sources of Truth

- **Master Blueprint:** `MASTER_TEMPLATE.md` (universal person-agnostic instructions)
- **Candidate Profile & Rules:** `AGENTS.md` & `user_inputs/candidate_preferences_and_rules.md`
- **Secrets & Credentials (Local Only):** `.env` & `~/.config/job-agent/.candidate_secrets.json` (gitignored)
- **Universal ATS Automation Engine:** `tools/ats_runner.py` & `tools/linkedin_easy_apply_runner.py` (headed Playwright with persistent browser)
- **Deterministic Q&A Semantics:** `core/qa_semantics_engine.py`
- **Application Tracker & Local DB:** `user_inputs/job_search_tracker.csv` & `jobs.db` via `tools/sync_tracker.py`
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
- **Daily Easy Apply Submissions Completed Today:** 33 applications (LinkedIn account-level daily limit reached)
- **Daily Limit Guard:** Automated detector for `"You reached today’s Easy Apply limit"` modal, clicks 'Got it', alerts user, and terminates cleanly.

---

## 4. Operational Directives & Invariants

1. **NEVER Close the Browser Window:** When automation finishes or pauses, leave the browser open and interactive on display.
2. **Token-Lean Architecture:** Never create throwaway or single-job scripts (`apply_xyz.py`). All automation must use parameterized reusable engines.
3. **Zero Em Dashes:** Never use em dashes (`—`) in prose or code. Use standard hyphens (`-`), commas, or parentheses.
4. **Zero-Cost OpenRouter Models:** Use only models ending with `:free`. Never incur billable spend.
5. **Daily Application Limit:** Enforce strict safety ceiling of 40 Easy Apply submissions per rolling 24 hours.

---

## 5. Ready-to-Run Command for Next Clean Session

To launch the autonomous LinkedIn Easy Apply run in the new session:

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
