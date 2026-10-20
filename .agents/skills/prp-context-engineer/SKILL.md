---
name: prp-context-engineer
description: Product Requirements Prompt (PRP) and Context Engineering workflow for CareerPilot AI. Creates information-dense, self-validating implementation blueprints with executable validation gates, preventing model hallucinations and ensuring zero-regression code delivery.
---

# PRP Context Engineer

This skill operationalizes the Context Engineering & PRP (Product Requirements Prompt) methodology from `coleam00/context-engineering-intro` and `RiyaParikh0112/vibe-coding-playbook`.

## Core Principles
1. **Context is King:** Never ask an agent to implement a feature with vague instructions. Assemble relevant documentation, gotchas, code examples, and explicit constraints before coding.
2. **Executable Validation Gates:** Every plan must include runnable test commands (`pytest`, linter, security verification) that the agent must execute and achieve 100% pass before reporting completion.
3. **Information Density:** Use exact symbol names, file paths, and known repository quirks.
4. **Zero Financial Cost:** Enforce OpenRouter `:free` model constraints throughout.

## Workflow

### Step 1: Create a Feature PRP
When planning a new feature or complex refactor, generate a specification following `templates/PRP_TEMPLATE.md`:
- **Goal & Why:** Quantified business value.
- **Context & References:** Relevant paths (`core/db.py`, `automation/browser.py`, `utils/ssrf_guard.py`).
- **Known Gotchas:** Zero em dashes, zero hardcoded PII, single-attempt login, SSRF checks.
- **Validation Gates:** Exact commands required to verify success.

### Step 2: Implement with Progressive Validation
1. Create interface and dataclasses.
2. Implement core logic with graceful error handling.
3. Run intermediate tests after each logical block.

### Step 3: Run the Quality Gate
Execute the comprehensive verification pipeline:
```bash
tools/quality_gate.sh
```
All 5 automated checks (PII, SSRF, Linter, Python 3.15, Test Suite) must exit 0.
