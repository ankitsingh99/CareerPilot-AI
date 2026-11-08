#!/usr/bin/env python3
"""
Unit tests for QASemanticsEngine.
Verifies deterministic pattern matching, compensation guarding,
excluded technology checks, compliance screening, and dropdown option matching.

Rule: Zero em dashes permitted.
Uses standard library unittest.TestCase for full compatibility with GitHub CI unittest runner and pytest.
"""

import re
import unittest
from unittest.mock import patch
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

        # 3. Monthly format
        self.assertEqual(QASemanticsEngine.match_question("Current monthly CTC", field_type="text"), "150000")
        self.assertEqual(QASemanticsEngine.match_question("Expected salary per month", field_type="text"), "233333")

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
        self.assertEqual(QASemanticsEngine.match_question("How many years of Python experience do you have?", field_type="number"), "5")
        self.assertEqual(QASemanticsEngine.match_question("Years of experience with SQL", field_type="number"), "4")
        self.assertEqual(QASemanticsEngine.match_question("Years of Snowflake experience", field_type="number"), "4")
        self.assertEqual(QASemanticsEngine.match_question("Years of Apache Airflow experience", field_type="number"), "4")

    def test_notice_period_and_availability(self):
        self.assertEqual(QASemanticsEngine.match_question("What is your notice period?", field_type="text"), "0")
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

    def test_experience_and_duration_integer_only(self):
        # 1. Verification that learned/KB questions return integer only, never '0 years' or '0 days'
        fake_kb = {
            "how many years of work experience do you have with erwin?": "0 years",
            "in how many days can you join us?": "0 days",
            "how many years of work experience do you have working on splunk": "0 years",
            "how many years of work experience do you have with pyton-scripting,": "4 years",
        }
        with patch.object(QASemanticsEngine, "lookup_knowledge_base", side_effect=lambda q, **kwargs: fake_kb.get(q.strip().lower())):
            self.assertEqual(QASemanticsEngine.match_question("how many years of work experience do you have with erwin?", field_type="text"), "0")
            self.assertEqual(QASemanticsEngine.match_question("in how many days can you join us?", field_type="text"), "0")
            self.assertEqual(QASemanticsEngine.match_question("how many years of work experience do you have working on splunk", field_type="text"), "0")
            self.assertEqual(QASemanticsEngine.match_question("how many years of work experience do you have with pyton-scripting,", field_type="text"), "4")

        # 2. Direct unit sanitizer test
        self.assertEqual(QASemanticsEngine.sanitize_experience_or_duration("0 years", "experience with erwin"), "0")
        self.assertEqual(QASemanticsEngine.sanitize_experience_or_duration("0 days", "in how many days can you join"), "0")
        self.assertEqual(QASemanticsEngine.sanitize_experience_or_duration("4.8 years", "python experience"), "4")
        self.assertEqual(QASemanticsEngine.sanitize_experience_or_duration("4 years", "total experience"), "4")

    def test_total_experience_and_db_tools(self):
        # Database & SQL tools strictly 4 years
        self.assertEqual(QASemanticsEngine.match_question("How many years of experience do you have with DB?", field_type="text"), "4")
        self.assertEqual(QASemanticsEngine.match_question("Years of experience with database", field_type="text"), "4")
        self.assertEqual(QASemanticsEngine.match_question("How many years of experience do you have with datalake?", field_type="text"), "4")
        self.assertEqual(QASemanticsEngine.match_question("Years of experience with PostgreSQL", field_type="text"), "4")
        self.assertEqual(QASemanticsEngine.match_question("How many years of experience with SQL?", field_type="text"), "4")

        # Total work experience strictly 5 years or 60 months
        self.assertEqual(QASemanticsEngine.match_question("Total experience", field_type="text"), "5")
        self.assertEqual(QASemanticsEngine.match_question("Overall work experience", field_type="text"), "5")
        self.assertEqual(QASemanticsEngine.match_question("Years of experience", field_type="text"), "5")
        self.assertEqual(QASemanticsEngine.match_question("Total experience in months", field_type="text"), "60")
        self.assertEqual(QASemanticsEngine.match_question("Total months of experience", field_type="text"), "60")

    def test_gender_strictly_male(self):
        # 1. Text field
        self.assertEqual(QASemanticsEngine.match_question("What is your gender?", field_type="text"), "Male")
        self.assertEqual(QASemanticsEngine.match_question("Gender identity", field_type="text"), "Male")
        self.assertEqual(QASemanticsEngine.match_question("Biological sex", field_type="text"), "Male")

        # 2. Options list where Female precedes Male
        gender_opts = ["Female", "Male", "Non-Binary", "Prefer not to say"]
        self.assertEqual(QASemanticsEngine.match_question("What best describes your gender?", field_type="select", options=gender_opts), "Male")
        self.assertEqual(QASemanticsEngine.match_question("Gender", field_type="radio", options=gender_opts), "Male")

    def test_demographic_diversity_questions(self):
        # LGBTQ
        self.assertEqual(QASemanticsEngine.match_question("Do you identify as LGBTQ?", field_type="radio", options=["Yes", "No"]), "No")
        self.assertEqual(QASemanticsEngine.match_question("Sexual orientation", field_type="select", options=["Heterosexual / Straight", "Gay / Lesbian", "Bisexual", "Other"]), "Heterosexual / Straight")

        # Veteran
        self.assertEqual(QASemanticsEngine.match_question("Are you a protected veteran?", field_type="radio", options=["I am not a veteran", "I identify as one or more"]), "I am not a veteran")

        # Disability
        self.assertEqual(QASemanticsEngine.match_question("Do you have a disability?", field_type="radio", options=["Yes, I have a disability", "No, I do not have a disability"]), "No, I do not have a disability")

    def test_compliance_and_notice_period_dropdown_options(self):
        # EXL style notice period options: must pick 'Less than 15 Days', not '30 Days'
        exl_np_opts = ['Select an option', 'Less than 15 Days', '15 Days', '30 Days', '45 Days', '60 Days', '90 Days']
        self.assertEqual(QASemanticsEngine.match_question("What is your notice period?", field_type="select", options=exl_np_opts), "Less than 15 Days")

        # Prior employment / worked before
        self.assertEqual(QASemanticsEngine.match_question("Have you Worked with exlservice.com (I) Pvt. Ltd. Or any Associate / Subsidiary Company ever before", field_type="text"), "No")
        # Physical ailment
        self.assertEqual(QASemanticsEngine.match_question("Have you passed through or are you passing through any physical ailment or state of health", field_type="text"), "No")
        # Prior interview

    def test_education_graduation_year(self):
        self.assertEqual(QASemanticsEngine.match_question("What was your year of graduation?", field_type="text"), "2020")
        self.assertEqual(QASemanticsEngine.match_question("Year of completion", field_type="text"), "2020")
        self.assertEqual(QASemanticsEngine.match_question("College year of completion", field_type="text"), "2020")
        self.assertEqual(QASemanticsEngine.match_question("Passing year of degree", field_type="text"), "2020")
        self.assertEqual(QASemanticsEngine.match_question("College start year", field_type="text"), "2017")
        self.assertEqual(QASemanticsEngine.match_question("Have you ever appeared for an Interview at any Exl location during the last 90 days?", field_type="text"), "No")
        # Passport & Shifts
        self.assertEqual(QASemanticsEngine.match_question("Do you have a Valid Indian Passport ?", field_type="select", options=["Select an option", "Yes", "No"]), "Yes")
        self.assertEqual(QASemanticsEngine.match_question("Are you willing to work in shifts (Including Night Shifts) ?", field_type="select", options=["Select an option", "Yes", "No"]), "Yes")

    def test_proficiency_and_domain_experience(self):
        prof_opts = ["Expert", "Intermediate", "Beginner", "None"]
        # Core skills -> Expert
        self.assertEqual(QASemanticsEngine.match_question("Please rate your level of proficiency with the Pandas library in Python.", field_type="radio", options=prof_opts), "Expert")
        self.assertEqual(QASemanticsEngine.match_question("Please rate your level of proficiency with PostgreSQL.", field_type="radio", options=prof_opts), "Expert")
        # Secondary skills -> Intermediate
        self.assertEqual(QASemanticsEngine.match_question("Please rate your level of proficiency with R.", field_type="radio", options=prof_opts), "Intermediate")
        self.assertEqual(QASemanticsEngine.match_question("Please rate your level of proficiency with applied statistics and modelling.", field_type="radio", options=prof_opts), "Intermediate")
        # Excluded skills -> None
        self.assertEqual(QASemanticsEngine.match_question("Rate your proficiency in Java Spring Boot", field_type="radio", options=prof_opts), "None")
        # Domain Experience (Pharma / ZS Associates) -> Yes
        self.assertEqual(QASemanticsEngine.match_question("Do u have Experience in Pharma Domain", field_type="radio", options=["Yes", "No"]), "Yes")
        self.assertEqual(QASemanticsEngine.match_question("Do u have Experience in Pharma Domain", field_type="text"), "Yes")
        # Compensation expectations
        self.assertEqual(QASemanticsEngine.match_question("What are your compensation expectations for this role?*", field_type="text"), "2800000")
        self.assertEqual(QASemanticsEngine.match_question("What are your compensation expectations in LPA?", field_type="text"), "28")
        self.assertEqual(QASemanticsEngine.match_question("What is your desired compensation?", field_type="text"), "2800000")
        self.assertEqual(QASemanticsEngine.match_question("What is your current compensation?", field_type="text"), "1800000")

        # Open-ended text
        self.assertIn("quantitative data engineering", QASemanticsEngine.match_question("What is your reason for seeking a job change?", field_type="text"))
        # Autonomous synthesis fallback
        self.assertIn(QASemanticsEngine.synthesize_autonomous_answer("Any novel question?", field_type="radio", options=["Option A", "Option B"]), ["Option A", "Option B"])

    def test_start_date_and_residence(self):
        # Start date: returns formatted next business day
        res_date = QASemanticsEngine.match_question("By what date in the future can you start? *", field_type="text")
        self.assertTrue(re.match(r"^\d{2}/\d{2}/\d{4}$", res_date))
        res_iso_date = QASemanticsEngine.match_question("Start date", field_type="date")
        self.assertTrue(re.match(r"^\d{4}-\d{2}-\d{2}$", res_iso_date))
        
        # Residence
        self.assertEqual(QASemanticsEngine.match_question("Where do you reside?", field_type="text"), "Noida, Uttar Pradesh, India")
        self.assertEqual(QASemanticsEngine.match_question("Where do you reside?", field_type="select", options=["Bengaluru", "Noida", "Mumbai"]), "Noida")
        self.assertEqual(QASemanticsEngine.match_question("Where do you reside?", field_type="select", options=["Delhi NCR", "Mumbai", "Hyderabad"]), "Delhi NCR")
        self.assertEqual(QASemanticsEngine.match_question("Where do you reside?", field_type="select", options=["India", "USA", "UK"]), "India")


if __name__ == "__main__":
    unittest.main()
