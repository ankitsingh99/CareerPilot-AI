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
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
KB_PATH = ROOT_DIR / "user_inputs" / "application_qa_knowledge_base.json"

_SEMIN_CACHE: Dict[str, str] = {}
_ENV_MEM_STATE: Dict[str, Any] = {"mtime": None}
_KB_MEM_CACHE: Dict[str, Any] = {"mtime": None, "entries": [], "pattern_tokens": []}


def load_env():
    """Load key-value pairs from .env into os.environ once per file modification."""
    env_file = ROOT_DIR / ".env"
    if not env_file.exists():
        return
    try:
        mtime = env_file.stat().st_mtime
    except OSError:
        mtime = None
    if _ENV_MEM_STATE["mtime"] == mtime and mtime is not None:
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    _ENV_MEM_STATE["mtime"] = mtime


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

    raw_ctc_lpa = os.getenv("CANDIDATE_CURRENT_CTC_LPA", "18").strip()
    try:
        f_ctc = float(raw_ctc_lpa)
        ctc_lpa = str(int(f_ctc)) if f_ctc.is_integer() else raw_ctc_lpa
    except ValueError:
        ctc_lpa = raw_ctc_lpa

    raw_exp_ctc_lpa = os.getenv("CANDIDATE_EXPECTED_CTC_LPA", "28").strip()
    try:
        f_exp = float(raw_exp_ctc_lpa)
        exp_ctc_lpa = str(int(f_exp)) if f_exp.is_integer() else raw_exp_ctc_lpa
    except ValueError:
        exp_ctc_lpa = raw_exp_ctc_lpa

    ctc_inr = os.getenv("CANDIDATE_CURRENT_CTC_INR", "1800000")
    exp_ctc_inr = os.getenv("CANDIDATE_EXPECTED_CTC_INR", "2800000")
    total_yoe = os.getenv("CANDIDATE_TOTAL_YOE", "5")
    try:
        yoe_f = float(total_yoe)
        yoe_int = str(int(yoe_f))
        yoe_months = str(int(yoe_f * 12)) if yoe_f > 0 else "60"
    except Exception:
        yoe_int = "5"
        yoe_months = "60"

    designation = "Business and Technology Consultant"
    linkedin = cand.get("linkedin") or os.getenv("CANDIDATE_LINKEDIN_URL", "https://linkedin.com/in/ankit-singh99")
    github = os.getenv("CANDIDATE_GITHUB_URL", "https://github.com/ankitsingh99")

    degree = os.getenv("CANDIDATE_DEGREE", "Bachelor of Arts (Hons.) Business Economics")
    major = os.getenv("CANDIDATE_MAJOR", "Business Economics")
    institution = os.getenv("CANDIDATE_UNIVERSITY", "University of Delhi")
    gpa = os.getenv("CANDIDATE_GPA", "6.5")
    grad_year = os.getenv("CANDIDATE_GRADUATION_YEAR", "2020")
    education_start_year = os.getenv("CANDIDATE_EDUCATION_START_YEAR", "2017")

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
        "yoe_months": yoe_months,
        "designation": designation,
        "linkedin": linkedin,
        "github": github,
        "degree": degree,
        "major": major,
        "institution": institution,
        "gpa": gpa,
        "grad_year": grad_year,
        "completion_year": grad_year,
        "education_start_year": education_start_year,
        "notice_period": os.getenv("CANDIDATE_NOTICE_PERIOD", "Immediate Joiner (0 days notice)"),
        "notice_period_text": os.getenv("CANDIDATE_NOTICE_PERIOD", "Immediate Joiner (0 days notice)"),
        "notice_period_days": os.getenv("CANDIDATE_NOTICE_PERIOD_DAYS", "0"),
        "current_company": os.getenv("CANDIDATE_CURRENT_COMPANY", "Rush by Kira"),
        "verified_companies": os.getenv("CANDIDATE_VERIFIED_COMPANIES", "ZS Associates,Rush by Kira,TresVista"),
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
        _KB_MEM_CACHE["mtime"] = None
    except Exception:
        pass
    try:
        from intelligence.fast_recall_cache import put_qa_answer
        put_qa_answer(question, answer, source=category)
    except Exception:
        pass


def ask_openrouter_free_llm(question: str, options: Optional[List[str]] = None, field_type: str = "text") -> str:
    """Resolve complex ATS questions: Local Ollama (offline) -> OpenRouter :free (on-demand only)."""
    cache_key = f"{field_type}::{question.strip().lower()}::{'|'.join(options or [])}"
    if cache_key in _SEMIN_CACHE:
        return _SEMIN_CACHE[cache_key]

    cand = load_candidate_context()

    try:
        from intelligence.llm_clients.openrouter import (
            ask,
            ask_local_ollama_if_online,
            is_on_demand_enabled,
        )
    except ImportError:
        return ""
    system_prompt = (
        "You are an ATS job application form filler representing the candidate.\n"
        "Your duty is to output ONLY the exact, factual string to enter or select into the form.\n"
        "Do NOT provide explanations, pleasantries, markdown, or commentary.\n"
        "CRITICAL RULE: Whenever experience, tenure, or duration is asked (e.g. years of experience, days notice, joining time, duration with a tool), "
        "NEVER write 'year', 'month', 'day', or decimals. Just write the integer value (e.g. 4 or 0).\n"
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

    task_tier = "draft" if field_type == "textarea" else "chore"
    max_tok = 180 if field_type == "textarea" else 80

    try:
        # Tier 1: Zero-external-token local Ollama inference if running
        response = ask_local_ollama_if_online(
            user_prompt, system=system_prompt, max_tokens=max_tok, temperature=0.2
        )
        # Tier 2: Cheaper/heavy :free OpenRouter tier strictly when opted in on-demand
        if not response:
            if not is_on_demand_enabled():
                return ""
            response = ask(
                user_prompt,
                system=system_prompt,
                model="auto",
                task_tier=task_tier,
                max_tokens=max_tok,
            )

        raw = response.strip()
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        clean_lines = []
        for ln in lines:
            cl = re.sub(r"^[\*\-•\d\.\s]+", "", ln).strip()
            cl = re.sub(r"^\*\*.*?\*\*:?\s*", "", cl).strip()
            if cl and not any(cl.lower().startswith(p) for p in [
                "we need", "so for", "field question", "the instruction", "constraint",
                "candidate", "i would", "here is", "likely", "probably", "note:", "output:"
            ]):
                clean_lines.append(cl)
        ans = clean_lines[-1].strip('"').strip("'").strip() if clean_lines else (lines[-1].strip('"').strip("'").strip() if lines else raw.strip('"').strip("'").strip())
        if field_type != "textarea" and (len(ans) > 70 or any(w in ans.lower() for w in ["we need", "candidate", "instruction", "constraint", "field label", "preferred name", "likely"])):
            ans = ""
        if ans and field_type not in ("select", "radio") and not options:
            ans = QASemanticsEngine.sanitize_experience_or_duration(ans, question)
        if ans:
            if options:
                ans_lower = ans.lower().strip()
                matched_opt = None
                for opt in options:
                    if opt.strip().lower() == ans_lower:
                        matched_opt = opt.strip()
                        break
                if not matched_opt:
                    for opt in options:
                        opt_c = opt.strip().lower()
                        if opt_c in ("select an option", "select", "please select", "none", ""):
                            continue
                        if ans_lower in opt_c or opt_c in ans_lower:
                            matched_opt = opt.strip()
                            break
                if matched_opt:
                    ans = matched_opt
            _SEMIN_CACHE[cache_key] = ans
            try:
                from intelligence.fast_recall_cache import put_qa_answer
                put_qa_answer(question, ans, field_type=field_type, options=options, source="llm")
            except Exception:
                pass
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
        r"\brag\b", r"\bvector\s*db\b", r"\blangchain\b",
        r"\bdatabases?\b", r"\brdbms\b"
    ]

    @classmethod
    def _get_kb_entries(cls) -> Tuple[List[Dict[str, Any]], List[Tuple[set, Dict[str, Any]]]]:
        """Load and cache application_qa_knowledge_base.json + normalized token sets by mtime."""
        if not KB_PATH.exists():
            return [], []
        try:
            mtime = KB_PATH.stat().st_mtime
            if _KB_MEM_CACHE["mtime"] != mtime:
                data = json.loads(KB_PATH.read_text(encoding="utf-8"))
                entries = data.get("qa_database", [])
                indexed: List[Tuple[set, Dict[str, Any]]] = []
                from intelligence.fast_recall_cache import normalize_tokens
                for item in entries:
                    for pat in item.get("question_patterns", []):
                        toks = set(normalize_tokens(pat))
                        if toks:
                            indexed.append((toks, item))
                _KB_MEM_CACHE["mtime"] = mtime
                _KB_MEM_CACHE["entries"] = entries
                _KB_MEM_CACHE["pattern_tokens"] = indexed
            return _KB_MEM_CACHE["entries"], _KB_MEM_CACHE["pattern_tokens"]
        except Exception:
            return [], []

    @classmethod
    def lookup_knowledge_base(cls, label: str, field_type: str = "text") -> Optional[str]:
        """Search mtime-cached local application_qa_knowledge_base.json (exact + token overlap)."""
        entries, indexed = cls._get_kb_entries()
        if not entries:
            return None
        lbl_clean = label.lower().strip()

        # 1. Fast exact/substring pattern match
        for item in entries:
            for pat in item.get("question_patterns", []):
                pat_clean = pat.lower().strip()
                if pat_clean in lbl_clean or (len(lbl_clean) > 5 and lbl_clean in pat_clean):
                    if field_type == "number" and "numeric_value" in item:
                        return str(item["numeric_value"])
                    if "standard_response" in item:
                        return str(item["standard_response"])

        # 2. Normalized token-Jaccard fallback for reworded ATS prompts
        try:
            from intelligence.fast_recall_cache import normalize_tokens
            q_toks = set(normalize_tokens(lbl_clean))
            if len(q_toks) >= 2:
                best_sim = 0.0
                best_item: Optional[Dict[str, Any]] = None
                for p_toks, item in indexed:
                    sim = len(q_toks & p_toks) / len(q_toks | p_toks)
                    if sim >= 0.80 and sim > best_sim:
                        best_sim = sim
                        best_item = item
                if best_item:
                    if field_type == "number" and "numeric_value" in best_item:
                        return str(best_item["numeric_value"])
                    if "standard_response" in best_item:
                        return str(best_item["standard_response"])
        except Exception:
            pass
        return None

    @classmethod
    def sanitize_experience_or_duration(cls, ans: str, lbl: str, field_type: str = "text") -> str:
        """
        Enforce strict user directive:
        Whenever experience, tenure, or duration is asked, never write 'year', 'month', or 'day',
        just write the integer value (e.g. 0, 4).
        """
        if not ans or ans == "N/A" or field_type in ("textarea", "radio", "select"):
            return ans

        # Check if question asks about experience, tenure, duration, years, days, months
        is_exp_or_dur = any(k in lbl for k in [
            "experience", "yoe", "years of", "how many years", "how many days", "how many months",
            "number of years", "work experience", "notice period in days", "days notice", "duration",
            "months of experience", "years have you", "in how many days", "tenure"
        ])

        # If answer has patterns like '0 years', '4 years', '4.8 years', '0 days', '15 days'
        unit_match = re.match(r"^\s*(\d+(?:\.\d+)?)\s*(?:years?|yrs?|months?|mos?|days?)\s*$", ans, re.IGNORECASE)
        if unit_match:
            try:
                return str(int(float(unit_match.group(1))))
            except ValueError:
                pass

        if is_exp_or_dur:
            m = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:years?|yrs?|months?|days?)?\b", ans, re.IGNORECASE)
            if m:
                try:
                    return str(int(float(m.group(1))))
                except ValueError:
                    pass

        return ans

    @classmethod
    def match_question(
        cls,
        label: str,
        field_type: str = "text",
        options: Optional[List[str]] = None,
        upper_salary: Optional[Tuple[str, str]] = None
    ) -> str:
        res = cls._match_question_core(
            label=label,
            field_type=field_type,
            options=options,
            upper_salary=upper_salary
        )
        lbl_clean = (label or "").strip().lower()
        return cls.sanitize_experience_or_duration(res, lbl_clean, field_type=field_type)

    @classmethod
    def _match_question_core(
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
                for opt in options:
                    opt_l = opt.lower()
                    if "immediate" in opt_l or re.search(r"(?<!\d)0\s*days\b", opt_l):
                        return opt.strip()
                for pref in ["less than 15", "0-15", "0 to 15", "less than 1", "serving", "15 days", "under 15"]:
                    for opt in options:
                        if pref in opt.lower():
                            return opt.strip()
                for pref in ["30 days", "1 month"]:
                    for opt in options:
                        if pref in opt.lower():
                            return opt.strip()

            # Sourcing / Referral Source options
            if any(k in lbl for k in ["how did you hear", "source", "hear about this", "where did you hear"]):
                for pref in [
                    "direct to careers at agoda", "direct to careers", "careers website",
                    "company website", "career website", "company career site", "careers page",
                    "social network (e.g. linkedin", "external job board", "linkedin"
                ]:
                    for opt in options:
                        if pref in opt.lower():
                            return opt.strip()

            # Employee relationship options
            if any(k in lbl for k in ["how you know the employee", "how do you know the employee", "relationship to employee", "relationship with employee"]):
                for pref in ["other", "none", "not applicable", "n/a", "friend"]:
                    for opt in options:
                        if pref in opt.lower():
                            return opt.strip()

            # Yes / No options
            if any(k in lbl for k in [
                "authorized", "relocate", "hybrid", "onsite", "travel", "background check",
                "drug", "consent", "privacy", "terms", "agree", "shift", "shifts", "us hours",
                "passport", "valid passport", "relocate to bangkok", "sms updates", "text/sms",
                "newsletters", "email me about other job openings", "use of personal data"
            ]):
                for opt in options:
                    if opt.strip().lower() == "yes" or opt.strip().lower().startswith("yes") or "willing" in opt.lower():
                        return opt.strip()

            if any(k in lbl for k in [
                "sponsorship", "referral", "relationship", "relative", "felony", "crime", "non-compete",
                "worked with", "worked before", "previously employed", "previous employment", "physical ailment",
                "ailment", "state of health", "interview at", "interviewed", "interview in last", "appeared for an interview",
                "deloitte", "independent auditor", "subsidiary entities", "associated with deloitte",
                "booking holdings", "presently employed", "previously applied"
            ]):
                for opt in options:
                    if opt.strip().lower() == "no" or opt.strip().lower().startswith("no"):
                        return opt.strip()

            # Degree options
            if any(k in lbl for k in ["degree", "education", "qualification"]):
                for pref in ["bachelor of arts", "bachelor's", "bachelors", "bachelor", "undergraduate", "ba", "b.a", "graduate"]:
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

            # Country Code / Phone Dial Code options
            if any(k in lbl for k in ["country code", "dial code", "phonecountrycode", "phone code", "calling code"]):
                for opt in options:
                    opt_clean = opt.strip()
                    if "british indian" in opt_clean.lower():
                        continue
                    if re.search(r"\b(india\b.*\+91|\+91\b|india\s*\(\+91\))", opt_clean, re.IGNORECASE) or opt_clean in ["India (+91)", "India", "+91"]:
                        return opt_clean

            # Language Proficiency options
            if any(k in lbl for k in ["language", "proficient in", "languages are you proficient", "languages"]):
                for opt in options:
                    if opt.strip().lower() in ["select", "select an option", "please select", "none", ""]:
                        continue
                    if "english" in opt.lower():
                        return opt.strip()

            # LGBTQ / Sexual Orientation options
            if any(k in lbl for k in ["lgbtq", "sexual orientation", "identify as lgbtq", "orientation"]):
                for opt in options:
                    if opt.strip().lower() in ["no", "heterosexual", "straight", "prefer not to say", "prefer not to disclose"]:
                        return opt.strip()
                for opt in options:
                    if any(term in opt.lower() for term in ["heterosexual", "straight"]):
                        return opt.strip()
                for opt in options:
                    if "no" in opt.lower() and "yes" not in opt.lower():
                        return opt.strip()
                return "No"

            # Gender options
            if (re.search(r"\b(gender|sex|biological sex)\b", lbl) or "gender identity" in lbl) and "orientation" not in lbl:
                for opt in options:
                    if opt.strip().lower() == "male":
                        return opt.strip()
                for opt in options:
                    if re.search(r"\bmale\b", opt.strip(), re.IGNORECASE) and "female" not in opt.lower():
                        return opt.strip()
                return "Male"

            # Veteran status
            if any(k in lbl for k in ["veteran", "military"]):
                for opt in options:
                    if any(term in opt.lower() for term in ["not a veteran", "no", "not a protected", "neither", "i am not"]):
                        return opt.strip()
                return "No"

            # Disability status
            if any(k in lbl for k in ["disability", "handicap", "physical or mental impairment"]):
                for opt in options:
                    if any(term in opt.lower() for term in ["do not have a disability", "no disability", "no, i don't", "no, i do not", "no", "not have a"]):
                        return opt.strip()
                return "No"

            # Race / Ethnicity
            if any(k in lbl for k in ["race", "ethnicity", "ethnic origin"]):
                for opt in options:
                    if any(term in opt.lower() for term in ["asian - indian", "asian indian", "asian", "south asian", "indian"]):
                        return opt.strip()

            # Location / Country options
            if any(k in lbl for k in ["country", "location", "citizenship", "nationality"]):
                for opt in options:
                    opt_clean = opt.strip()
                    if "british indian" in opt_clean.lower():
                        continue
                    if cand["city"].lower() in opt_clean.lower() or re.search(r"\bindia\b", opt_clean, re.IGNORECASE):
                        return opt_clean

            # Skill / Tool Proficiency ratings (Expert, Intermediate, Beginner, None)
            is_proficiency_q = any(k in lbl for k in ["proficiency", "rate your", "level of", "how proficient", "how comfortable", "expertise"])
            has_proficiency_opts = any(any(level in opt.lower() for level in ["expert", "intermediate", "beginner", "advanced", "proficient"]) for opt in options)
            if is_proficiency_q or has_proficiency_opts:
                is_core = any(k in lbl for k in [
                    "python", "pandas", "sql", "postgresql", "postgres", "pyspark", "spark", "snowflake",
                    "data warehouse", "data warehousing", "data modeling", "etl", "elt", "airflow",
                    "tableau", "power bi", "bi tool", "database", "databases", "analytics", "data analysis",
                    "excel", "dashboard"
                ])
                is_excluded = any(k in lbl for k in [
                    "java", "spring boot", "j2ee", "c++", "c#", "ruby", "php", "kubernetes", "docker", "devops"
                ])
                if is_excluded:
                    for opt in options:
                        if any(term in opt.lower() for term in ["none", "no experience", "not applicable", "0"]):
                            return opt.strip()
                    for opt in options:
                        if "beginner" in opt.lower():
                            return opt.strip()
                elif is_core:
                    for opt in options:
                        if any(term in opt.lower() for term in ["expert", "advanced", "proficient", "high"]):
                            return opt.strip()
                    for opt in options:
                        if "intermediate" in opt.lower():
                            return opt.strip()
                else:
                    for opt in options:
                        if any(term in opt.lower() for term in ["intermediate", "medium", "working knowledge", "moderate"]):
                            return opt.strip()
                    for opt in options:
                        if any(term in opt.lower() for term in ["expert", "advanced", "proficient"]):
                            return opt.strip()
                for opt in options:
                    if "intermediate" in opt.lower():
                        return opt.strip()

            # Domain experience & Positive qualifications (Yes)
            if any(k in lbl for k in [
                "experience in pharma", "pharma domain", "pharmaceutical", "healthcare", "life sciences",
                "commercial analytics", "hcp", "hco", "claims data", "retail", "e-commerce", "d2c",
                "consulting", "financial", "valuation", "machine learning projects", "ml projects",
                "time series", "time-series", "tca", "market structure", "trading", "derivatives",
                "bangalore", "bengaluru", "delhi", "noida", "mumbai", "pune", "hyderabad", "chennai", "gurgaon"
            ]):
                for opt in options:
                    if opt.strip().lower() in ["yes", "willing", "agree"] or opt.strip().lower().startswith("yes"):
                        return opt.strip()

        # ── 0. COMPENSATION NEGOTIABILITY ────────────────────────────────────────
        if any(k in lbl for k in ["negotiable", "open to negotiation", "is your ctc negotiable", "is your salary negotiable"]):
            return "Yes"

        # ── 1. TITLE / DESIGNATION OVERRIDE ──────────────────────────────────────
        if any(k in lbl for k in [
            "your title", "job title", "current title", "designation", "headline", "current role title",
            "present designation", "current designation", "title at company"
        ]):
            return cand["designation"]

        # ── 1.5 CURRENT EMPLOYER / COMPANY ───────────────────────────────────────
        if any(k in lbl for k in [
            "current company", "current employer", "present company", "present employer",
            "company name", "most recent employer", "employer name", "organization name",
            "current organization"
        ]) and not any(k in lbl for k in ["previous", "why this", "about us", "referred"]):
            return cand["current_company"]

        # ── 1.9 COMPENSATION NEGOTIABILITY ───────────────────────────────────────
        if any(k in lbl for k in ["negotiable", "open to negotiation", "is your ctc negotiable", "is your salary negotiable"]):
            return "Yes"

        # ── 2. COMPENSATION: DESIRED / EXPECTED CTC ──────────────────────────────
        if (
            (any(k in lbl for k in ["expect", "desired", "expectation", "expectations", "quote", "target", "looking for"]) and
             any(k in lbl for k in ["salary", "compensation", "ctc", "pay", "income", "package", "remuneration", "rate"]))
            or any(k in lbl for k in [
                "desired salary", "desired compensation", "desired ctc", "desired income",
                "desired pay", "expected salary", "expected ctc", "expected compensation",
                "expected income", "expected package", "salary expectation", "ctc expectation",
                "salary expectations", "compensation expectation", "compensation expectations",
                "expected annual", "minimum salary", "pay expectation", "pay expectations", "desired rate", "quote your ctc"
            ])
        ) and "negotiable" not in lbl:
            is_monthly = any(k in lbl for k in ["per month", "monthly", "in months", "a month", "/month", "/mo"])
            is_lpa = any(k in lbl for k in ["lpa", "lac", "lakh", "decimal", "in lacs", "in lakhs", "in lpa"])
            if is_monthly:
                base_val = int(upper_salary[0]) if (upper_salary and upper_salary[0] and upper_salary[0].isdigit()) else int(cand["exp_ctc_inr"])
                return str(base_val // 12)
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
            is_monthly = any(k in lbl for k in ["per month", "monthly", "in months", "a month", "/month", "/mo"])
            is_lpa = any(k in lbl for k in ["lpa", "lac", "lakh", "decimal", "in lacs", "in lakhs", "in lpa"])
            if is_monthly:
                return str(int(cand["ctc_inr"]) // 12)
            return cand["ctc_lpa"] if is_lpa else cand["ctc_inr"]

        # ── 4. NOTICE PERIOD / AVAILABILITY & START DATE ─────────────────────────
        # Future / Earliest Start Date (select next business day per user directive)
        if (
            any(k in lbl for k in [
                "date in the future can you start", "date you can start",
                "earliest start date", "by what date", "what date can you start",
                "start date", "date of joining", "joining date"
            ]) or (field_type == "date" and any(k in lbl for k in ["start", "join", "available", "begin"]))
        ):
            today = datetime.now()
            # 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun
            w = today.weekday()
            delta_days = 3 if w == 4 else (2 if w == 5 else 1)
            next_bday = today + timedelta(days=delta_days)
            if options:
                target_str = next_bday.strftime("%d/%m/%Y")
                alt_str = next_bday.strftime("%m/%d/%Y")
                iso_str = next_bday.strftime("%Y-%m-%d")
                for opt in options:
                    opt_clean = opt.strip()
                    if any(s in opt_clean for s in [target_str, alt_str, iso_str, "Immediate", "0 days", "Immediately"]):
                        return opt_clean
            if field_type == "date":
                return next_bday.strftime("%Y-%m-%d")
            if any(k in lbl for k in ["dd/mm", "dd-mm", "d/m/y"]):
                return next_bday.strftime("%d/%m/%Y")
            return next_bday.strftime("%m/%d/%Y")

        if any(k in lbl for k in [
            "notice days", "days notice", "how many days notice", "notice period in days",
            "how many days can you join", "in how many days", "availability to join (in days)",
            "availability to start (in days)", "notice in days", "notice period in months",
            "notice in months", "notice period in weeks", "notice in weeks"
        ]) or (field_type == "number" and any(k in lbl for k in ["notice", "availability", "joining"])):
            return "0"

        if any(k in lbl for k in [
            "notice period", "availability", "how soon", "joining time",
            "available to start", "days notice", "how many days notice",
            "serving notice", "availability to join"
        ]):
            return "0"

        # ── 5. CONTACT & PERSONAL IDENTITY ───────────────────────────────────────
        # Referral question guard (must precede name matching to avoid capturing "first and last name of employee")
        if any(k in lbl for k in ["referred to this position", "referred by a", "referral", "employee referral", "who referred you"]):
            if field_type in ["select", "radio", "checkbox"]:
                return "No"
            return ""

        if any(k in lbl for k in ["preferred name", "preferred", "nickname", "custpreferredname"]):
            return cand["first_name"]
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
        if any(k in lbl for k in ["country of residence", "residence country", "current country", "what country"]):
            return cand.get("country", "India")

        if (any(k in lbl for k in [
            "current location", "residence city", "place of residence", "residing city",
            "where do you reside", "where do you currently reside", "where do you live",
            "current residence", "location of residence"
        ]) or re.search(r"\bcity\b", lbl)) and not any(k in lbl for k in ["race", "ethnicity", "capacity"]):
            if options:
                for opt in options:
                    if "noida" in opt.lower():
                        return opt
                for opt in options:
                    if any(k in opt.lower() for k in ["delhi ncr", "delhi", "gurugram", "ncr"]):
                        return opt
                for opt in options:
                    if "india" in opt.lower():
                        return opt
            if re.search(r"\bcity\b", lbl) and not any(k in lbl for k in ["state", "country", "address", "where", "reside", "live"]):
                return cand["city"]
            return f"{cand['city']}, {cand['state']}, {cand['country']}"
        if any(k in lbl for k in ["postal", "zip", "pincode", "pin code", "postal code"]):
            return cand["pincode"]
        if any(k in lbl for k in ["street address", "address line 1", "residential address", "home address"]):
            return cand["address"]
        if (any(k in lbl for k in ["gender", "what is your gender", "biological sex", "gender identity"]) or re.search(r"\bsex\b", lbl)) and "sexual" not in lbl and "orientation" not in lbl:
            return "Male"
        if any(k in lbl for k in ["race", "ethnicity", "ethnic origin"]):
            return "Asian"

        # ── 5.5 PROFESSIONAL REFERENCES (STRICT ZERO-FABRICATION RULE) ───────────
        # Consent/permission to contact references is Yes, but candidate has not provided
        # external reference person details. NEVER pull names/contacts out of thin air.
        if any(k in lbl for k in ["contact your references", "contact references", "may we contact", "permission to contact"]):
            return "Yes"
        if any(k in lbl for k in [
            "reference name", "ref name", "custname", "reference contact", "ref contact",
            "reference phone", "ref phone", "custphone", "reference email", "ref email", "custemail",
            "reference occupation", "ref occupation", "custoccupat", "reference company", "ref company", "custcompany",
            "years of working together", "years known", "years working", "custyears", "reference title"
        ]):
            return ""

        # ── 6. EDUCATION & ACADEMICS ─────────────────────────────────────────────
        if any(k in lbl for k in ["graduation year", "year of graduation", "completion year", "year of completion", "passing year", "year of passing", "passout year", "year of passout", "degree completion", "college year of completion"]):
            return cand.get("grad_year", "2020")
        if any(k in lbl for k in ["commencement year", "start year", "year of joining", "admission year"]) and any(k in lbl for k in ["college", "university", "education", "degree", "school"]):
            return cand.get("education_start_year", "2017")
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

        # ── 8. SPECIFIC & CORE TECH EXPERIENCE CHECK ─────────────────────────────
        # Azure Cloud / Synapse / Data Factory -> 2 years
        if any(k in lbl for k in ["azure", "synapse", "data factory", "adf", "azure cloud"]) and any(k in lbl for k in ["year", "yoe", "experience", "how many"]):
            return "2"

        # Databricks / Spark -> 4 years
        if any(k in lbl for k in ["databricks", "spark", "pyspark", "apache spark"]) and any(k in lbl for k in ["year", "yoe", "experience", "how many"]):
            return "4"

        # Power BI / QuickSight / BI Dashboards -> 4 years
        if any(k in lbl for k in ["power bi", "powerbi", "quicksight", "tableau", "bi tool", "dashboard"]) and any(k in lbl for k in ["year", "yoe", "experience", "how many"]):
            return "4"

        # GCP / BigQuery -> 4 years
        if any(k in lbl for k in ["gcp", "bigquery", "google cloud", "cloud storage"]) and any(k in lbl for k in ["year", "yoe", "experience", "how many"]):
            return "4"

        # Airflow / ETL / ELT -> 4 years
        if any(k in lbl for k in ["airflow", "apache airflow", "etl", "elt", "data pipeline"]) and any(k in lbl for k in ["year", "yoe", "experience", "how many"]):
            return "4"

        # Database / Data Lake / SQL / PostgreSQL / DBMS / DB Tools -> strictly 4 years
        if any(k in lbl for k in [
            "db", "database", "databases", "datalake", "data lake", "sql", "postgresql",
            "postgres", "rdbms", "dbms", "database tool", "database tools", "snowflake",
            "trino", "oracle", "nosql", "relational database"
        ]) and any(k in lbl for k in ["year", "yoe", "experience", "how many", "duration"]):
            return "4"

        for pat in cls.CORE_TECH_PATTERNS:
            if re.search(pat, lbl) and any(k in lbl for k in ["year", "yoe", "experience", "how many", "level"]):
                return cand["yoe_int"]

        # ── 9. TOTAL EXPERIENCE / SENIORITY ──────────────────────────────────────
        is_tool_specific = any(w in lbl for w in [" with ", " on ", " using ", " working on "])
        if not is_tool_specific and any(k in lbl for k in [
            "total experience", "overall experience", "years of experience", "total yoe",
            "relevant experience", "total work experience", "overall work experience",
            "months of experience", "experience in months", "total months"
        ]):
            is_months = any(k in lbl for k in ["in month", "in months", "total months", "months of experience", "months"])
            return cand.get("yoe_months", "60") if is_months else cand["yoe_int"]

        # ── 10. COMPLIANCE & LEGAL SCREENING (YES / NO) ──────────────────────────
        # Referral question (text vs boolean)
        if any(k in lbl for k in ["referred to this position", "referred by a current employee", "referral name", "employee referral"]):
            if field_type in ["select", "radio", "checkbox"]:
                return "No"
            return ""

        # City residence check: Factual (Candidate lives in Noida/NCR, open to relocate)
        # If question specifically asks if candidate currently resides in another city (e.g. Bangalore, Mumbai, Pune, Hyderabad)
        # Note: Relocation willingness is handled under positive compliance ('Yes')
        if any(k in lbl for k in [
            "currently residing in bengaluru", "currently residing in bangalore", "currently based in bengaluru",
            "currently based in bangalore", "currently in mumbai", "currently residing in mumbai",
            "currently in hyderabad", "currently residing in hyderabad", "currently in pune", "currently residing in pune",
            "currently based in hyderabad", "currently based in pune", "currently based in chennai"
        ]) and not any(k in lbl for k in ["relocate", "open to", "comfortable"]):
            return "No"

        # Currently residing in Delhi/Noida/NCR -> Yes
        if any(k in lbl for k in ["delhi", "noida", "gurugram", "gurgaon", "ncr"]) and any(k in lbl for k in ["currently", "reside", "based in", "from"]):
            return "Yes"

        # Currently Employed -> Yes
        if any(k in lbl for k in ["currently employed", "are you employed", "presently employed"]):
            return "Yes"

        # Active job offers in hand -> Yes
        if any(k in lbl for k in ["active job offers", "job offers in hand", "offer in hand", "holding any offer", "any other offers"]):
            return "Yes"

        # CTC Negotiable -> Yes
        if any(k in lbl for k in ["negotiable", "is your ctc negotiable", "is your salary negotiable", "open to negotiation"]):
            return "Yes"

        # Negative compliance & demographic questions (Always 'No')
        if any(k in lbl for k in [
            "visa sponsorship", "require sponsorship", "need sponsorship", "require visa",
            "future sponsorship", "employer-sponsored", "employer sponsored",
            "employee referral", "referred by", "personal relationship",
            "current employee", "know anyone", "family member", "relative",
            "current or former", "previously employed", "previous employment",
            "mindbody", "classpass", "egym", "booker",
            "felony", "criminal", "convicted", "crime", "misdemeanor",
            "non-compete", "non compete", "non-solicitation", "restrictive agreement",
            "worked with", "worked before", "associate / subsidiary", "worked for", "employee id",
            "physical ailment", "state of health", "medical condition", "maternity leave", "on leave during last 12 months",
            "appeared for an interview", "interview at any", "interviewed with", "interviewed during", "interview in last",
            "lgbtq", "identify as lgbtq", "sexual orientation", "veteran", "military", "disability", "disabled"
        ]):
            return "No"

        # Positive compliance questions (Always 'Yes')
        if any(k in lbl for k in [
            "eligible to work", "authorized to work in india", "authorized to work", "legally authorized", "right to work",
            "relocate", "relocation", "hybrid", "onsite", "in-office", "5 days onsite", "five days onsite", "remote",
            "open for 6 months contract", "open for contract", "contractor", "open for a contract",
            "exp in dbt and snowflake", "dbt and snowflake", "exp in dbt", "dbt", "snowflake",
            "travel", "willing to travel", "rotational", "flexible hours", "timezones",
            "us hours", "shift", "shifts", "night shift", "night shifts", "background check", "drug test",
            "passport", "valid passport", "indian passport",
            "agree to", "consent", "privacy policy", "terms and conditions", "gdpr",
            "talent community", "receive alerts", "future job alerts",
            "text messages", "receive sms", "consent to receive text"
        ]):
            return "Yes"

        # ── 11. TEXT & TEXTAREA ANSWERS (MICRO-NARRATIVES) ───────────────────────
        if field_type in ("text", "textarea"):
            if any(k in lbl for k in ["reason for seeking a job change", "reason for change", "why change", "why looking for a change"]):
                return (
                    "Seeking a higher-impact role in quantitative data engineering and analytics to leverage 4.8 years of "
                    "experience building high-scale data pipelines and statistical workflows."
                )
            if any(k in lbl for k in ["why do you want to join", "why this company", "why us", "interest in joining", "interested in joining"]):
                return (
                    "Excited to leverage my data engineering and analytics consulting background to solve mission-critical "
                    "enterprise challenges, build reliable data systems, and deliver measurable operational impact."
                )
            if any(k in lbl for k in ["tell us about yourself", "summary", "profile", "overview", "pitch", "brief bio"]):
                return (
                    "Business & Technology Consultant with 4.8 years of experience across healthcare commercial analytics, "
                    "Big Data pipelines, and AI agent automation. Ex-ZS Associates with a track record of driving data quality, "
                    "reconciliation agents, and high-performance ETL architectures."
                )
            if any(k in lbl for k in ["what makes you a good fit", "why should we hire you", "why are you the best"]):
                return (
                    "With 4.8 years of experience spanning Big Data pipelines, SQL performance tuning, and AI agent automation "
                    "at ZS Associates and Rush by Kira, I combine strong analytical rigor with practical execution."
                )
            if any(k in lbl for k in ["leadership", "management", "team", "people management"]):
                return (
                    "Managed a team of four at ZS Associates overseeing data standardization, cross-functional delivery, "
                    "and stakeholder reporting, reducing manual touchpoints by 80% while ensuring zero data discrepancies."
                )
            if any(k in lbl for k in ["describe your experience with", "work experience with", "experience working with"]):
                return (
                    "Extensive experience designing end-to-end data pipelines, ETL architectures, and predictive analytics "
                    "across Python, SQL, PostgreSQL, Snowflake, and Apache Airflow with zero data discrepancies."
                )
            if any(k in lbl for k in ["experience in pharma", "pharma domain", "pharmaceutical", "healthcare"]):
                return "Yes"

        # ── 12. DROPDOWN OPTION MATCHING ─────────────────────────────────────────
        if options:
            preferred_matches = [
                "yes", "immediate", "0 days", "0-15 days", "15 days",
                cand["city"].lower(), "india", "bachelor", "economics",
                cand["yoe_int"], "3-5 years", "3 to 5 years", "4-5 years"
            ]
            for pref in preferred_matches:
                for opt in options:
                    if "british indian" in opt.lower():
                        continue
                    if opt.strip().lower().startswith(pref):
                        return opt.strip()

        # ── 13. LOCAL KNOWLEDGE BASE LOOKUP (0 TOKENS, 0 NETWORK CALLS) ───────────
        kb_hit = cls.lookup_knowledge_base(lbl, field_type=field_type)
        if kb_hit:
            return kb_hit

        # ── 13.5. FAST SQLITE/FTS5 RECALL CACHE (EXACT + FUZZY) ───────────────────
        try:
            from intelligence.fast_recall_cache import get_qa_answer
            cached_qa = get_qa_answer(label, field_type=field_type, options=options)
            if cached_qa:
                return cached_qa
        except Exception:
            pass

        # ── 14. TIER 2 OPENROUTER FREE LLM FALLBACK ──────────────────────────────
        ai_res = ask_openrouter_free_llm(label, options=options, field_type=field_type)
        if ai_res:
            return ai_res

        # Fallback defaults
        if field_type == "number":
            return cand["yoe_int"]
        return "N/A"

    @classmethod
    def synthesize_autonomous_answer(
        cls,
        question: str,
        field_type: str = "text",
        options: Optional[List[str]] = None
    ) -> str:
        """
        Synthesize an autonomous, fact-based answer for any screening question
        directly from candidate profile without prompting the user.
        """
        ans = cls.match_question(question, field_type=field_type, options=options)
        if ans and ans != "N/A":
            return ans

        cand = load_candidate_context()
        lbl = (question or "").strip().lower()

        # Options-based autonomous resolution
        if options:
            opts_clean = [o.strip() for o in options if o.strip()]
            has_yes = any(o.lower() in ("yes", "willing", "agree") for o in opts_clean)
            has_no = any(o.lower() in ("no", "disagree") for o in opts_clean)
            if has_yes and has_no:
                if any(k in lbl for k in ["sponsorship", "crime", "felony", "non-compete", "disability", "veteran", "lgbtq"]):
                    return "No"
                return "Yes"

            # Proficiency levels (Intermediate / Expert)
            for opt in opts_clean:
                if any(level in opt.lower() for level in ["intermediate", "proficient", "expert", "advanced"]):
                    return opt

            for opt in opts_clean:
                if opt.lower() not in ("select", "select an option", "please select", "none", ""):
                    return opt

        if field_type == "number":
            if any(k in lbl for k in ["notice", "day", "week", "month", "gap"]):
                return "0"
            if any(k in lbl for k in ["ctc", "salary", "income", "compensation", "package"]):
                is_monthly = any(k in lbl for k in ["month", "monthly", "mo"])
                is_lpa = any(k in lbl for k in ["lpa", "lac", "lakh"])
                if is_monthly:
                    return str(int(cand["exp_ctc_inr"]) // 12)
                return cand["exp_ctc_lpa"] if is_lpa else cand["exp_ctc_inr"]
            return cand["yoe_int"]

        if any(k in lbl for k in ["experience", "background", "work", "project"]):
            return "Extensive experience designing scalable data pipelines, SQL transformations, and analytics solutions across Python, PostgreSQL, and Snowflake with 4.8 years of proven delivery."
        if any(k in lbl for k in ["why", "reason", "interest"]):
            return "Excited to leverage my data engineering and analytics consulting background to solve mission-critical data challenges and deliver high-impact enterprise solutions."

        return "Yes"
