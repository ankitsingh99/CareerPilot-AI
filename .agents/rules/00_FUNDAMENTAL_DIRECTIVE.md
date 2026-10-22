---
trigger: always_on
description: THE MOST FUNDAMENTAL DIRECTIVE - ALWAYS CHECK CAPABILITIES
---

# URGENT AND FUNDAMENTAL DIRECTIVE

**CRITICAL INSTRUCTION FOR ALL MODELS:**
Before you do *anything* else, you MUST ALWAYS initiate your thought process and execution by explicitly checking all available **SKILLS, TOOLS, and PLUGINS** in your context. 

This is the MOST FUNDAMENTAL thing you are supposed to do. **NEVER FORGET THIS.** Always see what capabilities are at your disposal before proceeding with any user request.

Always use openrouter free models only.

## OPENROUTER ON-DEMAND INVOCATION DIRECTIVE
**Do NOT use OpenRouter until explicitly asked for by the user.**
Use OpenRouter ONLY if:
1. The user explicitly requests to use OpenRouter (e.g. "use openrouter").
2. The user previously asked to perform a task using OpenRouter and then answers a follow-up question or provides input for that task without explicitly repeating "use openrouter".
In all other scenarios, rely on local deterministic compute and offline parsers.

## TOKEN-LEAN ARCHITECTURE & STRICT REUSABILITY MANDATE (ZERO-TOLERANCE)
**You must not create py or any kind of script for one single application, only reusable codes are allowed.**
We are on a token-lean architecture where each token matters. NEVER generate or execute throwaway or job-specific application scripts (`apply_<company>.py`, `fix_<job>.py`). All automation logic, locators, and form-handling enhancements MUST be integrated directly into the universal core modules (`tools/ats_runner.py`, `automation/browser.py`, `core/qa_semantics_engine.py`). Individual job runs must ONLY be executed through parameterized reusable engines (e.g. `python tools/ats_runner.py --url "<URL>" --mode apply`).