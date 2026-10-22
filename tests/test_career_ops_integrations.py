#!/usr/bin/env python3
"""
Unit tests for CareerPilot AI & career-ops integration modules:
- core.job_liveness_detector
- core.repost_detector
- core.ats_classifier
- tools.contact_pitch_generator
- tools.offer_contract_analyzer

Rule: Zero em dashes permitted. Standard unittest.TestCase runner.
"""

import unittest
from datetime import date
from core.job_liveness_detector import normalize_for_match, is_job_expired
from core.repost_detector import title_identity_key, RepostDetector
from core.ats_classifier import classify_ats_vendor
from tools.contact_pitch_generator import generate_connection_note
from tools.offer_contract_analyzer import analyze_contract_text


class TestCareerOpsIntegrations(unittest.TestCase):
    
    # ── 1. Job Liveness Detector ──────────────────────────────────────────────
    def test_liveness_normalization(self):
        self.assertEqual(normalize_for_match("Cette offre n’est plus disponible."), "Cette offre n'est plus disponible.")
        self.assertEqual(normalize_for_match("Job   is   closed"), "Job is closed")

    def test_liveness_expired_detection(self):
        closed_samples = [
            "This job is no longer available. Explore other jobs.",
            "The job you are trying to apply for has been filled. Thank you.",
            "This position is closed",
            "This role is closed",
            "Applications have closed for this opening.",
            "Cette offre n’est plus disponible.",
            "Diese Stelle ist bereits besetzt",
            "No longer accepting applications",
            "Job listing not found",
        ]
        for s in closed_samples:
            expired, reason = is_job_expired(s)
            self.assertTrue(expired, f"Failed to detect closure in: '{s}'")
            self.assertTrue(len(reason) > 0)

    def test_liveness_active_postings(self):
        active_samples = [
            "We are looking for a Senior Data Engineer to join our platform team.",
            "Apply now for Data Analyst in Bengaluru, India.",
            "Once the application form has been filled out, our team will review it.",
        ]
        for s in active_samples:
            expired, _ = is_job_expired(s)
            self.assertFalse(expired, f"False positive closure detected on: '{s}'")

    # ── 2. Repost Detector & Title Identity ───────────────────────────────────
    def test_title_identity_normalization(self):
        # Order and punctuation churn should produce identical keys
        key1 = title_identity_key("Senior Data Engineer")
        key2 = title_identity_key("Data Engineer - Senior")
        key3 = title_identity_key("Senior Data Engineer (Full Time)")
        self.assertEqual(key1, key2)
        self.assertEqual(key1, key3)
        self.assertIn("data", key1)
        self.assertIn("engineer", key1)
        self.assertIn("senior", key1)

    # ── 3. ATS Vendor Classifier ──────────────────────────────────────────────
    def test_ats_vendor_classification(self):
        self.assertEqual(classify_ats_vendor("https://boards.greenhouse.io/stripe/jobs/123"), "greenhouse")
        self.assertEqual(classify_ats_vendor("https://jobs.lever.co/anthropic/456"), "lever")
        self.assertEqual(classify_ats_vendor("https://jobs.ashbyhq.com/retool/789"), "ashby")
        self.assertEqual(classify_ats_vendor("https://company.wd5.myworkdayjobs.com/Careers"), "workday")
        self.assertEqual(classify_ats_vendor("https://careers.smartrecruiters.com/Acme/001"), "smartrecruiters")
        self.assertEqual(classify_ats_vendor("https://customcompany.com/jobs"), "customcompany.com")

    # ── 4. Contact Pitch Generator ────────────────────────────────────────────
    def test_contact_pitch_generation(self):
        recruiter_note = generate_connection_note(
            recipient_name="Sarah Jenkins",
            recipient_title="Technical Recruiter",
            company="Zinnia",
            target_role="Data Engineer",
            persona="recruiter"
        )
        self.assertLessEqual(len(recruiter_note), 300)
        self.assertNotIn("—", recruiter_note)
        self.assertIn("Sarah", recruiter_note)
        self.assertIn("Zinnia", recruiter_note)
        self.assertIn("Immediate", recruiter_note)

        manager_note = generate_connection_note(
            recipient_name="David Patel",
            recipient_title="Engineering Director",
            company="Stripe",
            target_role="Analytics Engineer",
            persona="manager"
        )
        self.assertLessEqual(len(manager_note), 300)
        self.assertNotIn("—", manager_note)
        self.assertIn("David", manager_note)
        self.assertIn("Stripe", manager_note)

    # ── 5. Offer & Contract Analyzer ──────────────────────────────────────────
    def test_offer_contract_analyzer(self):
        sample = (
            "The employee shall not engage in any competing data engineering consulting "
            "business for 12 months post termination. Notice period shall be 60 days. "
            "A retention bonus of INR 3,00,000 is subject to clawback if employee departs within 1 year."
        )
        res = analyze_contract_text(sample)
        self.assertIn("non_compete", res["clauses_detected"])
        self.assertIn("notice_period", res["clauses_detected"])
        self.assertIn("clawback_or_bonus", res["clauses_detected"])
        self.assertGreater(len(res["questions_for_lawyer_or_hr"]), 0)


if __name__ == "__main__":
    unittest.main()
