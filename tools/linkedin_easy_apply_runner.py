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
        f"{context}"
    )

    user_prompt = f"Field Question: {question}\nField Type: {field_type}\n"
    if options:
        user_prompt += "Available Options:\n" + "\n".join(f"- {opt}" for opt in options) + "\n"
        user_prompt += "Select and return ONLY the single exact option text from the list that best matches the candidate."
    else:
        if field_type == "number":
            user_prompt += "Return ONLY a single numeric value (e.g., 4 or 5)."
        else:
            user_prompt += "Return ONLY the concise exact value to type into the field."

    try:
        # Strictly use zero-cost free models
        response = ask(user_prompt, system=system_prompt, model="auto", max_tokens=100)
        ans = response.strip().strip('"').strip("'").strip()
        if ans:
            _QA_CACHE[cache_key] = ans
            save_to_qa_knowledge_base(question, ans)
            print(f"  [OpenRouter Free QA] '{question[:40]}...' => '{ans}'")
            return ans
    except Exception as e:
        print(f"  [OpenRouter Free QA Note] {e}")

    return ""


# ── Q&A Answer Logic ──────────────────────────────────────────────────────────

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

    # ── 1. TEXT / NUMBER / TEL / URL inputs ────────────────────────────────────
    selectors = (
        ".jobs-easy-apply-modal input[type='text'],"
        ".jobs-easy-apply-modal input[type='number'],"
        ".jobs-easy-apply-modal input[type='tel'],"
        ".jobs-easy-apply-modal input[type='url']"
    )
    for inp in page.query_selector_all(selectors):
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
            if ans and ans != "N/A":
                inp.fill(ans)
        except Exception:
            pass

    # ── 2. TEXTAREA ────────────────────────────────────────────────────────────
    for ta in page.query_selector_all(".jobs-easy-apply-modal textarea"):
        try:
            if not ta.is_visible() or ta.input_value():
                continue
            ta_id = ta.get_attribute("id") or ""
            lbl_el = page.query_selector(f"label[for='{ta_id}']") if ta_id else None
            lbl = (lbl_el.inner_text() if lbl_el else "").strip()
            
            ans = QASemanticsEngine.match_question(lbl or "Describe candidate qualifications", field_type="textarea")
            ta.fill(ans if ans and ans != "N/A" else "4.8 years of experience in Data Engineering, Analytics & AI Agent Development.")
        except Exception:
            pass

    # ── 3. DROPDOWNS / SELECT ───────────────────────────────────────────────────
    for sel in page.query_selector_all(".jobs-easy-apply-modal select"):
        try:
            if not sel.is_visible():
                continue
            cur = sel.input_value()
            if cur and cur.lower() not in ("", "select an option", "please select"):
                continue
            
            options = sel.query_selector_all("option")
            opt_texts = [o.inner_text().strip() for o in options if o.inner_text().strip()]
            if not opt_texts:
                continue

            sel_id = sel.get_attribute("id") or ""
            lbl_el = page.query_selector(f"label[for='{sel_id}']") if sel_id else None
            lbl = (lbl_el.inner_text() if lbl_el else "").strip().lower()

            ans = QASemanticsEngine.match_question(lbl or sel_id, field_type="select", options=opt_texts)
            if ans:
                for opt in options:
                    if opt.inner_text().strip().lower() == ans.lower() or ans.lower() in opt.inner_text().strip().lower():
                        sel.select_option(value=opt.get_attribute("value") or "")
                        break
        except Exception:
            pass

    # ── 4. RADIO BUTTONS ────────────────────────────────────────────────────────
    for fs in page.query_selector_all(".jobs-easy-apply-modal fieldset"):
        try:
            legend = fs.query_selector("legend")
            leg_text = (legend.inner_text() if legend else "").strip().lower()
            radios = fs.query_selector_all("input[type='radio']")

            if any(r.is_checked() for r in radios):
                continue

            radio_labels = []
            for r in radios:
                r_id = r.get_attribute("id") or ""
                lbl_el = fs.query_selector(f"label[for='{r_id}']")
                if lbl_el:
                    radio_labels.append(lbl_el.inner_text().strip())

            ans = QASemanticsEngine.match_question(leg_text, field_type="radio", options=radio_labels)
            if ans:
                for r in radios:
                    r_id = r.get_attribute("id") or ""
                    lbl_el = fs.query_selector(f"label[for='{r_id}']")
                    lbl_txt = (lbl_el.inner_text() if lbl_el else "").strip().lower()
                    if ans.lower() in lbl_txt or lbl_txt in ans.lower():
                        r.check()
                        break
        except Exception:
            pass

    # ── 5. CHECKBOXES (consent, terms) ──────────────────────────────────────────
    for cb in page.query_selector_all(".jobs-easy-apply-modal input[type='checkbox']"):
        try:
            if not cb.is_visible() or cb.is_checked():
                continue
            cb_id = cb.get_attribute("id") or ""
            lbl_el = page.query_selector(f"label[for='{cb_id}']")
            lbl_txt = (lbl_el.inner_text() if lbl_el else "").lower()
            if any(k in lbl_txt for k in ["agree", "consent", "accept", "terms", "privacy", "policy", "acknowledge"]):
                cb.check()
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
                    '.jobs-easy-apply-modal button[aria-label="Dismiss"]',
                    '.jobs-easy-apply-modal button[aria-label="Fermer"]',
                    'button[aria-label="Dismiss"]',
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


def apply_to_current_job(page: Page) -> bool:
    """Complete the Easy Apply modal for whatever job is currently open."""
    btn = page.query_selector(".jobs-apply-button")
    if not btn or not btn.is_visible():
        return False
    if "easy apply" not in btn.inner_text().strip().lower():
        return False

    print("  [+] Clicking 'Easy Apply'…")
    try:
        btn.click(timeout=4000)
    except Exception:
        page.evaluate("(el) => el.click()", btn)
    time.sleep(2)

    # Check for LinkedIn daily rate limit message
    try:
        body_text = (page.inner_text("body") or "").lower()
        if any(k in body_text for k in ["reached the daily application limit", "reached the application limit", "cannot apply to any more jobs", "daily application limit"]):
            print("  [!] LinkedIn daily limit alert detected on page!")
            alert("LinkedIn Daily Limit", "LinkedIn stated that your daily application limit has been reached.")
            raise RuntimeError("LINKEDIN_DAILY_LIMIT_REACHED")
    except RuntimeError:
        raise
    except Exception:
        pass

    if not page.query_selector(".jobs-easy-apply-modal"):
        print("  [-] Modal did not appear.")
        return False

    review_clicked = False

    for step in range(15):
        time.sleep(1.5)
        print(f"  [*] Modal step {step + 1}…")

        # ── Resume upload ─────────────────────────────────────────────────
        file_input = page.query_selector(".jobs-easy-apply-modal input[type='file']")
        if file_input and RESUME_PATH and RESUME_PATH.exists():
            already = page.query_selector(".jobs-easy-apply-modal .jobs-document-upload__file-name")
            if not already:
                try:
                    file_input.set_input_files(str(RESUME_PATH))
                    print(f"  [+] Uploaded Master CV: {RESUME_PATH.name}")
                    time.sleep(2)
                except Exception as e:
                    print(f"  [!] Upload note: {e}")

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
        save_btn = _find_modal_btn(page, ".jobs-easy-apply-modal button:has-text('Save')")
        if save_btn:
            print("  [+] Inner Save button detected, saving card...")
            try:
                save_btn.click(timeout=2000)
            except Exception:
                page.evaluate("(el) => el.click()", save_btn)
            time.sleep(1.5)

        # ── Evaluate Primary Action in Modal Footer ───────────────────────
        action = page.evaluate("""() => {
            const modal = document.querySelector('.jobs-easy-apply-modal');
            if (!modal) return null;
            const btns = Array.from(modal.querySelectorAll('footer button, button'));
            
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
            print("  [✓] Submitting application…")
            page.evaluate("""() => {
                const modal = document.querySelector('.jobs-easy-apply-modal');
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
                    const dismiss = document.querySelector('[role="dialog"] button[aria-label="Dismiss"], [role="dialog"] .artdeco-modal__dismiss, button[aria-label="Dismiss"]');
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
                const modal = document.querySelector('.jobs-easy-apply-modal');
                const btns = Array.from((modal || document).querySelectorAll('button'));
                const btn = btns.find(b => {
                    const t = (b.innerText + ' ' + (b.getAttribute('aria-label') || '')).toLowerCase();
                    return t.includes('continue to next step') || t.includes('next');
                });
                if (btn) btn.click();
            }""")
            time.sleep(2)
            continue

        if action == "review" and not review_clicked:
            print("  [→] Review…")
            page.evaluate("""() => {
                const modal = document.querySelector('.jobs-easy-apply-modal');
                const btns = Array.from((modal || document).querySelectorAll('button'));
                const btn = btns.find(b => {
                    const t = (b.innerText + ' ' + (b.getAttribute('aria-label') || '')).toLowerCase();
                    return t.includes('review your application') || t.includes('review');
                });
                if (btn) btn.click();
            }""")
            review_clicked = True
            time.sleep(2)
            continue

        # ── 4. Validation errors check ───────────────────────────────────
        errors = [
            e.inner_text().strip()
            for e in page.query_selector_all(
                ".jobs-easy-apply-modal .artdeco-inline-feedback--error"
            )
            if e.is_visible()
        ]
        if errors:
            print(f"  [!] Validation errors encountered: {errors}")
        else:
            print("  [?] No actionable button found – bailing.")
        break

    # Dismiss without submitting
    clear_all_overlays(page)
    return False


# ── Authentication Helper ─────────────────────────────────────────────────────

def is_logged_in(page: Page) -> bool:
    """Return True if the current page indicates an active authenticated session."""
    try:
        url_lower = page.url.lower()
        if any(term in url_lower for term in ["login", "uas", "signup", "authwall", "checkpoint", "challenge"]):
            return False
        if page.query_selector(".global-nav__me, #global-nav, .feed-identity-module, .profile-rail-card, nav.global-nav"):
            return True
        title = page.title().lower()
        if any(term in title for term in ["sign in", "sign up", "login", "auth"]):
            return False
        return "feed" in url_lower or "jobs" in url_lower
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

        submit_btn = None
        for btn in page.query_selector_all("button"):
            try:
                if btn.is_visible() and ("sign in" in btn.inner_text().strip().lower() or btn.get_attribute("type") == "submit"):
                    submit_btn = btn
                    break
            except Exception:
                pass

        attempted = False
        if user_field and pwd_field and submit_btn and email and password:
            print("[LinkedIn Auth] Entering credentials (Single Attempt per Zero-Lockout Protocol)...")
            try:
                user_field.fill(email)
                time.sleep(0.5)
                pwd_field.fill(password)
                time.sleep(0.5)
                submit_btn.click()
                attempted = True
                time.sleep(5)
            except Exception as fe:
                print(f"[LinkedIn Auth] Note during automated fill: {fe}")
        else:
            print("[LinkedIn Auth] Login fields missing or already modified. Alerting user...")

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

SKIP_KEYWORDS = [
    "java", "kubernetes", "ios developer", "android developer",
    "spring boot", "docker", ".net", "vice president", "vp -",
    "intern", "internship", "trainee", "apprentice",
]

def run(target: int = 10, keywords: str = None, location: str = "India", sort: str = "DD"):
    global RESUME_PATH
    load_env()

    # Resolve latest master resume
    candidates = sorted(
        [p for d in ("cv", "user_inputs/cv") for p in Path(d).glob("*.pdf")
         if "archive" not in str(p).lower()],
        key=lambda x: x.stat().st_mtime, reverse=True,
    )
    RESUME_PATH = candidates[0].resolve() if candidates else None
    print(f"[Master CV] {RESUME_PATH}")

    # Build LinkedIn Easy Apply search URL
    # keywords default to the 4 requested designations:
    # "Data Analyst" OR "Data Consultant" OR "Data Engineer" OR "Data Scientist"
    if not keywords:
        keywords = '"Data Analyst" OR "Data Consultant" OR "Data Engineer" OR "Data Scientist"'

    encoded_kw = urllib.parse.quote(keywords)
    encoded_loc = urllib.parse.quote(location)
    # sortBy=DD = Date Descending (newest to oldest)
    # f_AL=true = Easy Apply
    search_url = (
        f"https://www.linkedin.com/jobs/search/?"
        f"keywords={encoded_kw}"
        f"&location={encoded_loc}"
        f"&f_AL=true"
        f"&sortBy={sort}"
    )

    print(f"\n[LinkedIn Setup]")
    print(f"  • Designations: {keywords}")
    print(f"  • Location: {location}")
    print(f"  • Filter: Easy Apply (f_AL=true)")
    print(f"  • Sorting: Date Descending / Newest to Oldest (sortBy={sort})")
    print(f"  • Target Applications: {target}")
    print(f"  • LLM Engine: OpenRouter Free Tier (:free)")

    today_applied = get_today_easy_apply_count()
    print(f"  • Today's Easy Apply Submissions: {today_applied}/{DAILY_EASY_APPLY_LIMIT}\n")

    if today_applied >= DAILY_EASY_APPLY_LIMIT:
        print(f"\n[Safety Gate] Daily Easy Apply ceiling reached ({today_applied}/{DAILY_EASY_APPLY_LIMIT} submitted today).")
        print("Halting automation to protect account standing against LinkedIn limits.\n")
        alert("Easy Apply Daily Limit", f"Reached {today_applied}/{DAILY_EASY_APPLY_LIMIT} applications today. Automation safely paused.")
        return

    pw = sync_playwright().start()
    session_dir = Path(".browser_session").resolve()
    session_dir.mkdir(parents=True, exist_ok=True)

    browser = pw.chromium.launch_persistent_context(
        user_data_dir=str(session_dir),
        headless=False,
        no_viewport=True,
        args=["--start-maximized", "--no-default-browser-check"]
    )
    page = browser.pages[0] if browser.pages else browser.new_page()

    # Step 1: Ensure authenticated
    ensure_authenticated(page)

    # Step 2: Navigate to sorted Easy Apply job list
    print(f"\n[Search] Navigating to: {search_url}")
    page.goto(search_url, wait_until="domcontentloaded")
    time.sleep(4)

    # Step 3: Load previously applied records
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
    page_num = 1
    total_tokens_spent = 0

    while applied < target:
        print(f"\n{'='*55}")
        print(f"[Scan] Page {page_num}  |  Applied {applied}/{target}  |  LLM Mode: OpenRouter Free")
        print(f"{'='*55}")

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
            print("[!] No job listings found on this page. Checking if search needs refresh...")
            time.sleep(3)
            # Second attempt after brief scroll
            page.evaluate("window.scrollTo(0, 300);")
            time.sleep(2)
            for card in page.query_selector_all("[data-occludable-job-id], .job-card-container, a[href*='jobs/view']"):
                jid = card.get_attribute("data-occludable-job-id") or card.get_attribute("data-job-id")
                if not jid:
                    href = card.get_attribute("href") or ""
                    m = re.search(r"jobs/view/(\d+)", href)
                    if m:
                        jid = m.group(1)
                if jid and jid not in job_ids:
                    job_ids.append(jid)

        if not job_ids:
            print("[!] No job listings found on this page.")
            break

        print(f"[Scan] {len(job_ids)} listings found on page {page_num}.")

        for jid in job_ids:
            if applied >= target:
                break
            if (today_applied + applied) >= DAILY_EASY_APPLY_LIMIT:
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
                title = t_el.inner_text().strip() if t_el else f"Job {jid}"
                company = c_el.inner_text().strip() if c_el else "Unknown Company"

                print(f"\n→ [{applied+1}/{target}] {title} @ {company}")

                # Check technology exclusions
                if any(bad in title.lower() for bad in SKIP_KEYWORDS):
                    print("  [-] Skipped due to exclusion rule (e.g. Java, DevOps, Internship).")
                    continue

                ok = apply_to_current_job(page)
                if ok:
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
                clear_all_overlays(page)
                time.sleep(1)

        # Pagination
        if applied < target:
            nxt = (
                page.query_selector(f"button[aria-label='Page {page_num + 1}']")
                or page.query_selector(".artdeco-pagination__button--next")
            )
            if nxt and nxt.is_visible() and not nxt.is_disabled():
                page.evaluate("(el) => el.click()", nxt)
                page_num += 1
                time.sleep(4)
            else:
                print("[Scan] No further pages available.")
                break

    print(f"\n{'='*55}")
    print(f"[Execution Summary] Applied {applied}/{target} Easy Apply jobs.")
    print(f"  • Roles: {keywords}")
    print(f"  • Sort: Date Descending (Newest to Oldest)")
    print(f"  • Q&A Engine: OpenRouter Free Models & Knowledge Base")
    print(f"  • Tracker: Synchronized with {TRACKER_CSV.name} and {JOBS_DB.name}")
    print(f"  • Browser: Preserved interactive per Rule 2.3.")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LinkedIn Easy Apply Runner with OpenRouter Free")
    parser.add_argument("count", nargs="?", type=int, default=10, help="Number of applications (default: 10)")
    parser.add_argument("--keywords", "-k", type=str, default='"Data Analyst" OR "Data Consultant" OR "Data Engineer" OR "Data Scientist"', help="Designations search query")
    parser.add_argument("--location", "-l", type=str, default="India", help="Location filter (default: India)")
    parser.add_argument("--sort", "-s", type=str, default="DD", choices=["DD", "R"], help="DD = Date Descending (newest to old), R = Relevant")
    args = parser.parse_args()

    run(target=args.count, keywords=args.keywords, location=args.location, sort=args.sort)
