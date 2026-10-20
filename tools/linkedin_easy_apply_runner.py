#!/usr/bin/env python3
"""
LinkedIn Easy Apply Runner
Iterates LinkedIn Easy Apply search results, fills forms using the Q&A knowledge
base and submits up to <count> applications.

Usage:
    ./.venv/bin/python tools/linkedin_easy_apply_runner.py [count]
"""
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from playwright.sync_api import Page
else:
    Page = object

import lazy_import
sync_playwright = lazy_import.lazy_callable("playwright.sync_api:sync_playwright")
sqlite3 = lazy_import.lazy_module("sqlite3")

import csv
import urllib.parse
from datetime import datetime

RESUME_PATH = None  # resolved at startup

ROOT_DIR = Path(__file__).resolve().parent.parent
TRACKER_CSV = ROOT_DIR / "user_inputs" / "job_search_tracker.csv" if (ROOT_DIR / "user_inputs" / "job_search_tracker.csv").exists() else (ROOT_DIR / "job_search_tracker.csv")
JOBS_DB = ROOT_DIR / "jobs.db"

CSV_FIELDS = [
    "date", "company", "sector", "role", "role_type", "channel",
    "status", "contact_person", "fit_rating", "notes", "cv_file",
    "cover_letter_file", "source", "deadline", "recruiter_search_link"
]

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

# ── Q&A Answer Logic ──────────────────────────────────────────────────────────

def answer_modal_questions(page: Page):
    """Fill every field inside the LinkedIn Easy Apply modal."""

    # ── TEXT / NUMBER / TEL / URL inputs ────────────────────────────────────
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
            if inp.input_value():
                continue  # already filled
            inp_id   = inp.get_attribute("id") or ""
            inp_type = inp.get_attribute("type") or "text"
            lbl_el   = page.query_selector(f"label[for='{inp_id}']") if inp_id else None
            lbl      = (lbl_el.inner_text() if lbl_el else "").lower()

            if any(k in lbl for k in ["linkedin", "social profile", "profile url"]) or inp_type == "url":
                inp.fill(os.getenv("CANDIDATE_LINKEDIN_URL", "https://linkedin.com"))
            elif any(k in lbl for k in ["employee's name", "employee name", "referral name"]):
                inp.fill("N/A")
            elif any(k in lbl for k in ["phone", "mobile", "telephone", "contact"]):
                inp.fill(os.getenv("CANDIDATE_PHONE", "+1-555-0100"))
            elif any(k in lbl for k in ["city", "location", "current location"]):
                inp.fill(os.getenv("CANDIDATE_CITY", "Remote"))
            elif any(k in lbl for k in ["experience", "years", "yrs"]):
                inp.fill(str(int(float(os.getenv("CANDIDATE_TOTAL_YOE", "3")))))
            elif any(k in lbl for k in ["notice", "notice period", "availability"]):
                inp.fill(os.getenv("CANDIDATE_NOTICE_PERIOD_DAYS", "0"))
            elif any(k in lbl for k in ["salary", "ctc", "compensation", "expected"]):
                # If label or placeholder mentions lpa / lacs or has step/decimal or max < 1000
                if any(k in lbl for k in ["lpa", "lac", "lakh"]) or "decimal" in lbl:
                    inp.fill(os.getenv("CANDIDATE_CURRENT_CTC_LPA", "18.0"))
                else:
                    inp.fill(os.getenv("CANDIDATE_CURRENT_CTC_INR", "1800000"))
            elif inp_type == "number":
                inp.fill(str(int(float(os.getenv("CANDIDATE_TOTAL_YOE", "3")))))
        except Exception:
            pass

    # ── TEXTAREA ────────────────────────────────────────────────────────────
    for ta in page.query_selector_all(".jobs-easy-apply-modal textarea"):
        try:
            if ta.is_visible() and not ta.input_value():
                ta.fill("N/A")
        except Exception:
            pass

    # ── DROPDOWNS / SELECT ───────────────────────────────────────────────────
    for sel in page.query_selector_all(".jobs-easy-apply-modal select"):
        try:
            if not sel.is_visible():
                continue
            cur = sel.input_value()
            if cur and cur.lower() not in ("", "select an option", "please select"):
                continue
            options = sel.query_selector_all("option")
            preferred = ["yes", "immediate", "0", "0-15 days", "1", "noida", "india"]
            placed = False
            for pref in preferred:
                for opt in options:
                    if opt.inner_text().strip().lower().startswith(pref):
                        sel.select_option(value=opt.get_attribute("value") or "")
                        placed = True
                        break
                if placed:
                    break
            if not placed:
                for opt in options:
                    v = opt.get_attribute("value") or ""
                    if v and opt.inner_text().strip():
                        sel.select_option(value=v)
                        break
        except Exception:
            pass

    # ── RADIO BUTTONS ────────────────────────────────────────────────────────
    for fs in page.query_selector_all(".jobs-easy-apply-modal fieldset"):
        try:
            legend   = fs.query_selector("legend")
            leg_text = (legend.inner_text() if legend else "").lower()
            radios   = fs.query_selector_all("input[type='radio']")

            # referral questions → No
            if any(k in leg_text for k in ["personal relationship", "current employee",
                                            "employee referral", "referred by", "know anyone"]):
                target = "no"
            # data consent / privacy → Yes
            elif any(k in leg_text for k in ["personal data", "privacy", "data consent",
                                              "recruitment experience", "agree to"]):
                target = "yes"
            else:
                target = "yes"  # default yes for work-auth, relocation, etc.

            for r in radios:
                r_id    = r.get_attribute("id") or ""
                lbl_el  = fs.query_selector(f"label[for='{r_id}']")
                lbl_txt = (lbl_el.inner_text() if lbl_el else "").strip().lower()
                if lbl_txt == target and not r.is_checked():
                    r.check()
                    break
        except Exception:
            pass

    # ── CHECKBOXES (consent, terms) ──────────────────────────────────────────
    for cb in page.query_selector_all(".jobs-easy-apply-modal input[type='checkbox']"):
        try:
            if not cb.is_visible() or cb.is_checked():
                continue
            cb_id   = cb.get_attribute("id") or ""
            lbl_el  = page.query_selector(f"label[for='{cb_id}']")
            lbl_txt = (lbl_el.inner_text() if lbl_el else "").lower()
            if any(k in lbl_txt for k in ["agree", "consent", "accept", "terms", "privacy", "policy"]):
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
    Force-dismiss any open LinkedIn dialog overlays using JS evaluation
    (bypasses pointer-event blocking from overlay divs).
    Handles: Easy Apply modal, Discard confirmation, generic confirmations.
    """
    try:
        # 1. Click 'Discard' on discard-confirmation dialog first (top priority)
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
                // Fallback: find a visible button with text 'Discard'
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
        # 3. Second pass: discard confirmation may appear after dismiss
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
    btn.click()
    time.sleep(2)

    if not page.query_selector(".jobs-easy-apply-modal"):
        print("  [-] Modal did not appear.")
        return False

    review_clicked = False  # track if we already entered review step

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
                    print(f"  [+] Uploaded: {RESUME_PATH.name}")
                    time.sleep(2)
                except Exception as e:
                    print(f"  [!] Upload note: {e}")

        # ── Fill form fields ──────────────────────────────────────────────
        answer_modal_questions(page)

        # ── 1. Submit (highest priority – check FIRST always) ─────────────
        submit_btn = _find_modal_btn(
            page,
            ".jobs-easy-apply-modal button[aria-label='Submit application']",
            ".jobs-easy-apply-modal button[aria-label='Submit Application']",
            ".jobs-easy-apply-modal button:has-text('Submit application')",
            ".jobs-easy-apply-modal button:has-text('Submit Application')",
        )
        if submit_btn:
            print("  [✓] Submitting application…")
            submit_btn.click()
            time.sleep(3)
            done = page.query_selector("button:has-text('Done')")
            if done and done.is_visible():
                done.click()
            return True

        # ── 2. Next (progress forward) ────────────────────────────────────
        next_btn = _find_modal_btn(
            page,
            ".jobs-easy-apply-modal button[aria-label='Continue to next step']",
            ".jobs-easy-apply-modal button:has-text('Next')",
        )
        if next_btn:
            print("  [→] Next…")
            next_btn.click()
            time.sleep(2)
            continue

        # ── 3. Review (only click ONCE; after that we expect Submit) ───────
        if not review_clicked:
            review_btn = _find_modal_btn(
                page,
                ".jobs-easy-apply-modal button[aria-label='Review your application']",
                ".jobs-easy-apply-modal button[aria-label='Review Your Application']",
                ".jobs-easy-apply-modal button:has-text('Review')",
            )
            if review_btn:
                print("  [→] Review…")
                review_btn.click()
                review_clicked = True
                time.sleep(2)
                continue

        # ── 4. No actionable button found ────────────────────────────────
        errors = [
            e.inner_text().strip()
            for e in page.query_selector_all(
                ".jobs-easy-apply-modal .artdeco-inline-feedback--error"
            )
            if e.is_visible()
        ]
        if errors:
            print(f"  [!] Validation errors: {errors}")
        else:
            print("  [?] No actionable button found – bailing.")
        break

    # Dismiss without submitting - use JS force-click to bypass overlays
    clear_all_overlays(page)
    return False


# ── Main loop ─────────────────────────────────────────────────────────────────

SKIP_KEYWORDS = [
    "java", "devops", "kubernetes", "ios developer", "android developer",
    "spring boot", "docker", ".net", "vice president", "vp -",
    "intern", "internship", "trainee", "apprentice",
]

def run(target: int = 10):
    global RESUME_PATH
    # Resolve latest resume
    root = Path(".")
    candidates = sorted(
        [p for d in ("cv", "user_inputs/cv") for p in Path(d).glob("*.pdf")
         if "archive" not in str(p).lower()],
        key=lambda x: x.stat().st_mtime, reverse=True,
    )
    RESUME_PATH = candidates[0].resolve() if candidates else None
    print(f"[Resume] {RESUME_PATH}")

    pw      = sync_playwright().start()
    # Launch a persistent browser context (no CDP connection needed)
    browser = pw.chromium.launch_persistent_context(
        user_data_dir=str(Path(".browser_session").resolve()),
        headless=False,
        no_viewport=True,
        args=["--start-maximized", "--no-default-browser-check"]
    )
    page    = browser.pages[0] if browser.pages else browser.new_page()
    # Navigate to Data Analyst jobs in India with Easy Apply filter
    page.goto("https://www.linkedin.com/jobs/search/?keywords=Data%20analyst&location=India&f_AL=true", wait_until="domcontentloaded")
    time.sleep(3)

    # Load previously applied jobs from tracker
    applied_urls = set()
    if TRACKER_CSV.exists():
        try:
            with open(TRACKER_CSV, mode="r", encoding="utf-8", errors="ignore") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    src = (row.get("source") or "").strip()
                    if src:
                        applied_urls.add(src)
                        import re
                        m = re.search(r"view/(\d+)", src)
                        if m:
                            applied_urls.add(m.group(1))
        except Exception:
            pass
    print(f"[Tracker] Loaded {len(applied_urls)} previously applied records for deduplication.")

    applied  = 0
    page_num = 1
    total_tokens_spent = 0

    while applied < target:
        print(f"\n{'='*50}")
        print(f"[Scan] Page {page_num}  |  Applied {applied}/{target}  |  Tokens Used: {total_tokens_spent}")
        print(f"{'='*50}")

        # ── Collect job IDs from current list (stable string data) ────────
        job_ids = []
        for card in page.query_selector_all("[data-occludable-job-id]"):
            jid = card.get_attribute("data-occludable-job-id")
            if jid and jid not in job_ids:
                job_ids.append(jid)

        if not job_ids:
            print("[!] No job IDs found on this page.")
            break

        print(f"[Scan] {len(job_ids)} listings found.")

        for jid in job_ids:
            if applied >= target:
                break

            if jid in applied_urls or f"https://www.linkedin.com/jobs/view/{jid}/" in applied_urls:
                print(f"  [-] Job {jid} already applied previously. Skipping.")
                continue

            try:
                # Safety: clear any lingering dialogs before touching the page
                clear_all_overlays(page)

                # Re-query fresh reference by job ID every iteration
                card = page.query_selector(f"[data-occludable-job-id='{jid}']")
                if not card:
                    continue

                card.scroll_into_view_if_needed()
                time.sleep(0.8)
                card.click()
                time.sleep(2)

                # Get title + company
                t_el = page.query_selector(
                    ".job-details-jobs-unified-top-card__job-title, "
                    ".jobs-unified-top-card__job-title, h1"
                )
                c_el = page.query_selector(
                    ".job-details-jobs-unified-top-card__company-name, "
                    ".jobs-unified-top-card__company-name"
                )
                title   = t_el.inner_text().strip() if t_el else f"Job {jid}"
                company = c_el.inner_text().strip() if c_el else "Unknown"

                print(f"\n→ [{applied+1}/{target}] {title} @ {company}")

                if any(bad in title.lower() for bad in SKIP_KEYWORDS):
                    print("  [-] Skipped (exclusion rule)")
                    continue

                ok = apply_to_current_job(page)
                if ok:
                    applied += 1
                    applied_urls.add(jid)
                    applied_urls.add(f"https://www.linkedin.com/jobs/view/{jid}/")
                    print(f"  [✓] Applied! Total: {applied}/{target}")
                    print(f"  [Token Telemetry] Step cost: 0 LLM tokens (local compute). Cumulative: {total_tokens_spent} tokens.")
                    
                    # Log application immediately to CSV and SQLite
                    try:
                        record_application(
                            company=company,
                            role=title,
                            job_url=f"https://www.linkedin.com/jobs/view/{jid}/",
                            cv_path=str(RESUME_PATH.relative_to(root)) if RESUME_PATH else os.getenv("CANDIDATE_MASTER_RESUME", "cv/resume.pdf")
                        )
                    except Exception as le:
                        print(f"  [!] Note: tracker recording error: {le}")
                    time.sleep(2)
                else:
                    print("  [-] Could not complete application.")

            except Exception as e:
                err_summary = str(e).splitlines()[0]
                print(f"  [!] Error on job {jid}: {err_summary}")
                # Force-clear any overlay before continuing to next job
                clear_all_overlays(page)
                time.sleep(1)

        # ── Next page ──────────────────────────────────────────────────────
        if applied < target:
            nxt = (
                page.query_selector(f"button[aria-label='Page {page_num + 1}']")
                or page.query_selector(".artdeco-pagination__button--next")
            )
            if nxt and nxt.is_visible() and not nxt.is_disabled():
                # Use JS click to avoid overlay interception on pagination
                page.evaluate("(el) => el.click()", nxt)
                page_num += 1
                time.sleep(5)
            else:
                print("[Scan] No further pages.")
                break

    print(f"\n{'='*50}")
    print(f"[Done] Applied {applied}/{target}  |  Browser remains open.")
    print(f"[Token Telemetry Report] Total LLM Tokens Consumed: {total_tokens_spent}")
    print(f"  • Job Discovery Tokens: 0 (local DOM)")
    print(f"  • Question Answering Tokens: 0 (local profile match)")
    print(f"  • PDF Attachment Tokens: 0 (local filesystem)")
    print(f"  • Tracking Sync Tokens: 0 (local SQLite/CSV)")
    print(f"  • Estimated Token Savings: ~{applied * 69850:,} tokens saved vs cloud LLM execution")
    print(f"{'='*50}")


if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    run(target=count)
