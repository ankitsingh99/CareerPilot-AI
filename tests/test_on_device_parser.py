"""
Unit & Accuracy tests for On-Device Local Parser and Token Optimization Engine.
Uses standard library unittest.TestCase for full compatibility with GitHub CI unittest runner and pytest.
"""

import json
import unittest
from parsers.document import OnDeviceParser, benchmark_parsing, count_tokens, sanitize_url


class TestSanitizeUrl(unittest.TestCase):
    def test_sanitize_url_tracking_removal(self):
        dirty_url = (
            "https://careers.bcg.com/global/en/job/BCG1US59403EXTERNALENGLOBAL/Global-Digital-Marketing-Analytics-Senior-Analyst"
            "?rx_a=1&rx_c=ap---marketing-tech&rx_ch=jobp4p&rx_group=626507&rx_id=f7e50109-adfd-11f1-8933-594f9448fb2d"
            "&rx_job=59403&rx_medium=cpc&rx_r=none&rx_source=Indeed&rx_ts=20261002T052121Z&rx_vp=cpc"
            "&utm_campaign=APACP092026-APA-global_recruitics_ap-marketing-tech&utm_medium=APACP092026-APA"
            "&utm_source=jobboard_indeed&rx_p=BMPDUDEGWF&rx_viewer=21a0b26eb71d11f19f29c3f44941b124758460e0f5a44046be2e1caff02744e8"
        )
        expected_clean_url = "https://careers.bcg.com/global/en/job/BCG1US59403EXTERNALENGLOBAL/Global-Digital-Marketing-Analytics-Senior-Analyst"
        
        clean_url = sanitize_url(dirty_url)
        self.assertEqual(clean_url, expected_clean_url)

        dirty_tokens = count_tokens(dirty_url)
        clean_tokens = count_tokens(clean_url)
        
        self.assertLess(clean_tokens, dirty_tokens)
        token_savings_pct = (dirty_tokens - clean_tokens) / dirty_tokens * 100.0
        self.assertGreater(token_savings_pct, 75.0)

    def test_sanitize_url_fallback(self):
        self.assertEqual(sanitize_url(""), "")
        self.assertEqual(sanitize_url("   "), "")
        
        clean_input = "https://jobs.lever.co/example/12345"
        self.assertEqual(sanitize_url(clean_input), clean_input)

        clean_query_input = "https://jobs.lever.co/example/12345?page=1&department=engineering"
        self.assertEqual(sanitize_url(clean_query_input), clean_query_input)

        odd_input = "http:///bad-url-schema"
        self.assertEqual(sanitize_url(odd_input), odd_input)


class TestOnDeviceParser(unittest.TestCase):
    def setUp(self):
        self.sample_raw_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Data Engineer - Healthcare Analytics - Careers at ZS</title>
            <script>console.log("analytics tracker payload 12345");</script>
            <style>body { background: #fff; }</style>
        </head>
        <body>
            <nav>
                <a href="/home">Home</a> <a href="/jobs">Search Jobs</a> <a href="/login">Login</a>
            </nav>
            <header>
                <h1>Join Our Team! Best Place to Work 2026</h1>
            </header>

            <main id="job-content">
                <div class="job-header">
                    <h2>Senior Data Engineer - Healthcare Solutions</h2>
                    <span>Location: Remote, India</span>
                    <span>Experience: 5+ years of experience required</span>
                </div>
                <div class="job-description">
                    <h3>About the Role</h3>
                    <p>We are seeking a Senior Data Engineer with 5+ years experience to build scalable healthcare data pipelines.</p>
                    
                    <h3>Key Responsibilities</h3>
                    <ul>
                        <li>Build scalable PySpark and SQL pipelines on Snowflake and AWS S3.</li>
                        <li>Orchestrate batch ETL jobs using Apache Airflow and Autosys.</li>
                        <li>Implement PII and HCP data masking compliant with HIPAA regulations.</li>
                    </ul>

                    <h3>Required Qualifications</h3>
                    <ul>
                        <li>5+ years of hands-on experience in Python, PySpark, SQL, and Snowflake.</li>
                        <li>Proven experience with AWS S3, SNS, and Apache Airflow.</li>
                        <li>Familiarity with Data Governance, HIPAA standards, and Healthcare commercial analytics.</li>
                        <li>Notice period: Immediate joiner or within 15 days preferred.</li>
                    </ul>
                </div>
            </main>

            <footer>
                <p>&copy; 2026 ZS Associates. All rights reserved. Privacy Policy | Cookie Settings</p>
                <svg><path d="M0 0h24v24H0z"/></svg>
            </footer>
        </body>
        </html>
        """

        self.sample_cv_bullets = [
            "Led a team of four responsible for tracking and developing data standardization layers incorporating healthcare media data.",
            "Managed 8+ Big data pipelines using PySpark, Airflow, Autosys, AWS SNS, and Snowflake jobs.",
            "Integrated HCP data stripping and data masking techniques into ingestion pipelines to ensure HIPAA compliance.",
            "Spearheaded technical consulting for healthcare clients, translating complex requirements into high-performance configurations.",
            "Developed DCF and comps models to evaluate valuation, capital allocation, and growth across TMT sectors.",
            "Autonomous Logistics Reconciliation Agent: Built automated courier audit pipeline correlating Shopify and iThinkLogistics CSVs.",
            "State Synchronization & Multi-Store SKU Orchestrator: Engineered bi-directional agents across Shopify stores.",
            "Class 10th score: 9.6 CGPA from Air Force School in March 2015."
        ]

    def test_clean_html_dom(self):
        parser = OnDeviceParser()
        cleaned_text = parser.clean_html_dom(self.sample_raw_html)

        self.assertNotIn("analytics tracker payload", cleaned_text)
        self.assertNotIn("Privacy Policy | Cookie Settings", cleaned_text)
        self.assertNotIn("<svg>", cleaned_text)

        self.assertIn("Senior Data Engineer", cleaned_text)
        self.assertIn("PySpark", cleaned_text)
        self.assertIn("HIPAA", cleaned_text)

    def test_extract_jd_entities(self):
        parser = OnDeviceParser()
        cleaned_text = parser.clean_html_dom(self.sample_raw_html)
        entities = parser.extract_jd_entities(cleaned_text)

        self.assertIn("Data Engineer", entities["job_title"])
        self.assertEqual(entities["years_required"], 5)
        self.assertIn(entities["remote_status"], ["Remote", "Hybrid"])
        
        expected_skills = {"pyspark", "sql", "snowflake", "aws", "apache airflow", "hipaa", "data governance"}
        extracted_set = set(entities["skills"])
        self.assertTrue(expected_skills.issubset(extracted_set))

    def test_prune_cv_for_jd(self):
        parser = OnDeviceParser()
        cleaned_text = parser.clean_html_dom(self.sample_raw_html)
        
        result = parser.prune_cv_for_jd(cleaned_text, self.sample_cv_bullets, top_n=3)

        top_bullets_str = " ".join(result["pruned_bullets"])
        self.assertTrue("PySpark" in top_bullets_str or "HIPAA" in top_bullets_str or "Snowflake" in top_bullets_str)
        self.assertFalse(any("Class 10th score" in b for b in result["pruned_bullets"]))
        self.assertGreater(result["token_reduction_pct"], 40.0)

    def test_benchmark_parsing_token_savings(self):
        full_ats_html = self.sample_raw_html + "\n" + """
        <div class="footer-seo">
            <p>Job ID: 9948123 | Department: Technology Consulting | Legal Notice: ZS Associates is an Equal Opportunity Employer. All qualified applicants will receive consideration for employment without regard to race, color, religion, sex, sexual orientation, gender identity, national origin, disability status, protected veteran status, or any other characteristic protected by law.</p>
            <script>var tracking_blob = """ + json.dumps({"analytics": "x" * 1000}) + """;</script>
        </div>
        """
        full_cv_text = "\n".join(self.sample_cv_bullets)
        benchmark = benchmark_parsing(full_ats_html, full_cv_text)

        self.assertGreater(benchmark["before_raw_tokens"], 0)
        self.assertLess(benchmark["after_optimized_tokens"], benchmark["before_raw_tokens"])
        self.assertGreater(benchmark["token_savings_pct"], 60.0)
        self.assertEqual(benchmark["extracted_entities"]["years_required"], 5)


if __name__ == "__main__":
    unittest.main()
