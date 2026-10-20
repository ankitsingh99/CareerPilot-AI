# Product Requirements Prompt (PRP) Blueprint
# CareerPilot AI Feature Specification & Execution Contract

---
feature_name: "[FEATURE_NAME]"
target_domain: "[discovery|intelligence|automation|parsers|ui|core]"
framework_version: "1.2.0"
runtime_target: "Python >=3.12 (CPython 3.15 Lazy Imports)"
cost_budget: "$0.00 (OpenRouter :free endpoints only)"
---

## 1. Goal & Architectural Purpose
- **Objective:** [Concise description of the capability being added or refined]
- **Value:** [Why this matters for autonomous job application, rate limiting, or ATS resilience]
- **Scope & Non-Goals:** [What this feature explicitly does NOT do]

---

## 2. Context & Required References
Before implementing, the agent MUST review the following context assets:
- **Core Architecture:** `MASTER_TEMPLATE.md` and `AGENTS.md`
- **Candidate Data Contract:** `.env` and `~/.config/job-agent/client_secret.json`
- **Related Code Patterns:**
  - Database: `core/db.py` (Concurrency leasing, parameterized queries)
  - Browser Automation: `automation/browser.py` (Zero-lockout, CDP attachment, headed mode)
  - Security Guard: `utils/ssrf_guard.py` (Vibe-check Category 6)
  - Validation: `parsers/linter.py` (Cover letter structural integrity)

---

## 3. Known Gotchas & Defensive Constraints
1. **Zero Em Dashes:** Never use em dashes (`—`). Use standard hyphens (`-`), commas, or parentheses.
2. **Zero Hardcoded PII:** Never embed phone numbers, names, emails, or personal addresses in tracked files.
3. **Zero Browser Termination:** Never call `browser.close()` or `page.close()` automatically. Leave headed windows open.
4. **Single-Attempt Auth:** At most 1 login attempt per domain. Instant abort and chime on auth failure.
5. **SSRF Guard:** All outbound URLs must pass `utils.ssrf_guard.validate_url()`.
6. **SQL Parameterization:** Never concatenate strings in SQL statements (`execute(f"...")` is strictly forbidden).

---

## 4. Technical Blueprint & Step-by-Step Plan
### Phase 1: Interface & Data Contract
- [ ] Define schemas, dataclasses, or method signatures.
- [ ] Ensure backward compatibility with existing CLI commands.

### Phase 2: Implementation & Error Handling
- [ ] Implement core logic in target domain.
- [ ] Wrap external I/O with exponential backoff and polite rate limiting.

### Phase 3: Automated Validation Gates (Self-Correction Loop)
The implementation is NOT complete until all of the following commands exit with code 0:
```bash
# 1. Unit tests for the new feature
.venv/bin/pytest tests/test_[feature_name].py -v

# 2. SSRF and Security verification
.venv/bin/python utils/ssrf_guard.py

# 3. PII and secret leak detection
.venv/bin/python tools/generate_workspace_from_master.py --audit-pii

# 4. Overall repository test suite
.venv/bin/pytest
```

---

## 5. Confidence Score & Review Checklist
- [ ] **Confidence Score (1-10):** [Must be >= 9 before considering complete]
- [ ] **Zero Cost Verified:** No paid LLM endpoints invoked.
- [ ] **Clean Git State:** Only feature-relevant files modified.
