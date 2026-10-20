# Continuous Application Learning & Self-Adaptation Directive

## 1. Core Principle & Objective
The agent MUST continuously learn, generalize, and self-adapt from every job application encountered across all ATS platforms (Greenhouse, Workday, Taleo, Lever, Ashby, SuccessFactors, Phenom, SmartRecruiters, iCIMS, Oracle HCM, custom portals).

Whenever a new question, screening prompt, dropdown selection, behavioral scenario, or portal-specific quirk is encountered:
1. **Analyze & Match**: Map the question to the candidate's core profile, past verified responses, and explicit user rules.
2. **Persist & Register**: Record the question pattern, category, and standard response in the centralized QA Knowledge Base (`user_inputs/application_qa_knowledge_base.json` and `user_inputs/candidate_preferences_and_rules.md`).
3. **Self-Adapt for Future Applications**: In all future applications across any company or ATS, automatically look up previously learned answer patterns and apply them seamlessly without requiring user clarification or making repetitive decisions.

---

## 2. File Upload vs. Manual Entry Hierarchy (Strict Rule)
- **Direct File Attachment Mandatory**: ALWAYS attach and upload the master CV PDF (dynamically resolved from `CANDIDATE_MASTER_RESUME` in `.env` / latest `cv/*.pdf`) and tailored Cover Letter (DOCX/PDF) directly via the file chooser input.
- **Manual Text Entry Forbidden if Upload Exists**: NEVER paste raw text into manual entry textareas ("Enter manually") for Resume or Cover Letter unless the portal strictly lacks a file upload mechanism or file upload is completely unsupported.

---

## 3. Learned Question Patterns & Standard Responses

### A. Experience & Seniority
- **Total Experience**: 3.8+ years (from March 2022 to Present across TresVista, ZS Associates, and Rush by Kira).
  - When options are bucketed (e.g., `< 8 years`, `3-5 years`): Select the matching bucket (`Less than 8 years` or `3–5 years`).
- **People Management Experience**: 1–2 years formal people management (led a team of 4 at ZS Associates managing data standardization, vendor deliverables, and operational SLAs).
  - Management description: "Directly managed a team with responsibility for goal setting, coaching, performance reviews, feedback, development plans, and overall team delivery."
- **VP Level Ineligibility**: Candidate is NOT eligible for VP / Vice President roles. Exclude all VP positions from job searches and applications.

### B. Operations, Support & Technical Capabilities
- **Operational Excellence & Process Improvement**: "Led process improvements that enhanced agent productivity, resolution quality, automation, workflows, or customer experience."
- **Agent Enablement, Knowledge & SOPs**: "Identified knowledge gaps and improved SOPs, Help Center content, workflows, decision trees, tooling, and agent enablement based on support trends."
- **Launch Support & Readiness**: "Owned support readiness for launches, including workflows, SOPs, tooling, automation, training, escalation paths, and agent preparedness."
- **Root Cause Analysis (RCA)**: Reduced production server discrepancies and data failures by 99% (Super Innova Award at ZS Associates); built autonomous dispute and reconciliation agents recovering ₹150,000+ at Rush by Kira.

### C. Compensation & Notice Period
- **Current CTC**: ₹18,00,000 INR (18 LPA).
- **Expected CTC**: ₹28,00,000 INR (28 LPA).
- **Notice Period / Availability**: `Currently serving notice or Immediately available to join` / `0-15 days` / `Immediate`.

### D. Logistics, Location & Work Model
- **Delhi / NCR Alignment**: `Yes, I am already in Delhi/NCR` (Candidate is located in Noida / Delhi NCR).
- **Relocation**: `Yes` (Open to relocation to Gurugram, Bengaluru, Hyderabad, Mumbai, or International).
- **Hybrid Work Model**: `Yes` (Fully comfortable with hybrid 3 days/week or onsite).
- **Global / US Overlapping Hours**: `Yes, I am comfortable`.
- **Business Travel & Flexible Shifts**: `Yes` (up to 25%).

### E. Legal, Sponsorship & Background
- **Work Authorization (India)**: Yes, lawfully authorized to work in India.
- **Visa Sponsorship Required**: No (for Indian entities).
- **Non-Compete / Non-Solicit Restrictions**: No.
- **GDPR / Privacy Consent**: Always agree / opt-in.
- **Talent Community / Job Alerts**: Always opt-in.
- **Source / Referral**: `Career Website` / `Company Website`.

---

## 4. Automatic Self-Adaptation Protocol
Before filling any form field or submitting any application:
1. Check `user_inputs/application_qa_knowledge_base.json` for matching keywords/regex.
2. If exact or high-confidence semantic match exists, populate the form with the recorded standard answer.
3. If a novel question is encountered, formulate the most truthful, profile-aligned answer based on this rule, apply it to the form, and append the new Q&A pair to `user_inputs/application_qa_knowledge_base.json`.
4. Document the resolution in `pre_submit_audit.md`.

---

## 5. LinkedIn Easy Apply - Learned Q&A Patterns (2026-10-15)

### F. Social Profile Links
- **LinkedIn Profile URL**: Loaded dynamically from `.env` (`CANDIDATE_LINKEDIN_URL`)
  - Patterns: "LinkedIn profile", "LinkedIn URL", "LinkedIn link", "your LinkedIn", "social profile"

### G. Employee Referral / Relationship Disclosure
- **"Do you have a personal relationship with a current employee?"**: `No`
- **"What is the employee's name?"** (follow-up): Leave blank or enter `N/A`
  - Patterns: "personal relationship with a current employee", "know anyone at the company", "employee referral", "do you have a referral"

### H. Recruitment Data Consent / Privacy
- **"Do you agree to [Company]'s use of personal data from your application to improve our recruitment experience?"**: `Yes`
  - Patterns: "use of personal data", "personal data from your application", "improve our recruitment experience", "data consent", "privacy consent"
  - Rule: Always agree/opt-in to recruitment data consent questions.

