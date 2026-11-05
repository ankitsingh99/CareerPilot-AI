# Product Requirements Prompt (PRP) Blueprint
# CareerOps Full Capabilities Integration Contract

---
feature_name: "career_ops_full_integration"
target_domain: "core|discovery|intelligence|tools"
framework_version: "1.2.0"
runtime_target: "Python >=3.12 (CPython 3.15 Lazy Imports)"
cost_budget: "$0.00 (OpenRouter :free endpoints only)"
---

## 1. Goal & Architectural Purpose
- **Objective:** Systematically integrate and port all advanced capabilities from `career-ops-hq/career-ops` into the CareerPilot AI Python 3.15+ native architecture.
- **Value:** Augments our high-velocity autonomous ATS application engine with comprehensive job intelligence, holistic 1-5 scoring (A-H Block evaluation), zero-token liveness checking, anti-hallucination fact verification, multi-platform public ATS scanning, interview preparation kits, and salary intelligence.
- **Scope & Non-Goals:**
  - In-scope: A-H block job evaluation engine, 1-5 score calculation, public ATS provider pollers (Greenhouse, Lever, Ashby, SmartRecruiters, Workable, BambooHR, Breezy), anti-hallucination fact auditor, interview question and STAR+R story generator, skill gap analyzer, and compensation reliability assessor.
  - Non-goals: Disabling or removing autonomous auto-apply. Unlike career-ops which refuses to click submit, CareerPilot AI maintains its primary mission of full autonomous form submission while gaining career-ops's deep evaluation intelligence.

---

## 2. Context & Required References
- **Core Architecture:** `MASTER_TEMPLATE.md` and `AGENTS.md`
- **Candidate Data Contract:** `.env` and `user_inputs/candidate_preferences_and_rules.md`
- **Related Modules:**
  - Liveness & Closed Job Detection: `core/job_liveness_detector.py`
  - Repost Detection: `core/repost_detector.py`
  - ATS Public Boards: `discovery/ats_discovery/boards.py`
  - Database & Concurrency: `core/db.py`, `core/tracker.py`
  - Validation: `parsers/linter.py`
  - Security Guard: `utils/ssrf_guard.py`

---

## 3. Known Gotchas & Defensive Constraints
1. **Zero Em Dashes:** Never use em dashes. Always use standard hyphens (-), commas, or colons.
2. **Zero Hardcoded PII:** Never embed phone numbers, candidate addresses, or emails in tracked files.
3. **Zero Paid Calls:** Only use OpenRouter free models ending with `:free` when LLM inference is explicitly needed.
4. **Zero-Token Local Execution:** All parsing, heuristics, regex checks, and scoring matrices run on local CPU without token expenditure.
5. **Quality Verification Gate:** Must achieve 100% pass on `tools/quality_gate.sh`.

---

## 4. Technical Blueprint & Components

### Component 1: Zero-Token Liveness Pre-Flight Probe (`core/job_liveness_detector.py`, `tools/check_liveness.py`)
- Pre-flight verification of URLs or pasted text before spending browser or LLM compute.
- Checks HTTP status codes, redirection loops, and closure DOM elements across major ATS systems.

### Component 2: Comprehensive 1-5 Scoring & A-H Block Evaluator (`core/job_evaluator.py`, `tools/evaluate_job.py`)
- Calculates 5 scoring dimensions: CV Match, North Star Alignment, Compensation, Culture Signals, Red Flags.
- Computes global 1.0 - 5.0 score with strict decision boundaries (>=4.0 Apply, <4.0 Skip).
- Renders full A-H blocks:
  - Block A: Archetype & Role Summary (Platform/Data, Analytics, AI Agents, Solutions Architect).
  - Block B: Core Requirements Match Matrix (Critical, High, Meaningful, Preferred) & Gap Mitigation.
  - Block C: Seniority Level & "Sell Senior Without Lying" Strategy.
  - Block D: Compensation Reliability, Fixed vs Variable Split, and HR Verification Questions.
  - Block E: Customization Plan (Top 5 CV and LinkedIn enhancements).
  - Block F: Interview STAR+R Stories (Situation, Task, Action, Result, Reflection).
  - Block G: Posting Legitimacy & Ghost Job Signals (Layoffs, Churn, Contractor vs Employee Risk).
  - Verdict (lead): Single bold directive sentence.
  - Risk Summary: Holistic table of all risk flags.
  - Block H: Auto-drafted Cover Letter and Screening Answers.
- Stores output reports in `reports/{NNN}-{company-slug}-{date}.md`.

### Component 3: Zero-Token Public ATS Multi-Board Scanner (`discovery/ats_discovery/boards.py`, `tools/scan_public_ats.py`)
- Ingests public job listings via official zero-auth APIs:
  - Greenhouse, Lever, Ashby, SmartRecruiters, Workable, BambooHR, Breezy HR, Recruitee.
- Extracts compensation, sanitizes HTML to text, filters for target locations (India / Remote), and syncs to `jobs.db`.

### Component 4: Anti-Hallucination CV Fact Checker (`core/cv_fact_checker.py`, `tools/verify_cv_facts.py`)
- Analyzes generated cover letters, outreach pitches, and application answers.
- Extracts all numerical metrics, percentages, tool names, and dates.
- Verifies facts against master candidate profile (`AGENTS.md`, `.env`, master CV).
- Flags ungrounded metrics and prevents model hallucinations.

### Component 5: Interview Preparation & Technical Simulator (`tools/interview_prep.py`)
- Generates structured interview preparation guides with STAR+R stories, technical probes, and questions to ask the interviewer.
- Stores output in `interview_prep/{company}_{role}_prep.md`.

### Component 6: Skill Gap & Upskill Roadmapper (`tools/upskill_analyzer.py`)
- Scans `jobs.db` records and identifies recurring skill gaps from skipped or passed opportunities.
- Produces prioritized learning roadmaps.

### Component 7: Recruiter Pitch & Network Outreach Generator (`tools/contact_pitch.py`)
- Generates high-burstiness, humanized connection requests and follow-up notes for hiring managers and recruiters.

---

## 5. Verification Gates
1. Unit tests for each new module in `tests/`.
2. Execution of `tools/quality_gate.sh` with 0 errors.
3. Clean zero-token execution benchmark.

