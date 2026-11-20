---
trigger: always_on
description: THE MOST FUNDAMENTAL DIRECTIVE - ALWAYS CHECK CAPABILITIES
---

# URGENT AND FUNDAMENTAL DIRECTIVE

**CRITICAL INSTRUCTION FOR ALL MODELS:**
Before you do *anything* else on any task in this tool, you MUST ALWAYS initiate your thought process and execution by explicitly going through:
1. **All Available Skills** (`.agents/skills/*/SKILL.md`, `.agents/plugins/*/skills/*/SKILL.md`, and system-listed skills relevant to the task).
2. **All Active Rules** (`AGENTS.md`, `.agents/rules/*.md`, and `user_inputs/candidate_preferences_and_rules.md`).
3. **All Available Tools & Plugins** (repository CLI modules in `tools/`, `parsers/`, `core/`, `automation/`, MCP servers, and installed plugins) before creating or modifying anything.

This is the MOST FUNDAMENTAL thing you are supposed to do. **NEVER FORGET THIS.** Always verify what rules govern the task and what existing skills/tools are at your disposal before proceeding with any user request.

## COST-INTELLIGENT MODEL ARCHITECTURE & ADAPTIVE PROMOTION DIRECTIVE
**Token-Lean Philosophy:** We aim to be token lean, but this does not mean never using Gemini or higher-reasoning models.
1. **Tier 1 (Chore / Low-Reasoning):** Use cheaper or free models (Ollama local, OpenRouter fast/free models like Nemotron, Gemma, Minimax, or low-cost endpoints) for low-reasoning jobs (regex extraction, basic field mapping, text trimming, initial job triage).
2. **Tier 2 (Frontier / High-Reasoning):** Reserve Gemini (Antigravity Gemini, Gemini Pro / Flash High Reasoning) for high-reasoning jobs (complex ATS screening questionnaires, cover letter authoring and humanization, customized executive outreach, tricky form logic, and debugging).
3. **Adaptive Escalation (User Halts & Mistake Promotion):**
   - Maintain a persistent log and ledger (`user_inputs/user_corrections_log.json` and `core/model_router.py`) tracking where the user has halted, corrected, or guided the agent.
   - If mistakes or user corrections in a task category rise (critical correction >= 1 or recurrence >= 2), the router dynamically escalates and promotes that entire task category to be handled exclusively by the higher-reasoning model (Gemini).
   - Track real-time routing analytics and telemetry via `python tools/model_analytics.py --status`, applying tool-call/JSON output rescue and 429 sliding-window cooldowns.

## OPENROUTER ON-DEMAND INVOCATION DIRECTIVE
**Do NOT use OpenRouter until explicitly asked for by the user.**
Use OpenRouter ONLY if:
1. The user explicitly requests to use OpenRouter (e.g. "use openrouter").
2. The user previously asked to perform a task using OpenRouter and then answers a follow-up question or provides input for that task without explicitly repeating "use openrouter".
In all other scenarios, rely on local deterministic compute and offline parsers.

## GEMINI-EXCLUSIVE COVER LETTER WRITING & HUMANIZING DIRECTIVE
**Exclusively use the active Gemini model (Antigravity Gemini) for writing, rewriting, proofreading, and humanizing cover letters.**
NEVER delegate cover letter drafting, proofreading, or humanizing to non-Gemini models (`cohere/north-mini-code:free`, `qwen2.5:7b` Ollama, `nvidia/*`, `minimax/*`, `deepseek/*`, `flint`, etc.). Run local deterministic tools (`tools/dl_humanizer_prefilter.py`, `parsers/turnitout_engine.py`, `parsers/linter.py`, `tools/validate_cover_letter.py`, `tools/verify_cv_facts.py`) strictly for pre-filtering, watermark/5-gram/ZipPy audits, structural/cliche linting, and factual grounding.

## STRICT RESUME AND COVER LETTER SEPARATION DIRECTIVE (ZERO-TOLERANCE)
**NEVER upload a resume into a cover letter field, and NEVER upload a cover letter into a resume field.**
If an ATS portal has a dedicated Cover Letter file input or section, a tailored, humanized cover letter MUST be generated and validated FIRST using Gemini before automation reaches that upload step. If no tailored cover letter is available, the runner MUST leave the cover letter field blank or pause; under NO circumstances should the master resume ever be substituted into a cover letter input.

## TOKEN-LEAN ARCHITECTURE & STRICT REUSABILITY MANDATE (ZERO-TOLERANCE)
**You must not create py or any kind of script for one single application, only reusable codes are allowed.**
We are on a token-lean architecture where each token matters. NEVER generate or execute throwaway or job-specific application scripts (`apply_<company>.py`, `fix_<job>.py`). All automation logic, locators, and form-handling enhancements MUST be integrated directly into the universal core modules (`tools/ats_runner.py`, `automation/browser.py`, `core/qa_semantics_engine.py`). Individual job runs must ONLY be executed through parameterized reusable engines (e.g. `python tools/ats_runner.py --url "<URL>" --mode apply`).