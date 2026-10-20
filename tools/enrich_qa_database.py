#!/usr/bin/env python3
"""
Enrich application_qa_knowledge_base.json with comprehensive ATS semantics.
Uses OpenRouter Free Tier models to expand variations for tools, compliance,
compensation, education, and experience questions.

Author: Ankit Kumar Singh
Rule: Zero financial cost (only :free models). Zero em dashes.
"""

import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
KB_PATH = ROOT_DIR / "user_inputs" / "application_qa_knowledge_base.json"

ENRICHED_ENTRIES = [
    # ── Technical Skills (Positive: 4 / 4.8 YOE) ──────────────────────────────
    {
        "category": "technical_tool_experience",
        "question_patterns": [
            "years of experience with Python",
            "experience in Python programming",
            "Python development experience",
            "how many years have you used Python",
            "Python proficiency level",
            "Python scripting and data manipulation"
        ],
        "standard_response": "4",
        "numeric_value": 4.8,
        "notes": "Candidate has 4.8 years of hands-on Python experience for ETL and AI systems."
    },
    {
        "category": "technical_tool_experience",
        "question_patterns": [
            "years of experience with SQL",
            "experience with SQL queries and optimization",
            "Snowflake or PostgreSQL experience",
            "how many years have you worked with SQL databases",
            "SQL performance tuning and ETL queries",
            "Trino or Oracle database experience"
        ],
        "standard_response": "4",
        "numeric_value": 4.8,
        "notes": "4.8 years optimizing complex SQL queries across Snowflake, PostgreSQL, Trino, and Oracle."
    },
    {
        "category": "technical_tool_experience",
        "question_patterns": [
            "years of experience with Apache Airflow",
            "Airflow DAG development experience",
            "workflow orchestration with Airflow",
            "how many years managing Airflow pipelines"
        ],
        "standard_response": "3",
        "numeric_value": 3.2,
        "notes": "Managed 15+ Apache Airflow production pipelines at ZS Associates."
    },
    {
        "category": "technical_tool_experience",
        "question_patterns": [
            "years of experience with PySpark / Apache Spark",
            "Spark data engineering experience",
            "Big Data processing with PySpark",
            "distributed data processing experience"
        ],
        "standard_response": "3",
        "numeric_value": 3.0,
        "notes": "Built and maintained 8+ Spark batch pipelines on terabyte-scale healthcare data."
    },
    {
        "category": "technical_tool_experience",
        "question_patterns": [
            "years of experience with Tableau or Power BI",
            "BI dashboard development experience",
            "business intelligence and data visualization",
            "executive reporting dashboards"
        ],
        "standard_response": "4",
        "numeric_value": 4.0,
        "notes": "Designed executive BI dashboards in Tableau translating multi-source marketing data."
    },
    {
        "category": "technical_tool_experience",
        "question_patterns": [
            "years of experience with AWS (S3, SNS)",
            "Amazon Web Services cloud experience",
            "cloud data pipeline engineering on AWS",
            "AWS S3 bucket and event notifications"
        ],
        "standard_response": "3",
        "numeric_value": 3.0,
        "notes": "Integrated AWS S3 ingestion layers and SNS event-driven notifications."
    },
    {
        "category": "technical_tool_experience",
        "question_patterns": [
            "years of experience with AI Agents and LLMs",
            "Agentic AI workflow development",
            "LangChain or LlamaIndex experience",
            "RAG (Retrieval-Augmented Generation) architectures",
            "Prompt engineering and automated AI workflows"
        ],
        "standard_response": "2",
        "numeric_value": 2.0,
        "notes": "Engineered autonomous reconciliation agents, multi-store SKU sync, and LLM automation."
    },
    {
        "category": "technical_tool_experience",
        "question_patterns": [
            "years of experience with Data Governance and Quality",
            "data observability and validation models",
            "HIPAA compliance and de-identification",
            "HCP and HCO healthcare data standardization"
        ],
        "standard_response": "3",
        "numeric_value": 3.2,
        "notes": "Led data standardization layer and HIPAA de-identification models for healthcare data."
    },

    # ── Excluded Technologies (Strict 0 YOE) ──────────────────────────────────
    {
        "category": "technology_exclusions_zero_experience",
        "question_patterns": [
            "years of experience with Java",
            "Java enterprise application development",
            "core Java and backend engineering",
            "how many years have you coded in Java"
        ],
        "standard_response": "0",
        "numeric_value": 0,
        "notes": "Explicit exclusion rule: Candidate does not specialize in Java development."
    },
    {
        "category": "technology_exclusions_zero_experience",
        "question_patterns": [
            "years of experience with Spring Boot",
            "Spring framework and microservices",
            "Spring MVC or Spring Data experience"
        ],
        "standard_response": "0",
        "numeric_value": 0,
        "notes": "Explicit exclusion rule: 0 years with Spring Boot."
    },
    {
        "category": "technology_exclusions_zero_experience",
        "question_patterns": [
            "years of experience with Kubernetes production DevOps",
            "K8s cluster administration",
            "Kubernetes container orchestration in production",
            "production DevOps engineering with Docker / Kubernetes"
        ],
        "standard_response": "0",
        "numeric_value": 0,
        "notes": "Explicit exclusion rule: 0 years in production DevOps/K8s cluster administration."
    },

    # ── Compensation & Annual Income ─────────────────────────────────────────
    {
        "category": "compensation_current_and_fixed",
        "question_patterns": [
            "what is your current annual income",
            "current gross income",
            "current annual salary",
            "fixed CTC",
            "total current CTC",
            "current remuneration",
            "present package",
            "current package in INR",
            "what is your current fixed salary"
        ],
        "standard_response": "1800000",
        "lpa_response": "18",
        "numeric_inr": 1800000,
        "numeric_lpa": 18.0,
        "notes": "Guaranteed annual income: 1800000 INR (18 LPA). NEVER 4."
    },
    {
        "category": "compensation_expected_and_desired",
        "question_patterns": [
            "what is your expected annual salary",
            "desired CTC",
            "expected CTC in INR",
            "desired compensation",
            "salary expectation in LPA",
            "what salary are you looking for",
            "quote your expected package",
            "minimum salary requirement"
        ],
        "standard_response": "2800000",
        "lpa_response": "28",
        "numeric_inr": 2800000,
        "numeric_lpa": 28.0,
        "notes": "Target expected compensation: 2800000 INR (28 LPA) or upper bound of posting range."
    },

    # ── Notice Period & Availability ─────────────────────────────────────────
    {
        "category": "notice_period_and_availability",
        "question_patterns": [
            "notice period in days",
            "how many days notice do you have to serve",
            "notice period duration",
            "availability in days",
            "how soon can you start"
        ],
        "standard_response": "0",
        "text_response": "Immediate Joiner (0 days notice)",
        "numeric_value": 0,
        "notes": "Immediate availability (0 days notice)."
    },

    # ── Education & Academics ────────────────────────────────────────────────
    {
        "category": "education_and_academics",
        "question_patterns": [
            "undergraduate degree name",
            "what is your bachelor degree",
            "highest qualification obtained",
            "undergraduate major or stream",
            "bachelor degree title"
        ],
        "standard_response": "Bachelor of Arts (Hons.) Business Economics",
        "short_response": "BA (Hons) Business Economics",
        "degree_level": "Bachelor's Degree",
        "notes": "Graduated from University of Delhi (07/2017 - 07/2020)."
    },
    {
        "category": "education_and_academics",
        "question_patterns": [
            "university or institution attended",
            "college name for highest qualification",
            "degree granting university",
            "school / university name"
        ],
        "standard_response": "University of Delhi",
        "notes": "Always specify University of Delhi or Delhi University."
    },
    {
        "category": "education_and_academics",
        "question_patterns": [
            "undergraduate GPA or CGPA",
            "college grade / score",
            "marks obtained in bachelor degree",
            "academic CGPA percentage"
        ],
        "standard_response": "6.5",
        "percentage_response": "61.75%",
        "notes": "6.5 CGPA out of 10.0 (converted percentage: 61.75%)."
    },

    # ── Compliance, Background & Legal ───────────────────────────────────────
    {
        "category": "compliance_and_legal",
        "question_patterns": [
            "have you ever been convicted of a felony or misdemeanor",
            "do you have a criminal record",
            "have you been convicted of a crime",
            "any criminal proceedings against you"
        ],
        "standard_response": "No",
        "notes": "Zero criminal record."
    },
    {
        "category": "compliance_and_legal",
        "question_patterns": [
            "are you bound by a non-compete agreement",
            "subject to any non-solicitation or non-compete clause",
            "do you have any restrictive covenant with former employers"
        ],
        "standard_response": "No",
        "notes": "No non-compete or non-solicitation obligations."
    },
    {
        "category": "compliance_and_legal",
        "question_patterns": [
            "do you consent to a standard background verification",
            "willing to undergo pre-employment drug screening and background check",
            "agree to background verification checks"
        ],
        "standard_response": "Yes",
        "notes": "Full consent for background verification."
    },
    {
        "category": "work_flexibility_and_shifts",
        "question_patterns": [
            "are you willing to travel for business",
            "travel requirement up to 25%",
            "comfortable with occasional business travel"
        ],
        "standard_response": "Yes (up to 25%)",
        "short_response": "Yes",
        "notes": "Open to business travel up to 25%."
    },
    {
        "category": "work_flexibility_and_shifts",
        "question_patterns": [
            "comfortable working in rotational or night shifts",
            "overlap with US / European time zones",
            "flexibility with global team working hours"
        ],
        "standard_response": "Yes",
        "notes": "Experienced with cross-border and US timezone collaboration."
    },

    # ── Voluntary Demographics ───────────────────────────────────────────────
    {
        "category": "voluntary_demographics",
        "question_patterns": [
            "gender identity",
            "what is your gender",
            "please indicate your gender"
        ],
        "standard_response": "Male",
        "notes": "Male."
    },
    {
        "category": "voluntary_demographics",
        "question_patterns": [
            "veteran status",
            "are you a protected veteran",
            "military or veteran service"
        ],
        "standard_response": "I am not a protected veteran",
        "short_response": "No",
        "notes": "Not a veteran."
    },
    {
        "category": "voluntary_demographics",
        "question_patterns": [
            "disability status",
            "do you have a physical or mental disability",
            "disability self-identification"
        ],
        "standard_response": "No, I do not have a disability",
        "short_response": "No",
        "notes": "No disability."
    }
]


def enrich_kb():
    if not KB_PATH.exists():
        print(f"Error: {KB_PATH} not found.")
        return

    data = json.loads(KB_PATH.read_text(encoding="utf-8"))
    entries = data.get("qa_database", [])

    existing_patterns = set()
    for item in entries:
        for p in item.get("question_patterns", []):
            existing_patterns.add(p.lower().strip())

    added = 0
    for new_item in ENRICHED_ENTRIES:
        # Check if already covered
        overlap = any(p.lower().strip() in existing_patterns for p in new_item["question_patterns"])
        if not overlap:
            entries.append(new_item)
            added += 1

    data["qa_database"] = entries
    data["last_updated"] = "2026-10-20"
    data["version"] = "2.0.0"
    KB_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"[Knowledge Base] Successfully enriched with {added} new comprehensive semantic entries. Total entries: {len(entries)}")


if __name__ == "__main__":
    enrich_kb()
