# Workspace State: AI Job Search & Application Pipeline

## 1. Active Task Goal
Execute end-to-end job application workflow across target roles with zero Java constraints, generating tailored cover letters, autofilling ATS portals, auditing pre-submission states, and synchronizing tracking in `job_search_tracker.csv` and `jobs.db`.

---

## 2. Current Architecture & Operational Directives
- **Runtime:** CPython 3.15.0rc3 with native interpreter lazy imports (`PYTHON_LAZY_IMPORTS=all` via PEP 690 / PEP 810).
- **Master Blueprint:** `MASTER_TEMPLATE.md` is the single candidate-agnostic master template.
- **Workspace Hydration & Audit:** `python tools/generate_workspace_from_master.py` instantiates files; `--audit-pii` verifies zero PII leaks.
- **Data Sovereignty:** All personal candidate details reside in local `.env`, `cv/`, and `~/.config/job-agent/client_secret.json` (gitignored). Zero PII in git.
- **Zero-Cost LLM Execution:** Strictly open-source models ending with `:free` via OpenRouter.
- **Formatting Constraints:** Hard constraint: zero em dashes (`—`). Standard hyphens, commas, or parentheses only.
- **Browser Automation:** Headed Playwright (`tools/ats_runner.py`). Never close the browser automatically.

---

## 3. Current In-Flight Pipeline

| Portal / Company | Role | Req ID | Current Step / Status | Next Action |
| :--- | :--- | :--- | :--- | :--- |
| **LSEG** | Data Strategy Manager | `R0123404` | **Failed** (Email link required) | User marked failed; retry later. |
| **PwC Gurugram** | Senior Associate - Data Governance | `563244WD-5` | **Step 5: Voluntary Disclosures** | Fill demographics, proceed to Review, audit, submit. |
| **PwC Noida** | Senior Associate | `525571WD-2` | **Queued** (Apply URL loaded) | Autofill with resume, tailor cover letter, submit. |
| **NatWest Group** | Data & Analytics Analyst | `R-00285541-1` | **Queued** (Sign In loaded) | Create/login account, autofill resume, submit. |
| **EXL Service** | Analytics Consultant | `14353` | **Queued** (Oracle HCM) | Fill form, tailor cover letter, submit. |
| **Hilti** | Associate Reporting Analyst | `17942-en` | **Queued** (Careers Page) | Autofill resume, submit. |
| **WSP** | Analyst - Data | `95413` | **Queued** (Oracle HCM) | Fill form, submit. |
| **BOLD / LiveCareer** | Senior Software Engineer - Data Science | `7079852` | **Awaiting Email Code** | Awaiting verification code. |
| **McKinsey & Co** | Knowledge Analyst - Mining | `108484` | **Queued** (Avature) | Complete registration & submission. |

---

## 4. Key File References
- **Master Blueprint:** [`MASTER_TEMPLATE.md`](MASTER_TEMPLATE.md)
- **Master Resume:** Dynamically loaded from `.env` (`CANDIDATE_MASTER_RESUME`) or latest `cv/*.pdf`
- **Candidate Profile & Rules:** [`AGENTS.md`](AGENTS.md)
- **Application Tracking:** [`job_search_tracker.csv`](job_search_tracker.csv) and [`jobs.db`](jobs.db)
- **Universal ATS Runner:** [`tools/ats_runner.py`](tools/ats_runner.py)
- **LinkedIn Easy Apply Runner:** [`tools/linkedin_easy_apply_runner.py`](tools/linkedin_easy_apply_runner.py)
- **Anti-AI Humanizer Engine:** [`parsers/turnitout_engine.py`](parsers/turnitout_engine.py)
- **Sync Tool:** [`tools/sync_tracker.py`](tools/sync_tracker.py)

---

## 5. Active Next Steps
1. **PwC Gurugram:** Complete Step 5 (Voluntary Disclosures) -> Step 6 (Review) -> Pre-submission audit -> Final Submit.
2. **PwC Noida:** Reuse active PwC Workday session to process `525571WD-2`.
3. **NatWest:** Register account using candidate credentials from `.env` and complete application.
4. **Oracle HCM Batch (EXL, WSP) & Hilti:** Complete sequential autofill and submission.
5. **Sync Tracker:** Run `python tools/sync_tracker.py` upon each completion.
