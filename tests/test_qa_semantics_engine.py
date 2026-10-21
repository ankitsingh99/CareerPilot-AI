#!/usr/bin/env python3
"""
Unit tests for QASemanticsEngine.
Verifies deterministic pattern matching, compensation guarding,
excluded technology checks, compliance screening, and dropdown option matching.

Rule: Zero em dashes permitted.
Uses standard library unittest.TestCase for full compatibility with GitHub CI unittest runner and pytest.
"""

import unittest
from core.qa_semantics_engine import QASemanticsEngine


class TestQASemanticsEngine(unittest.TestCase):
    def test_annual_income_and_ctc_guarded(self):
        # 1. Full integer format
        self.assertEqual(QASemanticsEngine.match_question("What is your current annual income?", field_type="text"), "1800000")
        self.assertEqual(QASemanticsEngine.match_question("Fixed CTC / Total Annual CTC", field_type="number"), "1800000")
        self.assertEqual(QASemanticsEngine.match_question("Current package in INR", field_type="text"), "1800000")

        # 2. LPA / Lakh / Decimal format
        self.assertEqual(QASemanticsEngine.match_question("Current CTC (in LPA)", field_type="text"), "18")
        self.assertEqual(QASemanticsEngine.match_question("Annual income in Lakhs", field_type="text"), "18")

    def test_expected_ctc_and_upper_salary(self):
        self.assertEqual(QASemanticsEngine.match_question("Expected salary in INR", field_type="text"), "2800000")
        self.assertEqual(QASemanticsEngine.match_question("Desired CTC (in LPA)", field_type="text"), "28")

        # Upper salary range override
        upper = ("3500000", "35")
        self.assertEqual(QASemanticsEngine.match_question("Desired salary", field_type="text", upper_salary=upper), "3500000")
        self.assertEqual(QASemanticsEngine.match_question("Desired salary in LPA", field_type="text", upper_salary=upper), "35")

    def test_excluded_technology_returns_zero(self):
        self.assertEqual(QASemanticsEngine.match_question("How many years of Java experience do you have?", field_type="number"), "0")
        self.assertEqual(QASemanticsEngine.match_question("Years of experience with Spring Boot", field_type="number"), "0")
        self.assertEqual(QASemanticsEngine.match_question("Years of Kubernetes experience", field_type="number"), "0")

    def test_core_tools_return_candidate_experience(self):
        self.assertEqual(QASemanticsEngine.match_question("How many years of Python experience do you have?", field_type="number"), "4")
        self.assertEqual(QASemanticsEngine.match_question("Years of experience with SQL", field_type="number"), "4")
        self.assertEqual(QASemanticsEngine.match_question("Years of Snowflake experience", field_type="number"), "4")
        self.assertEqual(QASemanticsEngine.match_question("Years of Apache Airflow experience", field_type="number"), "4")

    def test_notice_period_and_availability(self):
        self.assertEqual(QASemanticsEngine.match_question("What is your notice period?", field_type="text"), "Immediate Joiner (0 days notice)")
        self.assertEqual(QASemanticsEngine.match_question("Notice period in days", field_type="number"), "0")
        self.assertEqual(QASemanticsEngine.match_question("Availability to start (in days)", field_type="number"), "0")

    def test_education_and_academics(self):
        self.assertEqual(QASemanticsEngine.match_question("What is your undergraduate CGPA / grade?", field_type="text"), "6.5")
        self.assertEqual(QASemanticsEngine.match_question("Highest degree title", field_type="text"), "Bachelor of Arts (Hons.) Business Economics")
        self.assertEqual(QASemanticsEngine.match_question("Major or field of study", field_type="text"), "Business Economics")
        self.assertEqual(QASemanticsEngine.match_question("Degree granting institution / university", field_type="text"), "University of Delhi")

    def test_compliance_and_screening(self):
        # Negative compliance (No)
        self.assertEqual(QASemanticsEngine.match_question("Do you require visa sponsorship now or in future?", field_type="text"), "No")
        self.assertEqual(QASemanticsEngine.match_question("Do you have a personal relationship with an employee?", field_type="text"), "No")
        self.assertEqual(QASemanticsEngine.match_question("Have you ever been convicted of a felony?", field_type="text"), "No")
        self.assertEqual(QASemanticsEngine.match_question("Are you subject to any non-compete clause?", field_type="text"), "No")

        # Positive compliance (Yes)
        self.assertEqual(QASemanticsEngine.match_question("Are you authorized to work in India?", field_type="text"), "Yes")
        self.assertEqual(QASemanticsEngine.match_question("Are you willing to relocate?", field_type="text"), "Yes")
        self.assertEqual(QASemanticsEngine.match_question("Are you open to hybrid / onsite work?", field_type="text"), "Yes")
        self.assertEqual(QASemanticsEngine.match_question("Are you willing to travel for business?", field_type="text"), "Yes")
        self.assertEqual(QASemanticsEngine.match_question("Consent to background verification and drug screen", field_type="text"), "Yes")

    def test_dropdown_option_selection(self):
        notice_opts = ["30 Days", "60 Days", "Immediate / 0 days", "90 Days"]
        self.assertEqual(QASemanticsEngine.match_question("Notice period", field_type="select", options=notice_opts), "Immediate / 0 days")

        degree_opts = ["High School", "Associate", "Bachelor of Arts / Science", "Master", "PhD"]
        self.assertEqual(QASemanticsEngine.match_question("Highest level of education", field_type="select", options=degree_opts), "Bachelor of Arts / Science")

        exp_opts = ["0-1 year", "1-3 years", "3-5 years", "5-8 years", "8+ years"]
        self.assertEqual(QASemanticsEngine.match_question("Years of Python experience", field_type="select", options=exp_opts), "3-5 years")

    def test_designation_override(self):
        self.assertEqual(QASemanticsEngine.match_question("Your job title / designation", field_type="text"), "Business and Technology Consultant")


if __name__ == "__main__":
    unittest.main()
