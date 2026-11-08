#!/usr/bin/env python3
"""
LinkedIn Easy Apply Runner with OpenRouter Free Tier Integration.
Searches LinkedIn Easy Apply jobs for specified designations sorted by date descending,
fills application modals using candidate profile and OpenRouter Free models,
records applications to SQLite & CSV trackers, and keeps the browser interactive.

Usage:
    ./.venv/bin/python tools/linkedin_easy_apply_runner.py [--count N] [--keywords QUERY] [--location LOC] [--sort DD]
"""
import sys
import os
import time
import json
import re
import csv
import urllib.parse
import subprocess
import argparse
import shutil
from pathlib import Path
from datetime import datetime
from typing import TYPE_CHECKING, Optional, List, Dict

from playwright.sync_api import sync_playwright, Page, BrowserContext
import sqlite3

# ── Load Environment (.env) ──────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

def load_env():
    """Load key-value pairs from .env into os.environ if not already set."""
    env_file = ROOT_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

load_env()

TRACKER_CSV = (
    ROOT_DIR / "user_inputs" / "job_search_tracker.csv"
    if (ROOT_DIR / "user_inputs" / "job_search_tracker.csv").exists()
    else (ROOT_DIR / "job_search_tracker.csv")
)
JOBS_DB = ROOT_DIR / "jobs.db"
QA_KB_PATH = ROOT_DIR / "user_inputs" / "application_qa_knowledge_base.json"

CSV_FIELDS = [
    "date", "company", "sector", "role", "role_type", "channel",
    "status", "contact_person", "fit_rating", "notes", "cv_file",
    "cover_letter_file", "source", "deadline", "recruiter_search_link"
]

DAILY_EASY_APPLY_LIMIT = 40

LINKEDIN_GEO_MAP = {
    "delhi ncr": ("Delhi, India", "103444604"),
    "delhi": ("Delhi, India", "103444604"),
    "ncr": ("Delhi, India", "103444604"),
    "new delhi": ("New Delhi, Delhi, India", "106198888"),
    "noida": ("Noida, Uttar Pradesh, India", "104101886"),
    "gurugram": ("Gurugram, Haryana, India", "105556991"),
    "gurgaon": ("Gurugram, Haryana, India", "105556991"),
    "bengaluru": ("Bengaluru, Karnataka, India", "105214831"),
    "bangalore": ("Bengaluru, Karnataka, India", "105214831"),
    "hyderabad": ("Hyderabad, Telangana, India", "105556992"),
    "mumbai": ("Mumbai, Maharashtra, India", "106153096"),
    "pune": ("Pune, Maharashtra, India", "103644278"),
    "chennai": ("Chennai, Tamil Nadu, India", "104101887"),
    "india": ("India", "102713980"),
}

def resolve_linkedin_geo(loc_input: str) -> tuple[str, str]:
    """Resolve human location string to canonical LinkedIn location string and official geoId."""
    clean = loc_input.strip().lower()
    if clean in LINKEDIN_GEO_MAP:
        return LINKEDIN_GEO_MAP[clean]
    for k, v in LINKEDIN_GEO_MAP.items():
        if k in clean:
            return v
    foreign_terms = ["us", "usa", "united states", "uk", "germany", "singapore", "canada", "uae", "dubai", "michigan"]
    if "india" not in clean and not any(term in clean for term in foreign_terms):
        return (f"{loc_input.strip()}, India", "102713980")
    return (loc_input.strip(), "")

def get_today_easy_apply_count() -> int:
    """Return number of LinkedIn Easy Apply jobs submitted on the current calendar date."""
    today_str = datetime.now().strftime("%Y-%m-%d")
    count = 0
    if TRACKER_CSV.exists():
        try:
            with open(TRACKER_CSV, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get("date") == today_str and "Easy Apply" in (row.get("channel") or ""):
                        count += 1
        except Exception:
            pass
    return count


def alert(title: str, message: str):
    """Play alert chime and trigger macOS notification per Rule 2.3."""
    try:
        subprocess.Popen(["afplay", "/System/Library/Sounds/Glass.aiff"])
    except Exception:
        pass
    try:
        subprocess.run([
            "osascript", "-e",
            f'display notification "{message}" with title "{title}"'
        ], check=False)
    except Exception:
        pass


FAILED_APPS_CSV = ROOT_DIR / "user_inputs" / "failed_applications.csv"

def record_failed_application(company: str, role: str, job_url: str, reason: str, details: str = ""):
    """Record skipped, blocked, or failed Easy Apply attempts for diagnosis and review."""
    today = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fields = ["timestamp", "company", "role", "job_url", "reason", "details"]
    try:
        file_exists = FAILED_APPS_CSV.exists()
        FAILED_APPS_CSV.parent.mkdir(parents=True, exist_ok=True)
        with open(FAILED_APPS_CSV, mode="a", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            if not file_exists:
                writer.writeheader()
            writer.writerow({
                "timestamp": today,
                "company": company,
                "role": role,
                "job_url": job_url,
                "reason": reason,
                "details": details[:250]
            })
    except Exception:
        pass

def extract_min_yoe_requirement(desc_text: str) -> Optional[int]:
    """Extract required years of experience from job description if explicitly stated."""
    if not desc_text:
        return None
    patterns = [
        r'(?:minimum|at least|req(?:uire[sd]?)?)\s*(?:of)?\s*(\d+)\+?\s*years?',
        r'(\d+)\+?\s*years?(?:\s+of)?\s+(?:relevant\s+)?experience',
        r'(\d+)\s*(?:-|to)\s*(\d+)\s*years?(?:\s+of)?\s+experience',
    ]
    max_found = 0
    for pat in patterns:
        for match in re.finditer(pat, desc_text, re.IGNORECASE):
            val = int(match.group(1))
            if 0 < val <= 25:
                max_found = max(max_found, val)
    return max_found if max_found > 0 else None

def record_application(company: str, role: str, job_url: str, cv_path: str):
    """Append applied job to tracker CSV and jobs.db SQLite database."""
    today = datetime.now().strftime("%Y-%m-%d")
    clean_name = company.split("(")[0].strip().replace("&", "and")
    encoded_query = urllib.parse.quote(f"{clean_name} recruiter")
    recruiter_link = f"https://www.linkedin.com/search/results/people/?keywords={encoded_query}&origin=GLOBAL_SEARCH_HEADER"
    
    row_dict = {
        "date": today,
        "company": company,
        "sector": "Analytics & Technology",
        "role": role,
        "role_type": "Data Analytics",
        "channel": "LinkedIn Easy Apply",
        "status": "applied",
        "contact_person": "",
        "fit_rating": "90%",
        "notes": f"Applied autonomously via LinkedIn Easy Apply. Master CV: {cv_path}",
        "cv_file": cv_path,
        "cover_letter_file": "",
        "source": job_url,
        "deadline": "",
        "recruiter_search_link": recruiter_link
    }
    
    # 1. Append to CSV
    try:
        file_exists = TRACKER_CSV.exists()
        TRACKER_CSV.parent.mkdir(parents=True, exist_ok=True)
        with open(TRACKER_CSV, mode="a", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            if not file_exists:
                writer.writeheader()
            writer.writerow(row_dict)
        print(f"  [+] Logged to tracker CSV: {TRACKER_CSV.name}")
    except Exception as ce:
        print(f"  [!] Failed to append to CSV: {ce}")

    # 2. Append / update SQLite DB
    try:
        conn = sqlite3.connect(JOBS_DB)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_key TEXT UNIQUE,
                source TEXT,
                company TEXT NOT NULL,
                sector TEXT,
                title TEXT NOT NULL,
                role_type TEXT,
                url TEXT UNIQUE NOT NULL,
                location TEXT,
                department TEXT,
                salary TEXT,
                jd_text TEXT,
                fit_rating TEXT,
                score REAL DEFAULT 0.0,
                status TEXT DEFAULT 'discovered',
                notes TEXT,
                cv_file TEXT,
                cover_letter_file TEXT,
                contact_person TEXT,
                deadline TEXT,
                recruiter_search_link TEXT,
                claim_pid INTEGER,
                lease_until REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            INSERT INTO jobs (
                company, sector, title, role_type, source, status,
                contact_person, fit_rating, score, notes, cv_file,
                cover_letter_file, url, deadline, recruiter_search_link,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                status = excluded.status,
                notes = excluded.notes,
                updated_at = excluded.updated_at
        """, (
            company, "Analytics & Technology", role, "Data Analytics", "LinkedIn Easy Apply", "applied",
            "", "90%", 90.0, row_dict["notes"], cv_path,
            "", job_url, "", recruiter_link,
            today, today
        ))
        conn.commit()
        conn.close()
        print(f"  [+] Logged to SQLite database: {JOBS_DB.name}")
    except Exception as de:
        print(f"  [!] Failed to sync to SQLite: {de}")


# ── OpenRouter Free Model Q&A Engine ──────────────────────────────────────────

_QA_CACHE: Dict[str, str] = {}

def get_candidate_context_summary() -> str:
    """Return compact candidate context for OpenRouter free prompt caching."""
    name = os.getenv("CANDIDATE_NAME", "Candidate")
    yoe = os.getenv("CANDIDATE_TOTAL_YOE", "4.8")
    skills = os.getenv("CANDIDATE_PRIMARY_SKILLS", "Python, PySpark, SQL, Airflow, ETL")
    excluded = os.getenv("CANDIDATE_EXCLUDED_TECHS", "Java, Spring Boot, Kubernetes, Docker")
    ctc_lpa = os.getenv("CANDIDATE_CURRENT_CTC_LPA", "18.0")
    exp_ctc_lpa = os.getenv("CANDIDATE_EXPECTED_CTC_LPA", "28.0")
    ctc_inr = os.getenv("CANDIDATE_CURRENT_CTC_INR", "1800000")
    exp_ctc_inr = os.getenv("CANDIDATE_EXPECTED_CTC_INR", "2800000")
    notice = os.getenv("CANDIDATE_NOTICE_PERIOD", "Immediate Joiner (0 days notice)")
    city = os.getenv("CANDIDATE_CITY", "Noida")
    state = os.getenv("CANDIDATE_STATE", "Uttar Pradesh")
    country = os.getenv("CANDIDATE_COUNTRY", "India")
    edu = f"{os.getenv('CANDIDATE_DEGREE', '')}, {os.getenv('CANDIDATE_UNIVERSITY', '')}"
    
    return (
        f"Candidate: {name}\n"
        f"Total Experience: {yoe} years\n"
        f"Core Technical Skills: {skills}\n"
        f"Excluded Technologies (0 experience): {excluded}\n"
        f"Current Notice Period: {notice} (0 days, immediate availability)\n"
        f"Compensation: Current CTC = {ctc_lpa} LPA ({ctc_inr} INR) | Expected CTC = {exp_ctc_lpa} LPA ({exp_ctc_inr} INR)\n"
        f"Current Location: {city}, {state}, {country}. Authorized to work in India (No visa sponsorship required).\n"
        f"Work Flexibility: Open to Onsite/Hybrid/Remote and willing to relocate.\n"
        f"Education: {edu}\n"
        f"Referrals / Felonies / Non-compete: No personal relations at companies, No criminal record, No non-compete."
    )


def save_to_qa_knowledge_base(question: str, answer: str):
    """Save novel Q&A pair to application_qa_knowledge_base.json for permanent zero-token reuse."""
    if not QA_KB_PATH.exists():
        return
    try:
        data = json.loads(QA_KB_PATH.read_text(encoding="utf-8"))
        entries = data.get("qa_database", [])
        q_norm = question.strip().lower()
        for item in entries:
            for pat in item.get("question_patterns", []):
                if pat.lower() in q_norm or q_norm in pat.lower():
                    return  # already covered
        entries.append({
            "category": "ats_screening_openrouter_free",
            "question_patterns": [question.strip()],
            "standard_response": answer.strip(),
            "notes": "Generated autonomously via OpenRouter Free tier model."
        })
        QA_KB_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"  [KB] Stored new Q&A: '{question[:45]}...' -> '{answer}'")
    except Exception as e:
        print(f"  [KB Note] Could not save QA: {e}")


def ask_openrouter_free(question: str, options: Optional[List[str]] = None, field_type: str = "text") -> str:
    """Query OpenRouter zero-cost free models to answer ATS screening questions."""
    cache_key = f"{field_type}::{question.strip().lower()}::{'|'.join(options or [])}"
    if cache_key in _QA_CACHE:
        return _QA_CACHE[cache_key]

    try:
        from intelligence.llm_clients.openrouter import ask
    except ImportError:
        return ""

    context = get_candidate_context_summary()
    system_prompt = (
        "You are an ATS job application form filler representing the candidate.\n"
        "Your duty is to output ONLY the exact, factual string to enter or select into the form.\n"
        "Do NOT provide explanations, pleasantries, markdown, or commentary.\n"
        "CRITICAL RULE: Whenever experience, tenure, or duration is asked (e.g. years of experience, days notice, joining time, duration with a tool), "
        "NEVER write 'year', 'month', 'day', or decimals. Just write the integer value (e.g. 4 or 0).\n"
        f"{context}"
    )

    user_prompt = f"Field Question: {question}\nField Type: {field_type}\n"
    if options:
        user_prompt += "Available Options:\n" + "\n".join(f"- {opt}" for opt in options) + "\n"
        user_prompt += "Select and return ONLY the single exact option text from the list that best matches the candidate."
    else:
        if field_type == "number":
            user_prompt += "Return ONLY a single numeric value (e.g., 4 or 0)."
        else:
            user_prompt += "Return ONLY the concise exact value to type into the field."

    try:
        # Strictly use zero-cost free models
        response = ask(user_prompt, system=system_prompt, model="auto", max_tokens=100)
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
        if ans and field_type not in ("select", "radio"):
            # Enforce integer-only for duration / experience questions
            unit_match = re.match(r"^\s*(\d+(?:\.\d+)?)\s*(?:years?|yrs?|months?|mos?|days?)\s*$", ans, re.IGNORECASE)
            if unit_match:
                try:
                    ans = str(int(float(unit_match.group(1))))
                except ValueError:
                    pass
            elif any(k in question.lower() for k in ["experience", "yoe", "how many years", "how many days", "days notice"]):
                m_dig = re.search(r"\b(\d+(?:\.\d+)?)\b", ans)
                if m_dig:
                    try:
                        ans = str(int(float(m_dig.group(1))))
                    except ValueError:
                        pass
        if ans:
            _QA_CACHE[cache_key] = ans
            save_to_qa_knowledge_base(question, ans)
            print(f"  [OpenRouter Free QA] '{question[:40]}...' => '{ans}'")
            return ans
    except Exception as e:
        print(f"  [OpenRouter Free QA Note] {e}")

    return ""


# ── Q&A Answer Logic ──────────────────────────────────────────────────────────

def ask_user_for_answer(question: str, field_type: str = "text", options: list = None, timeout: int = 120) -> str:
    """
    Autonomously synthesize or resolve answer for screening question based on candidate profile.
    Acts as a true end-to-end automated agent, avoiding manual prompt stalls.
    """
    clean_q = re.sub(r"\s+", " ", question).strip()
    user_ans = ""

    # 1. First, synthesize autonomously from candidate profile and knowledge base
    try:
        from core.qa_semantics_engine import QASemanticsEngine
        user_ans = QASemanticsEngine.synthesize_autonomous_answer(clean_q, field_type=field_type, options=options)
    except Exception as synth_err:
        print(f"  [Auto-Synthesize Note] {synth_err}")

    if user_ans and user_ans != "N/A":
        print(f"  [✓] Autonomously answered from candidate profile: '{user_ans}' (Question: {clean_q[:60]})")
        save_to_qa_knowledge_base(clean_q, user_ans)
        _QA_CACHE[clean_q] = user_ans
        try:
            from core.qa_semantics_engine import QASemanticsEngine
            QASemanticsEngine.record_answer(clean_q, user_ans, field_type=field_type)
        except Exception:
            pass
        return user_ans

    # Fallback default
    fallback = options[0] if options else "Yes"
    save_to_qa_knowledge_base(clean_q, fallback)
    _QA_CACHE[clean_q] = fallback
    return fallback


def extract_upper_salary(page: Page) -> tuple[Optional[str], Optional[str]]:
    """
    Extract upper salary value from job posting text if a range is present.
    Returns (upper_inr_or_full, upper_lpa_or_number)
    """
    try:
        text = page.evaluate("""() => {
            const topCard = document.querySelector('.jobs-unified-top-card, .job-details-jobs-unified-top-card') || document.body;
            return topCard.innerText;
        }""")
        if not text:
            return None, None

        # Match LPA range: e.g. 20 - 35 LPA or 20-30 lakh
        m_lpa = re.search(r'(\d+(?:\.\d+)?)\s*(?:-|to|–|—)\s*(\d+(?:\.\d+)?)\s*(?:lpa|lac|lakh|lac/annum|lpa/annum)', text, re.IGNORECASE)
        if m_lpa:
            upper_lpa = m_lpa.group(2)
            upper_inr = str(int(float(upper_lpa) * 100000))
            return upper_inr, upper_lpa

        # Match INR range: e.g. ₹20,00,000 - ₹35,00,000
        m_inr = re.search(r'(?:₹|rs\.?|inr)\s*([\d,]+)\s*(?:-|to|–|—)\s*(?:₹|rs\.?|inr)?\s*([\d,]+)', text, re.IGNORECASE)
        if m_inr:
            upper_raw = m_inr.group(2).replace(',', '')
            return upper_raw, str(float(upper_raw) / 100000)

        # Match USD hourly range: e.g. $150–$200/hr
        m_usd = re.search(r'\$\s*([\d,]+)\s*(?:-|to|–|—)\s*\$\s*([\d,]+)', text, re.IGNORECASE)
        if m_usd:
            upper_usd = m_usd.group(2).replace(',', '')
            return upper_usd, upper_usd
    except Exception:
        pass
    return None, None


def answer_modal_questions(page: Page):
    """Fill every field inside the LinkedIn Easy Apply modal using QASemanticsEngine + OpenRouter Free fallback."""
    from core.qa_semantics_engine import QASemanticsEngine

    up_sal = extract_upper_salary(page)

    MODAL_SCOPE = "dialog[data-testid='dialog'], [data-sdui-screen*='EasyApply'], [role='dialog'], .jobs-easy-apply-modal, .artdeco-modal"
    scope = page.query_selector(MODAL_SCOPE) or page

    # ── 1. TEXT / NUMBER / TEL / URL / DATE inputs ────────────────────────────
    selectors = (
        "input[type='text'],"
        "input[type='number'],"
        "input[type='tel'],"
        "input[type='url'],"
        "input[type='date'],"
        "input:not([type])"
    )
    for inp in scope.query_selector_all(selectors):
        try:
            if not inp.is_visible():
                continue

            inp_id   = inp.get_attribute("id") or ""
            inp_type = inp.get_attribute("type") or "text"
            lbl_el   = page.query_selector(f"label[for='{inp_id}']") if inp_id else None
            lbl_text = (lbl_el.inner_text() if lbl_el else "").strip().lower()
            placeholder = (inp.get_attribute("placeholder") or "").strip().lower()
            name_attr = (inp.get_attribute("name") or "").strip().lower()
            aria_lbl = (inp.get_attribute("aria-label") or "").strip().lower()
            lbl = f"{lbl_text} {placeholder} {name_attr} {aria_lbl}"

            # Override outdated designation
            if "information technology consultant" in (inp.input_value() or "").lower():
                inp.fill("Business and Technology Consultant")

            if any(k in lbl for k in ["your title", "job title", "designation", "headline"]):
                inp.fill("Business and Technology Consultant")
                continue

            if inp.input_value():
                continue

            ans = QASemanticsEngine.match_question(
                label=lbl,
                field_type=inp_type,
                upper_salary=up_sal
            )
            if not ans or ans == "N/A":
                is_req = inp.get_attribute("required") is not None or inp.get_attribute("aria-required") == "true"
                if is_req:
                    clean_lbl = lbl_text or placeholder or aria_lbl or inp_id
                    ans = ask_user_for_answer(clean_lbl, field_type=inp_type)

            if ans and ans != "N/A":
                inp.fill(ans)
        except Exception:
            pass

    # ── 2. TEXTAREA ────────────────────────────────────────────────────────────
    for ta in scope.query_selector_all("textarea"):
        try:
            if not ta.is_visible():
                continue
            ta_id = ta.get_attribute("id") or ""
            lbl_el = page.query_selector(f"label[for='{ta_id}']") if ta_id else None
            lbl_text = (lbl_el.inner_text() if lbl_el else "").strip()
            placeholder = (ta.get_attribute("placeholder") or "").strip()
            aria_lbl = (ta.get_attribute("aria-label") or "").strip()
            parent_lbl = ta.evaluate("el => el.closest('.fb-dash-form-element, fieldset, div')?.querySelector('label, legend, span, p')?.innerText || ''").strip()
            lbl = f"{lbl_text} {aria_lbl} {placeholder} {parent_lbl}".strip()
            
            # If current value is invalid or wrong, or empty, recompute
            cur_val = ta.input_value()
            needs_fill = not cur_val or (
                any(k in lbl.lower() for k in ["compensation", "salary", "ctc", "pay"]) and
                any(k in cur_val.lower() for k in ["bachelor", "degree", "economics", "consultant", "experience"])
            )
            if not needs_fill:
                continue

            ans = QASemanticsEngine.match_question(lbl or "Describe candidate qualifications", field_type="textarea", upper_salary=up_sal)
            if not ans or ans == "N/A":
                is_req = ta.get_attribute("required") is not None or ta.get_attribute("aria-required") == "true"
                if is_req:
                    ans = ask_user_for_answer(lbl or "Candidate Qualifications", field_type="textarea")

            ta.fill(ans if ans and ans != "N/A" else "4.8 years of experience in Data Engineering, Analytics & AI Agent Development.")
        except Exception:
            pass

    # ── 3. DROPDOWNS / SELECT ───────────────────────────────────────────────────
    for sel in scope.query_selector_all("select"):
        try:
            if not sel.is_visible():
                continue
            cur = sel.input_value()
            if cur and cur.lower() not in ("", "select an option", "please select", "select", "none"):
                continue
            
            options = sel.query_selector_all("option")
            opt_texts = [o.inner_text().strip() for o in options if o.inner_text().strip()]
            if not opt_texts:
                continue

            # ── 3a. Handle Date Dropdowns (Work Experience & Education Month/Year) ──
            is_month_dropdown = any(m in opt_texts for m in ["January", "Jan", "February", "Feb"])
            is_year_dropdown = any(y in opt_texts for y in ["2020", "2021", "2022", "2023", "2024"])

            if is_month_dropdown or is_year_dropdown:
                container_text = sel.evaluate("""el => {
                    const p = el.closest('fieldset, .fb-dash-form-element, div[class*="date"], div');
                    return p ? (p.innerText || '') : '';
                }""").lower()
                is_end_date = "end" in container_text or "to" in container_text or "graduation" in container_text
                is_education = "education" in container_text or "degree" in container_text or "school" in container_text or "university" in container_text
                target_val = None
                if is_month_dropdown:
                    target_month = "July" if is_education else ("July" if is_end_date else "October")
                    for opt in options:
                        t = opt.inner_text().strip()
                        if t.lower().startswith(target_month.lower()[:3]):
                            target_val = opt.get_attribute("value") or t
                            break
                elif is_year_dropdown:
                    if is_education:
                        target_year = "2020" if is_end_date else "2017"
                    else:
                        target_year = "2024" if is_end_date else "2020"
                    for opt in options:
                        t = opt.inner_text().strip()
                        if target_year in t:
                            target_val = opt.get_attribute("value") or t
                            break
                if target_val is not None:
                    sel.select_option(value=target_val)
                    sel.dispatch_event("change")
                    print(f"  [Date Dropdown] Selected '{target_val}' ({'End' if is_end_date else 'Start'} {'Month' if is_month_dropdown else 'Year'})")
                    continue

            sel_id = sel.get_attribute("id") or ""
            lbl_el = page.query_selector(f"label[for='{sel_id}']") if sel_id else None
            lbl = (lbl_el.inner_text() if lbl_el else "").strip().lower()
            if not lbl:
                lbl = (sel.get_attribute("aria-label") or "").strip().lower()
            if not lbl:
                try:
                    parent_lbl = sel.evaluate("el => el.closest('.fb-dash-form-element, .jobs-easy-apply-modal__section, label')?.querySelector('label, .fb-dash-form-element__label, legend')?.innerText || ''")
                    if parent_lbl:
                        lbl = parent_lbl.strip().lower()
                except Exception:
                    pass

            ans = QASemanticsEngine.match_question(lbl or sel_id, field_type="select", options=opt_texts)
            if not ans or ans == "N/A":
                ans = ask_user_for_answer(lbl or sel_id, field_type="select", options=opt_texts)

            if ans and ans != "N/A":
                ans_clean = ans.strip().lower()
                matched_val, matched_txt = None, None
                for opt in options:
                    opt_t = opt.inner_text().strip()
                    opt_clean = opt_t.lower()
                    if opt_clean == ans_clean:
                        matched_val, matched_txt = opt.get_attribute("value"), opt_t
                        break
                if not matched_val:
                    for opt in options:
                        opt_t = opt.inner_text().strip()
                        opt_clean = opt_t.lower()
                        if ans_clean == "male" and "female" in opt_clean:
                            continue
                        if re.search(r"\b" + re.escape(ans_clean) + r"\b", opt_clean):
                            matched_val, matched_txt = opt.get_attribute("value"), opt_t
                            break
                if not matched_val and ans_clean not in ("male", "no"):
                    for opt in options:
                        opt_t = opt.inner_text().strip()
                        opt_clean = opt_t.lower()
                        if ans_clean in opt_clean or opt_clean in ans_clean:
                            matched_val, matched_txt = opt.get_attribute("value"), opt_t
                            break
                if matched_val is not None:
                    sel.select_option(value=matched_val)
                    sel.dispatch_event("change")
                    print(f"  [Dropdown] Selected '{matched_txt}' for '{lbl[:30]}'")
        except Exception:
            pass

    # ── 4. RADIO BUTTONS (Robust Name-Based Grouping for SDUI & Standard HTML) ─
    all_radios = scope.query_selector_all("input[type='radio']")
    radio_groups = {}
    for r in all_radios:
        if not r.is_visible():
            continue
        r_name = r.get_attribute("name") or f"unnamed_{id(r)}"
        radio_groups.setdefault(r_name, []).append(r)

    for group_name, radios in radio_groups.items():
        try:
            if not radios or any(r.is_checked() for r in radios):
                continue

            first_r = radios[0]
            leg_text = first_r.evaluate("""el => {
                const aria = el.getAttribute('aria-label');
                if (aria && aria.trim()) return aria.trim();
                const fs = el.closest('fieldset');
                if (fs) {
                    const leg = fs.querySelector('legend');
                    if (leg && leg.innerText.trim()) return leg.innerText.trim();
                }
                const rg = el.closest('[role="radiogroup"], .fb-dash-form-element, div[class*="form"], div');
                if (rg) {
                    const p = rg.parentElement;
                    const prev = p ? p.querySelector('label, [class*="label"], p, span, h3, h4, legend') : null;
                    if (prev && prev.innerText.trim()) return prev.innerText.trim();
                    const direct = rg.querySelector('label, [class*="label"], p, span, legend');
                    if (direct && direct.innerText.trim()) return direct.innerText.trim();
                }
                return '';
            }""").strip().lower()

            radio_labels = []
            for r in radios:
                r_lbl = r.evaluate("""el => {
                    let optText = "";
                    let p = el.parentElement;
                    for (let i = 0; i < 3 && p; i++) {
                        const t = (p.innerText || "").trim();
                        if (t && t !== el.getAttribute("aria-label")) { optText = t; break; }
                        p = p.parentElement;
                    }
                    return (optText || el.value || "").trim();
                }""").strip()
                if r_lbl:
                    radio_labels.append(r_lbl)

            # Direct Demographic & Enterprise Rules
            if (any(k in leg_text for k in ["gender", "what is your gender", "biological sex", "gender identity"]) or re.search(r"\bsex\b", leg_text)) and "orientation" not in leg_text:
                ans = "Male"
            elif any(k in leg_text for k in ["lgbtq", "identify as lgbtq", "sexual orientation"]):
                ans = "No"
            elif any(k in leg_text for k in ["veteran", "military status", "protected veteran"]):
                ans = "No"
            elif any(k in leg_text for k in ["disability", "disabled"]):
                ans = "No"
            elif any(k in leg_text for k in ["personal relationship", "relationship with a current", "relationship with employee"]):
                ans = "No"
            elif any(k in leg_text for k in ["booking holdings", "presently employed"]):
                ans = "No"
            elif any(k in leg_text for k in ["use of personal data", "personal data"]):
                ans = "Yes"
            elif any(k in leg_text for k in ["sms updates", "text/sms updates"]):
                ans = "Yes"
            elif any(k in leg_text for k in ["newsletters", "email me about other job openings"]):
                ans = "Yes"
            elif any(k in leg_text for k in ["previously applied"]):
                ans = "No"
            else:
                ans = QASemanticsEngine.match_question(leg_text or "Screening question", field_type="radio", options=radio_labels)
                if not ans or ans == "N/A":
                    ans = ask_user_for_answer(leg_text or "Screening question", field_type="radio", options=radio_labels)

            if ans and ans != "N/A":
                ans_clean = ans.strip().lower()
                matched_r, matched_lbl, matched_txt = None, None, None

                # 1. Exact match first
                for r in radios:
                    lbl_txt = r.evaluate("""el => {
                        let optText = "";
                        let p = el.parentElement;
                        for (let i = 0; i < 3 && p; i++) {
                            const t = (p.innerText || "").trim();
                            if (t && t !== el.getAttribute("aria-label")) { optText = t; break; }
                            p = p.parentElement;
                        }
                        return (optText || el.value || "").trim().toLowerCase();
                    }""")
                    if ans_clean == lbl_txt:
                        matched_r, matched_txt = r, lbl_txt
                        break

                # 2. Word boundary regex (strictly avoid "female" matching "male")
                if not matched_r:
                    for r in radios:
                        lbl_txt = r.evaluate("""el => {
                            let optText = "";
                            let p = el.parentElement;
                            for (let i = 0; i < 3 && p; i++) {
                                const t = (p.innerText || "").trim();
                                if (t && t !== el.getAttribute("aria-label")) { optText = t; break; }
                                p = p.parentElement;
                            }
                            return (optText || el.value || "").trim().toLowerCase();
                        }""")
                        if ans_clean == "male" and "female" in lbl_txt:
                            continue
                        if re.search(r"\b" + re.escape(ans_clean) + r"\b", lbl_txt):
                            matched_r, matched_txt = r, lbl_txt
                            break

                # 3. Fallback loose match only if not male/female or boolean
                if not matched_r and ans_clean not in ("male", "no"):
                    for r in radios:
                        lbl_txt = r.evaluate("""el => {
                            let optText = "";
                            let p = el.parentElement;
                            for (let i = 0; i < 3 && p; i++) {
                                const t = (p.innerText || "").trim();
                                if (t && t !== el.getAttribute("aria-label")) { optText = t; break; }
                                p = p.parentElement;
                            }
                            return (optText || el.value || "").trim().toLowerCase();
                        }""")
                        if ans_clean in lbl_txt or lbl_txt in ans_clean:
                            matched_r, matched_txt = r, lbl_txt
                            break

                if matched_r:
                    try:
                        page.evaluate("""(r) => {
                            let p = r.parentElement;
                            for (let i = 0; i < 2 && p; i++) {
                                p.click();
                                p = p.parentElement;
                            }
                            r.click();
                            r.checked = true;
                            r.dispatchEvent(new Event('input', { bubbles: true }));
                            r.dispatchEvent(new Event('change', { bubbles: true }));
                        }""", matched_r)
                    except Exception:
                        try:
                            if matched_lbl and matched_lbl.is_visible():
                                matched_lbl.click()
                            else:
                                matched_r.check(force=True)
                        except Exception:
                            pass
                    print(f"  [Radio] Selected '{matched_txt or ans}' for '{leg_text[:30]}'")
        except Exception:
            pass

    # ── 5. CHECKBOXES (consent, terms, and candidate skills) ───────────────────────
    CORE_SKILLS = ["sql", "python", "pyspark", "spark", "snowflake", "airflow", "tableau", "aws", "postgresql", "bigquery", "databricks", "trino", "excel", "powerbi", "git", "linux", "etl"]

    for cb in scope.query_selector_all("input[type='checkbox']"):
        try:
            if not cb.is_visible() or cb.is_checked():
                continue
            cb_id = cb.get_attribute("id") or ""
            lbl_el = page.query_selector(f"label[for='{cb_id}']") if cb_id else None
            lbl_txt = (lbl_el.inner_text() if lbl_el else "").strip().lower()
            if not lbl_txt:
                lbl_txt = cb.evaluate("el => (el.closest('label, li, div')?.innerText || el.getAttribute('aria-label') || '')").strip().lower()

            # 1. Terms & consent
            if any(k in lbl_txt for k in ["agree", "consent", "accept", "terms", "privacy", "policy", "acknowledge"]):
                cb.check()
                print(f"  [Checkbox] Checked terms/consent: '{lbl_txt[:30]}'")
                continue

            # 2. Candidate core technical skills
            if any(skill in lbl_txt for skill in CORE_SKILLS) and "none" not in lbl_txt:
                cb.check()
                print(f"  [Checkbox] Checked skill: '{lbl_txt[:30]}'")
                continue
        except Exception:
            pass


# ── Single-job application flow ───────────────────────────────────────────────

def _find_modal_btn(page: Page, *selectors):
    """Return first visible button matching any selector, else None."""
    for sel in selectors:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible() and not el.is_disabled():
                return el
        except Exception:
            pass
    return None


def clear_all_overlays(page: Page):
    """
    Force-dismiss any open LinkedIn dialog overlays using JS evaluation.
    Handles: Easy Apply modal, Discard confirmation, generic confirmations.
    """
    try:
        # 1. Click 'Discard' on discard-confirmation dialog first
        page.evaluate("""
            () => {
                const discardSelectors = [
                    'button[data-control-name="discard_application_confirm_btn"]',
                    'button.artdeco-modal__confirm-dialog-btn',
                    'button[data-test-dialog-secondary-action]',
                ];
                for (const sel of discardSelectors) {
                    const btn = document.querySelector(sel);
                    if (btn) { btn.click(); return; }
                }
                for (const btn of document.querySelectorAll('button')) {
                    if (btn.innerText.trim().toLowerCase() === 'discard') {
                        btn.click(); return;
                    }
                }
            }
        """)
        time.sleep(0.8)
    except Exception:
        pass

    try:
        # 2. Dismiss Easy Apply modal if still open
        page.evaluate("""
            () => {
                const dismissSelectors = [
                    'dialog[data-testid="dialog"] button[aria-label*="Dismiss" i]',
                    'dialog[data-testid="dialog"] button[aria-label*="Close" i]',
                    '[data-sdui-screen*="EasyApply"] button[aria-label*="Dismiss" i]',
                    '[data-sdui-screen*="EasyApply"] button[aria-label*="Close" i]',
                    '.jobs-easy-apply-modal button[aria-label="Dismiss"]',
                    '.jobs-easy-apply-modal button[aria-label="Fermer"]',
                    'button[aria-label="Dismiss"]',
                    'button[aria-label="Close"]',
                ];
                for (const sel of dismissSelectors) {
                    const btn = document.querySelector(sel);
                    if (btn && btn.offsetParent !== null) { btn.click(); return; }
                }
            }
        """)
        time.sleep(0.8)
    except Exception:
        pass

    try:
        # 3. Second pass for discard confirmation
        page.evaluate("""
            () => {
                for (const btn of document.querySelectorAll('button')) {
                    if (btn.innerText.trim().toLowerCase() === 'discard') {
                        btn.click(); return;
                    }
                }
            }
        """)
        time.sleep(0.5)
    except Exception:
        pass


def apply_to_current_job(page: Page, review_only: bool = False) -> bool:
    """Complete the Easy Apply modal for whatever job is currently open."""
    # ── Job Liveness Pre-Flight Check (Zero-Token Expired Posting Guard) ────
    try:
        from core.job_liveness_detector import is_job_expired
        card_text = page.evaluate("() => { const card = document.querySelector('.jobs-search__job-details, .jobs-details'); return card ? card.innerText : ''; }")
        expired, reason = is_job_expired(card_text)
        if expired:
            print(f"  [-] Skipped closed/expired posting: '{reason}'")
            return False
    except Exception:
        pass

    # ── Easy Apply Button Resolution (Polling up to 4.0s) ─────────────────
    btn = None
    easy_apply_selectors = [
        "button[aria-label*='Easy Apply' i]",
        "a[aria-label*='Easy Apply' i]",
        "button.jobs-apply-button",
        "a.jobs-apply-button",
        ".jobs-apply-button--top-card button",
        ".jobs-apply-button--top-card a",
        ".jobs-s-apply button",
        ".jobs-s-apply a",
        "[data-view-name='job-details'] button:has-text('Easy Apply')",
        "[data-view-name='job-details'] a:has-text('Easy Apply')",
        "button:has-text('Easy Apply')",
        "a:has-text('Easy Apply')",
        "[role='button']:has-text('Easy Apply')",
        "div[aria-label*='Easy Apply' i]"
    ]

    for poll_idx in range(8):
        # 1. Check if already applied
        applied_el = page.query_selector(".jobs-applied-badge, [aria-label*='Applied' i], span:has-text('Applied')")
        if applied_el and applied_el.is_visible():
            applied_txt = (applied_el.inner_text() or "").strip()
            if "applied" in applied_txt.lower():
                print(f"  [-] Already applied on LinkedIn ('{applied_txt}').")
                return False

        # 2. Check for Easy Apply button
        for sel in easy_apply_selectors:
            try:
                candidate_btn = page.query_selector(sel)
                if candidate_btn and candidate_btn.is_visible():
                    c_txt = (candidate_btn.inner_text() or "").strip().lower()
                    c_aria = (candidate_btn.get_attribute("aria-label") or "").lower()
                    if "easy apply" in c_txt or "easy apply" in c_aria:
                        btn = candidate_btn
                        break
            except Exception:
                pass
        if btn:
            break

        # 3. Check for external Apply
        ext_el = page.query_selector("button.jobs-apply-button, a.jobs-apply-button, button:has-text('Apply')")
        if ext_el and ext_el.is_visible():
            ext_txt = (ext_el.inner_text() or "").strip().lower()
            if ext_txt == "apply" or "apply on company website" in (ext_el.get_attribute("aria-label") or "").lower():
                print(f"  [-] Skipped external company site application (not Easy Apply).")
                return False

        time.sleep(0.5)

    if not btn:
        print("  [-] Easy Apply button not found (posting may be loading, expired, or non-Easy Apply).")
        return False

    print("  [+] Clicking 'Easy Apply'…")
    try:
        btn.scroll_into_view_if_needed()
        time.sleep(0.2)
        btn.click(timeout=4000)
    except Exception:
        page.evaluate("(el) => el.click()", btn)
    time.sleep(2)

    MODAL_SEL = "dialog[data-testid='dialog'], [data-sdui-screen*='EasyApply'], [role='dialog'], .jobs-easy-apply-modal, .artdeco-modal"
    modal = None
    for _ in range(8):
        modal = page.query_selector(MODAL_SEL)
        if modal and modal.is_visible():
            break
        time.sleep(0.5)

    if not modal or not modal.is_visible():
        print("  [-] Modal did not appear.")
        return False

    # Check for LinkedIn daily Easy Apply limit popup or page warning
    modal_txt = (modal.inner_text() or "").replace("’", "'").lower()
    page_txt = (page.inner_text("body") or "").replace("’", "'").lower()
    combined_alert_text = f"{modal_txt} {page_txt}"
    limit_keywords = [
        "reached today's easy apply limit",
        "limit easy apply submissions",
        "continue applying tomorrow",
        "reached the daily application limit",
        "reached the application limit",
        "cannot apply to any more jobs",
        "daily application limit",
        "daily easy apply limit"
    ]
    if any(k in combined_alert_text for k in limit_keywords):
        print("\n" + "=" * 65)
        print("  [!] LINKEDIN DAILY EASY APPLY LIMIT REACHED!")
        print("  [!] LinkedIn stated: 'You reached today’s Easy Apply limit.'")
        print("  [!] All available submissions for today have been completed.")
        print("  [!] Halting automation immediately per Rule 2.5 to protect account standing.")
        print("=" * 65 + "\n")
        alert("LinkedIn Daily Limit", "You reached today’s Easy Apply limit on LinkedIn. Automation halted safely.")
        try:
            got_it = modal.query_selector("button:has-text('Got it'), button[aria-label='Dismiss']")
            if got_it:
                got_it.click()
        except Exception:
            pass
        raise RuntimeError("LINKEDIN_DAILY_LIMIT_REACHED")

    review_clicked = False
    last_step_sig = ""
    last_unfilled_sig = None
    stuck_count = 0

    for step in range(15):
        time.sleep(1.5)
        print(f"  [*] Modal step {step + 1}…")

        current_step_sig = page.evaluate("""() => {
            const m = document.querySelector("dialog[data-testid='dialog'], [data-sdui-screen*='EasyApply'], [role='dialog'], .jobs-easy-apply-modal, .artdeco-modal");
            return m ? m.innerText.replace(/\\s+/g, ' ').trim() : '';
        }""")

        norm_step = current_step_sig.replace("’", "'").lower()
        if any(k in norm_step for k in limit_keywords):
            print("\n" + "=" * 65)
            print("  [!] LINKEDIN DAILY EASY APPLY LIMIT REACHED (detected in modal step)!")
            print("  [!] Halting automation immediately per Rule 2.5 to protect account standing.")
            print("=" * 65 + "\n")
            alert("LinkedIn Daily Limit", "You reached today’s Easy Apply limit on LinkedIn. Automation halted safely.")
            try:
                got_it = modal.query_selector("button:has-text('Got it'), button[aria-label='Dismiss']")
                if got_it:
                    got_it.click()
            except Exception:
                pass
            raise RuntimeError("LINKEDIN_DAILY_LIMIT_REACHED")

        if last_step_sig and current_step_sig == last_step_sig:
            stuck_count += 1
            print(f"  [!] Modal remained on step after click (attempt {stuck_count}). Checking for missing answers / errors…")
        else:
            stuck_count = 0
            last_unfilled_sig = None

            # Try saving inner card first
            inner_save = _find_modal_btn(
                page,
                "dialog[data-testid='dialog'] button:has-text('Save')",
                "[data-sdui-screen*='EasyApply'] button:has-text('Save')",
                ".jobs-easy-apply-modal button:has-text('Save')",
                "[role='dialog'] button:has-text('Save')"
            )
            if inner_save:
                print("  [+] Inner Save button detected, attempting to save card...")
                try:
                    inner_save.click(timeout=2000)
                except Exception:
                    page.evaluate("(el) => el.click()", inner_save)
                time.sleep(1.5)

            # Inspect unfilled fields or error messages with SDUI radio support
            unfilled = page.evaluate("""() => {
                const modal = document.querySelector("dialog[data-testid='dialog'], [data-sdui-screen*='EasyApply'], [role='dialog'], .jobs-easy-apply-modal, .artdeco-modal");
                if (!modal) return [];
                const res = [];
                const seenRadioNames = new Set();

                for (const el of modal.querySelectorAll("input, select, textarea")) {
                    if (el.offsetParent === null) continue;
                    const tag = el.tagName.toLowerCase();
                    const type = (el.getAttribute("type") || tag).toLowerCase();
                    if (type === "hidden" || type === "file") continue;
                    
                    let isUnfilled = false;
                    let opts = [];
                    if (type === "radio") {
                        const name = el.getAttribute("name") || el.id;
                        if (seenRadioNames.has(name)) continue;
                        seenRadioNames.add(name);

                        // Check if ANY radio in this group is checked
                        const groupChecked = el.name ? !!modal.querySelector(`input[type='radio'][name='${el.name}']:checked`) : el.checked;
                        if (groupChecked) continue;

                        isUnfilled = true;
                        const radios = el.name ? Array.from(modal.querySelectorAll(`input[type='radio'][name='${el.name}']`)) : [el];
                        opts = radios.map(r => {
                            let optText = "";
                            let p = r.parentElement;
                            for (let i = 0; i < 3 && p; i++) {
                                const t = (p.innerText || "").trim();
                                if (t && t !== r.getAttribute("aria-label")) { optText = t; break; }
                                p = p.parentElement;
                            }
                            return (optText || r.value || "").trim();
                        }).filter(Boolean);
                    } else if (type === "checkbox") {
                        if (!el.checked && (el.required || el.getAttribute("aria-required") === "true")) {
                            isUnfilled = true;
                        }
                    } else if (tag === "select") {
                        if (!el.value || el.value.toLowerCase() === "select an option") {
                            isUnfilled = true;
                            opts = Array.from(el.options).map(o => o.text.trim()).filter(t => t && !t.toLowerCase().includes("select"));
                        }
                    } else {
                        if (!el.value.trim() && (el.required || el.getAttribute("aria-required") === "true")) {
                            isUnfilled = true;
                        }
                    }
                    
                    if (isUnfilled) {
                        let lbl = "";
                        if (el.id) {
                            const l = modal.querySelector(`label[for="${el.id}"]`);
                            if (l) lbl = l.innerText.trim();
                        }
                        if (!lbl) lbl = el.getAttribute("aria-label") || "";
                        if (!lbl) {
                            const p = el.closest(".fb-dash-form-element, fieldset, label, div");
                            lbl = p ? (p.querySelector("label, legend, span, p")?.innerText || "") : "";
                        }
                        res.push({tag, type, id: el.id, name: el.name || "", label: lbl.trim(), options: opts});
                    }
                }
                return res;
            }""")

            unfilled_sig = tuple(sorted(f"{uf.get('type')}:{uf.get('id')}:{uf.get('label')}" for uf in unfilled))
            is_deadlocked = bool(unfilled_sig and unfilled_sig == last_unfilled_sig)
            last_unfilled_sig = unfilled_sig
            if is_deadlocked:
                print("  [!] Form deadlock detected: required questions remain unchanged across consecutive passes.")

            for uf in unfilled:
                q_lbl = uf.get("label") or uf.get("id") or "Screening question"
                q_type = uf.get("type", "text")
                q_opts = uf.get("options", [])

                # Check cache first before bothering user
                cached_ans = _QA_CACHE.get(q_lbl) or _QA_CACHE.get(q_lbl.lower())
                if not cached_ans:
                    from core.qa_semantics_engine import QASemanticsEngine
                    cached_ans = QASemanticsEngine.match_question(q_lbl, field_type=q_type, options=q_opts)
                if not cached_ans or cached_ans == "N/A":
                    val = ask_user_for_answer(q_lbl, field_type=q_type, options=q_opts)
                else:
                    val = cached_ans

                if val and val != "N/A":
                    try:
                        if q_type in ("text", "number", "tel", "url", "textarea", "date") and uf.get("id"):
                            el = page.query_selector(f"#{uf['id']}")
                            if el:
                                el.fill(val)
                        elif q_type == "select" and uf.get("id"):
                            el = page.query_selector(f"#{uf['id']}")
                            if el:
                                for opt in el.query_selector_all("option"):
                                    if val.lower() in opt.inner_text().strip().lower():
                                        el.select_option(value=opt.get_attribute("value"))
                                        el.dispatch_event("change")
                                        break
                        elif q_type == "radio":
                            # Atomic radio selection by name or id
                            r_name = uf.get("name")
                            r_id = uf.get("id")
                            page.evaluate("""([targetName, targetId, answer]) => {
                                const ansLower = answer.trim().toLowerCase();
                                const radios = targetName
                                    ? Array.from(document.querySelectorAll(`input[type='radio'][name='${targetName}']`))
                                    : (targetId ? [document.getElementById(targetId)] : []);
                                for (const r of radios) {
                                    if (!r) continue;
                                    let optText = "";
                                    let p = r.parentElement;
                                    for (let i = 0; i < 3 && p; i++) {
                                        const t = (p.innerText || "").trim();
                                        if (t && t !== r.getAttribute("aria-label")) { optText = t; break; }
                                        p = p.parentElement;
                                    }
                                    const lbl = (optText || r.value || "").trim().toLowerCase();
                                    if (lbl === ansLower || (ansLower.length > 2 && lbl.includes(ansLower)) || (lbl.length > 2 && ansLower.includes(lbl))) {
                                        let parent = r.parentElement;
                                        for (let i = 0; i < 2 && parent; i++) {
                                            parent.click();
                                            parent = parent.parentElement;
                                        }
                                        r.click();
                                        r.checked = true;
                                        r.dispatchEvent(new Event('input', { bubbles: true }));
                                        r.dispatchEvent(new Event('change', { bubbles: true }));
                                        break;
                                    }
                                }
                            }""", [r_name, r_id, val])
                    except Exception as fe:
                        pass

            if stuck_count >= 3 or (stuck_count >= 2 and is_deadlocked):
                print("\n" + "=" * 65)
                print("  [!] Form cannot advance automatically (stall/deadlock detected).")
                print("  [!] Leaving form modal open on display for candidate review.")
                print("  [!] Application modal is NOT dismissed per user instruction.")
                print("=" * 65 + "\n")
                alert("Application Paused", "Application paused for review. Modal is open on screen.")
                return False

        last_step_sig = current_step_sig

        # ── Resume verification and upload (Token-Lean & Duplicate Prevention) ──
        if RESUME_PATH and RESUME_PATH.exists():
            cv_target_name = RESUME_PATH.name.lower()
            cv_stem = RESUME_PATH.stem.lower()

            # Cross-verify if CV matching our latest tool CV is already present / selected
            cv_already_selected = page.evaluate("""([targetName, targetStem]) => {
                const modal = document.querySelector("dialog[data-testid='dialog'], [data-sdui-screen*='EasyApply'], [role='dialog'], .jobs-easy-apply-modal, .artdeco-modal");
                if (!modal) return false;

                // 1. Check existing file name elements
                const nameEls = Array.from(modal.querySelectorAll(
                    '.jobs-document-upload__file-name, .jobs-resume-picker__resume-name, .jobs-resume-picker__file-name, [data-test-resume-file-name]'
                ));
                for (const el of nameEls) {
                    const txt = (el.innerText || '').toLowerCase();
                    if (txt.includes(targetName) || (targetStem && txt.includes(targetStem))) {
                        const container = el.closest('[role="radio"], .jobs-resume-picker__resume, label, li');
                        const isChecked = container && (
                            container.getAttribute('aria-checked') === 'true' ||
                            container.querySelector('input[type="radio"]:checked') !== null ||
                            container.classList.contains('jobs-resume-picker__resume--selected')
                        );
                        if (isChecked || !modal.querySelector('input[type="radio"]')) {
                            return true;
                        }
                    }
                }

                // 2. Check selectable resume radio options / cards
                const radioEls = Array.from(modal.querySelectorAll('input[type="radio"]'));
                for (const r of radioEls) {
                    const lbl = r.closest('label')?.innerText || r.closest('.fb-dash-form-element, li')?.innerText || '';
                    const lblLow = lbl.toLowerCase();
                    if (lblLow.includes(targetName) || (targetStem && lblLow.includes(targetStem))) {
                        if (r.checked || r.getAttribute('aria-checked') === 'true') {
                            return true;
                        }
                        const clickTarget = r.closest('label') || r;
                        clickTarget.click();
                        return true;
                    }
                }

                // 3. Fallback: if displayed resume card text in modal contains target CV name
                const resumeSection = modal.querySelector('.jobs-document-upload, .jobs-resume-picker, .fb-dash-form-element');
                if (resumeSection && resumeSection.innerText.toLowerCase().includes(targetName)) {
                    return true;
                }

                return false;
            }""", [cv_target_name, cv_stem])

            if cv_already_selected:
                print(f"  [CV Check] Latest CV '{RESUME_PATH.name}' is already attached and selected. Skipping re-upload.")
            else:
                # Disambiguate file inputs: target resume upload specifically (avoid cover letter)
                resume_input = None
                for inp in page.query_selector_all("dialog[data-testid='dialog'] input[type='file'], [data-sdui-screen*='EasyApply'] input[type='file'], [role='dialog'] input[type='file'], .jobs-easy-apply-modal input[type='file']"):
                    inp_id = (inp.get_attribute("id") or "").lower()
                    lbl = inp.evaluate("el => el.closest('label, .fb-dash-form-element, div')?.innerText || ''").lower()
                    if "cover" not in inp_id and "cover letter" not in lbl:
                        resume_input = inp
                        break
                if resume_input:
                    try:
                        resume_input.set_input_files(str(RESUME_PATH))
                        print(f"  [+] Uploaded Master CV: {RESUME_PATH.name}")
                        time.sleep(2)
                    except Exception as e:
                        print(f"  [!] Upload note: {e}")

        # ---- Upload Cover Letter if field exists (Multi-document routing) ----
        cover_candidates = sorted(
            [p for d in ("cover_letters", "user_inputs") for p in Path(d).glob("cover*") if p.suffix.lower() in (".pdf", ".docx", ".txt")],
            key=lambda x: x.stat().st_mtime, reverse=True
        )
        cover_letter_path = cover_candidates[0] if cover_candidates else Path(ROOT_DIR) / "user_inputs" / "cover_letter.txt"
        if not cover_letter_path.exists():
            cover_letter_path.write_text(
                f"Dear Hiring Team,\n\nI am excited to apply for this role. My background in {os.getenv('CANDIDATE_PRIMARY_SKILLS', 'Data Engineering and Analytics')} aligns well with the position.\n\nThank you for your consideration.\n\nBest regards,\n{os.getenv('CANDIDATE_NAME', 'Ankit Kumar Singh')}"
            )
        # Find file input elements specifically labeled for cover letter
        cover_input = None
        for inp in page.query_selector_all("dialog[data-testid='dialog'] input[type='file'], [data-sdui-screen*='EasyApply'] input[type='file'], [role='dialog'] input[type='file'], .jobs-easy-apply-modal input[type='file']"):
            inp_id = (inp.get_attribute("id") or "").lower()
            lbl = inp.evaluate("el => el.closest('label, .fb-dash-form-element, div')?.innerText || ''").lower()
            if "cover" in inp_id or "cover letter" in lbl:
                cover_input = inp
                break
        if cover_input:
            already_cov = page.evaluate("""() => {
                const modal = document.querySelector("dialog[data-testid='dialog'], [data-sdui-screen*='EasyApply'], [role='dialog'], .jobs-easy-apply-modal, .artdeco-modal");
                if (!modal) return false;
                const txt = modal.innerText.toLowerCase();
                return txt.includes('cover_letter') || txt.includes('cover letter uploaded');
            }""")
            if not already_cov:
                try:
                    cover_input.set_input_files(str(cover_letter_path))
                    print(f"  [+] Uploaded Cover Letter: {cover_letter_path.name}")
                    time.sleep(2)
                except Exception as e:
                    print(f"  [!] Cover letter upload error: {e}")

        # ── Fill form fields with rules + OpenRouter Free ─────────────────
        answer_modal_questions(page)

        # ── Auto-select typeahead suggestion if visible ───────────────────
        try:
            page.evaluate("""() => {
                const opt = document.querySelector('.basic-typeahead__selectable-list li, .artdeco-typeahead__results-list li, [role="listbox"] [role="option"]');
                if (opt) opt.click();
            }""")
        except Exception:
            pass

        # ── Inner Save (experience or education card) ─────────────────────
        save_btn = _find_modal_btn(
            page,
            "dialog[data-testid='dialog'] button:has-text('Save')",
            "[data-sdui-screen*='EasyApply'] button:has-text('Save')",
            ".jobs-easy-apply-modal button:has-text('Save')",
            "[role='dialog'] button:has-text('Save')"
        )
        if save_btn:
            print("  [+] Inner Save button detected, saving card...")
            try:
                save_btn.click(timeout=2000)
            except Exception:
                page.evaluate("(el) => el.click()", save_btn)
            time.sleep(1.5)

        # ── Evaluate Primary Action in Modal Footer ───────────────────────
        action = page.evaluate("""() => {
            const modal = document.querySelector("dialog[data-testid='dialog'], [data-sdui-screen*='EasyApply'], [role='dialog'], .jobs-easy-apply-modal, .artdeco-modal");
            if (!modal) return null;
            const btns = Array.from(modal.querySelectorAll('footer button, [data-testid="dialog-footer"] button, button'));
            
            // 1. Submit
            const submitBtn = btns.find(b => {
                const t = (b.innerText + ' ' + (b.getAttribute('aria-label') || '')).toLowerCase();
                return (t.includes('submit application') || t.includes('submit')) && b.offsetParent !== null && !b.disabled;
            });
            if (submitBtn) return 'submit';

            // 2. Next
            const nextBtn = btns.find(b => {
                const t = (b.innerText + ' ' + (b.getAttribute('aria-label') || '')).toLowerCase();
                return (t.includes('continue to next step') || t.includes('next')) && b.offsetParent !== null && !b.disabled;
            });
            if (nextBtn) return 'next';

            // 3. Review
            const reviewBtn = btns.find(b => {
                const t = (b.innerText + ' ' + (b.getAttribute('aria-label') || '')).toLowerCase();
                return (t.includes('review your application') || t.includes('review')) && b.offsetParent !== null && !b.disabled;
            });
            if (reviewBtn) return 'review';

            return null;
        }""")

        if action == "submit":
            if review_only:
                print("  [Review Mode] Reached final review step. Form populated for human review.")
                print("  [Review Mode] Submit button NOT clicked per --review-only instruction.")
                alert("Review Ready", "Application populated and paused at review screen.")
                return True
            print("  [✓] Submitting application…")
            page.evaluate("""() => {
                const modal = document.querySelector("dialog[data-testid='dialog'], [data-sdui-screen*='EasyApply'], [role='dialog'], .jobs-easy-apply-modal, .artdeco-modal");
                // Uncheck 'Follow company' if present to keep candidate feed clean
                try {
                    const followCbs = (modal || document).querySelectorAll('input[type="checkbox"][id*="follow-company"], input[type="checkbox"][name*="follow-company"]');
                    for (const fcb of followCbs) {
                        if (fcb && fcb.checked) {
                            const l = fcb.closest('label');
                            if (l) l.click();
                            else fcb.click();
                        }
                    }
                } catch (e) {}

                const btns = Array.from((modal || document).querySelectorAll('button'));
                const btn = btns.find(b => {
                    const t = (b.innerText + ' ' + (b.getAttribute('aria-label') || '')).toLowerCase();
                    return t.includes('submit application') || t.includes('submit');
                });
                if (btn) btn.click();
            }""")
            time.sleep(3)
            try:
                page.evaluate("""() => {
                    const dismiss = document.querySelector('[role="dialog"] button[aria-label*="Dismiss" i], dialog[data-testid="dialog"] button[aria-label*="Dismiss" i], [role="dialog"] .artdeco-modal__dismiss, button[aria-label="Dismiss"], button[aria-label="Close"]');
                    if (dismiss) dismiss.click();
                    const notNow = Array.from(document.querySelectorAll('button')).find(b => b.innerText.trim().toLowerCase() === 'not now');
                    if (notNow) notNow.click();
                }""")
            except Exception:
                pass
            return True

        if action == "next":
            print("  [→] Next…")
            page.evaluate("""() => {
                const modal = document.querySelector("dialog[data-testid='dialog'], [data-sdui-screen*='EasyApply'], [role='dialog'], .jobs-easy-apply-modal, .artdeco-modal");
                const btns = Array.from((modal || document).querySelectorAll('button'));
                const btn = btns.find(b => {
                    const t = (b.innerText + ' ' + (b.getAttribute('aria-label') || '')).toLowerCase();
                    return t.includes('continue to next step') || t.includes('next');
                });
                if (btn) btn.click();
            }""")
            time.sleep(2)
            continue

        if action == "review":
            print("  [→] Review…")
            page.evaluate("""() => {
                const modal = document.querySelector("dialog[data-testid='dialog'], [data-sdui-screen*='EasyApply'], [role='dialog'], .jobs-easy-apply-modal, .artdeco-modal");
                const btns = Array.from((modal || document).querySelectorAll('button'));
                const btn = btns.find(b => {
                    const t = (b.innerText + ' ' + (b.getAttribute('aria-label') || '')).toLowerCase();
                    return t.includes('review your application') || t.includes('review');
                });
                if (btn) btn.click();
                const content = (modal || document).querySelector('.jobs-easy-apply-modal__content, .artdeco-modal__content, [data-test-easy-apply-scrollable]');
                if (content) content.scrollTop = content.scrollHeight;
            }""")
            review_clicked = True
            time.sleep(2)
            if review_only:
                print("  [Review Mode] Reached final review step. Form populated for human review.")
                print("  [Review Mode] Submit button NOT clicked per --review-only instruction.")
                alert("Review Ready", "Application populated and paused at review screen.")
                return True
            # Check if submit is now available after review transition/scroll
            submit_after_review = page.evaluate("""() => {
                const modal = document.querySelector("dialog[data-testid='dialog'], [data-sdui-screen*='EasyApply'], [role='dialog'], .jobs-easy-apply-modal, .artdeco-modal");
                if (!modal) return false;
                const content = modal.querySelector('.jobs-easy-apply-modal__content, .artdeco-modal__content, [data-test-easy-apply-scrollable]');
                if (content) content.scrollTop = content.scrollHeight;

                // Uncheck 'Follow company' if present
                try {
                    const followCbs = modal.querySelectorAll('input[type="checkbox"][id*="follow-company"], input[type="checkbox"][name*="follow-company"]');
                    for (const fcb of followCbs) {
                        if (fcb && fcb.checked) {
                            const l = fcb.closest('label');
                            if (l) l.click();
                            else fcb.click();
                        }
                    }
                } catch (e) {}

                const btns = Array.from(modal.querySelectorAll('footer button, [data-testid="dialog-footer"] button, button'));
                const submitBtn = btns.find(b => {
                    const t = (b.innerText + ' ' + (b.getAttribute('aria-label') || '')).toLowerCase();
                    return (t.includes('submit application') || t.includes('submit')) && b.offsetParent !== null && !b.disabled;
                });
                if (submitBtn) {
                    submitBtn.click();
                    return true;
                }
                return false;
            }""")
            if submit_after_review:
                print("  [✓] Submitting application…")
                time.sleep(3)
                try:
                    page.evaluate("""() => {
                        const dismiss = document.querySelector('[role="dialog"] button[aria-label*="Dismiss" i], dialog[data-testid="dialog"] button[aria-label*="Dismiss" i], [role="dialog"] .artdeco-modal__dismiss, button[aria-label="Dismiss"], button[aria-label="Close"]');
                        if (dismiss) dismiss.click();
                        const notNow = Array.from(document.querySelectorAll('button')).find(b => b.innerText.trim().toLowerCase() === 'not now');
                        if (notNow) notNow.click();
                    }""")
                except Exception:
                    pass
                return True
            continue

        # ── 4. Validation errors check ───────────────────────────────────
        errors = [
            e.inner_text().strip()
            for e in page.query_selector_all(
                "dialog[data-testid='dialog'] .artdeco-inline-feedback--error, [data-sdui-screen*='EasyApply'] .artdeco-inline-feedback--error, [role='dialog'] .artdeco-inline-feedback--error, .jobs-easy-apply-modal .artdeco-inline-feedback--error, [data-test-form-element-error-message]"
            )
            if e.is_visible()
        ]
        if errors:
            print(f"  [!] Validation errors encountered: {errors}")
        else:
            print("  [?] No actionable button found – bailing.")
        break

    # Under NO circumstances close or discard the modal!
    print("  [!] Application paused. Modal remains open on display for candidate review.")
    alert("Application Paused", "Application modal left open on your display.")
    return False


# ── Authentication Helper ─────────────────────────────────────────────────────

def is_logged_in(page: Page) -> bool:
    """Return True if the current page indicates an active authenticated session."""
    try:
        url_lower = page.url.lower()
        if any(term in url_lower for term in ["login", "uas", "signup", "authwall", "checkpoint", "challenge"]):
            return False
        title = page.title().lower()
        if any(term in title for term in ["sign in", "sign up", "log in", "auth", "login"]):
            return False
        # Modern LinkedIn authenticated nav links and elements
        if page.query_selector("a[href*='/messaging'], a[href*='/notifications'], a[href*='/mynetwork'], .global-nav__me, #global-nav, nav.global-nav"):
            return True
        if "feed" in url_lower and "feed" in title:
            return True
        return False
    except Exception:
        return False


def ensure_authenticated(page: Page):
    """
    Ensure user is signed in to LinkedIn. Follows Rule 2.6 (Zero-Lockout Protocol):
    At most ONE automated sign-in attempt. If 2FA/checkpoint is hit, alert the user
    and wait without closing the browser.
    """
    page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
    time.sleep(3)

    if not is_logged_in(page):
        print("[LinkedIn Auth] Session expired or not signed in. Navigating to login...")
        page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
        time.sleep(3)

        email = os.getenv("LINKEDIN_EMAIL", "")
        password = os.getenv("LINKEDIN_PASSWORD", "")
        if not email or not password:
            try:
                from automation.browser import get_portal_credentials
                u, p, _ = get_portal_credentials("https://www.linkedin.com")
                email = email or u
                password = password or p
            except Exception:
                pass

        user_field = None
        for inp in page.query_selector_all("input[type='email'], input#username, input[name='session_key'], input[autocomplete='username']"):
            try:
                if inp.is_visible():
                    user_field = inp
                    break
            except Exception:
                pass

        pwd_field = None
        for inp in page.query_selector_all("input[type='password'], input#password, input[name='session_password'], input[autocomplete='current-password']"):
            try:
                if inp.is_visible():
                    pwd_field = inp
                    break
            except Exception:
                pass

        # Strictly locate the genuine LinkedIn email/password submit button.
        # NEVER match social login buttons (Apple, Google, Microsoft, Passkey).
        submit_btn = None
        for sel in [
            "button[data-litms-control-urn='login-submit']",
            "button[type='submit'][aria-label='Sign in']",
            "button[type='submit']:not([aria-label*='Apple']):not([aria-label*='Google'])",
            "#login-submit",
            "form[action*='login-submit'] button[type='submit']",
            "button.btn__primary--large[type='submit']",
        ]:
            try:
                btn = page.query_selector(sel)
                if btn and btn.is_visible():
                    text = (btn.inner_text() or "").strip().lower()
                    aria = (btn.get_attribute("aria-label") or "").lower()
                    if not any(soc in text or soc in aria for soc in ["apple", "google", "passkey", "qrcode"]):
                        submit_btn = btn
                        break
            except Exception:
                pass

        if not submit_btn:
            for btn in page.query_selector_all("button"):
                try:
                    if not btn.is_visible():
                        continue
                    text = (btn.inner_text() or "").strip().lower()
                    aria = (btn.get_attribute("aria-label") or "").lower()
                    if any(soc in text or soc in aria for soc in ["apple", "google", "passkey", "qrcode"]):
                        continue
                    if text in ("sign in", "log in", "login") or (btn.get_attribute("type") == "submit" and "sign in" in text):
                        submit_btn = btn
                        break
                except Exception:
                    pass

        attempted = False
        if user_field and pwd_field and email and password:
            print("[LinkedIn Auth] Entering credentials from secure store (Single Attempt per Zero-Lockout Protocol)...")
            try:
                user_field.fill(email)
                time.sleep(0.5)
                pwd_field.fill(password)
                time.sleep(0.5)
                if submit_btn and submit_btn.is_visible():
                    submit_btn.click()
                else:
                    pwd_field.press("Enter")
                attempted = True
                time.sleep(5)
            except Exception as fe:
                print(f"[LinkedIn Auth] Note during automated fill: {fe}")
        else:
            print("[LinkedIn Auth] Login fields missing or credentials not set. Alerting user...")

        if not is_logged_in(page):
            print("[LinkedIn Auth] Security verification / 2FA / checkpoint detected!")
            alert("LinkedIn Verification Required", "Please complete verification or 2FA in the open browser window.")
            print("[LinkedIn Auth] Browser remains open. Waiting for manual login completion in browser window...")
            for _ in range(60):
                time.sleep(3)
                if is_logged_in(page):
                    print("[LinkedIn Auth] Login verified successfully!")
                    break
    else:
        print("[LinkedIn Auth] Active authenticated session confirmed.")


# ── Main Runner ───────────────────────────────────────────────────────────────

DEFAULT_COMPANY_BLACKLIST = [
    "turing", "cybercoders", "robert half", "teksystems", "apex systems",
    "actalent", "collabera", "kforce", "jobot", "recruitment agency",
    "staffing", "talentship", "talent corner", "hays", "adecco",
    "randstad", "allegis group", "kelly services", "manpower"
]

DEFAULT_TITLE_BLACKLIST = [
    "intern", "internship", "trainee", "apprentice",
    "principal", "director", "vp", "vice president",
    "head of", "chief", "architect",
    "java", "kubernetes", "ios developer", "android developer",
    "spring boot", "docker", ".net"
]

SKIP_KEYWORDS = DEFAULT_TITLE_BLACKLIST

def run(
    target: int = 40,
    keywords: Optional[str] = None,
    location: str = "India",
    locations: Optional[List[str]] = None,
    sort: str = "DD",
    time_filter: Optional[str] = "r86400",
    experience_level: Optional[str] = "3,4",
    max_yoe_ceiling: int = 8,
    company_blacklist: Optional[List[str]] = None,
    title_blacklist: Optional[List[str]] = None,
    keep_open: bool = True,
    override_daily_limit: bool = False,
    review_only: bool = False,
    no_remote: bool = False
):
    global RESUME_PATH
    load_env()

    active_company_blacklist = set(c.lower() for c in DEFAULT_COMPANY_BLACKLIST)
    if company_blacklist:
        for c in company_blacklist:
            if c and c.strip():
                active_company_blacklist.add(c.strip().lower())

    active_title_blacklist = set(t.lower() for t in DEFAULT_TITLE_BLACKLIST)
    if title_blacklist:
        for t in title_blacklist:
            if t and t.strip():
                active_title_blacklist.add(t.strip().lower())

    # Resolve latest master resume
    candidates = sorted(
        [p for d in ("cv", "user_inputs/cv") for p in Path(d).glob("*.pdf")
         if "archive" not in str(p).lower()],
        key=lambda x: x.stat().st_mtime, reverse=True,
    )
    RESUME_PATH = candidates[0].resolve() if candidates else None
    print(f"[Master CV] {RESUME_PATH}")

    # Build time filter parameter (e.g. f_TPR=r86400 for past 24 hours)
    tpr_param = ""
    if time_filter:
        tf_clean = time_filter.strip().lower()
        if tf_clean in ("none", "all", "off", "any", ""):
            tpr_param = ""
        elif tf_clean in ("24h", "1d", "86400", "r86400"):
            tpr_param = "&f_TPR=r86400"
        elif tf_clean in ("week", "7d", "r604800"):
            tpr_param = "&f_TPR=r604800"
        elif tf_clean in ("month", "30d", "r2592000"):
            tpr_param = "&f_TPR=r2592000"
        elif tf_clean.startswith("r") or tf_clean.isdigit():
            tpr_param = f"&f_TPR={tf_clean if tf_clean.startswith('r') else 'r' + tf_clean}"
        else:
            tpr_param = f"&f_TPR={time_filter}"

    # Locations queue (Priority order: e.g. Delhi NCR -> India -> Remote / International)
    if locations:
        locations_to_scan = locations
    elif location:
        locations_to_scan = [loc.strip() for loc in location.split(",") if loc.strip()]
    else:
        locations_to_scan = ["India"]

    # Target designations query clusters
    if keywords and ";" in keywords:
        queries_to_scan = [k.strip() for k in keywords.split(";") if k.strip()]
    elif keywords and keywords.strip().lower() not in ("auto", "none", ""):
        queries_to_scan = [keywords.strip()]
    else:
        # Default clusters covering candidate's target roles from profile / .env
        queries_to_scan = [
            '"Data Engineer" OR "Analytics Engineer" OR "Big Data"',
            '"Data Analyst" OR "Data Consultant" OR "Analytics Consultant"',
            '"Business Technology Consultant" OR "Solutions Architect" OR "Technical Consultant"',
            '"Data Governance" OR "AI Engineer" OR "AI Automation Engineer"',
            '"Technical Product Manager" OR "Marketing Analytics Consultant"'
        ]

    today_applied = get_today_easy_apply_count()

    print(f"\n[LinkedIn Setup]")
    print(f"  • Locations Priority Queue: {locations_to_scan}")
    print(f"  • Designation Clusters: {len(queries_to_scan)} queries")
    for idx, q in enumerate(queries_to_scan, 1):
        print(f"      [{idx}] {q}")
    print(f"  • Filter: Easy Apply (f_AL=true)")
    exp_display = f"&f_E={experience_level}" if (experience_level and experience_level.lower() not in ("all", "none", "")) else "All levels"
    print(f"  • Experience Level Filter: {exp_display}")
    print(f"  • Company Blacklist: {len(active_company_blacklist)} rules active")
    print(f"  • Title Blacklist: {len(active_title_blacklist)} rules active")
    print(f"  • Max YOE Ceiling: {max_yoe_ceiling} years (Candidate: 4.8 YOE)")
    print(f"  • Sorting: Date Descending / Newest to Oldest (sortBy={sort})")
    print(f"  • Recency Filter: {tpr_param or 'None (All time)'}")
    print(f"  • Target Applications: {target}")
    print(f"  • LLM Engine: OpenRouter Free Tier (:free)")
    active_limit = "Unlimited (User Override)" if override_daily_limit else f"{DAILY_EASY_APPLY_LIMIT}"
    print(f"  • Today's Easy Apply Submissions: {today_applied}/{active_limit}\n")

    if not override_daily_limit and today_applied >= DAILY_EASY_APPLY_LIMIT:
        print(f"\n[Safety Gate] Daily Easy Apply ceiling reached ({today_applied}/{DAILY_EASY_APPLY_LIMIT} submitted today).")
        print("Halting automation to protect account standing against LinkedIn limits.")
        print("To bypass this ceiling upon explicit user instruction, pass --override-daily-limit.\n")
        alert("Easy Apply Daily Limit", f"Reached {today_applied}/{DAILY_EASY_APPLY_LIMIT} applications today. Automation safely paused.")
        return

    pw = sync_playwright().start()
    session_dir = Path(".browser_session").resolve()
    session_dir.mkdir(parents=True, exist_ok=True)

    browser = None
    try:
        browser = pw.chromium.connect_over_cdp("http://localhost:9222", timeout=5000)
        ctx = browser.contexts[0] if browser.contexts else browser.new_context(no_viewport=True)
        # Prioritize active tab that is on linkedin.com/jobs
        job_pages = [p for p in ctx.pages if "linkedin.com/jobs" in p.url]
        if job_pages:
            page = job_pages[0]
            print(f"[LinkedIn Setup] Reusing active LinkedIn page: {page.url[:80]}...")
        else:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
        print("[LinkedIn Setup] Attached to existing browser session on CDP port 9222.")
    except Exception as cdp_err:
        print(f"[LinkedIn Setup] CDP connect note: {cdp_err}. Launching persistent context...")
        browser = pw.chromium.launch_persistent_context(
            user_data_dir=str(session_dir),
            headless=False,
            no_viewport=True,
            args=["--start-maximized", "--no-default-browser-check", "--disable-gpu", "--disable-extensions", "--remote-debugging-port=9222"]
        )
        ctx = browser
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

    # Step 1: Ensure authenticated
    ensure_authenticated(page)

    # Step 2: Load previously applied records
    applied_urls = set()
    if TRACKER_CSV.exists():
        try:
            with open(TRACKER_CSV, mode="r", encoding="utf-8", errors="ignore") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    src = (row.get("source") or "").strip()
                    if src:
                        applied_urls.add(src)
                        m = re.search(r"view/(\d+)", src)
                        if m:
                            applied_urls.add(m.group(1))
        except Exception:
            pass
    print(f"[Tracker] Loaded {len(applied_urls)} previously applied records for deduplication.")

    applied = 0

    # Step 3: Iterate through locations and designation clusters
    for loc in locations_to_scan:
        if (review_only and applied > 0) or applied >= target or (not override_daily_limit and (today_applied + applied) >= DAILY_EASY_APPLY_LIMIT):
            break

        print(f"\n{'#'*65}")
        print(f"  [Location Priority Target] Scanning: {loc}")
        print(f"{'#'*65}")

        for kw in queries_to_scan:
            if (review_only and applied > 0) or applied >= target or (not override_daily_limit and (today_applied + applied) >= DAILY_EASY_APPLY_LIMIT):
                break

            canonical_loc, geo_id = resolve_linkedin_geo(loc)
            encoded_kw = urllib.parse.quote(kw)
            encoded_loc = urllib.parse.quote(canonical_loc)
            geo_param = f"&geoId={geo_id}" if geo_id else ""
            wt_param = "&f_WT=1%2C3" if no_remote else ""
            f_e_param = f"&f_E={urllib.parse.quote(experience_level)}" if (experience_level and experience_level.lower() not in ("all", "none", "")) else ""
            search_url = (
                f"https://www.linkedin.com/jobs/search/?"
                f"keywords={encoded_kw}"
                f"&location={encoded_loc}"
                f"{geo_param}"
                f"&f_AL=true"
                f"{wt_param}"
                f"{f_e_param}"
                f"&sortBy={sort}"
                f"{tpr_param}"
            )

            current_url = page.url
            page_num = 1
            matches_active = False
            if ("linkedin.com/jobs/search" in current_url or "linkedin.com/jobs/search-results" in current_url) and ("keywords=" in current_url or "f_AL=" in current_url):
                parsed_u = urllib.parse.urlparse(current_url)
                params = urllib.parse.parse_qs(parsed_u.query)
                active_kw = params.get("keywords", [""])[0].lower()
                active_loc = params.get("location", [""])[0].lower()
                active_geoid = params.get("geoId", [""])[0]
                if (kw.lower() in active_kw or active_kw == kw.lower()) and ("india" in active_loc or (geo_id and active_geoid == str(geo_id))):
                    matches_active = True
                    start_val = int(params.get("start", ["0"])[0])
                    if start_val > 0:
                        page_num = (start_val // 25) + 1
                        print(f"[Resume Detection] Continuing directly from active search page at start={start_val} (Page {page_num})")
                    else:
                        print(f"[Resume Detection] Continuing directly from active LinkedIn jobs search page.")

            if not matches_active:
                print(f"\n[Search URL] {search_url}")
                try:
                    page.goto(search_url, wait_until="domcontentloaded")
                    time.sleep(3.5)
                except Exception as ge:
                    print(f"[Navigation Note] {ge}")

            while applied < target and page_num <= 10:
                if not override_daily_limit and (today_applied + applied) >= DAILY_EASY_APPLY_LIMIT:
                    print(f"\n[Safety Gate] Reached daily safety ceiling of {DAILY_EASY_APPLY_LIMIT} Easy Apply applications today.")
                    alert("Easy Apply Daily Limit", f"Completed {DAILY_EASY_APPLY_LIMIT} applications today. Pausing safely.")
                    applied = target
                    break

                print(f"\n{'='*55}")
                print(f"[Scan] Loc: {loc} | Query: {kw[:35]}... | Page {page_num} | Applied {applied}/{target}")
                print(f"{'='*55}")

                # Scroll results list to ensure lazy-loaded cards render
                try:
                    page.evaluate("""() => {
                        const list = document.querySelector('.jobs-search-results-list, .scaffold-layout__list-detail-inner, .scaffold-layout__list') || window;
                        list.scrollTop = list.scrollHeight / 2;
                    }""")
                    time.sleep(1)
                    page.evaluate("""() => {
                        const list = document.querySelector('.jobs-search-results-list, .scaffold-layout__list-detail-inner, .scaffold-layout__list') || window;
                        list.scrollTop = list.scrollHeight;
                    }""")
                    time.sleep(1)
                except Exception:
                    pass

                # Collect job IDs from search list
                job_ids = []
                for card in page.query_selector_all("[data-occludable-job-id]"):
                    jid = card.get_attribute("data-occludable-job-id")
                    if jid and jid not in job_ids:
                        job_ids.append(jid)

                if not job_ids:
                    for card in page.query_selector_all(".job-card-container, [data-job-id], li.jobs-search-results__list-item"):
                        jid = card.get_attribute("data-job-id") or card.get_attribute("data-occludable-job-id")
                        if not jid:
                            link = card.query_selector("a[href*='jobs/view']")
                            if link:
                                href = link.get_attribute("href") or ""
                                m = re.search(r"jobs/view/(\d+)", href)
                                if m:
                                    jid = m.group(1)
                        if jid and jid not in job_ids:
                            job_ids.append(jid)

                if not job_ids:
                    # Check for modern LinkedIn LazyColumn layout
                    try:
                        lazy_cards = page.query_selector_all("[data-component-type='LazyColumn'] > div, [data-testid='lazy-column'] > div")
                    except Exception:
                        page.wait_for_timeout(1500)
                        try:
                            lazy_cards = page.query_selector_all("[data-component-type='LazyColumn'] > div, [data-testid='lazy-column'] > div")
                        except Exception:
                            lazy_cards = []
                    if lazy_cards:
                        print(f"[Scan:Modern] Found {len(lazy_cards)} items in modern LazyColumn layout.")
                        for card_idx, card_el in enumerate(lazy_cards):
                            if applied >= target:
                                break
                            if not override_daily_limit and (today_applied + applied) >= DAILY_EASY_APPLY_LIMIT:
                                print(f"\n[Safety Gate] Reached daily safety ceiling of {DAILY_EASY_APPLY_LIMIT} Easy Apply applications today.")
                                alert("Easy Apply Daily Limit", f"Completed {DAILY_EASY_APPLY_LIMIT} applications today. Pausing safely.")
                                applied = target
                                break

                            card_text = (card_el.inner_text() or "").strip()
                            if "easy apply" not in card_text.lower() or "all filters" in card_text.lower():
                                continue

                            lines = [l.strip() for l in card_text.split("\n") if l.strip()]
                            if not lines:
                                continue

                            c_title = lines[0]
                            if c_title.startswith("Selected,") or "(Verified" in c_title:
                                c_title = lines[1] if len(lines) > 1 else c_title
                            c_company = lines[2] if len(lines) > 2 else (lines[1] if len(lines) > 1 else "")
                            c_loc = lines[3] if len(lines) > 3 else (lines[2] if len(lines) > 2 else "")
                            c_work_model = next((l for l in lines if re.search(r"remote|on-site|onsite|hybrid", l, re.IGNORECASE)), "")

                            # Strict no-remote check
                            if no_remote and (re.search(r"\bremote\b|work from home|\bwfh\b", f"{c_title} {c_loc} {c_work_model}", re.IGNORECASE)):
                                print(f"  [-] Skipped remote job: '{c_title}' ({c_work_model or c_loc})")
                                continue

                            # Location check (must be India)
                            combined_loc = f"{c_loc} {c_work_model}".lower()
                            if combined_loc and "india" not in combined_loc and not any(city in combined_loc for city in ["delhi", "noida", "gurugram", "gurgaon", "bengaluru", "bangalore", "mumbai", "pune", "hyderabad", "chennai", "kolkata", "ahmedabad", "chandigarh", "kochi", "kanpur"]):
                                print(f"  [-] Skipped non-India location: '{c_loc}'")
                                continue

                            # Pre-click Company Blacklist Check
                            if any(b_comp in c_company.lower() for b_comp in active_company_blacklist):
                                print(f"  [-] Skipped blacklisted company: '{c_company}'")
                                continue

                            # Pre-click Title Blacklist Check
                            if any(bad in c_title.lower() for bad in active_title_blacklist):
                                print(f"  [-] Skipped blacklisted title: '{c_title}'")
                                continue

                            # Title filter: ensure role matches keywords if explicit query provided
                            if kw != "auto" and not any(term in c_title.lower() for term in [
                                "analyst", "analytics", "data", "business", "consultant", "scientist",
                                "engineer", "governance", "bi", "reporting", "etl", "sql", "ai", "llm"
                            ]):
                                print(f"  [-] Skipped non-matching title: '{c_title}'")
                                continue

                            # Click card to load details into right pane
                            try:
                                card_btn = card_el.query_selector("div[role='button']") or card_el
                                card_btn.scroll_into_view_if_needed()
                                time.sleep(0.15)
                                page.evaluate("(el) => el.click()", card_btn)
                                time.sleep(1.5)
                            except Exception as ce:
                                try:
                                    card_btn.click(timeout=1000)
                                except Exception:
                                    print(f"  [!] Card click note: {ce}")
                                    continue

                            # Extract Job ID from page URL
                            m_jid = re.search(r"currentJobId=(\d+)", page.url)
                            card_jid = m_jid.group(1) if m_jid else f"card_{card_idx}"

                            if card_jid in applied_urls or f"https://www.linkedin.com/jobs/view/{card_jid}/" in applied_urls:
                                print(f"  [-] Job {card_jid} ({c_title}) already applied previously. Skipping.")
                                continue

                            # Ensure active page is valid and open
                            if page.is_closed():
                                active_pages = [p for p in context.pages if not p.is_closed()]
                                if active_pages:
                                    page = active_pages[-1]
                                else:
                                    print("  [!] Browser page was closed. Reopening jobs page...")
                                    page = context.new_page()
                                    page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
                                    time.sleep(2.0)
                                    break

                            # Read full details from right pane if available
                            try:
                                t_el = page.query_selector("a[href*='/jobs/view/'], .job-details-jobs-unified-top-card__job-title, .jobs-unified-top-card__job-title, h1, h2")
                                c_el = page.query_selector("a[href*='/company/'], .job-details-jobs-unified-top-card__company-name, .jobs-unified-top-card__company-name")
                                det_title = t_el.inner_text().strip() if t_el and t_el.inner_text().strip() not in ("0 notifications", "Jobs filters") else c_title
                                det_company = c_el.inner_text().strip() if c_el else c_company
                            except Exception as pe:
                                print(f"  [!] Card detail inspection note ({pe}). Recovering...")
                                active_pages = [p for p in context.pages if not p.is_closed()]
                                if active_pages:
                                    page = active_pages[-1]
                                continue

                            # Detailed Pane Company & Title Blacklist Check
                            if any(b_comp in det_company.lower() for b_comp in active_company_blacklist):
                                print(f"  [-] Skipped blacklisted company (detail): '{det_company}'")
                                continue
                            if any(b_tit in det_title.lower() for b_tit in active_title_blacklist):
                                print(f"  [-] Skipped blacklisted title (detail): '{det_title}'")
                                continue

                            # Seniority YOE ceiling check (Candidate has 4.8 YOE; default ceiling 8 YOE)
                            jd_el = page.query_selector(".jobs-description__content, .jobs-box__html-content, #job-details, .jobs-description")
                            if jd_el:
                                jd_text = (jd_el.inner_text() or "").strip()
                                min_yoe = extract_min_yoe_requirement(jd_text)
                                if min_yoe and min_yoe > max_yoe_ceiling:
                                    print(f"  [-] Skipped senior role: requires {min_yoe}+ YOE > ceiling of {max_yoe_ceiling} YOE. (Role: {det_title})")
                                    record_failed_application(det_company, det_title, f"https://www.linkedin.com/jobs/view/{card_jid}/", "Seniority Ceiling Exceeded", f"Requires {min_yoe}+ YOE")
                                    continue

                            print(f"\n→ [{applied+1}/{target}] {det_title} @ {det_company} ({c_work_model or c_loc or loc}) [ID: {card_jid}]")

                            try:
                                try:
                            ok = apply_to_current_job(page, review_only=review_only)
                        except RuntimeError as re_err:
                            if "LINKEDIN_DAILY_LIMIT_REACHED" in str(re_err):
                                print("\n[!] Halting scan loop: LinkedIn account daily Easy Apply quota reached for today.")
                                return
                            raise
                            except RuntimeError as re_err:
                                if "LINKEDIN_DAILY_LIMIT_REACHED" in str(re_err):
                                    print("\n[!] Halting scan loop: LinkedIn account daily Easy Apply quota reached for today.")
                                    return
                                raise
                            if ok:
                                if review_only:
                                    applied += 1
                                    print(f"  [Review Mode] Application populated for review: {det_title} @ {det_company}")
                                    alert("Application Ready for Review", f"Review ready for {det_title} @ {det_company}")
                                    break
                                applied += 1
                                applied_urls.add(card_jid)
                                applied_urls.add(f"https://www.linkedin.com/jobs/view/{card_jid}/")
                                print(f"  [✓] Successfully Applied! Progress: {applied}/{target}")
                                try:
                                    record_application(
                                        company=det_company,
                                        role=det_title,
                                        job_url=f"https://www.linkedin.com/jobs/view/{card_jid}/",
                                        cv_path=str(RESUME_PATH.relative_to(ROOT_DIR)) if RESUME_PATH else "cv/Ankit_Resume_v4.pdf"
                                    )
                                except Exception as le:
                                    print(f"  [Tracker Note] {le}")
                            else:
                                modal_open = page.query_selector("dialog[data-testid='dialog'], [data-sdui-screen*='EasyApply'], [role='dialog'], .jobs-easy-apply-modal, .artdeco-modal")
                                if modal_open and modal_open.is_visible():
                                    print("  [!] Form modal remains open on display for candidate inspection.")
                                    alert("Form Paused on Screen", f"Modal open for {det_title} @ {det_company}. Please inspect.")
                                    print("  [Action Required] Once inspected/submitted on screen, close modal to proceed to next job.")
                                    for _ in range(150):  # wait up to 5 mins
                                        time.sleep(2)
                                        m_check = page.query_selector("dialog[data-testid='dialog'], [data-sdui-screen*='EasyApply'], [role='dialog'], .jobs-easy-apply-modal, .artdeco-modal")
                                        if not m_check or not m_check.is_visible():
                                            print("  [+] Modal dismissed/submitted by candidate. Resuming search scan.")
                                            break

                if not job_ids and not page.query_selector("[data-component-type='LazyColumn'], [data-testid='lazy-column']"):
                    print(f"  [Scan] No further job listings found for this query on page {page_num}.")
                    break

                print(f"[Scan] {len(job_ids)} listings found on page {page_num}.")

                for jid in job_ids:
                    if applied >= target:
                        break
                    if not override_daily_limit and (today_applied + applied) >= DAILY_EASY_APPLY_LIMIT:
                        print(f"\n[Safety Gate] Reached daily safety ceiling of {DAILY_EASY_APPLY_LIMIT} Easy Apply applications today.")
                        alert("Easy Apply Daily Limit", f"Completed {DAILY_EASY_APPLY_LIMIT} applications today. Pausing safely.")
                        applied = target
                        break

                    if jid in applied_urls or f"https://www.linkedin.com/jobs/view/{jid}/" in applied_urls:
                        print(f"  [-] Job {jid} already applied previously. Skipping.")
                        continue

                    try:
                        clear_all_overlays(page)

                        card = page.query_selector(f"[data-occludable-job-id='{jid}'], [data-job-id='{jid}'], a[href*='{jid}']")
                        if not card:
                            continue

                        card.scroll_into_view_if_needed()
                        time.sleep(0.5)
                        try:
                            card.click(timeout=3000)
                        except Exception:
                            page.evaluate("(el) => el.click()", card)
                        time.sleep(2)

                        t_el = page.query_selector(
                            ".job-details-jobs-unified-top-card__job-title, "
                            ".jobs-unified-top-card__job-title, h1"
                        )
                        c_el = page.query_selector(
                            ".job-details-jobs-unified-top-card__company-name, "
                            ".jobs-unified-top-card__company-name"
                        )
                        l_el = page.query_selector(
                            ".job-details-jobs-unified-top-card__primary-description-container, "
                            ".jobs-unified-top-card__bullet, "
                            ".job-card-container__metadata-item"
                        )
                        title = t_el.inner_text().strip() if t_el else f"Job {jid}"
                        company = c_el.inner_text().strip() if c_el else "Unknown Company"
                        job_loc = l_el.inner_text().strip() if l_el else ""

                        # Strict India‑only location guard (skip if location provided but not India)
                        if job_loc and "india" not in job_loc.lower():
                            print(f"  [-] Skipped non‑India location: '{job_loc}'.")
                            continue

                        # Strict no-remote guard
                        if no_remote:
                            combined_text = f"{title} {job_loc}".lower()
                            if "remote" in combined_text or "work from home" in combined_text or "wfh" in combined_text:
                                print(f"  [-] Skipped remote job per --no-remote preference: '{title}' ({job_loc}).")
                                continue

                        print(f"\n→ [{applied+1}/{target}] {title} @ {company} ({job_loc or loc})")

                        # # Strict India‑only location guard (legacy, disabled)
                        # non_india_indicators = [
                        #     "united states", "usa", ", us", ", mi", "michigan", ", ca", "california",
                        #     ", ny", "new york", ", tx", "texas", "united kingdom", ", uk", "canada", "australia"
                        # ]
                        # # If LinkedIn provides a location string, ensure it contains 'india'
                        # if job_loc:
                        #     if any(term in job_loc.lower() for term in non_india_indicators) or "india" not in job_loc.lower():
                        #         print(f"  [-] Skipped non‑India location: '{job_loc}'.")
                        #         continue
                        # non_india_indicators = [
                        #     "united states", "usa", ", us", ", mi", "michigan", ", ca", "california",
                        #     ", ny", "new york", ", tx", "texas", "united kingdom", ", uk", "canada", "australia"
                        # ]
                        # if any(term in job_loc.lower() for term in non_india_indicators) and "india" not in job_loc.lower():
                        #     print(f"  [-] Skipped non-India location: '{job_loc}' (US/Michigan guard triggered).")
                        #     continue

                        # Check company blacklist
                        if any(b_comp in company.lower() for b_comp in active_company_blacklist):
                            print(f"  [-] Skipped blacklisted company: '{company}'")
                            continue

                        # Check title blacklist
                        if any(bad in title.lower() for bad in active_title_blacklist):
                            print(f"  [-] Skipped blacklisted title: '{title}'")
                            continue

                        # Seniority YOE ceiling check
                        jd_el = page.query_selector(".jobs-description__content, .jobs-box__html-content, #job-details, .jobs-description")
                        if jd_el:
                            jd_text = (jd_el.inner_text() or "").strip()
                            min_yoe = extract_min_yoe_requirement(jd_text)
                            if min_yoe and min_yoe > max_yoe_ceiling:
                                print(f"  [-] Skipped senior role: requires {min_yoe}+ YOE > ceiling of {max_yoe_ceiling} YOE. (Role: {title})")
                                record_failed_application(company, title, f"https://www.linkedin.com/jobs/view/{jid}/", "Seniority Ceiling Exceeded", f"Requires {min_yoe}+ YOE")
                                continue

                        try:
                            ok = apply_to_current_job(page, review_only=review_only)
                        except RuntimeError as re_err:
                            if "LINKEDIN_DAILY_LIMIT_REACHED" in str(re_err):
                                print("\n[!] Halting scan loop: LinkedIn account daily Easy Apply quota reached for today.")
                                return
                            raise
                        if ok:
                            if review_only:
                                applied += 1
                                print("\n" + "=" * 65)
                                print(f"  [Review Mode] Application populated for review: {title} @ {company}")
                                print("  [Review Mode] Form modal is left open on your display.")
                                print("  [Review Mode] Submit button was NOT clicked per user instruction.")
                                print("  [Review Mode] Please review the form and submit directly on screen.")
                                print("=" * 65 + "\n")
                                alert("Application Ready for Review", f"Review ready for {title} @ {company}")
                                break
                            applied += 1
                            applied_urls.add(jid)
                            applied_urls.add(f"https://www.linkedin.com/jobs/view/{jid}/")
                            print(f"  [✓] Successfully Applied! Progress: {applied}/{target}")
                            
                            try:
                                record_application(
                                    company=company,
                                    role=title,
                                    job_url=f"https://www.linkedin.com/jobs/view/{jid}/",
                                    cv_path=str(RESUME_PATH.relative_to(ROOT_DIR)) if RESUME_PATH else "cv/Ankit_Resume_v4.pdf"
                                )
                            except Exception as le:
                                print(f"  [!] Tracker recording note: {le}")
                            time.sleep(2)
                        else:
                            print("  [-] Could not complete application for this job.")

                    except RuntimeError as re_err:
                        if "LINKEDIN_DAILY_LIMIT_REACHED" in str(re_err):
                            print("\n[!] Immediate stop triggered: LinkedIn daily application limit detected.")
                            applied = target
                            break
                        else:
                            err_summary = str(re_err).splitlines()[0]
                            print(f"  [!] Error processing job {jid}: {err_summary}")
                            clear_all_overlays(page)
                            time.sleep(1)
                    except Exception as e:
                        err_summary = str(e).splitlines()[0]
                        print(f"  [!] Error processing job {jid}: {err_summary}")
                        if "closed" in err_summary.lower() or (hasattr(page, "is_closed") and page.is_closed()):
                            print("  [!] Target browser or page was closed. Exiting search loop.")
                            break
                        clear_all_overlays(page)
                        time.sleep(1)

                if review_only and applied > 0:
                    break

                if hasattr(page, "is_closed") and page.is_closed():
                    print("  [!] Page was closed, stopping pagination.")
                    break

                # Pagination
                if applied < target:
                    try:
                        nxt = (
                            page.query_selector(f"button[aria-label='Page {page_num + 1}']")
                            or page.query_selector(".artdeco-pagination__button--next")
                        )
                        if nxt and nxt.is_visible() and not nxt.is_disabled():
                            page.evaluate("(el) => el.click()", nxt)
                            page_num += 1
                            time.sleep(3.5)
                        else:
                            print(f"[Scan] No further pages for this query in {loc}.")
                            break
                    except Exception as pe:
                        print(f"[Scan Note] Pagination note: {pe}")
                        break

    print(f"\n{'='*55}")
    print(f"[Execution Summary] Applied {applied}/{target} Easy Apply jobs.")
    print(f"  • Locations scanned: {locations_to_scan}")
    print(f"  • Sort: Date Descending (Newest to Oldest)")
    print(f"  • Recency Filter: {time_filter or 'None'}")
    print(f"  • Q&A Engine: OpenRouter Free Models & Knowledge Base")
    print(f"  • Tracker: Synchronized with {TRACKER_CSV.name} and {JOBS_DB.name}")
    print(f"  • Browser: Preserved interactive per Rule 2.3.")
    print(f"{'='*55}\n")

    if keep_open:
        print("[Rule 2.3 Directive] Browser remains permanently open and interactive on display.")
        print("[Status] Automation completed. Browser window is active.")
        try:
            # Keep script alive so Playwright persistent context remains open
            while True:
                time.sleep(2)
        except (KeyboardInterrupt, SystemExit):
            pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LinkedIn Easy Apply Runner with OpenRouter Free")
    parser.add_argument("count", nargs="?", type=int, default=40, help="Number of applications (default: 40)")
    parser.add_argument("-n", "--num", "--count", "--target", dest="count_flag", type=int, default=None, help="Number of applications (alias for count)")
    parser.add_argument("--keywords", "-k", nargs="*", default=["auto"], help="Designations search query or space/semicolon-separated queries (default: auto)")
    parser.add_argument("--location", "-l", type=str, default="Delhi NCR, India", help="Comma-separated location priority queue (India only, NCR prioritized)")
    parser.add_argument("--locations", type=str, default=None, help="Alias for comma-separated locations queue")
    parser.add_argument("--time-filter", "-t", type=str, default="r86400", help="Recency filter: r86400 / 24h (default: r86400)")
    parser.add_argument("--sort", "-s", type=str, default="DD", choices=["DD", "R"], help="DD = Date Descending (newest to old), R = Relevant")
    parser.add_argument("--experience-level", "-e", type=str, default="3,4", help="LinkedIn experience levels: 1=Intern, 2=Entry, 3=Associate, 4=Mid-Senior, 5=Director, 6=Exec (default: 3,4)")
    parser.add_argument("--max-yoe-ceiling", "--max-yoe", type=int, default=8, help="Maximum years of experience ceiling to apply (default: 8 YOE)")
    parser.add_argument("--company-blacklist", type=str, default="", help="Comma-separated additional company names to skip")
    parser.add_argument("--title-blacklist", type=str, default="", help="Comma-separated additional title keywords to skip")
    parser.add_argument("--no-keep-open", action="store_true", help="Do not keep browser loop active at end")
    parser.add_argument("--override-daily-limit", action="store_true", help="Bypass the daily Easy Apply safety limit of 40")
    parser.add_argument("--review-only", action="store_true", help="Populate the Easy Apply form and pause at review screen without clicking Submit")
    parser.add_argument("--no-remote", action="store_true", help="Exclude remote jobs (filter to onsite & hybrid only)")
    args = parser.parse_args()

    target_count = args.count_flag if args.count_flag is not None else args.count

    if isinstance(args.keywords, list):
        if len(args.keywords) == 1 and args.keywords[0] == "auto":
            keywords_arg = "auto"
        else:
            keywords_arg = "; ".join(args.keywords)
    else:
        keywords_arg = args.keywords

    loc_str = args.locations or args.location
    locations_list = [loc.strip() for loc in loc_str.split(",") if loc.strip()]

    extra_comps = [c.strip() for c in args.company_blacklist.split(",") if c.strip()] if args.company_blacklist else None
    extra_titles = [t.strip() for t in args.title_blacklist.split(",") if t.strip()] if args.title_blacklist else None

    run(
        target=target_count,
        keywords=keywords_arg,
        locations=locations_list,
        sort=args.sort,
        time_filter=args.time_filter,
        experience_level=args.experience_level,
        max_yoe_ceiling=args.max_yoe_ceiling,
        company_blacklist=extra_comps,
        title_blacklist=extra_titles,
        keep_open=not args.no_keep_open,
        override_daily_limit=args.override_daily_limit,
        review_only=args.review_only,
        no_remote=args.no_remote
    )

