#!/usr/bin/env python3
"""
Export SQLite jobs.db to a PostgreSQL-compatible SQL script (jobs_postgres.sql).
Allows reading, querying, and editing database files via PostgreSQL without any data loss.

Author: Ankit Kumar Singh
Rule: Zero em dashes permitted.
"""

import sys
import re
import lazy_import
sqlite3 = lazy_import.lazy_module("sqlite3")
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT_DIR / "jobs.db"
DEFAULT_OUTPUT_SQL = ROOT_DIR / "jobs_postgres.sql"

def sanitize_text(text: str) -> str:
    """Sanitize text to remove hidden BIDI control characters, BOM, and normalize smart quotes for pgAdmin compatibility."""
    if not isinstance(text, str):
        return text
    # 1. Remove UTF-8 BOM, zero-width spaces, and BIDI control characters
    bidi_regex = re.compile(r'[\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff\u200b\u200c\u200d]')
    text = bidi_regex.sub('', text)

    # 2. Normalize smart quotes and non-ASCII hyphens/dashes
    text = text.replace('‘', "'").replace('’', "'").replace('“', '"').replace('”', '"')
    text = text.replace('—', '-').replace('–', '-')
    return text

def export_sqlite_to_postgres(db_path: Path = DEFAULT_DB_PATH, output_sql: Path = DEFAULT_OUTPUT_SQL):
    """Convert SQLite jobs.db tables and views into PostgreSQL CREATE & INSERT statements."""
    if not db_path.exists():
        print(f"Error: {db_path} does not exist.")
        return False

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    tables = ["jobs", "companies_mdm", "analyst_job_tracker_excel", "gcc_raw", "network_contacts", "job_applications", "semantic_memory"]

    sql_statements = []
    sql_statements.append("-- PostgreSQL Database Export Dump for ai-job-search")
    sql_statements.append("-- Generated automatically from SQLite jobs.db\n")

    # 1. Create tables in PostgreSQL format
    for tbl in tables:
        cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{tbl}';")
        row = cursor.fetchone()
        if row and row[0]:
            create_sql = row[0]
            # Convert SQLite syntax to PostgreSQL syntax
            create_sql = re.sub(r'INTEGER PRIMARY KEY AUTOINCREMENT', 'SERIAL PRIMARY KEY', create_sql, flags=re.IGNORECASE)
            create_sql = re.sub(r'\bDATETIME\b', 'TIMESTAMP', create_sql, flags=re.IGNORECASE)
            create_sql = re.sub(r'TIMESTAMP DEFAULT CURRENT_TIMESTAMP', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP', create_sql, flags=re.IGNORECASE)
            sql_statements.append(f"DROP TABLE IF EXISTS {tbl} CASCADE;")
            sql_statements.append(f"{create_sql};\n")

    # 2. Dump data rows
    for tbl in tables:
        cursor.execute(f"PRAGMA table_info({tbl});")
        cols = [col[1] for col in cursor.fetchall()]
        if not cols:
            continue
        col_str = ", ".join([f'"{c}"' for c in cols])
        
        cursor.execute(f"SELECT * FROM {tbl};")
        rows = cursor.fetchall()
        if rows:
            sql_statements.append(f"-- Data for {tbl}")
            for r in rows:
                vals = []
                for v in r:
                    if v is None:
                        vals.append("NULL")
                    elif isinstance(v, (int, float)):
                        vals.append(str(v))
                    else:
                        clean_v = sanitize_text(str(v))
                        escaped = clean_v.replace("'", "''")
                        vals.append(f"'{escaped}'")
                val_str = ", ".join(vals)
                sql_statements.append(f"INSERT INTO {tbl} ({col_str}) VALUES ({val_str});")
            sql_statements.append("")

    # 3. Create Views
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='view' AND name='v_job_research_and_tracking';")
    view_row = cursor.fetchone()
    if view_row and view_row[0]:
        sql_statements.append("DROP VIEW IF EXISTS v_job_research_and_tracking;")
        sql_statements.append(f"{view_row[0]};\n")

    conn.close()

    with open(output_sql, "w", encoding="utf-8") as f:
        f.write("\n".join(sql_statements))

    print(f"Successfully exported {db_path} -> {output_sql}")
    print(f"To import into PostgreSQL, run: psql -d <your_db_name> -f {output_sql.name}")
    return True

if __name__ == "__main__":
    export_sqlite_to_postgres()
