# AI Job Search: Session Handoff Document
**Last Updated:** 2026-10-20 13:00:00 IST
**Active Git Branch / Commit:** `master` @ `origin/master` (Clean Squashed Release v1.2.0)
**Repository Visibility:** Public ([https://github.com/ankitsingh99/ai-job-search](https://github.com/ankitsingh99/ai-job-search))
**Model Context Status:** Optimal (Clean Context Handoff)

---

## 1. Executive Summary & Accomplishments

### 1. Python 3.15 Native Interpreter Lazy Imports Migration
- Upgraded virtual environment and project toolchain to CPython 3.15.0rc3 (`.python-version` pinned to 3.15, `pyproject.toml` with `>=3.15`).
- Enabled native interpreter-level lazy module deferral (`PYTHON_LAZY_IMPORTS=all` via PEP 690 / PEP 810).
- Created `utils/lazy_bootstrap.py` which activates `sys.set_lazy_imports('all')`.
- Heavy modules (`numpy`, `playwright`, `docx`, `sqlite3`) are deferred in `sys.lazy_modules` until attribute access, achieving sub-millisecond CLI startup and minimal memory footprint.
- Verified test suite: 400 passed, 1 skipped in 7.52s.

### 2. Universal Master Blueprint Architecture (`MASTER_TEMPLATE.md`)
- Created `MASTER_TEMPLATE.md` as the single candidate-agnostic blueprint containing all system directives, application workflows, ATS screening question databases, and behavioral rules.
- Built `tools/generate_workspace_from_master.py` with:
  - Automatic workspace instantiation from `.env` (`python tools/generate_workspace_from_master.py`).
  - Workspace reset to clean templates (`--clean`).
  - Automated PII auditing across all tracked git files (`--audit-pii`).

### 3. Complete Zero-PII Git Isolation & Repository Public Release
- **Local Files Retain Full Authenticity:** Master CVs (`cv/*.pdf`), generated cover letters (`cover_letters/*.md`), application tracking logs (`latest_application.md`, `job_search_tracker.csv`, `jobs.db`), and candidate credentials (`.env`, `~/.config/job-agent/client_secret.json`) are stored locally on disk and excluded by `.gitignore`.
- **Zero PII in Git:** All working modules (`automation/browser.py`, `core/db.py`, `core/tracker.py`, etc.) dynamically query `.env` without falling back to hardcoded dates of birth, phone numbers, or addresses.
- **Clean Squashed History:** Cleaned and squashed git history on `master` to guarantee 0 past PII leaks in `git log`. Created local safety backup branch `backup-pre-squash-history`.
- **Public Visibility Enabled:** Pushed clean master to GitHub and made `ankitsingh99/ai-job-search` public via GitHub CLI.

### 4. Zero-Cost OpenRouter Free Tier Integration
- Enforced strict zero-cost policy for all AI tasks. Only open-source models ending in `:free` are queried (`cohere/north-mini-code:free`, `google/gemma-4-31b-it:free`, `qwen/qwen3.8-27b:free`, `nvidia/nemotron-3.5-lightning:free`).
- Built-in text compression, prompt caching layout, and max token caps.

### 5. Author Attributions Standardized
- All code file headers and `pyproject.toml` uniformly specify: `Author: Ankit Kumar Singh`.

---

## 2. Core Architecture & Single Sources of Truth

- **Master Blueprint:** [`MASTER_TEMPLATE.md`](file:///Users/ashish/git/ai-job-search/MASTER_TEMPLATE.md)
- **Unified Agent Instructions:** [`AGENTS.md`](file:///Users/ashish/git/ai-job-search/AGENTS.md)
- **Local Credentials & PII (Local Only):** `.env` & `~/.config/job-agent/client_secret.json`
- **Master Resume:** Dynamically loaded from `.env` (`CANDIDATE_MASTER_RESUME`) or latest `cv/*.pdf`
- **Universal Automation Runner:** `tools/ats_runner.py` (headed Playwright with persistent browser)
- **Anti-AI TurnItOut Engine:** `parsers/turnitout_engine.py` & `tools/turnitout_humanizer.py`
- **Local Database (Local Only):** `jobs.db` & `job_search_tracker.csv` via `tools/sync_tracker.py`

---

## 3. Strict Operating Directives (Active)

1. **NEVER Close the Browser Window:** Under no circumstances must automation close the browser. Always leave the browser open and interactive for human verification.
2. **Zero PII in Git:** Never commit candidate phone numbers, email addresses, dates of birth, or street addresses to git. Verify before pushing with `python tools/generate_workspace_from_master.py --audit-pii`.
3. **Strict Zero-Cost OpenRouter Directive:** Exclusively use free-tier models ending in `:free`. Never incur billable API costs.
4. **No Em Dashes (`—`):** Never use em dashes. Use standard hyphens (`-`), commas, colons, or parentheses.
5. **Python 3.15 Native Lazy Imports:** Maintain `PYTHON_LAZY_IMPORTS=all` in `.env` and `utils/lazy_bootstrap.py`.
6. **Attachment Sanitization Guardrail:** Never inject candidate personal identity into comments/notes inputs. Master CV must have `Resume / CV: Yes` & `Relevant Files: Yes`; Cover Letters must have `Relevant Files: Yes`; older CVs deleted/unselected.
7. **High-Velocity Sub-Minute Execution:** Follow `benchmarks/fast_ats_execution_architecture.md` (atomic batch DOM injection, proactive dialog confirmation, zero arbitrary `time.sleep()`).

---

## 4. Recent Activity & Session Status (2026-10-20 Evening)
- **Profile & Semantics Upgrades:**
  - Undergrad GPA set to `6.5 CGPA` across `AGENTS.md`, `.env`, and all runners.
  - Annual Income explicitly guarded across all modules to `1800000` (or `18` LPA) with zero numeric fallback to `4`.
  - Designation uniformly set to `Business and Technology Consultant`.
  - Built universal [`core/qa_semantics_engine.py`](file:///Users/ashish/git/ai-job-search/core/qa_semantics_engine.py) with deterministic regex matching for 100+ questions, negative tech exclusions (Java, Spring Boot, Kubernetes -> 0), positive tool experience (Python, SQL, Airflow, PySpark, Tableau -> 4), compliance, compensation, and OpenRouter Free Tier LLM fallback.
  - Enriched [`user_inputs/application_qa_knowledge_base.json`](file:///Users/ashish/git/ai-job-search/user_inputs/application_qa_knowledge_base.json) from 25 to 49 comprehensive categories.
  - Integrated `QASemanticsEngine` into both [`tools/linkedin_easy_apply_runner.py`](file:///Users/ashish/git/ai-job-search/tools/linkedin_easy_apply_runner.py) and [`automation/browser.py`](file:///Users/ashish/git/ai-job-search/automation/browser.py).
  - Full automated quality verification gate passed 100% (427 passed, 1 skipped, 197 subtests, 0 PII leaks).
- **OpenRouter Quota & Request Optimization (Radical Reduction):**
  - **Tier 1 (Local Deterministic Rules & Knowledge Base):** Form fields, notice periods, tools, compensation, and 49 QA categories resolve locally in <1ms without touching network.
  - **Tier 2 (Local SQLite Persistent Disk Cache):** Implemented permanent disk cache in [`intelligence/llm_clients/openrouter.py`](file:///Users/ashish/git/ai-job-search/intelligence/llm_clients/openrouter.py) at `~/.cache/careerpilot/llm_responses_cache.sqlite`. Repeated questions return in 0ms with **0 network requests and 0 tokens consumed**.
  - **Tier 3 (OpenRouter Gateway Edge Caching):** Added `"X-OpenRouter-Cache": "true"` to all request headers. Upstream cache hits return in ~50ms, cost 0 credits, and **do not consume rate limits**.
- **Easy Apply Batch Progress:**
  - Submitted 35 Easy Apply applications today across Data Engineering, AI Systems, Analytics, and Consulting roles.
  - Synchronized all records into `job_search_tracker.csv` and SQLite `jobs.db` (Total: 136 tracked applications).
- **Session State:**
  - **Paused on user command due to LinkedIn daily limit ceiling (35-40 Max / 24h).**
  - Hardcoded safety ceiling (`DAILY_EASY_APPLY_LIMIT = 40`) and on-page rate limit detector active.
  - Headed Chrome browser left permanently open and interactive on the display per strict safety directives.

---

## 5. Instructions for Resuming
1. Allow LinkedIn account cooldown period before launching fresh batches.
2. Consider spacing queries across distinct target titles or utilizing search pagination (`start=75`, `start=100`).
3. Maintain zero-cost OpenRouter free tier integration for all future screening questions.
