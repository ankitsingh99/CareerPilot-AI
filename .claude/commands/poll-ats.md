# /poll-ats

Polls 2,000+ direct company ATS job boards (Greenhouse, Lever, Ashby, SmartRecruiters) using high-speed JSON APIs.

## Instructions
1. Run the board poller:
   `python3 tools/poll_boards.py --limit 100`
2. Sync discovered matching opportunities into `jobs.db` and tracker:
   `python3 core/db.py`
3. Present newly discovered high-match positions to the candidate.
