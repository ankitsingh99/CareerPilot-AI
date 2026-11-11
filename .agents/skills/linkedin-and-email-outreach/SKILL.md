---
name: linkedin-and-email-outreach
description: >-
  Generates JD-matched LinkedIn referral requests, recruiter/hiring-manager direct
  messages, <=300-char connection notes, and cold application emails grounded strictly
  in the candidate's verified CV and past outreach style. Use when the user asks to
  draft a LinkedIn referral DM, reply to a hiring post, or email a recruiter/HR lead.
framework_version: 1.2.0
---

# LinkedIn & Email Outreach Skill

Builds tailored, zero-slop outreach messages anchored in live job descriptions, company intelligence, and verified candidate records loaded dynamically from `.env` and `cv/`.

Refer to [outreach_examples.md](./references/outreach_examples.md) for the exact stylistic patterns trained on historical referrals, post replies, emails, and cover letters.

---

## Workflow Steps

### 1. Ingest Role & Research Context
- **Job URL provided:** Fetch clean markdown safely using Jina Reader (`curl -sL "https://r.jina.ai/<URL>"` or via `tools/contact_pitch.py --url "<URL>"`).
- **LinkedIn post / pasted JD:** Save text to a temporary file or pass context directly alongside `--company` and `--role`.
- **Company intelligence:** Run a targeted web search (`search_web`) for the target team's tech stack, recent initiatives, and domain context (e.g., commercial enablement, field force incentives, D2C dispatch).

### 2. Select Channel & Persona Tone
Choose the matching outreach format:
1. **LinkedIn Referral Request (`--type referral`):**
   - Use for asking an employee for a referral with a posting link.
   - Format: Warm greeting -> Role + top 3 matched skills + direct referral ask -> 1-sentence CV/domain fit -> `Role link: <URL>` -> low-friction CV offer.
2. **LinkedIn Direct Message (`--type dm`):**
   - Use for short post replies or peer messages to hiring leads.
   - Confident peer tone using exact domain jargon (`patient journeys`, `HCP/HCO`, `Snowflake`, `cohort analytics`). Avoid desperate notice-period begging.
3. **LinkedIn Connection Note (`--type invite`):**
   - Hard capped at `<= 300` characters via `tools/contact_pitch_generator.py`.
4. **Application / Recruiter Email (`--type email`):**
   - Default to `--tone soft` (`Hope you are having a good week...`) for warm HR readability paired with crisp, data-science-level technical bullets grounded strictly in the candidate's CV.
   - Pass `--include-hr-fields` if the posting explicitly asks for `Total exp`, `Current CTC`, `Expected CTC`, `Location`, and `Notice period`.

### 3. Generate Draft Using the Reusable Outreach Engine
Always run the universal CLI instead of creating one-off scripts:

```bash
# LinkedIn referral request from a live job URL
.venv/bin/python tools/contact_pitch.py \
  --url "<JOB_URL>" \
  --company "<Company>" \
  --role "<Role Title>" \
  --type referral \
  --save

# Soft HR email with requested experience/CTC details
.venv/bin/python tools/contact_pitch.py \
  --jd-file "<path/to/jd.txt>" \
  --name "<Recipient Name>" \
  --email "<recipient@company.com>" \
  --company "<Company>" \
  --role "<Role Title>" \
  --location "<City>" \
  --type email \
  --tone soft \
  --include-hr-fields \
  --save
```

Generated drafts saved with `--save` land in `documents/*Outreach*.md` (gitignored automatically to protect privacy).

### 4. Mandatory Verification Gate
Before sharing any outreach draft with the user, verify:
1. **Zero AI Slop & Em Dashes:** Confirmed automatically via `parsers.linter.lint_and_format(..., proofread_llm=False)` (`0` em dashes `—`, `0` banned cliches, `0` dangling metrics).
2. **Zero Hallucination & Exclusions:** Confirmed via `core.cv_fact_checker.CVFactChecker.audit_text()` (`0` excluded techs like Java/Spring Boot, exact verified employers/metrics only, zero overstretch of ML/AI years).
3. **OpenRouter Policy:** Executed 100% deterministically on local CPU unless the user explicitly requested OpenRouter.

