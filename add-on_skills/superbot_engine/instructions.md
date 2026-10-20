This document outlines how to deploy, configure, and operate the **AI Job Application Superbot Engine** built to automate candidate discovery, document generation, and ATS form submission.

---

## 1. Directory Structure

```
/superbot_engine
├── config/
│   ├── profile.json            # Master user profile, skill matrix, and QA bank
│   └── config.yaml             # Filters, fit thresholds, and LLM model assignments
├── engine/
│   ├── __init__.py
│   ├── router.py               # 3-Tier Dynamic LLM selection router
│   ├── discovery.py            # Job scraper driver & rule-based filter
│   ├── tailor.py               # Factual resume re-aligner & cover letter generator
│   └── executor.py             # Playwright stealth form submission driver
├── database/
│   ├── __init__.py
│   └── db_manager.py           # SQLite cache and submission tracking manager
├── pending_approvals/          # Human-in-the-loop staging queue (JSON files)
├── browser_session/            # Persistent browser context (cookies & login state)
├── requirements.txt            # Python dependencies
├── main.py                     # Central pipeline orchestrator
└── instructions.md             # System usage instructions
```

---

## 2. Quickstart Execution Guide

### Step 1: Extract and Navigate to Project
```bash
unzip superbot_engine.zip
cd superbot_engine
```

### Step 2: Install Dependencies & Playwright Binaries
```bash
pip install -r requirements.txt
playwright install chromium
```

### Step 3: Run the Superbot Pipeline
```bash
python main.py
```

---

## 3. Module Details & Configuration Rules

### A. Candidate Profile (`config/profile.json`)
* Edit `personal_info`, `current_employment`, and `experience_bullets` with updated employment history or contact details.
* Edit `qa_knowledge_base` to customize answers for standard screening questions (e.g., notice period, current/expected salary, work authorization).

### B. System Rules (`config/config.yaml`)
* **`fit_threshold`**: Minimum semantic score (out of 100) required before triggering document tailoring.
* **`candidate_filters.target_roles`**: List of job titles matched by rule filters.
* **`candidate_filters.excluded_titles_regex`**: Regular expression for titles to auto-reject (e.g., Interns, Directors, Managers).
* **`llm_tier_assignments`**: Assign specific model endpoints for Tier 1 (Fast), Tier 2 (Smart), and Tier 3 (Power) tasks.

### C. SQLite Caching (`database/cache.db`)
* Automatically created upon launch.
* Stores SHA-256 hashes computed from `title + company + description` to avoid re-evaluating or re-applying to duplicate jobs.

---

## 4. Operational Workflow & HITL Approval Gate

1. **Discovery**: `discovery.py` fetches raw job postings across targeted job portals.
2. **Pre-Filtering**: Local Python rules filter out non-compliant job titles or locations without consuming LLM API tokens.
3. **Semantic Scoring**: The Tier 2 model computes a 1–100 fit score.
4. **Tailoring**: The Tier 3 model reorganizes resume bullet points and generates a targeted cover letter for matches scoring above `fit_threshold`.
5. **HITL Review**: Application materials are staged in `pending_approvals/<job_hash>.json`. Prompting in `main.py` requires typing `yes` or `no` to approve submission.
6. **Stealth Form Submission**: Upon approval, `executor.py` opens a stealth Playwright session with persistent browser state, loads the application page, populates the fields, and records completion in `database/cache.db`.
