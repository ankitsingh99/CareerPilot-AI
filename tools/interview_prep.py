#!/usr/bin/env python3
"""
tools/interview_prep.py
-----------------------
Structured Interview Preparation & Technical Simulator.
Generates STAR+R behavioral stories, technical system design probes, red flag defenses,
and reverse interview questions tailored to a specific job opening.

Adapted from career-ops interview-prep.md and interview-redflag.md into
CareerPilot AI universal architecture.
Rule: Zero em dashes permitted. Zero financial cost.
"""

from __future__ import annotations

import argparse
import sys
import re
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.job_evaluator import slugify

INTERVIEW_PREP_DIR = ROOT / "interview_prep"


def generate_interview_kit(company: str, role: str, jd_text: str = "") -> str:
    """Generates comprehensive interview prep markdown."""
    INTERVIEW_PREP_DIR.mkdir(parents=True, exist_ok=True)
    today_str = datetime.now().strftime("%Y-%m-%d")
    jd_lower = (jd_text or "").lower()

    # Detect primary technical themes
    has_spark = "spark" in jd_lower or "pyspark" in jd_lower
    has_airflow = "airflow" in jd_lower or "orchestration" in jd_lower
    has_snowflake = "snowflake" in jd_lower or "warehouse" in jd_lower or "redshift" in jd_lower
    has_ai = "agent" in jd_lower or "llm" in jd_lower or "ai" in jd_lower

    md = f"""# Interview Preparation Brief: {company} - {role}

**Date Generated:** {today_str}
**Target Organization:** {company}
**Target Role:** {role}
**Candidate Persona:** Business & Technology Consultant | Data Engineering & Analytics (4.8 YOE)

---

## 1. Behavioral & Leadership (STAR+R Stories)

### Story 1: Handling Production Pipeline Outages / Bottlenecks
- **Situation:** A mission-critical analytics pipeline stalled during month-end reporting due to skewed data volume.
- **Task:** Diagnose the failure root-cause, restore pipeline SLA, and prevent recurrence without data loss.
- **Action:** Traced task execution logs in Airflow, identified data skew on join keys, optimized partitioning in PySpark, and implemented dynamic task timeout retries.
- **Result:** Cut pipeline latency by 45% and eliminated month-end batch SLA breaches.
- **Reflection:** Emphasize that monitoring data distribution early is as critical as monitoring memory and CPU metrics.

### Story 2: Cross-Functional Client / Stakeholder Alignment
- **Situation:** Business stakeholders requested ad-hoc data extracts with conflicting definitions of revenue KPIs.
- **Task:** Standardize KPI definitions across departments and build self-service data models.
- **Action:** Led discovery sessions with commercial teams, authored a unified metric dictionary, and built curated Snowflake dimensional tables.
- **Result:** Decreased ad-hoc report requests by 60% and achieved single-source-of-truth alignment across leadership.
- **Reflection:** Clear semantic definitions prevent technical rework faster than raw query optimization.

---

## 2. Technical Probes & Deep-Dive Preparation

### Core Technical Focus Areas
"""

    if has_snowflake:
        md += """- **Snowflake Architecture & Query Tuning:**
  - *Probe:* How do you diagnose query profile bottlenecks in Snowflake?
  - *Response Strategy:* Discuss warehouse sizing, clustering keys for micro-partition pruning, search optimization service, and avoiding spill to local/remote storage.
"""

    if has_airflow:
        md += """- **Airflow DAG Design & Reliability:**
  - *Probe:* How do you structure production DAGs to handle backfills and idempotency?
  - *Response Strategy:* Explain deterministic execution dates, task atomicity, custom sensors, connection pooling, and error alerting webhooks.
"""

    if has_spark:
        md += """- **PySpark & Distributed Data Processing:**
  - *Probe:* How do you resolve memory OOM and shuffle failures in Spark?
  - *Response Strategy:* Highlight broadcast joins for dimension tables, adaptive query execution (AQE), salted join keys for severe skew, and tuning executor memory overhead.
"""

    if has_ai:
        md += """- **AI Agent Automation & LLM Integration:**
  - *Probe:* How do you ensure accuracy and cost control in agentic pipelines?
  - *Response Strategy:* Detail local heuristic pre-filtering, token-lean caching, schema validation gates, and fallback models with strict zero-cost budgeting.
"""

    if not (has_snowflake or has_airflow or has_spark or has_ai):
        md += """- **Data Engineering Fundamentals:**
  - *Probe:* Walk through your approach to modern ETL/ELT architecture design.
  - *Response Strategy:* Cover schema-on-write vs schema-on-read, medallion architecture (bronze, silver, gold), automated testing, and SLA monitoring.
"""

    md += f"""
---

## 3. Red Flag Defenses & Objection Handling

1. **"Why are you looking to move from your current engagement?"**
   - *Strategic Framing:* "I have built strong foundational consulting and engineering rigor across healthcare analytics and retail operations. I am now seeking a dedicated technical data engineering role where I can deepen long-term architectural ownership and scale data infrastructure."
2. **"How do you handle ambiguous requirements?"**
   - *Strategic Framing:* "In technology consulting, requirements are rarely handed down fully formed. I build rapid proof-of-concept pipelines, align with stakeholders on draft outputs, and iterate rapidly rather than guessing in isolation."

---

## 4. Reverse Interview Questions (Questions to Ask the Interviewer)

1. *"What does the current deployment and CI/CD workflow look like for data pipelines, from local development to production?"*
2. *"What is the single biggest architectural bottleneck or data reliability challenge the team is working through this quarter?"*
3. *"How does the engineering team balance technical debt remediation with business feature delivery?"*
4. *"How is success evaluated for this role over the first 90 to 180 days?"*
"""

    out_file = INTERVIEW_PREP_DIR / f"{slugify(company)}_{slugify(role)}_prep.md"
    out_file.write_text(md, encoding="utf-8")
    return str(out_file)


def main():
    parser = argparse.ArgumentParser(description="Generate tailored interview preparation brief")
    parser.add_argument("--company", "-c", required=True, help="Company name")
    parser.add_argument("--role", "-r", required=True, help="Role title")
    parser.add_argument("--file", "-f", help="Optional path to job description file")
    args = parser.parse_args()

    jd_text = ""
    if args.file and Path(args.file).is_file():
        jd_text = Path(args.file).read_text(encoding="utf-8", errors="ignore")

    path = generate_interview_kit(args.company, args.role, jd_text)
    print(f"\n[✓] Tailored Interview Kit successfully generated:")
    print(f"    {path}\n")


if __name__ == "__main__":
    main()

