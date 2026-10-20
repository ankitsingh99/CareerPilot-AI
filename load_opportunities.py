# -*- coding: utf-8 -*-
"""
Script to load the researched opportunities CSV into the PostgreSQL `job_tracker` database.
It creates a table `opportunities` (if missing) and inserts rows while respecting the
user's preference to exclude VP‑level roles.
"""
import os
from pathlib import Path
import pandas as pd
import psycopg
from psycopg import sql
from dotenv import load_dotenv

# Load environment variables (same as setup_job_tracker_db.py)
load_dotenv()
PG_HOST = os.getenv("PGHOST", "localhost")
PG_PORT = int(os.getenv("PGPORT", "5432"))
PG_USER = os.getenv("PGUSER", "your_username")
PG_PASSWORD = os.getenv("PGPASSWORD", "your_password")
DB_NAME = os.getenv("DB_NAME", "job_tracker")

CSV_PATH = Path(__file__).parent / "user_inputs" / "company_research" / "researched_opportunities.csv"

def connect_db(dbname: str) -> psycopg.Connection:
    """Return a psycopg connection with autocommit enabled."""
    return psycopg.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=dbname,
        user=PG_USER,
        password=PG_PASSWORD,
        autocommit=True,
    )

def create_opportunities_table():
    stmt = sql.SQL(
        """
        CREATE TABLE IF NOT EXISTS opportunities (
            priority_rank INTEGER,
            company TEXT NOT NULL,
            industry_category TEXT,
            role_title TEXT NOT NULL,
            job_id BIGINT PRIMARY KEY,
            location TEXT,
            location_tier TEXT,
            fit_rating NUMERIC,
            match_reasons TEXT,
            job_url TEXT
        );
        """
    )
    with connect_db(DB_NAME) as conn:
        with conn.cursor() as cur:
            cur.execute(stmt)
    print("Table 'opportunities' ensured.")

def load_csv():
    df = pd.read_csv(CSV_PATH)
    # Exclude VP‑level roles – user preference stored in preferences.md
    vp_mask = df["role_title"].str.contains(r"\bVP\b|Vice President", case=False, na=False)
    df = df[~vp_mask]
    # Clean fit_rating column: remove % and convert to float
    if "fit_rating" in df.columns:
        df["fit_rating"] = df["fit_rating"].astype(str).str.rstrip('%').replace('', None).astype(float)
    return df

def upsert_opportunities(df: pd.DataFrame):
    cols = ["priority_rank","company","industry_category","role_title","job_id","location","location_tier","fit_rating","match_reasons","job_url"]
    # Convert DataFrame rows to list of tuples compatible with psycopg executemany
    records = list(df[cols].itertuples(index=False, name=None))
    insert_stmt = sql.SQL(
        "INSERT INTO opportunities (priority_rank, company, industry_category, role_title, job_id, location, location_tier, fit_rating, match_reasons, job_url) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
        "ON CONFLICT (job_id) DO UPDATE SET "
        "priority_rank = EXCLUDED.priority_rank, "
        "company = EXCLUDED.company, "
        "industry_category = EXCLUDED.industry_category, "
        "role_title = EXCLUDED.role_title, "
        "location = EXCLUDED.location, "
        "location_tier = EXCLUDED.location_tier, "
        "fit_rating = EXCLUDED.fit_rating, "
        "match_reasons = EXCLUDED.match_reasons, "
        "job_url = EXCLUDED.job_url"
    )
    with connect_db(DB_NAME) as conn:
        with conn.cursor() as cur:
            cur.executemany(insert_stmt, records)
    print(f"Inserted/updated {len(records)} opportunity rows.")

def main():
    create_opportunities_table()
    df = load_csv()
    upsert_opportunities(df)
    print("Load complete.")

if __name__ == "__main__":
    main()
