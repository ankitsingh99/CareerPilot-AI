"""
Unit tests for direct ATS discovery, SQLite database engine, LinkedIn resolver, and pre-submit audits.
Rule: Zero em dashes permitted.
"""

import os
import unittest
import tempfile
import sqlite3
import json
from unittest.mock import patch, MagicMock

try:
    import requests
except ImportError:
    requests = None

from discovery.ats_discovery.normalize import detect_ats, html_to_text
from discovery.ats_discovery.filters import matches_role, matches_location, filter_job
from discovery.ats_discovery.boards import (
    poll_greenhouse,
    poll_lever,
    poll_ashby,
    poll_smartrecruiters,
    extract_salary
)
from discovery.resolve_linkedin import resolve_linkedin
from core.db import (
    init_db,
    insert_job,
    bulk_insert_jobs,
    claim_job,
    release_job,
    sync_from_csv,
    export_to_csv,
    get_job_stats
)
from core.audit_record import create_audit_record


class TestAtsNormalize(unittest.TestCase):
    def test_detect_ats(self):
        self.assertEqual(detect_ats("https://boards.greenhouse.io/stripe/jobs/123")[0], "greenhouse")
        self.assertEqual(detect_ats("https://jobs.lever.co/figma/abc-123")[0], "lever")
        self.assertEqual(detect_ats("https://jobs.ashbyhq.com/openai/xyz")[0], "ashby")
        self.assertEqual(detect_ats("https://jobs.smartrecruiters.com/Square/456")[0], "smartrecruiters")
        self.assertEqual(detect_ats("https://example.com/careers")[0], "other")


    def test_html_to_text(self):
        html = "<p>Hello <b>World</b></p><br/><ul><li>Data Engineer</li></ul>"
        text = html_to_text(html)
        self.assertIn("Hello World", text)
        self.assertIn("Data Engineer", text)
        self.assertNotIn("<p>", text)


class TestAtsFilters(unittest.TestCase):
    def test_matches_role(self):
        self.assertTrue(matches_role("Senior Data Engineer"))
        self.assertTrue(matches_role("Analytics Engineer"))
        self.assertTrue(matches_role("AI Systems Engineer"))
        self.assertTrue(matches_role("Technical Consultant"))
        self.assertFalse(matches_role("Office Receptionist"))

    def test_matches_location(self):
        self.assertTrue(matches_location("Remote")[0])
        self.assertTrue(matches_location("Anywhere in India")[0])
        self.assertTrue(matches_location("Noida, Uttar Pradesh")[0])
        self.assertTrue(matches_location("Bengaluru, Karnataka")[0])
        self.assertTrue(matches_location("Gurugram")[0])
        self.assertFalse(matches_location("Berlin, Germany - Onsite Only")[0])

    def test_filter_job(self):
        job = {
            "title": "Lead Data Governance Engineer",
            "location": "Remote - India",
            "text": "Snowflake, PySpark, HIPAA compliance"
        }
        self.assertTrue(filter_job(job))

    def test_extract_salary(self):
        self.assertEqual(extract_salary("Base salary range: $140,000 - $180,000 per year"), (140000, 180000))
        self.assertEqual(extract_salary("Compensation is 18 - 25 LPA based on experience"), (1800000, 2500000))


@unittest.skipUnless(requests, "requires optional requests")
class TestAtsBoards(unittest.TestCase):
    @patch("requests.get")
    def test_fetch_greenhouse_jobs(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "jobs": [
                {
                    "id": 101,
                    "title": "Data Engineer",
                    "company_name": "stripe",
                    "absolute_url": "https://boards.greenhouse.io/stripe/jobs/101",
                    "location": {"name": "Remote, India"},
                    "departments": [{"name": "Engineering"}],
                    "content": "<p>PySpark and SQL</p>"
                }
            ]
        }
        mock_get.return_value = mock_resp
        jobs = list(poll_greenhouse("stripe"))
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["company"], "stripe")
        self.assertEqual(jobs[0]["title"], "Data Engineer")

    @patch("requests.get")
    def test_fetch_lever_jobs(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {
                "id": "lev-1",
                "text": "Senior Analytics Engineer",
                "hostedUrl": "https://jobs.lever.co/figma/lev-1",
                "categories": {"location": "Remote", "team": "Data"},
                "descriptionPlain": "Build SQL models and pipelines."
            }
        ]
        mock_get.return_value = mock_resp
        jobs = list(poll_lever("figma"))
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["company"], "figma")
        self.assertEqual(jobs[0]["title"], "Senior Analytics Engineer")

    @patch("requests.get")
    def test_fetch_ashby_jobs(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "jobs": [
                {
                    "id": "ash-1",
                    "title": "AI Agent Developer",
                    "jobUrl": "https://jobs.ashbyhq.com/sample/ash-1",
                    "location": "India Remote",
                    "department": "AI Systems",
                    "descriptionHtml": "<p>LLMs and LangChain</p>"
                }
            ]
        }
        mock_get.return_value = mock_resp
        jobs = list(poll_ashby("sample"))
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["title"], "AI Agent Developer")



class TestResolveLinkedin(unittest.TestCase):
    def test_resolve_direct_ats_link(self):
        direct_gh = "https://boards.greenhouse.io/company/jobs/12345"
        self.assertEqual(resolve_linkedin(direct_gh), direct_gh)



class TestDbState(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_jobs.db")
        self.csv_path = os.path.join(self.temp_dir.name, "test_tracker.csv")
        init_db(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_insert_and_claim_job(self):
        job = {
            "job_key": "gh:testco:123",
            "source": "greenhouse",
            "company": "Test Co",
            "title": "Data Engineer",
            "url": "https://boards.greenhouse.io/testco/jobs/123",
            "location": "Remote",
            "score": 90.0,
            "status": "ready_to_apply"
        }
        job_id = insert_job(job, db_path=self.db_path)
        self.assertIsNotNone(job_id)

        # Claim job
        claimed = claim_job(job_id, pid=9999, lease_seconds=60, db_path=self.db_path)
        self.assertTrue(claimed)

        # Re-claiming while active should fail
        claimed_again = claim_job(job_id, pid=1111, lease_seconds=60, db_path=self.db_path)
        self.assertFalse(claimed_again)

        # Release job
        released = release_job(job_id, status="applied", notes="Submitted successfully", db_path=self.db_path)
        self.assertTrue(released)

        stats = get_job_stats(self.db_path)
        self.assertEqual(stats.get("applied"), 1)

    def test_csv_sync_and_export(self):
        # Create temporary CSV
        with open(self.csv_path, mode="w", encoding="utf-8") as f:
            f.write("date,company,sector,role,role_type,channel,status,contact_person,fit_rating,notes,cv_file,cover_letter_file,source,deadline\n")
            f.write("2026-09-28,AlphaCo,Tech,Data Engineer,Remote,Greenhouse,applied,,95%,Submitted,cv/resume.pdf,,https://example.com/job1,\n")
        
        synced = sync_from_csv(self.csv_path, self.db_path)
        self.assertEqual(synced, 1)

        # Bulk insert
        count = bulk_insert_jobs([
            {"company": "BetaCo", "title": "Data Engineer", "url": "https://example.com/job2"},
            {"company": "GammaCo", "title": "AI Engineer", "url": "https://example.com/job3"}
        ], db_path=self.db_path)
        self.assertEqual(count, 2)


class TestPollBoards(unittest.TestCase):
    def test_load_seeds(self):
        from discovery.boards import load_seeds
        seeds = load_seeds()
        self.assertTrue(len(seeds) > 0)
        self.assertIn("ats", seeds[0])
        self.assertIn("slug", seeds[0])

    @patch("discovery.boards.POLLERS")
    def test_poll_single_company(self, mock_pollers):
        from discovery.boards import poll_single_company
        mock_poller = MagicMock(return_value=[
            {
                "company": "testco",
                "title": "Lead Data Engineer",
                "location": "Remote",
                "url": "https://boards.greenhouse.io/testco/1",
                "salary_min": 1800000,
                "salary_max": 2500000,
                "jd_text": "Snowflake, Airflow, PySpark"
            }
        ])
        mock_pollers.get.return_value = mock_poller

        results = poll_single_company({"ats": "greenhouse", "slug": "testco"})
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["company"], "testco")
        self.assertEqual(results[0]["title"], "Lead Data Engineer")


class TestAuditRecord(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_audit_record(self):
        audit_file = create_audit_record(
            company="Acme Corp",
            role="Senior Analytics Engineer",
            ats_type="Lever",
            url="https://jobs.lever.co/acme/123",
            form_data={
                "Name": "Jane Doe",
                "Email": "placeholder@email.com",
                "Current CTC": "18 LPA"
            },
            custom_qa={
                "What ETL tools have you used?": "PySpark, Apache Airflow, Snowflake, and DBT"
            },
            output_dir=self.temp_dir.name
        )
        self.assertTrue(os.path.isfile(audit_file))
        with open(audit_file, mode="r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("Acme Corp", content)
            self.assertIn("Senior Analytics Engineer", content)
            self.assertIn("placeholder@email.com", content)
            self.assertIn("Apache Airflow", content)
            self.assertNotIn("—", content)


if __name__ == "__main__":
    unittest.main()

