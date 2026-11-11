# Outreach Training Corpus & Style Patterns

This reference distills the verified structure, tone, and constraints learned from the candidate's past successful cover letters, referral requests, LinkedIn DMs, and HR outreach emails.

---

## 1. LinkedIn Referral Request (High-Converting Short Pattern)

**When to use:** Messaging an employee at a target company for a referral with a live job posting URL.  
**Structure (75 to 95 words):**
1. Warm greeting (`Hope you are doing well!` or `Hi <FirstName>, hope you are doing well!`)
2. Role + top 2 to 3 matched stack keywords + direct referral ask (`I saw <Company> is hiring for a <Role> (<Stack>) and wanted to check if you would be open to referring me.`)
3. 1-sentence domain & stack fit anchored in verified resume experience (`ZS Associates`, `Rush by Kira`, exact metrics)
4. `Role link: <URL>`
5. Low-friction closing (`Happy to share my CV if you would like to take a quick look. Thanks!`)

**Reference Pattern:**
```text
Hope you are doing well!
I saw <Company> is hiring for a <Role> (<Top 3 Matched Skills>) and wanted to check if you would be open to referring me.

I have <YOE> years of data engineering experience across <Matched Stack>, including <Verified Company + Domain Pipeline Impact>.

Role link: <URL>

Happy to share my CV if you would like to take a quick look. Thanks!
```

---

## 2. LinkedIn Direct Message (Post Reply / Hiring Lead)

**When to use:** Replying to a LinkedIn hiring post (e.g., MDM / Data Governance, Brand & Patient, Analytics Lead) where you are sending a regular message, not a long InMail.  
**Rules learned from feedback:**
- Do NOT write "I am an immediate joiner (0 days notice)" in cold peer DMs — it can sound desperate. Save notice period for HR forms/emails or when requested.
- Use confident domain terminology matching the post (e.g., `patient journeys`, `sales`, `claims`, `NPP data`, `HCP/HCO`, `Snowflake`, `HIPAA`).
- Keep it to 3 to 5 lines max.

**Reference Pattern (Domain Peer Voice):**
```text
Hey <FirstName>,

Saw your post for the <Role> opening at <Company>. I have <YOE> years across <Matched Tools>, including <Relevant Domain Story at Verified Employer>.

Happy to share my CV or connect briefly if this aligns with what your team is looking for.
```

---

## 3. Recruiter / HR Outreach Email (Soft Opener + Technical Depth)

**When to use:** Sending an email application directly to a recruiter, HR contact, or director (e.g., Dr. Morepen Home, Indegene).  
**Rules learned from feedback:**
- **Opener (`--tone soft`):** Keep the greeting warm and polite (`Hope you are having a good week. I came across your post for... and wanted to share my profile for your consideration.`). NEVER use dramatic AI truisms (`Rapid X comes down to Y and Z.`) or summarize the company's own business back to them.
- **Technical Elevation:** Even for a Business Analyst title, frame the candidate's upper hand clearly: predictive modeling, Scikit-learn anomaly checks, automated PySpark/Snowflake/Airflow pipelines, cohort analytics, and webhook AI automation — without ever overstretching beyond real CV work.
- **Structured Details:** If the job post explicitly asks for `Total exp / Current CTC / Expected CTC / Location / Notice period`, include that scannable block right before sign-off (pulling dynamically from `.env`).
- **Bullets:** Limit to 2 or 3 crisp bullets with verified employer names (`Rush by Kira`, `ZS Associates`, `TresVista`) and exact metrics (`40%`, `35%`, `25%`, `15%`, `30%`, `15+`, `8+`).

---

## 4. Lessons Learned from Historical Cover Letters

Auditing prior cover letters (`Axtria`, `dunnhumby`, `BCG`, `UnitedHealth`) established these strict non-regression rules:
1. **No Dangling Operators:** Always ensure quantified percentages and `+` counts render completely (`40%`, `15+`, never `by %` or `over  Airflow`).
2. **Zero AI Clichés:** Never output `spearheaded`, `leveraged`, `delve`, `synergy`, `testament`, `fostered`, `pivotal`, `seamlessly`, `robust`, `holistic`, `cutting-edge`, or `thrilled to apply`.
3. **Zero Em Dashes (`—`):** Always use standard hyphens (`-`), commas, or colons.
4. **No Excluded Technologies:** Never claim `Java`, `Spring Boot`, `J2EE`, or production `Kubernetes`/`Docker` DevOps.
5. **High Sentence Burstiness:** Mix ultra-short assertions with detailed technical compound sentences, avoiding repetitive 3-item triads.

