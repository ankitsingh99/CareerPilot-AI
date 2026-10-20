# /connect - Recruiter Connection Automator

Generate a highly tailored LinkedIn connection note for recruiters, hiring managers, or peers. 

## Execution Steps

1. Parse the input for the target company and the target person's role or name (e.g. `/connect "Rush by Kira" "Hiring Manager"` or `/connect "ZS Associates"`).
2. Read `.claude/skills/job-application-assistant/01-candidate-profile.md` for context on your core experience.
3. Determine your public resume URL from `CLAUDE.md` or `.claude/skills/job-application-assistant/08-application-qa.md` (e.g. LinkedIn profile link).
4. Draft a connection note exactly following these rules:
   - **Must be strictly under 300 characters** (LinkedIn's hard limit).
   - Lead with "Hi" or "Hello". Do not use "Dear Sir/Madam".
   - Briefly state your identity (e.g. "Hi, I'm Ankit — 5-yr Data Engineer & AI Consultant shipping autonomous agents and data pipelines.").
   - Mention the target company or interest (e.g. "Would love to connect regarding opportunities at [Company].").
   - Ensure the pitch aligns with the user's focus on Data Engineering, AI Agent Automation, and Analytics.
   - Include the profile or resume URL at the end.
5. Output the note in a code block so it can be easily copied.
6. Provide a clickable LinkedIn people search URL for the target company and role so the user can find the recruiter immediately:
   `https://www.linkedin.com/search/results/people/?keywords=<url-encoded "<Company Name> <Role>">&origin=GLOBAL_SEARCH_HEADER`
