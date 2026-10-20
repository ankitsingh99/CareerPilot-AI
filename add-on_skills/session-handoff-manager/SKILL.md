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
   - When the conversation reaches **> 40–50 turns** or **Checkpoints 2+**.
   - When message serialization latency or queuing is detected.
   - When a logical sub-task concludes.

---

## Core Responsibilities:

### 1. Maintain `SESSION_HANDOFF.md` on Disk
Always write/update `SESSION_HANDOFF.md` at the project root with the following structure:

```markdown
# AI Job Search: Session Handoff Document
**Last Updated:** <YYYY-MM-DD HH:MM:SS>
**Active Git Branch / Commit:** <branch @ short-sha>
**Model Context Status:** <Optimal / High Token Load / Ready for New Session>

---

## 1. Executive Summary & Current State
- Brief summary of the current project state and what was just accomplished.

## 2. Key Architecture & Single Sources of Truth
- **Candidate Profile & Rules:** `GEMINI.md`, `CLAUDE.md`, `user_inputs/candidate_preferences_and_rules.md`
- **Secrets & Credentials (Local Only):** `client_secret.json` (gitignored & geminiignored)
- **Universal ATS Engine:** `tools/ats_runner.py` (non-blocking, instant streaming)
- **Master Resume:** Loaded dynamically from `.env` (`CANDIDATE_MASTER_RESUME`)
- **Application Tracker:** `job_search_tracker.csv` & `jobs.db`

## 3. Recently Established Rules & Directives (Active)
- Section 10: Place of Residence (Candidate configured primary and fallback city)
- Section 11: Local-only `client_secret.json` with auto-login -> auto-register flow
- Section 12: Manual login intervention nudge & explicit user confirmation
- Section 13: Zero blind waiting for OTP/PIN/CAPTCHA; prompt user directly in chat

## 4. Pending / Next Immediate Tasks
- [ ] Next action item 1
- [ ] Next action item 2

## 5. Instructions for New Session / Next Model
- Run `git status` to verify working tree.
- Read `SESSION_HANDOFF.md` and `user_inputs/candidate_preferences_and_rules.md`.
- Resume directly on pending tasks without re-asking established candidate preferences.
```

---

## 2. Proactive "New Session" Nudge Protocol
When context growth starts degrading responsiveness:
1. Update `SESSION_HANDOFF.md` with the latest progress.
2. Alert the user with a gentle nudge:
   > 💡 **Optimal Time for a Fresh Session:**
   > `SESSION_HANDOFF.md` has been fully generated and updated on disk. You can safely start a new chat now. In the new chat, simply say **"Continue from handoff"** and we will pick up instantly with zero lag.
