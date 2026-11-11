#!/usr/bin/env python3
"""Tests for universal JD-aware LinkedIn and email outreach engine (tools/contact_pitch.py)."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.contact_pitch import (
    analyze_jd_fit,
    audit_and_finalize_outreach,
    fetch_jd_markdown,
    generate_linkedin_dm,
    generate_linkedin_referral,
    generate_outreach_email,
)


class TestOutreachEngine(unittest.TestCase):
    """Validates domain matching, outreach formatting, SSRF guards, and anti-slop rules."""

    def test_analyze_jd_fit_pharma_commercial(self):
        jd = (
            "Commercial Enablement Data Engineer at a pharmaceutical company. "
            "Build batch pipelines for field force sales performance, incentive calculations, "
            "Snowflake, Python, SQL window functions, Spark, and Airflow."
        )
        fit = analyze_jd_fit(jd, role="Data Engineer - Commercial Enablement")
        self.assertEqual(fit["primary_domain"], "pharma_commercial")
        self.assertIn("SQL", fit["matched_skills"])
        self.assertIn("Python", fit["matched_skills"])
        self.assertIn("Snowflake", fit["matched_skills"])

    def test_generate_linkedin_referral_abbott_pattern(self):
        jd = "Pharmaceutical commercial enablement field force incentives SQL Python Snowflake PySpark Airflow AWS"
        url = "https://www.jobs.abbott/us/en/job/ABLAUS31163167ENUSEXTERNAL/Data-Engineer-Commercial-Enablement"
        msg = generate_linkedin_referral(
            company="Abbott",
            role="Data Engineer – Commercial Enablement",
            url=url,
            jd_text=jd,
        )
        self.assertIn("Hope you are doing well!", msg)
        self.assertIn("referring me", msg)
        self.assertIn("ZS Associates", msg)
        self.assertIn("field force incentives", msg)
        self.assertIn(f"Role link: {url}", msg)
        self.assertNotIn("—", msg)
        self.assertTrue(audit_and_finalize_outreach(msg)["passed"])

    def test_generate_linkedin_dm_confident_peer_tone(self):
        jd = "Hiring D2C Business Analyst with WhatsApp automation, Shopify, SQL, Excel, and Power BI."
        dm = generate_linkedin_dm(
            company="Morepen Home",
            role="Business Analyst",
            recipient_name="Richa",
            jd_text=jd,
        )
        self.assertIn("Hi Richa,", dm)
        self.assertNotIn("immediate joiner", dm.lower())
        self.assertNotIn("—", dm)
        self.assertTrue(audit_and_finalize_outreach(dm)["passed"])

    def test_generate_outreach_email_soft_and_hr_fields(self):
        jd = "Business Analyst in Gurugram. Advanced Excel, SQL, Power BI, AI tools, MIS dashboards."
        email = generate_outreach_email(
            recipient_name="Richa Tyagi",
            company="Dr. Morepen Home",
            role="Business Analyst",
            recipient_email="richa.tyagi@drmorepenhome.com",
            jd_text=jd,
            location="Gurugram",
            tone="soft",
            include_hr_fields=True,
        )
        self.assertIn("Hope you are having a good week.", email)
        self.assertIn("Total exp:", email)
        self.assertIn("Current ctc:", email)
        self.assertIn("Expected ctc:", email)
        self.assertIn("Notice period:", email)
        self.assertNotIn("—", email)
        self.assertNotIn("Java", email)
        self.assertTrue(audit_and_finalize_outreach(email)["passed"])

    def test_fetch_jd_markdown_ssrf_guard(self):
        self.assertEqual(fetch_jd_markdown("http://127.0.0.1:8080/internal"), "")
        self.assertEqual(fetch_jd_markdown("file:///etc/passwd"), "")


if __name__ == "__main__":
    unittest.main()

