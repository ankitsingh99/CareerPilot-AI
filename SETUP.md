# Setup Guide

Step-by-step instructions for getting the AI Job Search automation framework running on your workstation.

---

## 1. Prerequisites

### Python (3.15+ for Native Interpreter Lazy Imports)

Python 3.15+ is required across the framework to leverage native interpreter lazy imports (PEP 690 / PEP 810) via `PYTHON_LAZY_IMPORTS=all`, eliminating heavy module load overhead during CLI commands and local processing.

Check your Python version:

```bash
python3 --version  # Must report Python 3.15+
```

You can install and pin Python 3.15 using your package manager or `uv`:

```bash
# Using uv (fastest)
uv python install 3.15
uv venv .venv --python 3.15
source .venv/bin/activate
uv pip install -r requirements.txt
playwright install chromium
```

Or using standard Python 3.15 `venv`:

```bash
python3.15 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

---

## 2. Fork and clone

> **Privacy Warning**: GitHub forks of public repositories are public by default. Initializing setup writes personal data into tracked files. If your repository is public, your personal data will be visible to everyone. Refer to [SETUP.md §8](#8-pulling) for instructions on creating a private remote repository.

```bash
gh repo fork ankitsingh99/ai-job-search --clone
cd ai-job-search
```

---

## 3. Zero-PII Candidate Profile Configuration

The framework uses a strict separation between public code templates and private candidate identifiable data (PII). **No PII is ever committed to git.**

### Step 1: Create Your Local Environment File

Copy the provided environment template:

```bash
cp .env.example .env
```

### Step 2: Populate Your Candidate Information in `.env`

Open `.env` in your editor and configure your details:

```ini
# Identity & Contact (Kept strictly on your local machine)
CANDIDATE_NAME="Your Full Name"
CANDIDATE_FIRST_NAME="Your First Name"
CANDIDATE_LAST_NAME="Your Last Name"
CANDIDATE_EMAIL="your.email@example.com"
CANDIDATE_PHONE="+91-XXXXXXXXXX"
CANDIDATE_RAW_PHONE="XXXXXXXXXX"
CANDIDATE_DOB="YYYY-MM-DD"
CANDIDATE_ADDRESS="Your Street Address, City, State, PIN, Country"
CANDIDATE_CITY="Noida"
CANDIDATE_STATE="Uttar Pradesh"
CANDIDATE_COUNTRY="India"
CANDIDATE_PINCODE="201304"

# Professional & Compensation
CANDIDATE_NOTICE_PERIOD="Immediate Joiner (0 days notice)"
CANDIDATE_TOTAL_YOE="4.8"
CANDIDATE_CURRENT_CTC_LPA="18"
CANDIDATE_EXPECTED_CTC_LPA="28"
CANDIDATE_MASTER_RESUME="cv/Ankit_Resume_v4.pdf"

# Model & Lazy Imports
OPENROUTER_API_KEY="sk-or-v1-..."
PYTHON_LAZY_IMPORTS="all"
```

Because `.env` is listed in `.gitignore`, your credentials and contact information will never be pushed to GitHub.

---

## 4. Hydrate Workspace from Master Blueprint

All instructions, templates, and behavioral directives reside in `MASTER_TEMPLATE.md`. To instantiate or rehydrate your localized workspace:

```bash
# Generate localized workspace files from MASTER_TEMPLATE.md + .env
python tools/generate_workspace_from_master.py
```

This generates or updates:
- `AGENTS.md` (unified agent instructions with your profile variables)
- `.claude/skills/job-application-assistant/01-candidate-profile.md`
- `user_inputs/candidate_preferences_and_rules.md`

### Audit Your Workspace for PII Leaks

Before pushing any commits to GitHub, verify that no personal data has leaked into tracked files:

```bash
python tools/generate_workspace_from_master.py --audit-pii
```

If any hardcoded phone numbers, email addresses, or dates of birth are detected in git-tracked files, the audit tool flags the exact file and line number.

---

## 5. Local CV & Cover Letter Storage

Your master resume and generated cover letters remain stored on your local disk with full authenticity:

- Place your master resume PDF in `cv/` (e.g. `cv/Ankit_Resume_v4.pdf`).
- `.gitignore` automatically excludes all resume PDFs and generated cover letter markdown files (`cv/*.pdf`, `cv/*.docx`, `cover_letters/*.md`, `cover_letters/*.docx`).
- Automation scripts dynamically resolve your latest resume from `cv/` or the `CANDIDATE_MASTER_RESUME` setting in `.env`.

---

## 6. Free-Tier OpenRouter Model Configuration

The framework enforces a **Strict Zero-Cost Policy**. Only open-source models ending in `:free` are permitted for AI reasoning:

- Default free model: `cohere/north-mini-code:free`
- Free model pool: `google/gemma-4-31b-it:free`, `qwen/qwen3.8-27b:free`, `nvidia/nemotron-3.5-lightning:free`

Set your OpenRouter API key in `.env` or in `~/.config/job-agent/client_secret.json`:

```json
{
  "api_keys": {
    "openrouter_api_key": "sk-or-v1-..."
  }
}
```

Verify connection:

```bash
python -c "from intelligence.llm_clients.openrouter import ask; print(ask('say pong in 1 word'))"
```

---

## 7. End-to-End Application Automation

### Headed Playwright Runner (`tools/ats_runner.py`)

Run the universal browser runner on any job application URL:

```bash
# Review mode: fills all form fields and pauses on the final screen for user review
python tools/ats_runner.py --url "https://boards.greenhouse.io/company/jobs/12345" --mode review

# Apply mode: fills form, performs pre-submission audit, and notifies user
python tools/ats_runner.py --url "https://company.wd3.myworkdayjobs.com/en-US/Careers/job/123" --mode apply
```

**Browser Safety Directive:**
The automation runner never closes the browser window automatically. Once fields are populated, the browser remains open and interactive for you to inspect, verify documents, and click the final submit button.

### LinkedIn Easy Apply Autopilot

Run the automated LinkedIn Easy Apply runner:

```bash
python tools/linkedin_easy_apply_runner.py --keyword "Data Engineer" --location "Remote"
```

---

## 8. Pulling upstream updates into your fork

<a id="8-pulling"></a>

If you maintain a private repository to keep personal data safe while pulling updates from upstream:

1. **Create a private repository:** Create a private repository on GitHub (do not fork directly if you need privacy, since forks of public repos remain public).
2. **Push your private code:** Push your private workspace to your private remote repository.
3. **Add upstream remote:**
   ```bash
   git remote add upstream https://github.com/ankitsingh99/ai-job-search.git
   git fetch upstream
   git merge upstream/master
   ```

---

## 9. JobRadar Local Web Dashboard

Launch the zero-dependency local glassmorphism web dashboard:

```bash
python tools/jobradar_dashboard.py --port 8765
```

Open `http://localhost:8765` in your browser to inspect applications in `jobs.db`, filter opportunities, and view your tracking metrics.

---

## 10. Synchronizing Tracking Database & Verification

Replicate changes between `job_search_tracker.csv` and SQLite `jobs.db`:

```bash
python tools/sync_tracker.py
```

Verify all components pass quality checks:

```bash
# Run complete test suite (400+ tests under Python 3.15)
pytest tests/

# Verify repository security and permissions allowlist
python utils/security.py

# Verify zero PII leaks across git files
python tools/generate_workspace_from_master.py --audit-pii
```
