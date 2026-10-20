#!/usr/bin/env python3
"""
CareerPilot AI - Universal ATS QA & Semantics Engine.
Provides high-velocity deterministic semantic pattern matching across all ATS platforms
(LinkedIn Easy Apply, Workday, Taleo, SuccessFactors, Greenhouse, Pinpoint),
backed by OpenRouter Free Tier LLM fallback for novel questions with autonomous learning.

Author: Ankit Kumar Singh
Rule: Zero em dashes permitted. Zero financial cost (only :free models).
"""

from __future__ import annotations

import os
import re
import json
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
KB_PATH = ROOT_DIR / "user_inputs" / "application_qa_knowledge_base.json"

_SEMIN_CACHE: Dict[str, str] = {}


def load_env():
    """Load key-value pairs from .env into os.environ if not already set."""
    env_file = ROOT_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def load_candidate_context() -> Dict[str, Any]:
    """Dynamically resolve candidate attributes from .env."""
    load_env()
    cand: Dict[str, str] = {}

    first = os.getenv("CANDIDATE_FIRST_NAME", "Ankit")
    last = os.getenv("CANDIDATE_LAST_NAME", "Singh")
    name = os.getenv("CANDIDATE_NAME", f"{first} {last}")
    email = os.getenv("CANDIDATE_EMAIL", "")
    phone = os.getenv("CANDIDATE_PHONE", "")
    city = os.getenv("CANDIDATE_CITY", "Noida")
    state = os.getenv("CANDIDATE_STATE", "Uttar Pradesh")
    country = os.getenv("CANDIDATE_COUNTRY", "India")
    pincode = os.getenv("CANDIDATE_PINCODE", "201304")
    address = os.getenv("CANDIDATE_ADDRESS", f"Sector 137, {city}, {state}, {pincode}")

    ctc_lpa = os.getenv("CANDIDATE_CURRENT_CTC_LPA", "18.0")
    exp_ctc_lpa = os.getenv("CANDIDATE_EXPECTED_CTC_LPA", "28.0")
    ctc_inr = os.getenv("CANDIDATE_CURRENT_CTC_INR", "1800000")
    exp_ctc_inr = os.getenv("CANDIDATE_EXPECTED_CTC_INR", "2800000")
    total_yoe = os.getenv("CANDIDATE_TOTAL_YOE", "4.8")
    yoe_int = str(int(float(total_yoe)))

    designation = "Business and Technology Consultant"
    linkedin = cand.get("linkedin") or os.getenv("CANDIDATE_LINKEDIN_URL", "https://linkedin.com/in/ankit-singh99")
    github = os.getenv("CANDIDATE_GITHUB_URL", "https://github.com/ankitsingh99")

    degree = os.getenv("CANDIDATE_DEGREE", "Bachelor of Arts (Hons.) Business Economics")
    major = os.getenv("CANDIDATE_MAJOR", "Business Economics")
    institution = os.getenv("CANDIDATE_UNIVERSITY", "University of Delhi")
    gpa = os.getenv("CANDIDATE_GPA", "6.5")

    return {
        "name": name,
        "first_name": first,
        "last_name": last,
        "email": email,
        "phone": phone,
        "address": address,
        "city": city,
        "state": state,
        "country": country,
        "pincode": pincode,
        "ctc_lpa": ctc_lpa,
        "exp_ctc_lpa": exp_ctc_lpa,
        "ctc_inr": ctc_inr,
        "exp_ctc_inr": exp_ctc_inr,
        "total_yoe": total_yoe,
        "yoe_int": yoe_int,
        "designation": designation,
        "linkedin": linkedin,
        "github": github,
        "degree": degree,
        "major": major,
        "institution": institution,
        "gpa": gpa,
        "notice_period_days": os.getenv("CANDIDATE_NOTICE_PERIOD_DAYS", "0"),
        "notice_period_text": "Immediate Joiner (0 days notice)",
        "skills": "Python, SQL, PySpark, Snowflake, PostgreSQL, Trino, Oracle, Apache Airflow, Tableau, AWS (S3, SNS), Scikit-learn, AI Agents, LLM Fine-Tuning, RAG, Data Governance, HIPAA",
        "excluded_skills": "Java, Spring Boot, J2EE, Kubernetes production DevOps, Docker production DevOps, .NET, C#",
    }


def save_novel_qa_to_kb(question: str, answer: str, category: str = "openrouter_learned"):
    """Persist newly resolved Q&A pair into user_inputs/application_qa_knowledge_base.json."""
    if not KB_PATH.exists():
        return
    try:
        data = json.loads(KB_PATH.read_text(encoding="utf-8"))
        entries = data.get("qa_database", [])
        q_norm = question.strip().lower()

        # Check deduplication
        for item in entries:
            for pat in item.get("question_patterns", []):
                if pat.lower() in q_norm or q_norm in pat.lower():
                    return

        entries.append({
            "category": category,
            "question_patterns": [question.strip()],
            "standard_response": answer.strip(),
            "notes": "Learned and confirmed autonomously via OpenRouter Free Tier integration."
        })
        KB_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


def ask_openrouter_free_llm(question: str, options: Optional[List[str]] = None, field_type: str = "text") -> str:
    """Query OpenRouter strictly on zero-cost free tier (:free) to resolve complex ATS questions."""
    cache_key = f"{field_type}::{question.strip().lower()}::{'|'.join(options or [])}"
    if cache_key in _SEMIN_CACHE:
        return _SEMIN_CACHE[cache_key]

    cand = load_candidate_context()

    # ── Local deterministic fast resolution to preserve OpenRouter quota ─────
    q_low = question.lower()
    if field_type == "number":
        for pat in QASemanticsEngine.EXCLUDED_TECH_PATTERNS:
            if re.search(pat, q_low):
                return "0"
        return cand["yoe_int"]

    if field_type == "radio" and options:
        if any(k in q_low for k in ["sponsorship", "referral", "relationship", "felony", "crime", "non-compete"]):
            for opt in options:
                if opt.lower().startswith("no") or "no" in opt.lower():
                    return opt
        for opt in options:
            if opt.lower().startswith("yes") or "yes" in opt.lower():
                return opt
        return options[0]

    if field_type == "select" and options:
        return options[0]

    try:
        from intelligence.llm_clients.openrouter import ask
    except ImportError:
        return ""
    system_prompt = (
        "You are an ATS job application form filler representing the candidate.\n"
        "Your duty is to output ONLY the exact, factual string to enter or select into the form.\n"
        "Do NOT provide explanations, pleasantries, markdown, or commentary.\n"
        f"Candidate: {cand['name']}\n"
        f"Designation: {cand['designation']}\n"
        f"Total Experience: {cand['total_yoe']} years\n"
        f"Notice Period: {cand['notice_period_text']} ({cand['notice_period_days']} days)\n"
        f"Current CTC: {cand['ctc_lpa']} LPA ({cand['ctc_inr']} INR)\n"
        f"Expected CTC: {cand['exp_ctc_lpa']} LPA ({cand['exp_ctc_inr']} INR)\n"
        f"Core Technical Skills: {cand['skills']}\n"
        f"Explicit Technology Exclusions (0 years experience): {cand['excluded_skills']}\n"
        f"Education: {cand['degree']} from {cand['institution']}, Score: {cand['gpa']} CGPA\n"
        f"Location: {cand['city']}, {cand['country']}. Authorized to work in India (No sponsorship required).\n"
        f"Work Model: Open to Remote/Hybrid/Onsite and willing to relocate (Domestic & International).\n"
        f"Compliance: No criminal record, no non-compete, no relatives or personal referrals at the company."
    )

    user_prompt = f"Field Question / Label: {question}\nField Type: {field_type}\n"
    if options:
        user_prompt += "Available Options:\n" + "\n".join(f"- {opt}" for opt in options) + "\n"
        user_prompt += "Select and return ONLY the single exact option text from the list that best represents the candidate."
    else:
        if field_type == "number":
            user_prompt += "Return ONLY a single numeric value (e.g., 4 or 0 or 1800000)."
        elif field_type == "textarea":
            user_prompt += "Return a concise, factual professional response (2-3 sentences max) without corporate buzzwords."
        else:
            user_prompt += "Return ONLY the concise exact value to type into the field."

    try:
        response = ask(user_prompt, system=system_prompt, model="auto", max_tokens=150)
        ans = response.strip().strip('"').strip("'").strip()
        if ans:
            _SEMIN_CACHE[cache_key] = ans
            save_novel_qa_to_kb(question, ans)
            return ans
    except Exception:
        pass

    return ""


class QASemanticsEngine:
    """Universal semantic engine for matching ATS form questions and generating precise answers."""

    # 1. Negative Exclusions: Tool experience MUST return '0'
    EXCLUDED_TECH_PATTERNS = [
        r"\bjava\b", r"\bspring\s*boot\b", r"\bj2ee\b",
        r"\bkubernetes\b", r"\bdocker\s*production\b",
        r"\b\.net\b", r"\bc#\b", r"\bios\s*developer\b",
        r"\bandroid\s*developer\b", r"\bswift\b", r"\bkotlin\b"
    ]

    # 2. Positive Technical Tools: Return Candidate Experience (4 or 4.8)
    CORE_TECH_PATTERNS = [
        r"\bpython\b", r"\bsql\b", r"\bpyspark\b", r"\bspark\b",
        r"\bsnowflake\b", r"\bairflow\b", r"\btableau\b", r"\baws\b",
        r"\bs3\b", r"\bsns\b", r"\bpostgresql\b", r"\bpostgres\b",
        r"\btrino\b", r"\boracle\b", r"\bdata\s*engineer\w*\b",
        r"\betl\b", r"\belt\b", r"\bdata\s*pipeline\w*\b",
        r"\bdata\s*model\w*\b", r"\bdata\s*warehous\w*\b",
        r"\bdata\s*governance\b", r"\bdata\s*qualit\w*\b",
        r"\bdata\s*observab\w*\b", r"\bhipaa\b", r"\bexcel\b",
        r"\bpower\s*bi\b", r"\bpowerbi\b", r"\bgit\b", r"\bbitbucket\b",
        r"\blinux\b", r"\bunix\b", r"\bmachine\s*learning\b",
        r"\bscikit-learn\b", r"\bllm\b", r"\bai\s*agent\w*\b",
        r"\brag\b", r"\bvector\s*db\b", r"\blangchain\b"
    ]

    @classmethod
    def lookup_knowledge_base(cls, label: str, field_type: str = "text") -> Optional[str]:
        """Search local application_qa_knowledge_base.json first (0 tokens, 0 network requests)."""
        if not KB_PATH.exists():
            return None
        try:
            data = json.loads(KB_PATH.read_text(encoding="utf-8"))
            entries = data.get("qa_database", [])
            lbl_clean = label.lower().strip()

            for item in entries:
                for pat in item.get("question_patterns", []):
                    pat_clean = pat.lower().strip()
                    if pat_clean in lbl_clean or (len(lbl_clean) > 5 and lbl_clean in pat_clean):
                        if field_type == "number" and "numeric_value" in item:
                            return str(item["numeric_value"])
                        if "standard_response" in item:
                            return str(item["standard_response"])
        except Exception:
            pass
        return None

    @classmethod
    def match_question(
        cls,
        label: str,
        field_type: str = "text",
        options: Optional[List[str]] = None,
        upper_salary: Optional[Tuple[str, str]] = None
    ) -> str:
        """
        Evaluate an ATS question label/placeholder and return the optimal factual answer.
        upper_salary: Optional tuple of (full_inr_or_amount, lpa_or_decimal)
        """
        cand = load_candidate_context()
        lbl = (label or "").strip().lower()

        # If options are provided, check if any option matches common preferences first
        if options:
            # Notice period options
            if any(k in lbl for k in ["notice", "availability", "how soon", "joining time"]):
                for pref in ["immediate", "0 days", "0-15", "less than 1", "serving", "15 days", "1 month"]:
                    for opt in options:
                        if pref in opt.lower():
                            return opt.strip()

            # Yes / No options
            if any(k in lbl for k in [
                "authorized", "relocate", "hybrid", "onsite", "travel", "background check",
                "drug", "consent", "privacy", "terms", "agree", "shift", "shifts", "us hours"
            ]):
                for opt in options:
                    if opt.strip().lower() == "yes" or opt.strip().lower().startswith("yes"):
                        return opt.strip()

            if any(k in lbl for k in [
                "sponsorship", "referral", "relationship", "relative", "felony", "crime", "non-compete"
            ]):
                for opt in options:
                    if opt.strip().lower() == "no" or opt.strip().lower().startswith("no"):
                        return opt.strip()

            # Degree options
            if any(k in lbl for k in ["degree", "education", "qualification"]):
                for pref in ["bachelor", "undergraduate", "ba", "b.a", "graduate"]:
                    for opt in options:
                        if pref in opt.lower():
                            return opt.strip()

            # Major / Field of Study options
            if any(k in lbl for k in ["major", "field of study", "specialization", "stream"]):
                for pref in ["business economics", "economics", "business", "analytics", "commerce"]:
                    for opt in options:
                        if pref in opt.lower():
                            return opt.strip()

            # Experience options
            if any(k in lbl for k in ["experience", "yoe", "years"]):
                for pref in ["4", "3-5", "3 to 5", "4-5", "4+", "less than 5", "less than 8"]:
                    for opt in options:
                        if pref in opt.lower():
                            return opt.strip()

            # Location / Country options
            for opt in options:
                if cand["city"].lower() in opt.lower() or "india" in opt.lower():
                    return opt.strip()

        # ── 1. TITLE / DESIGNATION OVERRIDE ──────────────────────────────────────
        if any(k in lbl for k in [
            "your title", "job title", "current title", "designation", "headline", "current role title",
            "present designation", "current designation", "title at company"
        ]):
            return cand["designation"]

        # ── 2. COMPENSATION: DESIRED / EXPECTED CTC ──────────────────────────────
        if any(k in lbl for k in [
            "desired salary", "desired compensation", "desired ctc", "desired income",
            "desired pay", "expected salary", "expected ctc", "expected compensation",
            "expected income", "expected package", "salary expectation", "ctc expectation",
            "expected annual", "minimum salary", "pay expectation", "desired rate", "quote your ctc"
        ]):
            is_lpa = any(k in lbl for k in ["lpa", "lac", "lakh", "decimal", "in lacs", "in lakhs", "in lpa"])
            if upper_salary and upper_salary[0]:
                return upper_salary[1] if is_lpa else upper_salary[0]
            return cand["exp_ctc_lpa"] if is_lpa else cand["exp_ctc_inr"]

        # ── 3. COMPENSATION: CURRENT CTC / ANNUAL INCOME / FIXED CTC ─────────────
        # Rule: Whenever any field asks for annual income, compensation, current CTC,
        # package, or fixed salary, ALWAYS use 1800000 (or 18 LPA). NEVER fill 4.
        if any(k in lbl for k in [
            "annual income", "current income", "current ctc", "fixed ctc", "total ctc",
            "current package", "gross income", "gross salary", "fixed salary", "current salary",
            "current compensation", "current remuneration", "present salary", "present ctc",
            "earnings", "take home", "fixed pay", "annual compensation", "annual package",
            "current base", "base salary", "compensation", "remuneration", "package", "salary",
            "ctc"
        ]):
            is_lpa = any(k in lbl for k in ["lpa", "lac", "lakh", "decimal", "in lacs", "in lakhs", "in lpa"])
            return cand["ctc_lpa"] if is_lpa else cand["ctc_inr"]

        # ── 4. NOTICE PERIOD / AVAILABILITY ──────────────────────────────────────
        if any(k in lbl for k in [
            "notice period", "notice days", "availability", "how soon", "joining time",
            "earliest start date", "available to start", "days notice", "how many days notice",
            "serving notice", "notice period in days", "availability to join"
        ]):
            if field_type == "number":
                return cand["notice_period_days"]
            return cand["notice_period_text"]

        # ── 5. CONTACT & PERSONAL IDENTITY ───────────────────────────────────────
        if any(k in lbl for k in ["phone", "mobile", "telephone", "contact number", "cell"]):
            return cand["phone"]
        if any(k in lbl for k in ["email", "e-mail", "email address"]):
            return cand["email"]
        if any(k in lbl for k in ["first name", "given name"]):
            return cand["first_name"]
        if any(k in lbl for k in ["last name", "family name", "surname"]):
            return cand["last_name"]
        if any(k in lbl for k in ["linkedin", "social profile", "profile url", "linkedin url"]) or field_type == "url":
            return cand["linkedin"]
        if any(k in lbl for k in ["github", "portfolio", "git url", "code repository"]):
            return cand["github"]
        if any(k in lbl for k in ["city", "current location", "residence city", "place of residence", "residing city"]):
            return f"{cand['city']}, {cand['state']}, {cand['country']}"
        if any(k in lbl for k in ["postal", "zip", "pincode", "pin code", "postal code"]):
            return cand["pincode"]
        if any(k in lbl for k in ["street address", "address line 1", "residential address", "home address"]):
            return cand["address"]

        # ── 6. EDUCATION & ACADEMICS ─────────────────────────────────────────────
        if any(k in lbl for k in ["gpa", "cgpa", "grade", "percentage", "academic score", "marks"]):
            return cand["gpa"]
        if any(k in lbl for k in ["university", "college", "institution", "school name", "granting institution"]):
            return cand["institution"]
        if any(k in lbl for k in ["major", "field of study", "specialization", "stream", "branch"]):
            return cand["major"]
        if any(k in lbl for k in ["degree", "highest qualification", "degree obtained", "qualification"]):
            return cand["degree"]

        # ── 7. EXCLUDED TECH EXPERIENCE CHECK (STRICT 0) ─────────────────────────
        for pat in cls.EXCLUDED_TECH_PATTERNS:
            if re.search(pat, lbl):
                return "0"

        # ── 8. CORE TECH EXPERIENCE CHECK (CANDIDATE EXPERIENCE: 4 or 4.8) ───────
        for pat in cls.CORE_TECH_PATTERNS:
            if re.search(pat, lbl) and any(k in lbl for k in ["year", "yoe", "experience", "how many", "level"]):
                return cand["yoe_int"]

        # ── 9. TOTAL EXPERIENCE / SENIORITY ──────────────────────────────────────
        if any(k in lbl for k in ["total experience", "overall experience", "years of experience", "total yoe", "relevant experience"]):
            return cand["yoe_int"]

        # ── 10. COMPLIANCE & LEGAL SCREENING (YES / NO) ──────────────────────────
        # Negative compliance questions (Always 'No')
        if any(k in lbl for k in [
            "visa sponsorship", "require sponsorship", "need sponsorship", "require visa",
            "future sponsorship", "employee referral", "referred by", "personal relationship",
            "current employee", "know anyone", "family member", "relative",
            "felony", "criminal", "convicted", "crime", "misdemeanor",
            "non-compete", "non compete", "non-solicitation", "restrictive agreement"
        ]):
            return "No"

        # Positive compliance questions (Always 'Yes')
        if any(k in lbl for k in [
            "authorized to work in india", "authorized to work", "legally authorized", "right to work",
            "relocate", "relocation", "hybrid", "onsite", "in-office",
            "travel", "willing to travel", "rotational", "flexible hours", "timezones",
            "us hours", "shift", "shifts", "background check", "drug test",
            "agree to", "consent", "privacy policy", "terms and conditions", "gdpr",
            "talent community", "receive alerts", "future job alerts"
        ]):
            return "Yes"

        # ── 11. TEXTAREA ANSWERS (MICRO-NARRATIVES) ──────────────────────────────
        if field_type == "textarea":
            if any(k in lbl for k in ["tell us about yourself", "summary", "profile", "overview", "pitch"]):
                return (
                    "Business & Technology Consultant with 4.8 years of experience across healthcare commercial analytics, "
                    "Big Data pipelines, and AI agent automation. Ex-ZS Associates with a track record of driving data quality, "
                    "reconciliation agents, and high-performance ETL architectures."
                )
            if any(k in lbl for k in ["why do you want to join", "why this company", "why us", "interest"]):
                return (
                    "Excited to leverage my data engineering and AI automation experience to solve mission-critical "
                    "enterprise challenges, build reliable data systems, and deliver measurable operational impact."
                )
            if any(k in lbl for k in ["leadership", "management", "team", "people management"]):
                return (
                    "Managed a team of four at ZS Associates overseeing data standardization, cross-functional delivery, "
                    "and stakeholder reporting, reducing manual touchpoints by 80% while ensuring zero data discrepancies."
                )

        # ── 12. DROPDOWN OPTION MATCHING ─────────────────────────────────────────
        if options:
            preferred_matches = [
                "yes", "immediate", "0 days", "0-15 days", "15 days",
                cand["city"].lower(), "india", "bachelor", "economics",
                cand["yoe_int"], "3-5 years", "3 to 5 years", "4-5 years"
            ]
            for pref in preferred_matches:
                for opt in options:
                    if opt.strip().lower().startswith(pref):
                        return opt.strip()

        # ── 13. LOCAL KNOWLEDGE BASE LOOKUP (0 TOKENS, 0 NETWORK CALLS) ───────────
        kb_hit = cls.lookup_knowledge_base(lbl, field_type=field_type)
        if kb_hit:
            return kb_hit

        # ── 14. TIER 2 OPENROUTER FREE LLM FALLBACK ──────────────────────────────
        ai_res = ask_openrouter_free_llm(label, options=options, field_type=field_type)
        if ai_res:
            return ai_res

        # Fallback defaults
        if field_type == "number":
            return cand["yoe_int"]
        return "N/A"
