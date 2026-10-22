---
name: self-learning-adaptive-evaluator
description: >-
  Extracts, learns, and synthesizes negative constraints, candidate rules, and field formatting guidelines
  from user feedback, manual corrections, and ATS form validation mistakes. Enforces zero-regression execution
  across all job applications via deterministic pre-submission audits.
---

# Self-Learning & Adaptive Evaluator Skill

This skill operationalizes a continuous learning loop that transforms user corrections, negative feedback, and ATS validation failures into permanent, executable negative constraints and deterministic rules.

## Core Directives & Permanent Lessons

Whenever interacting with application portals, the agent must adhere to the 5 core learned invariants synthesized from candidate feedback:

| Category | Defect Prevented | Invariant Rule | Action on Detection |
| :--- | :--- | :--- | :--- |
| **References** | Fabricating manager names / contact info out of thin air | **Zero Reference Person Fabrication**: Candidate has never provided references. External reference person details must remain completely blank. | Leave `custname`, `custphone`, `custemail`, `custoccupat`, `custcompany` empty (`""`). Grant permission *"May we contact your references?"* -> `Yes`. |
| **Education** | Unnecessary high school / secondary school inclusion | **College-Only Education Default**: Only submit university degree (`University of Delhi`, Bachelor of Arts (Hons.) Business Economics). | Prune rows to exactly 1 college degree. Do NOT add 10th or 12th unless explicitly mandated by the portal. |
| **Scores / CGPA** | Unprompted grade / metric injection | **Omit Scores / CGPA Unless Mandatory**: Do not write CGPA (`6.5`), percentage, or scores unless explicitly required with an asterisk (`*`). | Leave `finalGrade` / `gpa` blank if optional. |
| **Dates** | Missing timeline in dynamic tables / shadow DOM | **Mandatory Start and End Dates**: All work experience and education rows must have complete start and end dates populated. | Inspect Shadow DOM date pickers (`<ui5-date-picker-xweb-calendar-widget>`) and dispatch native change events in `MM/DD/YYYY` format. |
| **Domain Categorization** | Misclassifying company industry / organization | **Rush by Kira D2C Retail Spec**: Rush by Kira is strictly an active D2C retail e-commerce business. | Set Type of Business to `Retail`, Organization to `D2C Retail & E-Commerce Operations`. |

---

## 4-Step Self-Adaptation Protocol

### Step 1: User Correction Ingestion
When the user provides feedback (e.g., *"did i ever provide you any references?"*, *"do not add education other than college"*, *"rush by kira is D2C retail"*):
1. **Identify the Defect Type**: Hallucination, Over-inclusion, Omission, or Misclassification.
2. **Isolate the Scope**: Specific field names (`custname`, `finalGrade`), sections (`Education`, `Work Experiences`), or global candidate preferences.

### Step 2: Negative Constraint Synthesis
Translate the correction into a strict negative constraint:
- `NEVER [Defect] WHEN [Condition]`
- Example: `NEVER populate reference person fields unless explicitly configured in .env`
- Example: `NEVER include school education below undergraduate level unless the form prevents progression without it`

### Step 3: Knowledge Base & Persistent Rule Sync
Permanently record the learned directive into:
1. `user_inputs/application_qa_knowledge_base.json` (semantic regex & standard answer).
2. `.agents/rules/05_APPLICATION_LEARNING_AND_ADAPTATION.md` (universal rule).
3. `user_inputs/candidate_preferences_and_rules.md` (candidate preference ledger).

### Step 4: Deterministic Pre-Submit Audit Verification
Before declaring an application ready for review or generating `pre_submit_audit.md`:
1. Execute the automated evaluator:
   ```python
   from core.adaptive_evaluator import audit_form_state
   audit_result = audit_form_state(form_data)
   assert audit_result["passed"] is True, f"Learned constraint violated: {audit_result['violations']}"
   ```
2. Verify all 5 invariants pass with 0 defects before presenting to the candidate.

---

## Architecture & Token-Lean Principles
- **100% Deterministic Local Compute**: Feedback parsing and rule enforcement execute locally on CPU (<5ms, 0 LLM tokens).
- **Zero Financial Cost**: Never invoke paid LLM endpoints to evaluate candidate rules.
- **Universal Reusability**: All fixes are committed directly into core modules (`core/qa_semantics_engine.py`, `automation/browser.py`, `core/adaptive_evaluator.py`), never in single-use throwaway scripts.
