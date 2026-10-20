---
name: agent-reach-research
description: Uses Agent Reach capabilities to perform deep company research, parse job postings with Jina Reader, and scrape social media for interview prep.
---

# Agent Reach Intelligence Gatherer

This skill integrates the `agent-reach` toolkit to execute zero-token, deep-research workflows *before* generating cover letters or preparing for interviews.

## 1. Web Parsing (Job Descriptions & Career Pages)
Instead of relying on fragile Playwright scripts or raw `curl` that dumps HTML tokens, **ALWAYS use Jina Reader via Agent Reach** for plain webpages and job descriptions:
```bash
curl -s "https://r.jina.ai/https://example.com/job-posting"
```
This converts the page into clean Markdown, optimizing token usage.

## 2. Company "Social Listening" (Pre-Cover Letter)
Before writing a cover letter, gather insider intelligence on the company's tech stack, culture, and recent news.
- **Exa Search (Web)**: Search for the company's latest news or tech blogs.
  ```bash
  mcporter call exa.web_search_exa query="<Company Name> engineering blog or news" numResults=3
  ```
- **GitHub**: Search the company's open source projects to understand their tech stack.
  ```bash
  gh search repos --owner <company_github_org> --limit 5
  ```
- **Reddit / V2EX (Culture & Interviews)**: Search for employee experiences and past interview questions.
  ```bash
  opencli reddit search "Interview at <Company>" -f yaml
  ```

## 3. Hiring Manager Outreach (LinkedIn)
If the user requests a personalized cold email or LinkedIn message, use Agent-Reach's LinkedIn MCP to fetch the profile of the hiring manager:
```bash
mcporter call linkedin.get_person_profile linkedin_username="<username>"
```

## 4. Execution Directives
- **Zero-Config Priority**: Jina Reader (`r.jina.ai`), GitHub (`gh`), and Exa (`mcporter`) are zero-config and should be used as the primary data-gathering methods.
- **Failover Strategy**: If a specific platform (e.g., LinkedIn) fails or requires credentials not yet configured, fail gracefully and fall back to Exa Search or Jina Reader.
- **Integration with Profile**: Inject the gathered insights (e.g., matching the candidate's PySpark/Airflow skills with the company's newly open-sourced data tool) into the `humanized-professional-writer` skill to generate a hyper-personalized cover letter.
