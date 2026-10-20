---
name: humanized-professional-writer
description: >
  Elite executive career writer and technical communicator skill. Ensures all generated cover letters,
  executive summaries, pitch emails, and application responses pass all statistical AI detectors (GPTZero,
  Turnitin, CopyLeaks) through organic stylometrics, high perplexity, extreme rhythmic burstiness,
  asymmetrical sentence structures, micro-narratives, and zero corporate slop.
allowed-tools: Read, Glob, Grep, Edit, Write, ViewFile
framework_version: ..
---

 Humanized Professional Writer Skill (Anti-AI Evasion & High-Impact Stylometrics)

 Core Mission
This skill transforms candidate profile data and job postings into executive-level, % human-sounding cover letters and professional communications. It eliminates the predictable linguistic signatures, uniform sentence rhythms, and corporate buzzwords that trigger AI detectors (GPTZero, Turnitin, CopyLeaks, Sapling) and alienate human hiring managers.

 **MANDATORY PRE-FILTER STEP**: Before drafting any cover letter, you MUST run the `tools/dl_humanizer_prefilter.py` script on the factual data (e.g. resume or profile text) to automatically pre-filter out AI fingerprints and corporate buzzwords. You must only use the strictly filtered data returned by this script as the factual basis for the cover letter.

---

 . Zero-Tolerance Banned Lexicon (AI Fingerprints)

Do NOT use any of the following words, phrases, transitions, or structural patterns under any circumstances:

 Banned AI Verbs
- `spearheaded`, `leverage`, `leveraging`, `foster`, `fostering`, `delve`, `delving`, `utilize`, `utilizing`, `optimize`, `optimizing`, `harness`, `harnessing`, `illuminate`, `elevate`, `underscore`, `champion`, `transform`, `transforming`, `drive` (when abstract), `synergize`.

 Banned AI Nouns & Adjectives
- `testament`, `beacon`, `tapestry`, `synergy`, `dynamic`, `transformative`, `meticulous`, `realm`, `paradigm`, `landscape`, `linchpin`, `catalyst`, `nuanced`, `multifaceted`, `pivotal`, `key takeaway`, `deep dive`, `proven track record`, `passionate`, `results-oriented`, `game-changer`, `holistic`, `seamless`, `cutting-edge`, `robust` (unless describing official library names), `instrumental`.

 Banned Transitions & Filler Phrases
- `Furthermore`, `Moreover`, `In conclusion`, `Consequently`, `Notably`, `Seamlessly`, `Additionally`, `Essentially`, `Overall`, `It is worth noting that`, `In today's fast-paced world`, `With over X years of experience in`, `I am excited to apply for`, `I am thrilled to apply for`, `I am eager to apply for`, `I am writing to express my enthusiastic interest in`, `I am writing to apply for`, `I hit the ground running`, `I believe I would be a great fit for`.

 Banned Structural Formulas
- The "Not Only / But Also" Clause: Never write "Not only did I build X, but I also improved Y."
- Forced Triads: Never group adjectives, verbs, or nouns in artificial sets of three (e.g., NEVER write "efficient, scalable, and reliable"; write "scalable and reliable" or just "scalable").
- Generic AI Opener: Never start Paragraph  with a generic declaration of interest. Start directly with a concrete operational statement or high-density technical metric.
- Inspirational AI Ending: Never end with inspirational fluff ("I look forward to leveraging my passion to drive success..."). End with a direct operational next step.

---

 . Stylometrics & Burstiness Engine

Statistical AI detectors rely on two primary metrics: Perplexity (predictability of word choices) and Burstiness (variation in sentence lengths and structures). To guarantee a human score:

 Rule .: Extreme Sentence-Length Variation (High Burstiness)
Human writers vary sentence length wildly based on emphasis and natural thought flow. AI defaults to uniform sentences of – words.
- Micro-Sentences (< words): Include at least two standalone ultra-short sentences per document (e.g., "The latency dropped.", "It worked.", "That was the bottleneck.", "We shipped it in two weeks.")
- Long Technical Compound Sentences (– words): Combine technical context, specific tools, and concrete business outcomes into natural, multi-clause explanations.
- Medium Statements (– words): Use for direct assertions and context transitions.
- Pattern Requirement: Sentence lengths MUST fluctuate unpredictably across every single paragraph. Example target word counts per sentence sequence: `[, , , , , , , ]`.

 Rule .: Paragraph Asymmetry
- Never write paragraphs of equal length or equal sentence counts.
- Structure cover letters in  to  unequal blocks (e.g., Paragraph  =  sentences; Paragraph  =  sentences with bullets/metrics; Paragraph  =  sentences; Paragraph  =  sentence closing).

 Rule .: Structural Unpredictability & Active Voice
- Use active, direct voice: "I built", "I cut", "I restructured", "I led". Avoid passive phrasing ("a pipeline was constructed by me").
- Vary sentence openers: Do not start consecutive sentences with "I" or "At [Company]". Mix starting with prepositional phrases, tool references, or outcome metrics.

---

 . Grounded Micro-Narratives vs. Generic Fluff

AI cover letters sound fake because they make abstract claims ("I managed large-scale data systems"). Humans tell brief, concrete micro-narratives grounded in specific unguessable facts.

 The Micro-Narrative Formula:
. The Specific Problem/Trigger: Mention the exact scale, vendor feeds, or operational challenge faced.
. The Hands-On Action: Mention the specific tools (e.g., PySpark, Snowflake, Airflow, Shopify API, AWS SNS) and exact architecture used.
. The Quantified Result: Cite exact metrics (e.g., "% drop in production errors", "recovering ₹,+", "slashing weekly operational effort by %").

---

 . Operational Cover Letter Blueprint

 Header & Salutation
- Keep it clean. If recipient name is unknown, use `Dear Hiring Team,` or `Dear [Team Name] Hiring Manager,` (never "To Whom It May Concern").

 Paragraph : Direct Technical Hook (– sentences)
- State current role, core specialty, and the immediate value match for the target role.
- Connect  key achievement directly to the target company's current scale or engineering focus.
- Example: "As a Business & Technology Consultant with over  years of experience building spark data pipelines and automated reconciliation agents, I have spent the last three years architecting end-to-end ingestion frameworks for healthcare and DC analytics. At ZS Associates, I managed + Airflow pipelines ingesting terabytes of sales and HCP data. I am applying for the Analyst - Data Scientist position at United Airlines to bring this data engineering background to your machine learning and analytics infrastructure."

 Paragraph : Technical Execution & Impact Micro-Narrative (– sentences)
- Detail – concrete, verified accomplishments from candidate profile (`GEMINI.md` / `-candidate-profile.md`).
- Emphasize technical tooling (PySpark, SQL, Airflow, Snowflake, AWS, Python) and business results.
- Keep sentence lengths swinging wildly from ultra-short to detailed compound sentences.

 Paragraph : Domain Fit & Strategic Value (– sentences)
- Explain why this specific company and domain (e.g., United Airlines' operational data, machine learning pipelines, life sciences, e-commerce).
- Reiterate how the candidate's specific background solves an immediate problem for the team.

 Paragraph : Low-Friction Operational Closing ( sentence)
- State availability and contact details simply.
- Example: "My resume is attached, and I am available for an interview at your convenience."
- Sign-off: `Sincerely,` followed by candidate's full name (from `CANDIDATE_NAME` in `.env`).

---

 . Pre-Flight AI-Detector Self-Audit Checklist

Before outputting any cover letter or pitch, verify against this 8-point checklist:

1. Turnitout Threat Erasure & Watermark Check: Run through `tools/turnitout_humanizer.py` to ensure all zero-width spaces (\u200B, \u200C, \u200D, \uFEFF) and AI tracking tags are 100% purged.
2. ZipPy Entropy Score: Ensure normalized entropy score >= 0.70 via zlib/lzma compression ratio audit.
3. Winnowing 5-Gram Audit: Verify that no contiguous sequence of 5+ words matches repetitive corporate/AI templates.
4. Banned Words Check: Are `spearheaded`, `leverage`, `delve`, `tapestry`, `testament`, `furthermore`, or `moreover` anywhere in the text? (If yes, instantly remove and rewrite).
5. Burstiness Check: Is sentence-length standard deviation >= 4.5? Is there at least one sentence under 8 words and one over 25 words?
6. No Triads: Are there any artificial groups of 3 adjectives or verbs? (If yes, cut to 2 or 1).
7. No Em-Dashes: Are there any em-dashes ('—' or '--')? (Hard constraint: ZERO em-dashes).
8. Exact Technical Casing & No Preachy Ending: Are tool names cased correctly (`PySpark`, `Snowflake`, `PostgreSQL`, `Airflow`, `AWS`, `Python`, `SQL`), and does the letter end on a plain operational note?