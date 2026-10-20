# CareerPilot AI - AI Assistant Engineering & Review Guidelines

This document outlines architectural conventions, execution directives, and human review expectations for AI assistants (Claude Code, Google Antigravity, Cursor) working on CareerPilot AI.

Maintainer: **Ankit Kumar Singh** (Data & Analytics Consultant | Ex-ZS Associates)

---

## 1. Core Engineering Conventions

1. **Zero-PII Git Discipline**:
   - Never commit candidate PII (phone number, personal email, street address, date of birth) to git.
   - All candidate identity and credential data is isolated in the local, gitignored `.env` and `~/.config/job-agent/`.
   - Before proposing git commits, verify with `python tools/generate_workspace_from_master.py --audit-pii`.

2. **Deterministic Architecture Over Generative Guesswork**:
   - Favor deterministic CPU compute (regex, token matching, fuzzy matching) over LLM generation.
   - All screening answers route through `core/qa_semantics_engine.py`. LLM fallback is strictly reserved for open-ended textareas.
   - Zero billable API calls: only OpenRouter endpoints ending in `:free` are allowed. Responses are permanently cached locally in `~/.cache/careerpilot/llm_responses_cache.sqlite`.

3. **Resilient Browser Automation**:
   - Always operate Playwright in headed mode for human oversight.
   - **Never close the browser window**: under all conditions (success, error, pause), leave the browser open and interactive.
   - Never iterate on credential guesses. Auth failure triggers immediate halt with an attention chime (`Glass.aiff`).

4. **Data Pipeline Idempotency**:
   - Jobs are uniquely identified by SHA-256 hashes (`utils/job_key.py`).
   - Every application must be transactionally recorded in `user_inputs/job_search_tracker.csv` and mirrored into `jobs.db`.

---

## 2. Review & Quality Verification Gate

No AI-assisted change should be staged or committed without passing the 5 verification levels:

```bash
bash tools/quality_gate.sh
```

Verification includes:
- **Level 1**: PII & Leaked Secret Audit.
- **Level 2**: SSRF Defense Protocol verification (`tests/test_ssrf_guard.py`).
- **Level 3**: Cover Letter Structural Integrity Linter (`parsers/linter.py`).
- **Level 4**: Python 3.15 lazy imports compatibility.
- **Level 5**: Comprehensive pytest suite (425+ tests).

---

## 3. Human Review & Merge Policy

Every AI-assisted code change requires human review before merging:
- Review the diff line-by-line to ensure domain heuristics (e.g. LinkedIn daily rate limit ceiling, CTC guardrails, healthcare data standards) are maintained.
- Ensure all newly introduced tools or modules have accompanying deterministic tests in `tests/`.
- Commit messages must be concise, descriptive, and human-readable (avoiding generic or overly templated commit essays).
