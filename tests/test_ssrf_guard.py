#!/usr/bin/env python3
"""Tests for utils/ssrf_guard.py (Vibe-Check Category 6 Defense)."""

import unittest
from utils.ssrf_guard import validate_url


class SSRFGuardTests(unittest.TestCase):
    def test_allows_public_https_url(self):
        ok, _ = validate_url("https://careers.google.com/jobs/results/")
        self.assertTrue(ok)

    def test_blocks_cloud_metadata_ip(self):
        ok, reason = validate_url("http://169.254.169.254/latest/meta-data/")
        self.assertFalse(ok)
        self.assertIn("SSRF guard", reason)

    def test_blocks_localhost_name(self):
        ok, reason = validate_url("http://localhost:8000/internal")
        self.assertFalse(ok)
        self.assertIn("SSRF guard", reason)

    def test_blocks_loopback_ip(self):
        ok, reason = validate_url("http://127.0.0.1:9222/json")
        self.assertFalse(ok)
        self.assertIn("loopback", reason)

    def test_blocks_private_subnet_10(self):
        ok, reason = validate_url("http://10.0.0.5/api")
        self.assertFalse(ok)
        self.assertIn("private subnet", reason)

    def test_blocks_non_http_schemes(self):
        ok, reason = validate_url("ftp://example.com/file")
        self.assertFalse(ok)
        self.assertIn("forbidden", reason)

        ok, reason = validate_url("file:///etc/passwd")
        self.assertFalse(ok)
        self.assertIn("forbidden", reason)


if __name__ == "__main__":
    unittest.main()
