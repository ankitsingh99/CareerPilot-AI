#!/usr/bin/env python3
"""
tests/test_career_ops_integration.py
------------------------------------
Comprehensive Unit Test Suite for CareerOps Integration Features:
1. Zero-Token Liveness Detection (core/job_liveness_detector.py, tools/check_liveness.py)
2. 1.0 - 5.0 Scoring & A-H Block Evaluation (core/job_evaluator.py, tools/evaluate_job.py)
3. Zero-Token Public ATS Multi-Board Scanning (discovery/ats_discovery/boards.py, tools/scan_public_ats.py)
4. Anti-Hallucination CV Fact Checker (core/cv_fact_checker.py, tools/verify_cv_facts.py)
5. Interview Preparation Kit Generator (tools/interview_prep.py)
6. Skill Gap & Upskill Roadmapper (tools/upskill_analyzer.py)
7. Recruiter & Outreach Pitch Generator (tools/contact_pitch.py)
8. Salary Gap & Compensation Intelligence (tools/salary_gap.py)

Rule: Zero em dashes permitted. Zero financial cost.
"""

import unittest
from pathlib import Path
import tempfile
import os

from core.job_liveness_detector import is_job_expired, check_url_liveness
from core.job_evaluator import JobEvaluator, slugify
from core.cv_fact_checker import CVFactChecker
from tools.interview_prep import generate_interview_kit
from tools.contact_pitch import generate_inmail_pitch, generate_followup_note
from tools.contact_pitch_generator import generate_connection_note
from tools.salary_gap import analyze_salary_gap
from discovery.ats_discovery.boards import POLLERS


class TestCareerOpsIntegration(unittest.TestCase):
    """Verifies all ported career-ops capabilities."""

    def test_liveness_detector_identifies_expired_indicators(self):
        expired_samples = [
            "This job has expired. Thank you for your interest.",
            "This position has been filled.",
            "We are no longer accepting applications for this requisition.",
            "Cette offre n'est plus disponible.",
            "Diese Stelle ist nicht mehr besetzt.",
            "Job listing not found.",
        ]
        for s in expired_samples:
            expired, reason = is_job_expired(s)
            self.assertTrue(expired, f"Failed to detect closure in: '{s}'")
            self.assertTrue(len(reason) > 0)

        active_samples = [
            "We are looking for a Senior Data Engineer with 4 years of experience.",
            "Join our fast-growing data analytics and engineering team.",
            "Apply now for full-time Data Consultant positions.",
        ]
        for s in active_samples:
            expired, _ = is_job_expired(s)
            self.assertFalse(expired, f"False positive closure in: '{s}'")

    def test_job_evaluator_scoring_and_report_generation(self):
        sample_jd = """
        About the Role:
        We are seeking a Senior Data Engineer to architect Snowflake and PySpark pipelines.
        Requirements:
        - 4+ years of experience with Python, SQL, and Snowflake.
        - Experience with Apache Airflow for data orchestration.
        - Experience with AWS (S3) cloud environments.
        Compensation: 24 - 30 LPA
        """
        res = JobEvaluator.evaluate(
            title="Senior Data Engineer",
            company="Test Tech Co",
            jd_text=sample_jd,
            url="https://example.com/job/123"
        )
        # Verify score >= 4.0
        self.assertGreaterEqual(res["score"], 4.0)
        self.assertEqual(res["decision"], "Apply (Tier 2 Recommended)")
        self.assertIn("Python", [s.title() for s in res["matched_skills"]])
        self.assertIn("Snowflake", [s.title() for s in res["matched_skills"]])
        self.assertIn("Airflow", [s.title() for s in res["matched_skills"]])

        # Verify A-H blocks in markdown report
        md = res["report_markdown"]
        self.assertIn("## Block A: Role & Context Summary", md)
        self.assertIn("## Block B: Requirements & Match Matrix", md)
        self.assertIn("## Block C: Seniority Level & Positioning Strategy", md)
        self.assertIn("## Block D: Compensation & Reliability Assessment", md)
        self.assertIn("## Block E: Customization Plan", md)
        self.assertIn("## Block F: Interview STAR+R Stories", md)
        self.assertIn("## Block G: Posting Legitimacy & Ghost Job Signals", md)
        self.assertIn("## Block H: Application Answers & Cover Letter Draft", md)
        self.assertNotIn("—", md, "Violation: Em dash found in generated evaluation report")

        # Clean up generated test report
        report_file = Path(res["report_path"])
        if report_file.is_file():
            report_file.unlink()

    def test_job_evaluator_disqualifier_red_flags(self):
        sample_jd_disqualified = """
        Must have 8+ years of Java and Spring Boot experience. Production Kubernetes DevOps mandatory.
        Unpaid internship position.
        """
        res = JobEvaluator.evaluate(
            title="Java Backend Intern",
            company="Legacy Enterprise",
            jd_text=sample_jd_disqualified
        )
        self.assertLess(res["score"], 3.5)
        self.assertIn("Skip", res["decision"])
        self.assertGreater(len(res["red_flags"]), 0)

        report_file = Path(res["report_path"])
        if report_file.is_file():
            report_file.unlink()

    def test_cv_fact_checker_anti_hallucination(self):
        # Grounded text passes cleanly
        grounded_text = "Reduced query latency by 40% across 15+ Airflow pipelines at Rush by Kira."
        audit_res = CVFactChecker.audit_text(grounded_text)
        self.assertTrue(audit_res["passed"], f"Grounded text failed audit: {audit_res['violations']}")

        # Hallucinated text with em dashes and banned slop fails
        slop_text = "Spearheaded Java pipelines — delivering synergistic game-changer results."
        audit_fail = CVFactChecker.audit_text(slop_text)
        self.assertFalse(audit_fail["passed"])
        self.assertGreaterEqual(len(audit_fail["violations"]), 3)

    def test_ats_pollers_registered(self):
        expected_ats = {"greenhouse", "lever", "ashby", "smartrecruiters", "workable", "bamboohr", "breezy", "recruitee"}
        self.assertTrue(expected_ats.issubset(set(POLLERS.keys())))

    def test_interview_prep_kit_generation(self):
        prep_path_str = generate_interview_kit(
            company="TestAnalytics",
            role="Data Architect",
            jd_text="Experience with Snowflake, Airflow, and PySpark required."
        )
        prep_path = Path(prep_path_str)
        self.assertTrue(prep_path.is_file())
        content = prep_path.read_text(encoding="utf-8")
        self.assertIn("STAR+R", content)
        self.assertIn("Snowflake", content)
        self.assertIn("Reverse Interview Questions", content)
        self.assertNotIn("—", content, "Violation: Em dash found in interview prep brief")
        prep_path.unlink()

    def test_contact_pitch_generation(self):
        note = generate_connection_note(
            recipient_name="Alex",
            recipient_title="Senior Recruiter",
            company="Zeta",
            target_role="Data Engineer"
        )
        self.assertLessEqual(len(note), 300)
        self.assertIn("Zeta", note)
        self.assertNotIn("—", note)

        inmail = generate_inmail_pitch("Jordan", "Zeta", "Data Engineer")
        self.assertIn("Jordan", inmail)
        self.assertIn("Data Engineer", inmail)
        self.assertNotIn("—", inmail)

        followup = generate_followup_note("Jordan", "Zeta", "Data Engineer", days_ago=5)
        self.assertIn("5 days ago", followup)
        self.assertNotIn("—", followup)

    def test_salary_gap_analyzer(self):
        res = analyze_salary_gap("25-32 LPA")
        self.assertIn("Tier 1", res["tier"])
        self.assertIn("25.0 - 32.0 LPA (INR)", res["advertised_range"])

        res_low = analyze_salary_gap("12-15 LPA")
        self.assertIn("Tier 3", res_low["tier"])


if __name__ == "__main__":
    unittest.main()

