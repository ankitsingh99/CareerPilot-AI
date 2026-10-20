---
framework_version: 1.2.0
template_type: universal_master_specification
---

# Universal Master Instructions & Profile Template

This is the central master blueprint for the AI Job Search automation framework. It contains all operational instructions, behavioral directives, application workflows, and a candidate-agnostic profile template.

For any person using this tool:
1. **Never commit personal identifiable information (PII) to git.**
2. Configure candidate credentials, contact info, and compensation in the local, gitignored `.env` file (see `.env.example`).
3. Run `python tools/generate_workspace_from_master.py` to instantiate or rehydrate your localized workspace files (`AGENTS.md`, `01-candidate-profile.md`, `candidate_preferences_and_rules.md`, and `application_settings.py`).

---

## Part 1: Candidate Profile Specification Template

All fields below are loaded from `.env` or structured user inputs. When generating individual workspace files, variables formatted as `{{VARIABLE_NAME}}` are automatically populated.

### 1.1 Identity & Contact
- **Full Name:** `{{CANDIDATE_NAME}}`
- **First Name:** `{{CANDIDATE_FIRST_NAME}}`
- **Last Name:** `{{CANDIDATE_LAST_NAME}}`
- **Email:** `{{CANDIDATE_EMAIL}}`
- **Phone:** `{{CANDIDATE_PHONE}}`
- **Raw Phone (digits only):** `{{CANDIDATE_RAW_PHONE}}`
- **Country Code:** `{{CANDIDATE_PHONE_COUNTRY_CODE}}`
- **Date of Birth:** `{{CANDIDATE_DOB_FORMATTED}}` (`{{CANDIDATE_DOB}}`)
- **Street Address:** `{{CANDIDATE_ADDRESS}}`
- **City:** `{{CANDIDATE_CITY}}`
- **State / Province:** `{{CANDIDATE_STATE}}`
- **Country:** `{{CANDIDATE_COUNTRY}}`
- **Postal / Zip Code:** `{{CANDIDATE_PINCODE}}`
- **Gender:** `{{CANDIDATE_GENDER}}`
- **Citizenship:** `{{CANDIDATE_CITIZENSHIP}}`
- **Work Authorization:** Authorized to work in `{{CANDIDATE_COUNTRY}}`
- **LinkedIn Profile:** `{{CANDIDATE_LINKEDIN_URL}}`
- **GitHub / Portfolio:** `{{CANDIDATE_PORTFOLIO_URL}}`
- **Current Headline:** `{{CANDIDATE_HEADLINE}}`

### 1.2 Professional Overview & Compensation
- **Status:** Actively exploring opportunities (Immediate availability)
- **Notice Period:** `{{CANDIDATE_NOTICE_PERIOD}}`
- **Total Experience:** `{{CANDIDATE_TOTAL_YOE}}` years
- **Current CTC / Compensation:** `{{CANDIDATE_CURRENT_CTC_LPA}}` LPA (`{{CANDIDATE_CURRENT_CTC_INR}}`)
- **Expected CTC / Salary Expectation:** `{{CANDIDATE_EXPECTED_CTC_LPA}}` LPA (`{{CANDIDATE_EXPECTED_CTC_INR}}`)
- **Master Resume Path:** `{{CANDIDATE_MASTER_RESUME}}`

### 1.3 Education Template
- **Higher Education / Degree:** `{{CANDIDATE_DEGREE}}`
  - **Institution:** `{{CANDIDATE_UNIVERSITY}}`
  - **Major / Field of Study:** `{{CANDIDATE_MAJOR}}`
  - **Duration:** `{{CANDIDATE_COLLEGE_START}}` - `{{CANDIDATE_COLLEGE_END}}`
  - **Score / Grade:** `{{CANDIDATE_COLLEGE_GRADE}}`
  - **Key Topics:** `{{CANDIDATE_EDUCATION_TOPICS}}`
- **Senior Secondary School (Class 12th):** `{{CANDIDATE_SENIOR_SECONDARY_SCHOOL}}`
  - **Grade / Score:** `{{CANDIDATE_SENIOR_SECONDARY_GRADE}}`
- **Secondary School (Class 10th):** `{{CANDIDATE_SECONDARY_SCHOOL}}`
  - **Grade / Score:** `{{CANDIDATE_SECONDARY_GRADE}}`

### 1.4 Professional Experience Template
*(Populated from candidate experience records in `.env` or structured data)*
`{{CANDIDATE_EXPERIENCE_ENTRIES}}`

### 1.5 Technical Skills Template
- **Primary Languages & Query Engines:** `{{CANDIDATE_PRIMARY_SKILLS}}`
- **ETL / Frameworks & Tools:** `{{CANDIDATE_TOOLS_AND_FRAMEWORKS}}`
- **Secondary / Data Science & ML:** `{{CANDIDATE_SECONDARY_SKILLS}}`
- **Domain Specializations:** `{{CANDIDATE_DOMAIN_SPECIALIZATIONS}}`
- **Explicit Technology Exclusions (DO NOT APPLY):** `{{CANDIDATE_EXCLUDED_TECHS}}`

### 1.6 Target Roles & Location Preferences
- **Target Roles:** `{{CANDIDATE_TARGET_ROLES}}`
- **Location Preferences:**
  1. 100% Remote
  2. Primary Metro / Regional Onsite / Hybrid: `{{CANDIDATE_CITY}}`
  3. Relocation: Willing to relocate (Domestic & International)
- **Target Sectors:** Open across high-growth tech, enterprise consulting, life sciences, e-commerce, and fintech.

---

## Part 2: Universal Formatting, Rules & Directives

The following behavioral and operational rules apply across all execution engines, scripts, and model subagents.

### 2.1 Formatting & Content Guardrails
- **NEVER use em dashes (`—`).** Always use standard hyphens (`-`), commas, colons, or parentheses.
- **Zero AI Clichés & Slop:** Never use banned corporate jargon (`spearheaded`, `leveraged`, `delve`, `synergy`, `testament`, `fostered`, `pivotal`, `game-changer`, `thrilled to apply`).
- **Humanized Writing & Asymmetry:** Keep high sentence-length variance (standard deviation > 4.5 words). Favor concise, punchy micro-narratives over robotic paragraph monotony.
- **Humanizer Pre-Filter:** ALWAYS run `tools/dl_humanizer_prefilter.py` on factual inputs before generating cover letters or application responses.

### 2.2 Model & Cost Directives
- **STRICT ZERO-COST OPENROUTER DIRECTIVE (NO PAID CALLS EVER):**
  - Zero financial budget. ONLY open-source models ending strictly with `:free` (e.g. `google/gemma-2-9b-it:free`, `nvidia/nemotron-70b:free`, `qwen/qwen-2.5-7b:free`) are permitted.
  - NEVER invoke, configure, or fall back to any paid tier or billable endpoint.
  - If free endpoints are busy, alert the user rather than incurring cost.

### 2.3 Browser Automation Hierarchy
1. **Primary Automation:** Local headed Playwright runner (`tools/ats_runner.py`).
2. **Secondary Fallback:** Chrome DevTools MCP server (`navigate_page`, `click`, `type_text`, `fill_form`, `evaluate_script`).
3. **NEVER Close the Browser Directive (ZERO-TOLERANCE):**
   - Under NO circumstances must the browser window ever be closed by the automation.
   - When automation completes, errors out, or is paused, stop the script but leave the browser window permanently open and interactive on the display for the user.
4. **Attention Alert Notification:**
   - Trigger a macOS system notification and chime (`Glass.aiff`) whenever a CAPTCHA, OTP, 2FA, or manual verification is required:
     `afplay /System/Library/Sounds/Glass.aiff && osascript -e 'display notification "<Prompt>" with title "Attention Needed"'`

### 2.4 File Upload & Application Rules
- **Direct File Upload Preference:** ALWAYS attach and upload the master CV PDF and tailored Cover Letter directly via the file chooser input.
- **Manual Text Entry Forbidden if Upload Exists:** NEVER paste raw resume text into manual textareas unless the portal has no file upload capability.
- **Dynamic CV Check:** Dynamically resolve the latest master resume PDF by checking `cv/` and `user_inputs/cv/` or referencing `CANDIDATE_MASTER_RESUME` from `.env`.
- **Autofill with Resume First:** If the portal offers "Autofill with Resume", always click it and upload the CV first to auto-populate fields.
- **Pre-Submission Review:** Always pause at the final review screen and generate an audit markdown report before submission.

### 2.5 Architecture & Optimization Directives
- **Python 3.15+ Native Lazy Imports:** The runtime operates on Python 3.15+ with `PYTHON_LAZY_IMPORTS=all` (PEP 690 / PEP 810) enabled. All imports (including heavy libraries like Playwright, NumPy, SQLite, and docx) are lazily deferred on-demand, minimizing CLI startup latency and conserving execution memory.
- **Single Universal Automation Engine:** NEVER write one-off python application scripts per job. Always use parameterized `tools/ats_runner.py`.
- **Zero Git Commits for Individual Job Applications:** Never commit or push to GitHub after applying to an individual role. Commits are reserved for framework upgrades.
- **Autonomous Tracker Recording:** Automatically record applied jobs in `user_inputs/job_search_tracker.csv` and replicate to SQLite `jobs.db` via `tools/sync_tracker.py`.
- **Continuous Learning & Adaptation:** Automatically capture novel ATS questions and candidate answers in `user_inputs/application_qa_knowledge_base.json` and reuse them.

---

## Part 3: End-to-End Application Workflow

Whenever a job URL is provided, follow this standard sequence:

1. **Direct Link Ingestion & Parsing:** Use Jina Reader (`curl -s "https://r.jina.ai/<URL>"`) to retrieve clean markdown job descriptions without HTML bloat.
2. **Company Intelligence Gathering:** Use `agent-reach-research` to gather tech stack and cultural insights.
3. **Fit Evaluation:** Score role requirements against the candidate profile in `.env`.
4. **Document Preparation:**
   - Resolve master CV PDF.
   - Run `tools/dl_humanizer_prefilter.py` on target facts.
   - Generate tailored, humanized cover letter (DOCX / Markdown).
5. **Form Automation:**
   - Run `tools/ats_runner.py --url "<URL>" --mode apply`.
   - Populate candidate details from `.env`.
   - Upload documents.
   - Generate pre-submission audit in `documents/applications/<company>_<role>/pre_submit_audit.md`.
6. **Sync Tracking:**
   - Update `user_inputs/job_search_tracker.csv`.
   - Run `python tools/sync_tracker.py` to mirror to `jobs.db`.

---

## Part 4: Standard ATS Screening QA Knowledge Base Template

Standard answers to common screening questions:

| Question Category | Screening Prompt Regex / Keyword | Standard Answer |
| :--- | :--- | :--- |
| **Work Authorization** | `authorized to work in (India\|US\|UK\|country)` | `Yes` |
| **Visa Sponsorship** | `require sponsorship (now or in future)` | `No` (for candidate's authorized countries) |
| **Notice Period** | `notice period / availability to start` | `Immediate Joiner (0 days notice)` / `Immediate` |
| **Relocation** | `willing to relocate / open to relocation` | `Yes` |
| **Hybrid / Onsite** | `comfortable working in hybrid / onsite model` | `Yes` |
| **Travel** | `willing to travel for business` | `Yes (up to 25%)` |
| **Flexible Shifts / Timezones** | `comfortable with global / flexible hours` | `Yes` |
| **Referral Source** | `how did you hear about us / source` | `Career Website` / `Company Website` |
| **Talent Community** | `join talent community / receive alerts` | `Yes` (Always opt-in) |
| **Data Consent / GDPR** | `consent to data processing / privacy policy` | `Yes` / `Agree` |
| **Personal Relationship** | `know anyone at the company / relationship with employee` | `No` |
| **Criminal Record / Felony** | `convicted of a crime / felony record` | `No` |
| **Non-Compete** | `subject to non-compete / non-solicit agreement` | `No` |

---

## Part 5: Workspace Generation & Rehydration

To generate all workspace files for a user from this master template:
```bash
# 1. Copy the environment template and fill in your details
cp .env.example .env

# 2. Generate or update workspace files
python tools/generate_workspace_from_master.py

# 3. Verify no un-templated PII leaks exist in tracked files
python tools/generate_workspace_from_master.py --audit-pii
```
