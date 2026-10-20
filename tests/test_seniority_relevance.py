#!/usr/bin/env python3
"""Unit tests for deterministic seniority and relevance guardrails in on_device_parser."""

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))

from parsers.document import OnDeviceParser


class TestSeniorityRelevance(unittest.TestCase):
    def setUp(self):
        self.parser = OnDeviceParser()

    def test_target_roles_score_high(self):
        roles = [
            ("Senior Data Engineer", "Looking for PySpark, Apache Airflow, SQL and Snowflake expertise"),
            ("Analytics Engineer", "Experience with dbt, SQL, ETL/ELT pipelines and Python"),
            ("AI Systems Engineer", "Building autonomous AI agents and Python data pipelines"),
        ]
        for title, jd in roles:
            res = self.parser.evaluate_seniority_and_relevance(title=title, jd_text=jd)
            self.assertTrue(res["passed_gate"], f"Role '{title}' failed gate: {res}")
            self.assertGreaterEqual(res["deterministic_fit_score"], 60.0)
            self.assertFalse(res["is_strictly_excluded"])

    def test_overqualified_roles_are_capped(self):
        over_senior_roles = [
            "VP of Engineering",
            "Director of Data Architecture",
            "Head of AI Infrastructure",
            "Principal Architect (15+ years exp)",
        ]
        for title in over_senior_roles:
            res = self.parser.evaluate_seniority_and_relevance(title=title, jd_text="12+ years experience required")
            self.assertLessEqual(res["deterministic_fit_score"], 35.0, f"Over-senior role '{title}' was not capped: {res}")
            self.assertFalse(res["passed_gate"])

    def test_underqualified_roles_are_capped(self):
        under_senior_roles = [
            "Software Engineering Intern (Summer 2026)",
            "Data Analyst Co-op / Freshman Student",
        ]
        for title in under_senior_roles:
            res = self.parser.evaluate_seniority_and_relevance(title=title, jd_text="Enrolled in undergrad program")
            self.assertLessEqual(res["deterministic_fit_score"], 20.0, f"Intern role '{title}' was not capped: {res}")
            self.assertFalse(res["passed_gate"])

    def test_strict_exclusions_are_penalized(self):
        excluded_roles = [
            ("Java Backend Developer", "Requires Spring Boot, Hibernate, Java 17"),
            ("DevOps Engineer", "Kubernetes cluster administration, Terraform infrastructure"),
            ("Site Reliability Engineer (SRE)", "Production infrastructure monitoring and K8s ops"),
        ]
        for title, jd in excluded_roles:
            res = self.parser.evaluate_seniority_and_relevance(title=title, jd_text=jd)
            self.assertEqual(res["deterministic_fit_score"], 0.0, f"Excluded role '{title}' was not zeroed out: {res}")
            self.assertTrue(res["is_strictly_excluded"])
            self.assertFalse(res["passed_gate"])


if __name__ == "__main__":
    unittest.main()
