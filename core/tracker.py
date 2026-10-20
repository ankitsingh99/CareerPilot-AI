#!/usr/bin/env python3
"""
Sync and replicate job search tracker CSV and SQLite database locally.
Generates recruiter search links directly from company names with zero LLM overhead.
Optimized for local execution using SQLite3 standard library.

Author: Ankit Kumar Singh
Rule: Zero em dashes permitted.
"""

import os
import sys
import csv
import sqlite3
import urllib.parse
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CSV_PATH = ROOT_DIR / "user_inputs" / "job_search_tracker.csv" if (ROOT_DIR / "user_inputs" / "job_search_tracker.csv").exists() else (ROOT_DIR / "job_search_tracker.csv")
DEFAULT_DB_PATH = ROOT_DIR / "jobs.db"

CSV_FIELDS = [
    "date", "company", "sector", "role", "role_type", "channel",
    "status", "contact_person", "fit_rating", "notes", "cv_file",
    "cover_letter_file", "source", "deadline", "recruiter_search_link"
]

def generate_recruiter_search_link(company: str) -> str:
    """Generate LinkedIn people search URL for recruiters at target company."""
    if not company or not company.strip():
        return ""
    # Clean company name (e.g. remove parentheticals like 'PwC (PricewaterhouseCoopers)' -> 'PwC')
    clean_name = company.split("(")[0].strip()
    clean_name = clean_name.replace("&", "and")
    query = f"{clean_name} recruiter"
    encoded_query = urllib.parse.quote(query)
    return f"https://www.linkedin.com/search/results/people/?keywords={encoded_query}&origin=GLOBAL_SEARCH_HEADER"

DEFAULT_MDM_CSV_PATH = ROOT_DIR / "job_discovery" / "master_companies_mdm.csv"

def ensure_db_schema(conn: sqlite3.Connection):
    """Ensure jobs, companies_mdm tables and unified research & tracking views exist."""
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
    cursor.execute("PRAGMA table_info(jobs)")
    columns = [col[1] for col in cursor.fetchall()]
    if "recruiter_search_link" not in columns:
        cursor.execute("ALTER TABLE jobs ADD COLUMN recruiter_search_link TEXT")
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_url ON jobs(url)")

    # Master Companies MDM table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS companies_mdm (
            company_name TEXT PRIMARY KEY,
            gcc_india_hub TEXT,
            domain_pillar TEXT,
            sub_domain TEXT,
            persona_match_rationale TEXT,
            recommended_target_roles TEXT,
            candidate_fit_score REAL,
            india_locations TEXT,
            core_functional_focus TEXT,
            compensation_benchmark TEXT,
            network_contacts TEXT,
            career_portal_url TEXT,
            company_overview TEXT,
            compensation_median_lpa REAL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_mdm_domain ON companies_mdm(domain_pillar)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_mdm_fit_score ON companies_mdm(candidate_fit_score)")

    # Unified Research and Application Tracking View
    cursor.execute("""
        CREATE VIEW IF NOT EXISTS v_job_research_and_tracking AS
        SELECT 
            j.id AS tracking_id,
            c.company_name,
            j.title AS applied_role,
            j.status AS application_status,
            c.domain_pillar,
            c.sub_domain,
            c.candidate_fit_score AS mdm_fit_score,
            j.score AS application_fit_score,
            c.compensation_benchmark,
            c.india_locations,
            c.career_portal_url,
            j.url AS job_posting_url,
            j.recruiter_search_link,
            j.notes,
            j.cv_file,
            j.cover_letter_file,
            j.created_at AS application_date,
            c.company_overview
        FROM companies_mdm c
        LEFT JOIN jobs j ON LOWER(TRIM(j.company)) = LOWER(TRIM(c.company_name))
        ORDER BY c.candidate_fit_score DESC, j.created_at DESC;
    """)
    conn.commit()

def sync_mdm_to_db(mdm_path: Path = DEFAULT_MDM_CSV_PATH, db_path: Path = DEFAULT_DB_PATH) -> int:
    """Sync master_companies_mdm.csv into companies_mdm table in jobs.db."""
    if not mdm_path.exists():
        return 0

    conn = sqlite3.connect(db_path)
    ensure_db_schema(conn)
    cursor = conn.cursor()

    count = 0
    with open(mdm_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            c_name = r.get("company_name", "").strip()
            if not c_name:
                continue
            try:
                fit_score = float(r.get("candidate_fit_score", 0)) if r.get("candidate_fit_score") else None
            except ValueError:
                fit_score = None
            try:
                lpa = float(r.get("compensation_median_lpa", 0)) if r.get("compensation_median_lpa") else None
            except ValueError:
                lpa = None

            cursor.execute("""
                INSERT INTO companies_mdm (
                    company_name, gcc_india_hub, domain_pillar, sub_domain,
                    persona_match_rationale, recommended_target_roles, candidate_fit_score,
                    india_locations, core_functional_focus, compensation_benchmark,
                    network_contacts, career_portal_url, company_overview, compensation_median_lpa,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(company_name) DO UPDATE SET
                    gcc_india_hub = excluded.gcc_india_hub,
                    domain_pillar = excluded.domain_pillar,
                    sub_domain = excluded.sub_domain,
                    persona_match_rationale = excluded.persona_match_rationale,
                    recommended_target_roles = excluded.recommended_target_roles,
                    candidate_fit_score = excluded.candidate_fit_score,
                    india_locations = excluded.india_locations,
                    core_functional_focus = excluded.core_functional_focus,
                    compensation_benchmark = excluded.compensation_benchmark,
                    network_contacts = excluded.network_contacts,
                    career_portal_url = excluded.career_portal_url,
                    company_overview = excluded.company_overview,
                    compensation_median_lpa = excluded.compensation_median_lpa,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                c_name, r.get("gcc_india_hub"), r.get("domain_pillar"), r.get("sub_domain"),
                r.get("persona_match_rationale"), r.get("recommended_target_roles"), fit_score,
                r.get("india_locations"), r.get("core_functional_focus"), r.get("compensation_benchmark"),
                r.get("network_contacts"), r.get("career_portal_url"), r.get("company_overview"), lpa
            ))
            count += 1

DEFAULT_EXCEL_PATH = ROOT_DIR / "Analyst job tracker.xlsx"

def sync_excel_to_db(excel_path: Path = DEFAULT_EXCEL_PATH, db_path: Path = DEFAULT_DB_PATH) -> int:
    """Sync Analyst job tracker.xlsx sheets into SQLite tables in jobs.db."""
    if not excel_path.exists():
        return 0

    try:
        import openpyxl
    except ImportError:
        return 0

    wb = openpyxl.load_workbook(excel_path, data_only=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. analyst_job_tracker_excel table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS analyst_job_tracker_excel (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            company TEXT,
            locations_focus TEXT,
            comp_notes TEXT,
            status TEXT,
            date_applied TEXT,
            notes TEXT,
            referer TEXT,
            job_id TEXT,
            job_urls TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("DELETE FROM analyst_job_tracker_excel")

    if "Analyst Job Tracker" in wb.sheetnames:
        sheet1 = wb["Analyst Job Tracker"]
        rows1 = list(sheet1.iter_rows(values_only=True))[1:]
        for r in rows1:
            if not any(r):
                continue
            cat, comp, loc, comp_notes, _, status, date_app, notes, ref, job_id, job_urls = (list(r) + [None] * 15)[:11]
            if not comp and not cat:
                continue
            cursor.execute("""
                INSERT INTO analyst_job_tracker_excel (category, company, locations_focus, comp_notes, status, date_applied, notes, referer, job_id, job_urls)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (str(cat or ""), str(comp or ""), str(loc or ""), str(comp_notes or ""), str(status or ""), str(date_app or ""), str(notes or ""), str(ref or ""), str(job_id or ""), str(job_urls or "")))

    # 2. gcc_raw table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gcc_raw (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            common_name TEXT,
            gcc_company_name TEXT,
            industry_category TEXT,
            india_locations TEXT,
            core_functional_focus TEXT,
            official_career_site TEXT
        )
    """)
    cursor.execute("DELETE FROM gcc_raw")

    if "gcc raw" in wb.sheetnames:
        sheet2 = wb["gcc raw"]
        rows2 = list(sheet2.iter_rows(values_only=True))[1:]
        for r in rows2:
            if not any(r):
                continue
            c_name, gcc_name, ind, loc, focus, link = (list(r) + [None] * 10)[:6]
            if not c_name and not gcc_name:
                continue
            cursor.execute("""
                INSERT INTO gcc_raw (common_name, gcc_company_name, industry_category, india_locations, core_functional_focus, official_career_site)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (str(c_name or ""), str(gcc_name or ""), str(ind or ""), str(loc or ""), str(focus or ""), str(link or "")))

    # 3. network_contacts table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS network_contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            programme TEXT,
            batch TEXT,
            email TEXT,
            phone TEXT,
            company_name TEXT,
            confluence_attended TEXT
        )
    """)
    cursor.execute("DELETE FROM network_contacts")

    if "Contact" in wb.sheetnames:
        sheet4 = wb["Contact"]
        rows4 = list(sheet4.iter_rows(values_only=True))[1:]
        for r in rows4:
            if not any(r):
                continue
            name, prog, batch, email, phone, comp, conf = (list(r) + [None] * 10)[:7]
            if not name:
                continue
            cursor.execute("""
                INSERT INTO network_contacts (name, programme, batch, email, phone, company_name, confluence_attended)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (str(name or ""), str(prog or ""), str(batch or ""), str(email or ""), str(phone or ""), str(comp or ""), str(conf or "")))

    conn.commit()
    conn.close()
    return 1


def sync_csv_to_db(csv_path: Path = DEFAULT_CSV_PATH, db_path: Path = DEFAULT_DB_PATH) -> int:
    """
    Replicates the CSV data into the local SQLite database.
    Calculates recruiter_search_link and syncs missing values with 0 LLM tokens.
    """
    if not csv_path.exists():
        print(f"Error: {csv_path} does not exist.")
        return 0

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    ensure_db_schema(conn)

    # 1. Read existing CSV rows and normalize fields
    rows = []
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for line_num, raw_row in enumerate(reader, start=2):
            if not raw_row or not any(field.strip() for field in raw_row):
                continue
            
            # Pad row to match expected columns
            padded = raw_row + [""] * max(0, 15 - len(raw_row))
            
            # Handle 8-col legacy row specifically if found
            if len(raw_row) == 8 and "@" not in padded[4] and "http" in padded[4]:
                # Format: date, company, role, status, url, cv_file, channel, notes
                date_val = padded[0].strip()
                company = padded[1].strip()
                role = padded[2].strip()
                status = padded[3].strip()
                source_url = padded[4].strip()
                cv_file = padded[5].strip()
                channel = padded[6].strip()
                notes = padded[7].strip()
                row_dict = {
                    "date": date_val,
                    "company": company,
                    "sector": "E-Commerce / Cloud BI",
                    "role": role,
                    "role_type": "Data Engineering",
                    "channel": channel,
                    "status": status,
                    "contact_person": "",
                    "fit_rating": "95%",
                    "notes": notes,
                    "cv_file": cv_file,
                    "cover_letter_file": "",
                    "source": source_url,
                    "deadline": "",
                    "recruiter_search_link": generate_recruiter_search_link(company)
                }
            else:
                company = padded[1].strip()
                recruiter_link = padded[14].strip() if len(padded) > 14 and padded[14].strip() else generate_recruiter_search_link(company)
                row_dict = {
                    "date": padded[0].strip(),
                    "company": company,
                    "sector": padded[2].strip(),
                    "role": padded[3].strip(),
                    "role_type": padded[4].strip(),
                    "channel": padded[5].strip(),
                    "status": padded[6].strip(),
                    "contact_person": padded[7].strip(),
                    "fit_rating": padded[8].strip(),
                    "notes": padded[9].strip(),
                    "cv_file": padded[10].strip(),
                    "cover_letter_file": padded[11].strip(),
                    "source": padded[12].strip(),
                    "deadline": padded[13].strip(),
                    "recruiter_search_link": recruiter_link
                }
            rows.append(row_dict)

    # 2. Write back standardized CSV with recruiter_search_link column
    with open(csv_path, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    # 3. Replicate rows into SQLite jobs.db
    cursor = conn.cursor()
    replicated_count = 0
    for r in rows:
        url = r["source"] or f"urn:company:{r['company']}:{r['role']}"
        fit_rating = r["fit_rating"]
        score = 0.0
        if fit_rating and "%" in fit_rating:
            try:
                score = float(fit_rating.replace("%", "").strip())
            except ValueError:
                pass
        
        cursor.execute("""
            INSERT INTO jobs (
                company, sector, title, role_type, source, status,
                contact_person, fit_rating, score, notes, cv_file,
                cover_letter_file, url, deadline, recruiter_search_link,
                created_at, updated_at
            ) VALUES (
                :company, :sector, :role, :role_type, :channel, :status,
                :contact_person, :fit_rating, :score, :notes, :cv_file,
                :cover_letter_file, :url, :deadline, :recruiter_search_link,
                :date, CURRENT_TIMESTAMP
            )
            ON CONFLICT(url) DO UPDATE SET
                company = excluded.company,
                sector = excluded.sector,
                title = excluded.title,
                role_type = excluded.role_type,
                source = excluded.source,
                status = excluded.status,
                contact_person = excluded.contact_person,
                fit_rating = excluded.fit_rating,
                score = excluded.score,
                notes = excluded.notes,
                cv_file = excluded.cv_file,
                cover_letter_file = excluded.cover_letter_file,
                deadline = excluded.deadline,
                recruiter_search_link = excluded.recruiter_search_link,
                updated_at = CURRENT_TIMESTAMP
        """, {
            "company": r["company"],
            "sector": r["sector"],
            "role": r["role"],
            "role_type": r["role_type"],
            "channel": r["channel"],
            "status": r["status"],
            "contact_person": r["contact_person"],
            "fit_rating": r["fit_rating"],
            "score": score,
            "notes": r["notes"],
            "cv_file": r["cv_file"],
            "cover_letter_file": r["cover_letter_file"],
            "url": url,
            "deadline": r["deadline"],
            "recruiter_search_link": r["recruiter_search_link"],
            "date": r["date"] if r["date"] else datetime.now().strftime("%Y-%m-%d")
        })
        replicated_count += 1

    conn.commit()
    conn.close()
    
    # Also sync MDM company records and Excel sheets into jobs.db
    sync_mdm_to_db(db_path=db_path)
    sync_excel_to_db(db_path=db_path)
    return replicated_count

def append_job_locally(
    company: str,
    role: str,
    status: str,
    url: str,
    sector: str = "",
    role_type: str = "",
    channel: str = "LinkedIn",
    fit_rating: str = "95%",
    notes: str = "",
    cv_file: str = os.getenv("CANDIDATE_MASTER_RESUME", "cv/resume.pdf"),
    cover_letter_file: str = "",
    deadline: str = "",
    csv_path: Path = DEFAULT_CSV_PATH,
    db_path: Path = DEFAULT_DB_PATH
):
    """
    Append or update a job record locally without calling an LLM.
    Synchronizes both job_search_tracker.csv and jobs.db in one shot.
    """
    recruiter_link = generate_recruiter_search_link(company)
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 1. Update/Append DB
    conn = sqlite3.connect(db_path)
    ensure_db_schema(conn)
    cursor = conn.cursor()
    
    score = 0.0
    if fit_rating and "%" in fit_rating:
        try:
            score = float(fit_rating.replace("%", "").strip())
        except ValueError:
            pass

    resolved_url = url or f"urn:company:{company}:{role}"
    cursor.execute("""
        INSERT INTO jobs (
            company, sector, title, role_type, source, status,
            contact_person, fit_rating, score, notes, cv_file,
            cover_letter_file, url, deadline, recruiter_search_link,
            created_at, updated_at
        ) VALUES (
            ?, ?, ?, ?, ?, ?, '', ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP
        )
        ON CONFLICT(url) DO UPDATE SET
            status = excluded.status,
            notes = excluded.notes,
            fit_rating = excluded.fit_rating,
            recruiter_search_link = excluded.recruiter_search_link,
            updated_at = CURRENT_TIMESTAMP
    """, (
        company, sector, role, role_type, channel, status,
        fit_rating, score, notes, cv_file, cover_letter_file,
        resolved_url, deadline, recruiter_link, today
    ))
    conn.commit()
    conn.close()

    # 2. Sync to CSV
    sync_csv_to_db(csv_path=csv_path, db_path=db_path)
    print(f"Successfully tracked '{company} - {role}' in CSV & SQLite DB (Recruiter Link: {recruiter_link})")

def main():
    parser = argparse.ArgumentParser(description="Zero-token local sync between CSV and SQLite DB with recruiter links.")
    subparsers = parser.add_subparsers(dest="command")

    # sync command
    sync_p = subparsers.add_parser("sync", help="Synchronize existing CSV and DB, populating missing recruiter search links.")
    sync_p.add_argument("--csv", default=str(DEFAULT_CSV_PATH), help="Path to tracker CSV")
    sync_p.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Path to SQLite DB")

    # add command
    add_p = subparsers.add_parser("add", help="Add or update a job record locally without LLM.")
    add_p.add_argument("--company", required=True, help="Company name")
    add_p.add_argument("--role", required=True, help="Job title / role")
    add_p.add_argument("--status", default="ready_to_apply", help="Application status (applied, ready_to_apply, etc.)")
    add_p.add_argument("--url", default="", help="Posting or application URL")
    add_p.add_argument("--sector", default="", help="Industry / sector")
    add_p.add_argument("--channel", default="LinkedIn", help="Channel / portal")
    add_p.add_argument("--fit", default="95%", help="Fit rating percentage")
    add_p.add_argument("--notes", default="", help="Application notes")
    add_p.add_argument("--cv", default=os.getenv("CANDIDATE_MASTER_RESUME", "cv/resume.pdf"), help="Attached CV path")
    add_p.add_argument("--cover-letter", default="", help="Cover letter path")
    add_p.add_argument("--deadline", default="", help="Deadline date")

    args = parser.parse_args()

    if args.command == "add":
        append_job_locally(
            company=args.company,
            role=args.role,
            status=args.status,
            url=args.url,
            sector=args.sector,
            channel=args.channel,
            fit_rating=args.fit,
            notes=args.notes,
            cv_file=args.cv,
            cover_letter_file=args.cover_letter,
            deadline=args.deadline
        )
    else:
        csv_path = Path(args.csv) if hasattr(args, "csv") else DEFAULT_CSV_PATH
        db_path = Path(args.db) if hasattr(args, "db") else DEFAULT_DB_PATH
        count = sync_csv_to_db(csv_path=csv_path, db_path=db_path)
        print(f"Zero-token local sync complete: {count} applications synchronized between job_search_tracker.csv and jobs.db.")

if __name__ == "__main__":
    import argparse
    main()
