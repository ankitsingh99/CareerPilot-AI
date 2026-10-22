#!/usr/bin/env python3
"""
ATS Vendor Classifier
=====================
Zero-token canonical ATS platform classifier.
Derives standard ATS vendor labels from job posting URLs or hostnames.

Adapted from career-ops ats-vendor.mjs into CareerPilot AI Python 3.15+ architecture.
"""

from urllib.parse import urlparse
import re
from typing import Optional, List


def _host_is(host: str, suffix: str) -> bool:
    return host == suffix or host.endswith(f".{suffix}")


ATS_VENDORS = [
    ("greenhouse", lambda h: _host_is(h, "greenhouse.io")),
    ("lever", lambda h: _host_is(h, "lever.co")),
    ("ashby", lambda h: _host_is(h, "ashbyhq.com")),
    ("workday", lambda h: _host_is(h, "myworkdayjobs.com") or _host_is(h, "myworkdaysite.com")),
    ("icims", lambda h: _host_is(h, "icims.com")),
    ("successfactors", lambda h: _host_is(h, "successfactors.com") or _host_is(h, "successfactors.eu") or _host_is(h, "jobs2web.com") or _host_is(h, "sapsf.com") or _host_is(h, "sapsf.eu") or _host_is(h, "join.cnh.com")),
    ("dayforce", lambda h: _host_is(h, "dayforcehcm.com")),
    ("ultipro", lambda h: _host_is(h, "ultipro.com") or _host_is(h, "ultipro.ca")),
    ("taleo", lambda h: _host_is(h, "taleo.net")),
    ("bamboohr", lambda h: _host_is(h, "bamboohr.com")),
    ("smartrecruiters", lambda h: _host_is(h, "smartrecruiters.com")),
    ("csod", lambda h: _host_is(h, "csod.com")),
    ("oraclecloud", lambda h: bool(re.search(r"(^|\.)oraclecloud(?:\d+)?\.com$", h))),
    ("rippling", lambda h: _host_is(h, "ats.rippling.com") or _host_is(h, "rippling.com")),
    ("pinpoint", lambda h: _host_is(h, "pinpointhq.com")),
    ("linkedin", lambda h: _host_is(h, "linkedin.com")),
]

KNOWN_ATS_NAMES = [name for name, _ in ATS_VENDORS]


def classify_ats_vendor(raw_url: str) -> Optional[str]:
    """
    Returns canonical ATS vendor id (e.g. 'workday', 'greenhouse', 'ashby'),
    or the lower-cased hostname for proprietary/unlisted career portals,
    or None if invalid URL.
    """
    if not isinstance(raw_url, str) or not raw_url.strip():
        return None
    
    url = raw_url.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        url = "https://" + url

    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if not host:
            return None
        
        for vendor_id, test_fn in ATS_VENDORS:
            if test_fn(host):
                return vendor_id
        
        return host
    except Exception:
        return None


if __name__ == "__main__":
    sample_urls = [
        "https://boards.greenhouse.io/stripe/jobs/12345",
        "https://jobs.lever.co/anthropic/67890",
        "https://jobs.ashbyhq.com/retool/abcde",
        "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite",
        "https://careers.smartrecruiters.com/AcmeCorp/111",
        "https://custom-portal.example.org/careers/job1",
    ]
    for u in sample_urls:
        print(f"{u} => {classify_ats_vendor(u)}")
