# Workspace State: AI Job Search & Application Pipeline

## 1. Active Task Goal
Execute end-to-end job application workflow across target roles with zero Java constraints, generating tailored cover letters, autofilling ATS portals, logging account credentials, auditing pre-submission states, and synchronizing tracking in `job_search_tracker.csv` and `jobs.db`.

---

## 2. Current Status & Metrics
- **Total Applications Processed:** 58
  - **Submitted & Confirmed:** 40
  - **Failed / Retries Queued:** 5 (including LSEG per user directive)
  - **Withdrawn / Skipped:** 13
- **Active ATS Session Credentials Record:** Stored in `.candidate_secrets.json` and `user_inputs/candidate_preferences_and_rules.md`

---

## 3. Current Step & Active In-Flight Pipeline

| Portal / Company | Role | Req ID | Current Step / Status | Next Action |
| :--- | :--- | :--- | :--- | :--- |
| **LSEG** | Data Strategy Manager | `R0123404` | **Failed** (Email link required) | User marked failed; retry later. |
| **PwC Gurugram** | Senior Associate - Data Governance | `563244WD-5` | **Step 5: Voluntary Disclosures** | Fill demographics, proceed to Review, audit, submit. |
| **PwC Noida** | Senior Associate | `525571WD-2` | **Queued** (Apply URL loaded) | Autofill with resume, tailor cover letter, submit. |
| **NatWest Group** | Data & Analytics Analyst | `R-00285541-1` | **Queued** (Sign In loaded) | Create/login account, autofill resume, submit. |
| **EXL Service** | Analytics Consultant | `14353` | **Queued** (Oracle HCM) | Fill form, tailor cover letter, submit. |
| **Hilti** | Associate Reporting Analyst | `17942-en` | **Queued** (Careers Page) | Autofill resume, submit. |
| **WSP** | Analyst - Data | `95413` | **Queued** (Oracle HCM) | Fill form, submit. |
| **BOLD / LiveCareer** | Senior Software Engineer - Data Science | `7079852` | **Awaiting Email Code** | Awaiting 8-char verification code. |
| **McKinsey & Co** | Knowledge Analyst - Mining | `108484` | **Queued** (Avature) | Complete registration & submission. |

---

## 4. Key File References
- **Master Resume:** Dynamically loaded from `.env` (`CANDIDATE_MASTER_RESUME`)
- **Candidate Profile & Rules:** [`GEMINI.md`](GEMINI.md), [`CLAUDE.md`](CLAUDE.md)
- **Application Tracking:** [`job_search_tracker.csv`](job_search_tracker.csv), [`jobs.db`](jobs.db)
- **Directives & Secrets:** [`.candidate_secrets.json`](.candidate_secrets.json), [`user_inputs/candidate_preferences_and_rules.md`](user_inputs/candidate_preferences_and_rules.md)
- **Sync Tool:** [`tools/db_state.py`](tools/db_state.py)

---

## 5. Active Blockers & Immediate Next Steps
1. **PwC Gurugram:** Complete Step 5 (Voluntary Disclosures) -> Step 6 (Review) -> Pre-submission audit -> Final Submit.
2. **PwC Noida:** Reuse active PwC Workday session to process `525571WD-2`.
3. **NatWest:** Register account using candidate credentials in `client_secret.json` and complete application.
4. **Oracle HCM Batch (EXL, WSP) & Hilti:** Complete sequential autofill and submission.
5. **Sync Tracker:** Run `python tools/db_state.py sync` upon each completion.
