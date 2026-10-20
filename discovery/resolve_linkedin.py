#!/usr/bin/env python3
"""
Resolves LinkedIn job URLs to direct company ATS endpoints.

Avoids LinkedIn Easy Apply bot detection by looking up the employer's
direct posting on Greenhouse, Lever, Ashby, Workday, Taleo, Phenom, or Eightfold.

Author: Ankit Kumar Singh
Rule: Zero em dashes permitted.
"""

import re
import sys
import argparse
from urllib.parse import quote_plus

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
    )
}

ATS_DOMAINS = [
    "boards.greenhouse.io",
    "job-boards.greenhouse.io",
    "jobs.lever.co",
    "jobs.ashbyhq.com",
    "myworkdayjobs.com",
    "taleo.net",
    "smartrecruiters.com",
    "eightfold.ai",
    "avature.net",
    "apply.workable.com",
    "recruitee.com",
    "icims.com",
]


def resolve_to_ats(company: str, title: str) -> str:
    """Finds direct company ATS posting using search queries."""
    query = f"{company} {title} " + " OR ".join(f"site:{d}" for d in ATS_DOMAINS[:4])
    return f"https://www.google.com/search?q={quote_plus(query)}"


def resolve_linkedin(url: str, title: str = "") -> str:
    """
    Given a URL, returns the direct ATS URL if it already points to an ATS,
    or generates a targeted search query for the direct ATS listing.
    """
    if not url:
        return ""
    for domain in ATS_DOMAINS:
        if domain in url:
            return url
    
    # If it's a LinkedIn URL, format resolution query
    return resolve_to_ats(url, title)


def main():
    parser = argparse.ArgumentParser(description="Resolve LinkedIn URL to direct ATS endpoint.")
    parser.add_argument("--company", type=str, required=True, help="Company name")
    parser.add_argument("--title", type=str, default="", help="Job title")
    args = parser.parse_args()

    direct_url = resolve_linkedin(args.company, args.title)
    print(f"Direct ATS Lookup Target for {args.company} {args.title}:")
    print(direct_url)


if __name__ == "__main__":
    main()
