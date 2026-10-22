#!/usr/bin/env python3
"""
Unit tests for core/adaptive_evaluator.py.
Verifies the self-learning adaptive evaluator engine and learned invariant rules:
1. Zero Reference Person Fabrication
2. College-Only Education Default
3. Omit Scores/CGPA Unless Required
4. Mandatory Date Population
5. Rush by Kira D2C Retail Spec
"""

import unittest
from core.adaptive_evaluator import AdaptiveEvaluator, audit_form_state


class TestAdaptiveEvaluator(unittest.TestCase):
    def setUp(self):
        self.valid_form_state = {
            "references": [
                {"name": "", "phone": "", "email": "", "company": ""}
            ],
            "education": [
                {
                    "institution": "University of Delhi",
                    "degree": "Bachelor of Arts (Hons.) Business Economics",
                    "start_date": "07/01/2017",
                    "end_date": "07/01/2020",
                    "grade": "",
                    "is_grade_mandatory": False,
                }
            ],
            "work_experience": [
                {
                    "company": "ZS Associates",
                    "title": "Data Engineering & Analytics Associate",
                    "business_type": "Consulting Services",
                    "organization": "Data & Analytics Practice",
                    "start_date": "07/01/2021",
                    "end_date": "09/30/2024",
                    "is_current": False,
                },
                {
                    "company": "Rush by Kira",
                    "title": "Technology & Operations Consultant",
                    "business_type": "Retail",
                    "organization": "D2C Retail & E-Commerce Operations",
                    "start_date": "09/01/2024",
                    "end_date": "",
                    "is_current": True,
                },
            ],
        }

    def test_valid_form_state_passes(self):
        res = audit_form_state(self.valid_form_state)
        self.assertTrue(res["passed"])
        self.assertEqual(res["violations_count"], 0)

    def test_reference_fabrication_flagged(self):
        invalid_state = dict(self.valid_form_state)
        invalid_state["references"] = [{"name": "Rahul Sharma", "phone": "9999999999"}]
        res = audit_form_state(invalid_state)
        self.assertFalse(res["passed"])
        self.assertTrue(any("ZERO_REFERENCE_FABRICATION" in v for v in res["violations"]))

    def test_school_education_flagged_when_unprompted(self):
        invalid_state = dict(self.valid_form_state)
        invalid_state["education"] = [
            {
                "institution": "University of Delhi",
                "degree": "Bachelors",
                "start_date": "07/01/2017",
                "end_date": "07/01/2020",
            },
            {
                "institution": "New Sainik Senior Secondary Public School",
                "degree": "Class 12th",
                "start_date": "04/01/2015",
                "end_date": "03/31/2017",
            },
        ]
        res = audit_form_state(invalid_state)
        self.assertFalse(res["passed"])
        self.assertTrue(any("COLLEGE_ONLY_EDUCATION" in v for v in res["violations"]))

    def test_optional_grade_flagged(self):
        invalid_state = dict(self.valid_form_state)
        invalid_state["education"] = [
            {
                "institution": "University of Delhi",
                "degree": "Bachelors",
                "start_date": "07/01/2017",
                "end_date": "07/01/2020",
                "grade": "6.5 CGPA",
                "is_grade_mandatory": False,
            }
        ]
        res = audit_form_state(invalid_state)
        self.assertFalse(res["passed"])
        self.assertTrue(any("OMIT_OPTIONAL_SCORES" in v for v in res["violations"]))

    def test_missing_dates_flagged(self):
        invalid_state = dict(self.valid_form_state)
        invalid_state["work_experience"] = [
            {
                "company": "ZS Associates",
                "title": "Associate",
                "start_date": "",
                "end_date": "09/30/2024",
                "is_current": False,
            }
        ]
        res = audit_form_state(invalid_state)
        self.assertFalse(res["passed"])
        self.assertTrue(any("MANDATORY_DATES" in v for v in res["violations"]))

    def test_rush_by_kira_misclassification_flagged(self):
        invalid_state = dict(self.valid_form_state)
        invalid_state["work_experience"] = [
            {
                "company": "Rush by Kira",
                "title": "Consultant",
                "business_type": "Consulting Services",
                "organization": "Data Engineering",
                "start_date": "09/01/2024",
                "is_current": True,
            }
        ]
        res = audit_form_state(invalid_state)
        self.assertFalse(res["passed"])
        self.assertTrue(any("RUSH_BY_KIRA_RETAIL" in v for v in res["violations"]))

    def test_sanitize_form_state_auto_corrects_all_invariants(self):
        dirty_state = {
            "references": [{"name": "John Doe", "phone": "1234567890"}],
            "education": [
                {
                    "institution": "University of Delhi",
                    "degree": "Bachelors",
                    "start_date": "07/01/2017",
                    "end_date": "07/01/2020",
                    "grade": "6.5 CGPA",
                    "is_grade_mandatory": False,
                },
                {
                    "institution": "Air Force School",
                    "degree": "Class 10th",
                    "start_date": "04/01/2013",
                    "end_date": "03/31/2015",
                },
            ],
            "work_experience": [
                {
                    "company": "Rush by Kira",
                    "title": "Operations",
                    "business_type": "Other",
                    "organization": "Tech",
                    "start_date": "09/01/2024",
                    "is_current": True,
                }
            ],
        }

        clean_state = AdaptiveEvaluator.sanitize_form_state(dirty_state)
        audit_res = audit_form_state(clean_state)
        self.assertTrue(audit_res["passed"], f"Sanitization failed: {audit_res['violations']}")
        self.assertEqual(len(clean_state["education"]), 1)
        self.assertEqual(clean_state["education"][0]["grade"], "")
        self.assertEqual(clean_state["references"][0]["name"], "")
        self.assertEqual(clean_state["work_experience"][0]["business_type"], "Retail")
        self.assertEqual(clean_state["work_experience"][0]["organization"], "D2C Retail & E-Commerce Operations")

    def test_parse_user_correction(self):
        feedback = "did i ever provide you any references? do not pull data out of thin air"
        parsed = AdaptiveEvaluator.parse_user_correction(feedback)
        self.assertEqual(parsed["status"], "LEARNED")
        self.assertTrue(any(m["invariant"] == "ZERO_REFERENCE_FABRICATION" for m in parsed["matched_corrections"]))

        feedback_edu = "do not add education other than college unless asked for, same for cgpa/score"
        parsed_edu = AdaptiveEvaluator.parse_user_correction(feedback_edu)
        self.assertEqual(parsed_edu["status"], "LEARNED")
        invariants = [m["invariant"] for m in parsed_edu["matched_corrections"]]
        self.assertIn("COLLEGE_ONLY_EDUCATION", invariants)
        self.assertIn("OMIT_OPTIONAL_SCORES", invariants)

        feedback_retail = "rush by kira is D2C retail business"
        parsed_retail = AdaptiveEvaluator.parse_user_correction(feedback_retail)
        self.assertEqual(parsed_retail["status"], "LEARNED")
        self.assertTrue(any(m["invariant"] == "RUSH_BY_KIRA_RETAIL" for m in parsed_retail["matched_corrections"]))


if __name__ == "__main__":
    unittest.main()
