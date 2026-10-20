#!/usr/bin/env python3
"""
SQLite database state engine for job applications lifecycle.
Provides concurrency-safe leasing, state transitions, and CSV synchronization.

Author: Ankit Kumar Singh
Rule: Zero em dashes permitted.
"""

import os
import sqlite3
import csv
import time
from typing import List, Dict, Any, Optional

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "jobs.db")
DEFAULT_CSV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "job_search_tracker.csv")

VALID_STATUSES = {
    "discovered",
    "scored",
    "queued",
    "ready_to_apply",
    "applying",
    "applied",
    "needs_human",
    "skipped_no_sponsorship",
    "withdrawn",
    "failed"
}

def get_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """Initialize SQLite tables for job search tracking."""
    with get_connection(db_path) as conn:
        conn.execute("""
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
                claim_pid INTEGER,
                lease_until REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER,
                action TEXT NOT NULL,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (job_id) REFERENCES jobs(id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_url ON jobs(url)")
        conn.commit()

def insert_job(job: Dict[str, Any], db_path: str = DEFAULT_DB_PATH) -> Optional[int]:
    """Insert or update a job record."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO jobs (
                job_key, source, company, sector, title, role_type, url,
                location, department, salary, jd_text, fit_rating, score,
                status, notes, cv_file, cover_letter_file, contact_person, deadline
            ) VALUES (
                :job_key, :source, :company, :sector, :title, :role_type, :url,
                :location, :department, :salary, :jd_text, :fit_rating, :score,
                :status, :notes, :cv_file, :cover_letter_file, :contact_person, :deadline
            )
            ON CONFLICT(url) DO UPDATE SET
                title = COALESCE(excluded.title, jobs.title),
                company = COALESCE(excluded.company, jobs.company),
                status = COALESCE(excluded.status, jobs.status),
                notes = COALESCE(excluded.notes, jobs.notes),
                fit_rating = COALESCE(excluded.fit_rating, jobs.fit_rating),
                cv_file = COALESCE(excluded.cv_file, jobs.cv_file),
                cover_letter_file = COALESCE(excluded.cover_letter_file, jobs.cover_letter_file),
                location = COALESCE(excluded.location, jobs.location),
                salary = COALESCE(excluded.salary, jobs.salary),
                updated_at = CURRENT_TIMESTAMP
        """, {
            "job_key": job.get("job_key"),
            "source": job.get("source", "direct_ats"),
            "company": job.get("company", ""),
            "sector": job.get("sector", ""),
            "title": job.get("title", ""),
            "role_type": job.get("role_type", ""),
            "url": job.get("url", ""),
            "location": job.get("location", ""),
            "department": job.get("department", ""),
            "salary": job.get("salary", ""),
            "jd_text": job.get("jd_text", ""),
            "fit_rating": job.get("fit_rating", ""),
            "score": float(job.get("score", 0.0) or 0.0),
            "status": job.get("status", "discovered"),
            "notes": job.get("notes", ""),
            "cv_file": job.get("cv_file", os.getenv("CANDIDATE_MASTER_RESUME", "cv/resume.pdf")),
            "cover_letter_file": job.get("cover_letter_file", ""),
            "contact_person": job.get("contact_person", ""),
            "deadline": job.get("deadline", "")
        })
        conn.commit()
        return cursor.lastrowid

def bulk_insert_jobs(jobs: List[Dict[str, Any]], db_path: str = DEFAULT_DB_PATH) -> int:
    """Bulk insert or ignore jobs."""
    init_db(db_path)
    count = 0
    with get_connection(db_path) as conn:
        for job in jobs:
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO jobs (
                        job_key, source, company, sector, title, role_type, url,
                        location, department, salary, jd_text, fit_rating, score, status
                    ) VALUES (
                        :job_key, :source, :company, :sector, :title, :role_type, :url,
                        :location, :department, :salary, :jd_text, :fit_rating, :score, :status
                    )
                """, {
                    "job_key": job.get("job_key"),
                    "source": job.get("source", "direct_ats"),
                    "company": job.get("company", ""),
                    "sector": job.get("sector", ""),
                    "title": job.get("title", ""),
                    "role_type": job.get("role_type", ""),
                    "url": job.get("url", ""),
                    "location": job.get("location", ""),
                    "department": job.get("department", ""),
                    "salary": job.get("salary", ""),
                    "jd_text": job.get("jd_text", ""),
                    "fit_rating": job.get("fit_rating", ""),
                    "score": float(job.get("score", 0.0) or 0.0),
                    "status": job.get("status", "discovered")
                })
                count += 1
            except Exception:
                pass
        conn.commit()
    return count

def claim_job(job_id: int, pid: Optional[int] = None, lease_seconds: int = 300, db_path: str = DEFAULT_DB_PATH) -> bool:
    """Lease a job for worker processing."""
    if pid is None:
        pid = os.getpid()
    now = time.time()
    lease_until = now + lease_seconds
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE jobs
            SET status = 'applying', claim_pid = ?, lease_until = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND (
                status IN ('queued', 'ready_to_apply', 'discovered')
                OR (status = 'applying' AND lease_until < ?)
            )
        """, (pid, lease_until, job_id, now))
        conn.commit()
        if cursor.rowcount > 0:
            cursor.execute("INSERT INTO audit_logs (job_id, action, details) VALUES (?, 'claim', ?)",
                           (job_id, f"Claimed by PID {pid} until {lease_until}"))
            conn.commit()
            return True
    return False

def release_job(job_id: int, status: str, notes: Optional[str] = None, db_path: str = DEFAULT_DB_PATH) -> bool:
    """Release a claimed job with updated status."""
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {status}. Must be one of {VALID_STATUSES}")
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE jobs
            SET status = ?, notes = COALESCE(?, notes), claim_pid = NULL, lease_until = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (status, notes, job_id))
        conn.commit()
        if cursor.rowcount > 0:
            cursor.execute("INSERT INTO audit_logs (job_id, action, details) VALUES (?, 'release', ?)",
                           (job_id, f"Status updated to {status}. Notes: {notes}"))
            conn.commit()
            return True
    return False

def sync_from_csv(csv_path: str = DEFAULT_CSV_PATH, db_path: str = DEFAULT_DB_PATH) -> int:
    """Import records from job_search_tracker.csv into SQLite."""
    init_db(db_path)
    if not os.path.isfile(csv_path):
        return 0
    count = 0
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get("url") and not row.get("source"):
                continue
            url = row.get("source") or row.get("url") or f"urn:company:{row.get('company')}:{row.get('role')}"
            fit_rating = row.get("fit_rating", "")
            score = 0.0
            if fit_rating and "%" in fit_rating:
                try:
                    score = float(fit_rating.replace("%", "").strip())
                except ValueError:
                    pass
            job_data = {
                "company": row.get("company", ""),
                "sector": row.get("sector", ""),
                "title": row.get("role", ""),
                "role_type": row.get("role_type", ""),
                "source": row.get("channel", "manual"),
                "status": row.get("status", "discovered"),
                "contact_person": row.get("contact_person", ""),
                "fit_rating": fit_rating,
                "score": score,
                "notes": row.get("notes", ""),
                "cv_file": row.get("cv_file", os.getenv("CANDIDATE_MASTER_RESUME", "cv/resume.pdf")),
                "cover_letter_file": row.get("cover_letter_file", ""),
                "url": url,
                "deadline": row.get("deadline", "")
            }
            insert_job(job_data, db_path=db_path)
            count += 1
    return count

def export_to_csv(csv_path: str = DEFAULT_CSV_PATH, db_path: str = DEFAULT_DB_PATH) -> int:
    """Export SQLite jobs state to job_search_tracker.csv."""
    init_db(db_path)
    fieldnames = [
        "date", "company", "sector", "role", "role_type", "channel",
        "status", "contact_person", "fit_rating", "notes", "cv_file",
        "cover_letter_file", "source", "deadline"
    ]
    count = 0
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jobs ORDER BY id ASC")
        rows = cursor.fetchall()
        with open(csv_path, mode="w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in rows:
                date_val = r["created_at"][:10] if r["created_at"] else time.strftime("%Y-%m-%d")
                writer.writerow({
                    "date": date_val,
                    "company": r["company"] or "",
                    "sector": r["sector"] or "",
                    "role": r["title"] or "",
                    "role_type": r["role_type"] or "",
                    "channel": r["source"] or "",
                    "status": r["status"] or "discovered",
                    "contact_person": r["contact_person"] or "",
                    "fit_rating": r["fit_rating"] or "",
                    "notes": r["notes"] or "",
                    "cv_file": r["cv_file"] or os.getenv("CANDIDATE_MASTER_RESUME", "cv/resume.pdf"),
                    "cover_letter_file": r["cover_letter_file"] or "",
                    "source": r["url"] or "",
                    "deadline": r["deadline"] or ""
                })
                count += 1
    return count

def get_job_stats(db_path: str = DEFAULT_DB_PATH) -> Dict[str, int]:
    """Retrieve count of jobs grouped by status."""
    init_db(db_path)
    stats = {}
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT status, COUNT(*) as cnt FROM jobs GROUP BY status")
        for row in cursor.fetchall():
            stats[row["status"]] = row["cnt"]
    return stats

if __name__ == "__main__":
    init_db()
    synced = sync_from_csv()
    stats = get_job_stats()
    print(f"Synced {synced} jobs from CSV. Current stats:")
    for status, cnt in sorted(stats.items()):
        print(f"  - {status}: {cnt}")
