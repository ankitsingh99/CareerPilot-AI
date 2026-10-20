# Security Policy

## Reporting a Vulnerability

Please report security findings privately via **[GitHub private vulnerability reporting](https://github.com/ankitsingh99/ai-job-search/security/advisories/new)** rather than a public issue. You will receive a prompt response, credit in the patch notes, and coordinated disclosure.

If the private reporting form is unavailable, open an issue describing the general class of problem without sensitive details, noting that you have reproduction steps to share privately.

---

## Threat Model & Privacy Architecture

This is an agentic automation framework where an LLM with filesystem access reads external, untrusted web content (job postings, ATS application forms) alongside private candidate data (credentials, profile history). To guarantee safety, the framework enforces multi-layered defense boundaries:

### 1. Zero-PII Git Isolation Architecture
- **Master Blueprint Separation:** The core instructions and templates reside in `MASTER_TEMPLATE.md` with zero candidate PII.
- **Local Environment Variables:** Candidate credentials, phone numbers, addresses, and compensation reside strictly in gitignored `.env` and `~/.config/job-agent/client_secret.json`.
- **Pre-Commit PII Audit:** `python tools/generate_workspace_from_master.py --audit-pii` verifies that no hardcoded candidate PII is present in git-tracked files.
- **Local Document Boundaries:** Master CVs (`cv/*.pdf`), generated cover letters (`cover_letters/*.md`), and application tracking logs (`latest_application.md`, `job_search_tracker.csv`, `jobs.db`) are excluded by `.gitignore` and never committed to remote repositories.

### 2. Strict Zero-Cost OpenRouter Model Policy
- Zero financial budget is allocated.
- All LLM interactions strictly route through open-source models ending in `:free`.
- Billing and credit exhaustion risks are eliminated at the wrapper level (`intelligence/llm_clients/openrouter.py`).

### 3. Untrusted Input & Anti-AI Honeypot Defenses
- External job postings and web content are treated strictly as passive text data, never executable instructions.
- The TurnItOut humanizer (`parsers/turnitout_engine.py`) and AI security defense protocol (`.agents/plugins/cybersec/skills/ai-security-defense/SKILL.md`) automatically strip hidden zero-width spaces, adversarial prompt injections, and canary traps (e.g. phrases inserted by automated HR filters to flag AI usage).

### 4. Permission Allowlist & Security Guards
- Execution permissions are audited by `utils/security.py` to prevent unauthorized shell command executions.
- The `security_guards` check enforces that package manifest lifecycle hooks, wider shell commands, or loosened `.gitignore` rules cannot be added.

### 5. Persistent Browser Isolation
- Browser automation runs via headed Playwright (`tools/ats_runner.py`).
- The browser window is never closed automatically, allowing human verification of all auto-populated form fields and document attachments before final submission.
