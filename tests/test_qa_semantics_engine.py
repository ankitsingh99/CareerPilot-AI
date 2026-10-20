#!/usr/bin/env python3
"""
Unit tests for QASemanticsEngine.
Verifies deterministic pattern matching, compensation guarding,
excluded technology checks, compliance screening, and dropdown option matching.

Rule: Zero em dashes permitted.
"""

import pytest
from core.qa_semantics_engine import QASemanticsEngine


def test_annual_income_and_ctc_guarded():
    # 1. Full integer format
    assert QASemanticsEngine.match_question("What is your current annual income?", field_type="text") == "1800000"
    assert QASemanticsEngine.match_question("Fixed CTC / Total Annual CTC", field_type="number") == "1800000"
    assert QASemanticsEngine.match_question("Current package in INR", field_type="text") == "1800000"

    # 2. LPA / Lakh / Decimal format
    assert QASemanticsEngine.match_question("Current CTC (in LPA)", field_type="text") == "18"
    assert QASemanticsEngine.match_question("Annual income in Lakhs", field_type="text") == "18"


def test_expected_ctc_and_upper_salary():
    assert QASemanticsEngine.match_question("Expected salary in INR", field_type="text") == "2800000"
    assert QASemanticsEngine.match_question("Desired CTC (in LPA)", field_type="text") == "28"

    # Upper salary range override
    upper = ("3500000", "35")
    assert QASemanticsEngine.match_question("Desired salary", field_type="text", upper_salary=upper) == "3500000"
    assert QASemanticsEngine.match_question("Desired salary in LPA", field_type="text", upper_salary=upper) == "35"


def test_excluded_technology_returns_zero():
    assert QASemanticsEngine.match_question("How many years of Java experience do you have?", field_type="number") == "0"
    assert QASemanticsEngine.match_question("Years of experience with Spring Boot", field_type="number") == "0"
    assert QASemanticsEngine.match_question("Years of Kubernetes experience", field_type="number") == "0"


def test_core_tools_return_candidate_experience():
    assert QASemanticsEngine.match_question("How many years of Python experience do you have?", field_type="number") == "4"
    assert QASemanticsEngine.match_question("Years of experience with SQL", field_type="number") == "4"
    assert QASemanticsEngine.match_question("Years of Snowflake experience", field_type="number") == "4"
    assert QASemanticsEngine.match_question("Years of Apache Airflow experience", field_type="number") == "4"


def test_notice_period_and_availability():
    assert QASemanticsEngine.match_question("What is your notice period?", field_type="text") == "Immediate Joiner (0 days notice)"
    assert QASemanticsEngine.match_question("Notice period in days", field_type="number") == "0"
    assert QASemanticsEngine.match_question("Availability to start (in days)", field_type="number") == "0"


def test_education_and_academics():
    assert QASemanticsEngine.match_question("What is your undergraduate CGPA / grade?", field_type="text") == "6.5"
    assert QASemanticsEngine.match_question("Highest degree title", field_type="text") == "Bachelor of Arts (Hons.) Business Economics"
    assert QASemanticsEngine.match_question("Major or field of study", field_type="text") == "Business Economics"
    assert QASemanticsEngine.match_question("Degree granting institution / university", field_type="text") == "University of Delhi"


def test_compliance_and_screening():
    # Negative compliance (No)
    assert QASemanticsEngine.match_question("Do you require visa sponsorship now or in future?", field_type="text") == "No"
    assert QASemanticsEngine.match_question("Do you have a personal relationship with an employee?", field_type="text") == "No"
    assert QASemanticsEngine.match_question("Have you ever been convicted of a felony?", field_type="text") == "No"
    assert QASemanticsEngine.match_question("Are you subject to any non-compete clause?", field_type="text") == "No"

    # Positive compliance (Yes)
    assert QASemanticsEngine.match_question("Are you authorized to work in India?", field_type="text") == "Yes"
    assert QASemanticsEngine.match_question("Are you willing to relocate?", field_type="text") == "Yes"
    assert QASemanticsEngine.match_question("Are you open to hybrid / onsite work?", field_type="text") == "Yes"
    assert QASemanticsEngine.match_question("Are you willing to travel for business?", field_type="text") == "Yes"
    assert QASemanticsEngine.match_question("Consent to background verification and drug screen", field_type="text") == "Yes"


def test_dropdown_option_selection():
    notice_opts = ["30 Days", "60 Days", "Immediate / 0 days", "90 Days"]
    assert QASemanticsEngine.match_question("Notice period", field_type="select", options=notice_opts) == "Immediate / 0 days"

    degree_opts = ["High School", "Associate", "Bachelor of Arts / Science", "Master", "PhD"]
    assert QASemanticsEngine.match_question("Highest level of education", field_type="select", options=degree_opts) == "Bachelor of Arts / Science"

    exp_opts = ["0-1 year", "1-3 years", "3-5 years", "5-8 years", "8+ years"]
    assert QASemanticsEngine.match_question("Years of Python experience", field_type="select", options=exp_opts) == "3-5 years"


def test_designation_override():
    assert QASemanticsEngine.match_question("Your job title / designation", field_type="text") == "Business and Technology Consultant"
