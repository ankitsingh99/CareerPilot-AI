---
framework_version: 1.2.0
template_type: universal_master_specification
---

# CareerPilot AI - Universal Master Instructions & Profile Template

This is the central master blueprint for CareerPilot AI (Autonomous Career Agent & Application Automation Framework). It contains all operational instructions, behavioral directives, application workflows, and a candidate-agnostic profile template.

For any person using this tool:
1. **Never commit personal identifiable information (PII) to git.**
2. Configure candidate credentials, contact info, and compensation in the local, gitignored `.env` file (see `.env.example`).
3. Run `python tools/generate_workspace_from_master.py` to instantiate or rehydrate your localized workspace files (`AGENTS.md`, `01-candidate-profile.md`, `candidate_preferences_and_rules.md`, and `application_settings.py`).

---

## Part 1: Candidate Profile Specification Template

All fields below are loaded from `.env` or structured user inputs. When generating individual workspace files, variables formatted as `[NOT_SET: VARIABLE_NAME]` are automatically populated.

### 1.1 Identity & Contact
- **Full Name:** `Ankit Kumar Singh`
- **First Name:** `Ankit`
- **Last Name:** `Singh`
- **Email:** `Loaded securely from `.env` (`CANDIDATE_EMAIL`)`
- **Phone:** `Loaded securely from `.env` (`CANDIDATE_PHONE`)`
- **Raw Phone (digits only):** `Loaded securely from `.env` (`CANDIDATE_RAW_PHONE`)`
- **Country Code:** `+91`
- **Date of Birth:** `Loaded securely from `.env` (`CANDIDATE_DOB_FORMATTED`)` (`Loaded securely from `.env` (`CANDIDATE_DOB`)`)
- **Street Address:** `Loaded securely from `.env` (`CANDIDATE_ADDRESS`)`
- **City:** `Noida`
- **State / Province:** `Uttar Pradesh`
- **Country:** `India`
- **Postal / Zip Code:** `201304`
- **Gender:** `Male`
- **Citizenship:** `Indian`
- **Work Authorization:** Authorized to work in `India`
- **LinkedIn Profile:** `https://linkedin.com/in/ankit-singh99`
- **GitHub / Portfolio:** `https://github.com/ankitsingh99`
- **Current Headline:** `Business & Technology Consultant | Data Engineering & Analytics | AI Agent Development | Ex-ZS Associates`

### 1.2 Professional Overview & Compensation
- **Status:** Actively exploring opportunities (Immediate availability)
- **Notice Period:** `Immediate Joiner (0 days notice)`
- **Total Experience:** `4.8` years
- **Current CTC / Compensation / Annual Income:** `18` LPA (`1800000`)
- **Annual Income Directive:** Whenever any field asks for annual income, current salary, compensation, current CTC, or package, ALWAYS use `1800000` (or `18` if LPA/decimal). NEVER fill `4` or years of experience into income/salary fields.
- **Expected CTC / Salary Expectation:** `28` LPA (`2800000`)
- **Upper Salary Range Directive:** Whenever any pay or salary range is written on a job posting or description, ALWAYS use the upper value as desired salary. If no range is written, fallback to 28 LPA (2800000 INR).
- **Master Resume Path:** `cv/Ankit_Resume_v4.pdf`

### 1.3 Education Template
- **Higher Education / Degree:** `Bachelor of Arts (Hons.) Business Economics`
  - **Institution:** `University of Delhi`
  - **Major / Field of Study:** `Business Economics`
  - **Duration:** `07/2017` - `07/2020`
  - **Score / Grade:** `6.5 CGPA`
  - **Key Topics:** `Statistics, Real Analysis, Econometrics, Quantitative Techniques for Management, Micro & Macro Economics, Database & Research, Organizational Behaviour`
- **Senior Secondary School (Class 12th):** `New Sainik Senior Secondary Public School`
  - **Grade / Score:** `72%`
- **Secondary School (Class 10th):** `Air Force School`
  - **Grade / Score:** `8.2 CGPA`

### 1.4 Professional Experience Template
*(Populated from candidate experience records in `.env` or structured data)*
`[NOT_SET: CANDIDATE_EXPERIENCE_ENTRIES]`

### 1.5 Technical Skills Template
- **Primary Languages & Query Engines:** `Python, PySpark, SQL (Snowflake, PostgreSQL, Trino, Oracle), Apache Airflow, ETL/ELT Architectures, AI Agents & Webhooks, SQL Performance Tuning`
- **ETL / Frameworks & Tools:** `Tableau, AWS (S3, SNS), Git, Bitbucket, SonarQube, Apache Airflow, Unix/Linux, Microsoft Excel, PowerPoint, Meta Ads & Pixel, Jupyter Notebooks`
- **Secondary / Data Science & ML:** `Machine Learning (Scikit-learn, Feature Engineering, Anomaly Modeling, Cohort Analytics, Time-Series Forecasting), AWS (SNS, S3), Autosys, REST APIs, Unix, SonarQube, Bitbucket`
- **Domain Specializations:** `Data Governance & Engineering, Healthcare Commercial Analytics (HIPAA, PII, HCP/HCO, Claims, Field Force & Sales Analytics), AI Agent Automation, E-commerce/D2C Analytics, Financial Valuation`
- **Explicit Technology Exclusions (DO NOT APPLY):** `Java, Spring Boot, J2EE, Kubernetes production DevOps, Docker production DevOps`

### 1.6 Target Roles & Location Preferences
- **Target Roles:** `Data Engineer, Analytics Engineer, Big Data Platform Engineer, Data Governance Engineer / Analyst / Specialist / Lead, Data Observability Engineer, Data Quality & Reliability Engineer, AI Systems / Agent Engineer, AI Automation Engineer, Applied AI / LLM Systems Engineer, Business Technology Consultant / Associate, Solutions Architect, Technical Consultant, Technical Product Manager, Analytics Advisory Consultant, Marketing Analytics Consultant`
- **Location Preferences:**
  1. 100% Remote
  2. Primary Metro / Regional Onsite / Hybrid: `Noida`
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
- **Attachment Table Sanitization & Comment Protection:** Never inject personal info or email into file comment/notes fields. When uploading the master CV, ensure `Resume / CV: Yes` and `Relevant Files: Yes` are set, older resumes are unselected or deleted, and any tailored Cover Letter is marked as `Relevant Files: Yes`.
- **Pre-Submission Review:** Always pause at the final review screen and generate an audit markdown report before submission.

### 2.5 Architecture & Optimization Directives
- **High-Velocity Sub-Minute Automation (30s - 60s Target):** Minimize execution latency by eliminating hardcoded `time.sleep()`, using atomic batch DOM injection via `page.evaluate()` (<15ms per page), proactive dialog confirmation, and event-driven locator polling (see `benchmarks/fast_ats_execution_architecture.md`).
- **Python 3.15+ Native Lazy Imports:** The runtime operates on Python 3.15+ with `PYTHON_LAZY_IMPORTS=all` (PEP 690 / PEP 810) enabled. All imports (including heavy libraries like Playwright, NumPy, SQLite, and docx) are lazily deferred on-demand, minimizing CLI startup latency and conserving execution memory.
- **Single Universal Automation Engine:** NEVER write one-off python application scripts per job. Always use parameterized `tools/ats_runner.py`.
- **Zero Git Commits for Individual Job Applications:** Never commit or push to GitHub after applying to an individual role. Commits are reserved for framework upgrades.
- **Autonomous Tracker Recording:** Automatically record applied jobs in `user_inputs/job_search_tracker.csv` and replicate to SQLite `jobs.db` via `tools/sync_tracker.py`.
- **Continuous Learning & Adaptation:** Automatically capture novel ATS questions and candidate answers in `user_inputs/application_qa_knowledge_base.json` and reuse them.
- **Daily Easy Apply Safety Ceiling (35-40 Max / 24h):** LinkedIn enforces an account-level daily rate limit on Easy Apply (typically 35-50 applications per rolling 24 hours). The framework enforces a strict safety ceiling of 40 Easy Apply submissions per calendar day to protect the candidate's account standing. Once reached or if an on-page application limit warning is detected, automation must immediately halt, sound a notification, and stop.

### 2.6 Strict Authentication & Zero-Lockout Protocol (ZERO-TOLERANCE)
- **Zero Credential Guessing / Single-Attempt Maximum:** Automation is permitted AT MOST ONE (1) login attempt per portal domain. NEVER iterate through password arrays, username guesses, or variations.
- **Immediate Halt on Auth Failure:** If attempt #1 fails or yields an error, automation must IMMEDIATELY HALT, sound a chime (`Glass.aiff`), send a macOS notification, and leave the browser interactive for the user.
- **Strict Ban on Auto-Registration for Existing Portals:** NEVER click 'New User', 'Create Account', or 'Register' if an account already exists or if login fails.
- **Domain-Specific Registry Lookup:** Always resolve credentials from `~/.config/job-agent/.candidate_secrets.json` (`accounts` registry) or exact `.env` portal keys before attempting login. If not found, prompt the user instead of trying generic passwords.
- **Security Warning Interceptor:** If any security warning ('last chance to sign in', 'account locked', 'too many attempts') appears on page, immediately abort.

### 2.7 Cover Letter Integrity & Two-Tier Validation Protocol (Future Applications)
- **Zero Broken Metrics & Dangling Operators:** All future generated cover letters must undergo strict automated validation before saving, converting to DOCX, or attaching to ATS forms.
- **Tier 1 (Local Deterministic Linter - Primary):** Execute `parsers/linter.py` (`audit_structural_integrity`) on the local CPU (<10ms, 0 tokens) to reject:
  1. Dangling percentage signs (`by %`, `discrepancies by %`).
  2. Dangling plus operators without quantities (`Managing +`, `+ Airflow`).
  3. Unpopulated placeholders or empty labels (`Req ID: `, `[NOT_SET]`, `[PLACEHOLDER]`, `<URL>`).
  4. Truncated profile handles/URLs (verified against `CANDIDATE_LINKEDIN_URL` from `.env`).
  5. Em dashes (`—`) and banned corporate slop.
- **Tier 2 (OpenRouter Free Tier Proofreader - Secondary):** If Tier 1 flags defects or warnings, automatically dispatch to OpenRouter zero-cost free tier (`cohere/north-mini-code:free` or `google/gemma-4-31b-it:free`) to restore accurate quantified facts (e.g. `40%`, `15+`) and grammar.
- **Old Letters Untouched:** Existing past application letters remain immutable; this validation gate strictly governs all newly generated cover letters.

### 2.8 Context Engineering, Quality Gates & Vibe Coding Protocol
- **PRP Blueprint Standard:** Any new feature or architectural addition must be guided by `templates/PRP_TEMPLATE.md` with explicit validation criteria, gotchas, and test requirements.
- **Automated Quality Verification Gate:** Before staging, committing, or deploying code changes, execute `tools/quality_gate.sh`. All 5 verification levels (PII audit, SSRF guard, linter integrity, Python 3.15 lazy imports, pytest suite) must achieve 100% pass.
- **XML Context Framing:** Structure prompts and agent interactions with explicit XML tags (`<context>`, `<intent>`, `<constraints>`, `<validation_gates>`) to maximize model instruction adherence and prevent context drift.
- **Session Continuity (Handoff Context):** Track ongoing progress, recent SHAs, and active decisions in `SESSION_HANDOFF.md` to ensure zero context loss across sessions.

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
