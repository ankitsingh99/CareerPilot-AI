---
name: session-handoff-manager
description: >-
  Generates and continuously updates structured session handoff documents on disk (SESSION_HANDOFF.md).
  Monitors context bloat and step count, tracks active state, credentials architecture, and pending tasks,
  and proactively nudges the user to start a new chat session at optimal milestones or model transitions.
---

# Session Handoff Manager

This skill maintains continuity across chat sessions and model switches by ensuring a comprehensive, canonical `SESSION_HANDOFF.md` document exists on disk and is continuously kept up to date.

---

## When to Trigger This Skill:
1. **Milestone Completions:** Whenever a major task (e.g. ATS integration, test suite run, document generation, git push) is completed.
2. **Model Transitions:** When switching between Claude, GPT, or Gemini models to pass full contextual state without loss.
3. **Session Context Bloat (Nudge Trigger):**
   - When the conversation reaches **> 40-50 turns** or **Checkpoints 2+**.
   - When message serialization latency or queuing is detected.
   - When a logical sub-task concludes.

---

## Core Responsibilities:

### 1. Maintain `SESSION_HANDOFF.md` on Disk
Always write or update `SESSION_HANDOFF.md` at the project root with the following structure:

```markdown
# AI Job Search: Session Handoff Document
**Last Updated:** <YYYY-MM-DD HH:MM:SS>
**Active Git Branch / Commit:** <branch @ short-sha>
**Model Context Status:** <Optimal / High Token Load / Ready for New Session>

---

## 1. Executive Summary & Current State
- Brief summary of the current project state and what was just accomplished.

## 2. Key Architecture & Single Sources of Truth
- **Master Blueprint:** `MASTER_TEMPLATE.md` (universal person-agnostic instructions)
- **Candidate Profile & Rules:** `AGENTS.md` (rehydrated via `tools/generate_workspace_from_master.py`)
- **Secrets & Credentials (Local Only):** `.env` & `~/.config/job-agent/client_secret.json` (gitignored)
- **Universal ATS Engine:** `tools/ats_runner.py` (headed Playwright with persistent browser)
- **Master Resume:** Loaded dynamically from `.env` (`CANDIDATE_MASTER_RESUME`) or `cv/*.pdf`
- **Application Tracker:** `job_search_tracker.csv` & `jobs.db`
- **Zero-Cost LLM:** OpenRouter free tier (`cohere/north-mini-code:free`, etc.)

## 3. Recently Established Rules & Directives (Active)
- Section 1: Python 3.15+ native interpreter lazy imports (`PYTHON_LAZY_IMPORTS=all`)
- Section 2: Zero hardcoded PII in git; verify with `python tools/generate_workspace_from_master.py --audit-pii`
- Section 3: Never close the browser window automatically
- Section 4: Zero em dashes (`—`)
```

### 2. Proactive Session Nudging
When token consumption grows large (>100k tokens in context), write the handoff document and inform the user with:
- Summary of completed work
- Clear pointer to `SESSION_HANDOFF.md`
- Suggested prompt for the next clean session
