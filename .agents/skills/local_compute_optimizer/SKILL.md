---
name: local-compute-optimizer
description: Maximizes local machine compute (Python, Playwright, Poppler, SQLite) to offload data filtering, PDF validation, ATS form filling, and job ranking, reducing LLM token consumption by 80-85%.
---

# Local Compute Optimizer Skill

This skill maximizes the use of local CPU, Python scripts, Playwright, and local SQLite/CSV databases to perform data processing, filtering, validation, and browser automation locally before or instead of calling LLM models.

## Local Compute Offloading Matrix

| Workflow Step | Local Machine Tool / Script | Token Impact |
| :--- | :--- | :--- |
| **Job Discovery** | `.agents/skills/*` CLIs & `tools/poll_boards.py` | 100% Zero-Token (Local HTTP/API & JSON parsing) |
| **Job Pre-Filtering** | `add-on_skills/local_compute_optimizer/tools/local_prefilter.py` | 100% Zero-Token (Local TF-IDF & Regex filtering) |
| **Fit Pre-Scoring** | `add-on_skills/local_compute_optimizer/tools/local_prefilter.py` | Hybrid (Filters <65% fit locally; LLM scores remaining) |
| **PDF & Layout Validation** | `tools/verify_pdf.py` & `tools/verify_layout.py` | 100% Zero-Token (Poppler CLI & pdfinfo parsing) |
| **ATS Form Autofill** | `tools/ats_runner.py` (Playwright) | 90% Zero-Token (Fills common fields from `client_secret.json`) |
| **Tracker & DB Management** | `tools/db_state.py` & `tools/audit_record.py` | 100% Zero-Token (Local SQLite & CSV mutations) |
| **OpenRouter LLM Requests** | `tools/openrouter.py` | 80-90% Token Reduction (Input trimming, prompt caching layout, max output caps, zero-cost :free models) |

## Quickstart Commands

```bash
# 1. Run local pre-filtering & TF-IDF match on scraped jobs (Zero-Token)
python add-on_skills/local_compute_optimizer/tools/local_prefilter.py --input raw_jobs.json --output qualified_jobs.json

# 2. Verify compiled PDF layout locally without LLM overhead (Zero-Token)
python tools/verify_pdf.py cv/Ankit_Resume_v3.pdf --min-chars 100 --pages 2

# 3. Auto-fill ATS application form using Playwright locally (90% Token Reduction)
python tools/ats_runner.py --url "<JOB_URL>" --role-name "<ROLE>" --mode apply

# 4. Run token-optimized OpenRouter request with input trimming & max_tokens cap
python tools/openrouter.py "Summarize requirements" --max-tokens 300 --json
```
