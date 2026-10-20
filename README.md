# CareerPilot AI

<img src="assets/mascot/pip_flight_loop.gif" alt="Pip" width="120" />

A local-first automation framework for job discovery, candidate fit evaluation, and ATS form application.

[![Python](https://img.shields.io/badge/python-3.15%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

## Features

- **Multi-Board Job Discovery**: Scrapes and normalizes listings across major ATS platforms (Greenhouse, Lever, Ashby, Workday).
- **Zero-Token Local Prefiltering**: Filters exclusions (e.g. Java backend, internships) and scores candidate skills locally on CPU before calling external APIs.
- **Headed Browser Automation**: Automates form entry and resume uploads with Playwright while keeping the browser open for human verification.
- **Centralized Q&A Semantics**: Evaluates screening questions against candidate profile rules and local knowledge base with persistent SQLite response caching.
- **Application Tracking**: Maintains bi-directional synchronization between `job_search_tracker.csv` and local SQLite `jobs.db`.
- **Data Sovereignty**: Credentials and personal details stay in gitignored local configuration (`.env`).

---

## Quickstart

### 1. Fork and clone

> **Privacy Warning**: GitHub forks of public repositories are public by default. While personal credentials are kept in gitignored `.env`, personal data should never be committed into tracked files. Refer to [SETUP.md §8](SETUP.md#8-pulling) for instructions on using a private remote repository.

```bash
gh repo fork ankitsingh99/CareerPilot-AI --clone
cd CareerPilot-AI
```

### 2. Environment Setup

Requires Python 3.15+:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### 3. Configure Profile

Copy the environment template and fill in your details:

```bash
cp .env.example .env
```

Instantiate localized workspace files from `.env`:

```bash
python tools/generate_workspace_from_master.py
```

---

## Usage

### Run Easy Apply Automation

```bash
python tools/linkedin_easy_apply_runner.py 5 --location "India"
```

### Apply via Universal ATS Runner

```bash
python tools/ats_runner.py --url "<JOB_URL>" --mode apply
```

### Poll Target Job Boards

```bash
python discovery/poll_mdm_companies.py
```

### Sync Application Tracker

```bash
python tools/sync_tracker.py
```

---

## Testing

Run the test suite:

```bash
pytest tests/
bash tools/quality_gate.sh
```

---

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for details.
