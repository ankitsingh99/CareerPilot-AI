---
name: ats-discovery
description: >
  Scans 2,000+ direct company ATS job boards (Greenhouse, Lever, Ashby, SmartRecruiters)
  at high speed via public JSON endpoints, bypasses browser bot walls, filters for
  candidate target roles and locations, and synchronizes with the SQLite database.
  Triggers on: /poll-ats, poll ats, poll boards, discover jobs, direct ats search.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(python3 tools/poll_boards.py *), Bash(python3 core/db.py)
---

# Direct ATS Job Discovery Engine

High-speed direct discovery scanning company career boards directly via public REST APIs without browser overhead.

## Capabilities

- **JSON Endpoints**: Greenhouse, Lever, Ashby, SmartRecruiters public board APIs.
- **Speed**: Scans 2,000+ company boards in seconds using parallel thread pools.
- **Precision Filtering**: Matches target roles (Data Engineering, Analytics Engineering, AI Agents, Solutions, Analytics) and location preferences (100% Remote, Delhi NCR, Bangalore, Hyderabad, Pune/Mumbai, India).
- **Salary Extraction**: Automatic parsing of USD ranges and INR (LPA) compensation.
- **SQLite Concurrency State**: Deduplicates against `jobs.db` and syncs with `job_search_tracker.csv`.

## Invocation

Run directly via CLI:
```bash
python3 tools/poll_boards.py --limit 100
```

Or target a specific ATS platform:
```bash
python3 tools/poll_boards.py --ats greenhouse --limit 50
python3 tools/poll_boards.py --ats lever --limit 50
python3 tools/poll_boards.py --ats ashby --limit 50
```

Sync newly discovered jobs to SQLite:
```bash
python3 core/db.py
```
