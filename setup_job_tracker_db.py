# -*- coding: utf-8 -*-
"""Setup script for the job_tracker PostgreSQL database.

Creates the `job_tracker` database (if missing) and defines schema:
- table `job_applications`
- indexes on company, status, applied_date
- view `recent_applications`
- materialised view `mv_status_counts`
- function `refresh_mv_status_counts`

Uses psycopg (psycopg‑3). Adjust connection variables via .env or edit below.
"""

import os
from pathlib import Path

import psycopg
from psycopg import sql

# Load environment variables from .env (requires python-dotenv)
from dotenv import load_dotenv
load_dotenv()

PG_HOST = os.getenv("PGHOST", "localhost")
PG_PORT = int(os.getenv("PGPORT", "5432"))
PG_USER = os.getenv("PGUSER", "your_username")
PG_PASSWORD = os.getenv("PGPASSWORD", "your_password")
DB_NAME = os.getenv("DB_NAME", "job_tracker")

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

def create_database_if_missing():
    """Create the target database if it does not already exist."""
    with connect_db("postgres") as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql.SQL("SELECT 1 FROM pg_database WHERE datname = %s"),
                (DB_NAME,)
            )
            if not cur.fetchone():
                cur.execute(f"CREATE DATABASE {DB_NAME}")
                print(f"Database '{DB_NAME}' created.")
            else:
                print(f"Database '{DB_NAME}' already exists – skipping.")

def create_schema():
    """Create tables, indexes, views, materialised view and helper function."""
    statements = [
        sql.SQL("""
            CREATE TABLE IF NOT EXISTS job_applications (
                id SERIAL PRIMARY KEY,
                applied_date DATE NOT NULL,
                company TEXT NOT NULL,
                sector TEXT,
                role TEXT,
                role_type TEXT,
                channel TEXT,
                status TEXT,
                contact_person TEXT,
                fit_rating NUMERIC,
                notes TEXT,
                cv_file TEXT,
                cover_letter_file TEXT,
                source TEXT,
                deadline DATE,
                recruiter_search_link TEXT
            );
        """),
        sql.SQL("""
            CREATE INDEX IF NOT EXISTS idx_company ON job_applications (company);
            CREATE INDEX IF NOT EXISTS idx_status ON job_applications (status);
            CREATE INDEX IF NOT EXISTS idx_applied_date ON job_applications (applied_date);
        """),
        sql.SQL("""
            CREATE OR REPLACE VIEW recent_applications AS
            SELECT * FROM job_applications
            WHERE applied_date >= CURRENT_DATE - INTERVAL '30 days';
        """),
        sql.SQL("""
            CREATE MATERIALIZED VIEW IF NOT EXISTS mv_status_counts AS
            SELECT status, COUNT(*) AS cnt FROM job_applications GROUP BY status;
        """),
        sql.SQL("""
            CREATE OR REPLACE FUNCTION refresh_mv_status_counts()
            RETURNS void LANGUAGE plpgsql AS $$
            BEGIN
                REFRESH MATERIALIZED VIEW CONCURRENTLY mv_status_counts;
            END;
            $$;
        """),
        sql.SQL("""
            GRANT SELECT ON recent_applications TO PUBLIC;
            GRANT SELECT ON mv_status_counts TO PUBLIC;
        """) ,

        sql.SQL("""
            CREATE TABLE IF NOT EXISTS dim_company (
                dim_company_id SERIAL PRIMARY KEY,
                company_key TEXT NOT NULL,
                effective_start DATE NOT NULL DEFAULT CURRENT_DATE,
                effective_end DATE,
                is_current BOOLEAN NOT NULL DEFAULT TRUE
            );
            CREATE UNIQUE INDEX IF NOT EXISTS ux_dim_company_key_current ON dim_company (company_key) WHERE is_current;
        """),
        sql.SQL("""
            CREATE TABLE IF NOT EXISTS dim_role (
                dim_role_id SERIAL PRIMARY KEY,
                role_key TEXT NOT NULL,
                effective_start DATE NOT NULL DEFAULT CURRENT_DATE,
                effective_end DATE,
                is_current BOOLEAN NOT NULL DEFAULT TRUE
            );
            CREATE UNIQUE INDEX IF NOT EXISTS ux_dim_role_key_current ON dim_role (role_key) WHERE is_current;
        """),

        sql.SQL("""
            CREATE OR REPLACE FUNCTION upsert_dim_company(p_company_key TEXT) RETURNS VOID AS $$
            BEGIN
                IF EXISTS (SELECT 1 FROM dim_company WHERE company_key = p_company_key AND is_current) THEN
                    UPDATE dim_company SET effective_end = CURRENT_DATE - INTERVAL '1 day',
                        is_current = FALSE
                    WHERE company_key = p_company_key AND is_current;
                END IF;
                INSERT INTO dim_company (company_key, effective_start, is_current)
                VALUES (p_company_key, CURRENT_DATE, TRUE);
            END;
            $$ LANGUAGE plpgsql;
        """),
        sql.SQL("""
            CREATE OR REPLACE FUNCTION upsert_dim_role(p_role_key TEXT) RETURNS VOID AS $$
            BEGIN
                IF EXISTS (SELECT 1 FROM dim_role WHERE role_key = p_role_key AND is_current) THEN
                    UPDATE dim_role SET effective_end = CURRENT_DATE - INTERVAL '1 day',
                        is_current = FALSE
                    WHERE role_key = p_role_key AND is_current;
                END IF;
                INSERT INTO dim_role (role_key, effective_start, is_current)
                VALUES (p_role_key, CURRENT_DATE, TRUE);
            END;
            $$ LANGUAGE plpgsql;
        """),
    ]
    with connect_db(DB_NAME) as conn:
        with conn.cursor() as cur:
            for stmt in statements:
                cur.execute(stmt)
    print("Schema objects created/updated.")

def main():
    create_database_if_missing()
    create_schema()
    # Populate materialised view initially
    with connect_db(DB_NAME) as conn:
        with conn.cursor() as cur:
            cur.execute("REFRESH MATERIALIZED VIEW mv_status_counts;")
    print("Setup complete – you can now query the DB.")

if __name__ == "__main__":
    main()
