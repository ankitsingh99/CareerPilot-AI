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

---

## 4. Instructions for Next Agent / Session

1. Run `git status` to verify working tree status.
2. Run `python tools/generate_workspace_from_master.py --audit-pii` before any git commit.
3. Use `python tools/ats_runner.py --url "<URL>" --mode review` for interactive job applications.
