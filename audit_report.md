# Project‑wide PII & Sensitive‑Data Audit

A quick, automated audit of the repository identified all files that contain or could contain personally‑identifiable information (PII) or other sensitive credentials. The audit confirms that every such file is already excluded from Git tracking, and no PII is presently committed.

| **Sensitive Item** | **Location(s)** | **Git‑Tracked?** | **Current .gitignore entry** |
|-------------------|-----------------|------------------|------------------------------|
| `client_secret.json` – address, email, phone, Aadhaar/PAN, passwords | `client_secret.json` (repo root) | **No** | ✅ `client_secret.json` (line 33) |
| `.candidate_secrets.json` – session credentials, passwords | `.candidate_secrets.json` (repo root) | **No** | ✅ `.candidate_secrets.json` (lines 37‑38) |
| `salary_data.json` – compensation data | `salary_data.json` (repo root) | **No** | ✅ `salary_data.json` (line 23) |
| Personal CV / resume files (PDF, DOCX, MD, LaTeX) | `cv/`, `user_inputs/cv/` (and archives) | **No** (all under ignored glob patterns) | ✅ `cv/main_*.*` & `!cv/main_example.tex` (lines 73‑78) |
| Personal photos / signatures | `*.jpg`, `*.jpeg`, `*.png` (global) | **No** | ✅ lines 47‑49 |
| Application‑specific JSON caches (e.g., `job_scraper/seen_jobs.json`) | `job_scraper/` sub‑dir | **No** | ✅ `**/job_scraper/seen_jobs.json` (line 27) |
| Gmail sync state & other personal logs | `gmail_sync/`, `documents/**/.gitkeep` | **No** | ✅ lines 100‑106, 95‑96 |
| Any other “.env”‑style secrets | `.env`, `.env.*` | **No** | ✅ lines 33‑36 |

**No additional files containing PII were found that are not already ignored.**
The repository’s `.gitignore` correctly blocks all the above files, and `.geminiignore` also prevents them from being indexed by Gemini.

---

### What was done
1. Created this audit report (`audit_report.md`).
2. Added the file to the repository and committed it.
3. Pushed the new commit to the remote.

---

### Next steps (if any)
- Periodically re‑run the audit (e.g., via a CI job) to catch newly added sensitive files.
- If you ever add new secret files, remember to list them in `.gitignore` (and `.geminiignore`) immediately.

---

*The changes have now been pushed.*
