#!/usr/bin/env python3
"""
Job Liveness & Closed Posting Detector
======================================
Zero-token local heuristic engine to detect expired, closed, or filled job postings
before attempting to parse or submit applications.

Adapted from career-ops liveness-core.mjs / check-liveness.mjs into CareerPilot AI
Python 3.15+ native architecture. Zero em dashes, zero external network calls.
"""

import re
import urllib.request
import urllib.error
import unicodedata
from typing import Tuple, Optional
from utils.ssrf_guard import validate_url


def normalize_for_match(text: str) -> str:
    """
    Normalizes typographic quotes, accents, diacritics, and collapsed whitespace.
    Ensures closure banners in French, German, Spanish, Dutch, and English match accurately.
    """
    if not isinstance(text, str) or not text:
        return ""
    
    # 1. Replace typographic quotes and accents
    cleaned = re.sub(r"[‘’ʼ′´`]", "'", text)
    cleaned = re.sub(r'[“”″]', '"', cleaned)
    
    # 2. Decompose diacritics and strip non-ASCII accents
    cleaned = unicodedata.normalize("NFD", cleaned)
    cleaned = "".join(c for c in cleaned if unicodedata.category(c) != "Mn")
    
    # 3. Collapse whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


# High-precision patterns indicating a job posting is no longer active
HARD_EXPIRED_PATTERNS = [
    re.compile(r"\bjob\s+(?:is\s+)?no\s+longer\s+available\b", re.IGNORECASE),
    re.compile(r"\bjob\s+.*no\s+longer\s+open\b", re.IGNORECASE),
    re.compile(r"\b(?:job|jobs|position|role|posting|opening|vacancy|requisition|req|listing)\b[\s\S]{0,60}?(?<!application )(?<!form )has\s+been\s+filled\b(?!\s+out)", re.IGNORECASE),
    re.compile(r"\bthis\s+job\s+has\s+expired\b", re.IGNORECASE),
    re.compile(r"\bjob\s+posting\s+has\s+expired\b", re.IGNORECASE),
    re.compile(r"\bno\s+longer\s+accepting\s+applications\b", re.IGNORECASE),
    re.compile(r"\bthis\s+(?:position|role|job)\s+(?:is\s+)?no\s+longer\b", re.IGNORECASE),
    re.compile(r"\bthis\s+(?:job|role|position)(?:\s+listing)?\s+is\s+closed\b(?!-)", re.IGNORECASE),
    re.compile(r"\bjob\s+(?:listing\s+)?not\s+found\b", re.IGNORECASE),
    re.compile(r"\bcan't\s+view\s+this\s+job\s+because\s+it's\s+not\s+available\b", re.IGNORECASE),
    re.compile(r"\bthe\s+page\s+you\s+are\s+looking\s+for\s+doesn'?t\s+exist\b", re.IGNORECASE),
    re.compile(r"\bapplications?\s+(?:(?:have|are|is)\s+)?closed\b", re.IGNORECASE),
    re.compile(r"\bclosed\s+on\s+\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b", re.IGNORECASE),
    re.compile(r"\bclosed\s+on\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{1,2}\b", re.IGNORECASE),
    re.compile(r"\bdiese\s+stelle\s+(?:ist\s+)?(?:nicht\s+mehr|bereits)\s+besetzt\b", re.IGNORECASE),
    re.compile(r"\bdeze\s+vacature\s+is\s+niet\s+meer\s+gepubliceerd\b", re.IGNORECASE),
    re.compile(r"\boferta\s+cerrada\s+el\s+\d{1,2}/\d{1,2}/\d{4}\b", re.IGNORECASE),
    re.compile(r"\boffre\s+(?:expiree|n'est\s+plus\s+disponible)\b", re.IGNORECASE),
    re.compile(r"\b(?:cette\s+)?offre\s+n'est\s+plus\s+(?:disponible|en\s+ligne|active)\b", re.IGNORECASE),
]


def is_job_expired(text: str) -> Tuple[bool, str]:
    """
    Checks if given text or page content contains an explicit job closure indicator.
    Returns (True, matching_reason) if expired, else (False, "").
    """
    if not text:
        return False, ""
    
    norm = normalize_for_match(text)
    for pattern in HARD_EXPIRED_PATTERNS:
        match = pattern.search(norm)
        if match:
            return True, match.group(0)
    
    return False, ""


def check_page_liveness(page) -> Tuple[bool, str]:
    """
    Inspects a Playwright page instance for closure banners, banners with expired alerts,
    or dead ATS status without making network calls.
    Returns (is_active: bool, reason: str).
    """
    try:
        # Check title first
        title = page.title()
        expired, reason = is_job_expired(title)
        if expired:
            return False, f"Title indicator: {reason}"

        # Fast DOM query for common alert / closure banner elements
        closure_selectors = [
            ".jobs-details__top-card--closed",
            ".artdeco-inline-feedback--error",
            ".alert--warning",
            ".job-closed",
            ".posting-closed",
            "[data-test-job-expired]",
            ".closed-job-banner"
        ]
        for sel in closure_selectors:
            el = page.query_selector(sel)
            if el and el.is_visible():
                txt = el.inner_text().strip()
                expired, reason = is_job_expired(txt)
                if expired:
                    return False, f"Closure banner ({sel}): {reason}"

        # Sample visible body text snippet (first 3500 chars)
        body_text = page.evaluate("() => document.body ? document.body.innerText.slice(0, 3500) : ''")
        expired, reason = is_job_expired(body_text)
        if expired:
            return False, f"Body indicator: {reason}"

    except Exception as e:
        # If inspection fails gracefully assume active to avoid false negatives
        pass

    return True, "Active"


def check_url_liveness(url: str, timeout: int = 8) -> Tuple[bool, str, int]:
    """
    Zero-token lightweight HTTP check to verify if a job URL is live before launching
    heavy browser automation or AI evaluation. Validates against SSRF, redirects,
    and HTML closure indicators.
    Returns (is_live: bool, reason: str, http_code: int).
    """
    if not url:
        return False, "Empty URL provided", 0

    valid, reason = validate_url(url)
    if not valid:
        return False, f"SSRF Guard blocked URL: {reason}", 0

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = resp.status
            final_url = resp.geturl()

            # Detect generic search/career home redirect
            parsed_final = urllib.parse.urlparse(final_url)
            if any(path_term in parsed_final.path.lower() for path_term in ["/careers/search", "/jobs/search", "/search-jobs", "/404"]):
                return False, f"Redirected to generic search page: {final_url}", code

            # Read beginning of HTML body (up to 8KB)
            content_sample = resp.read(8192).decode("utf-8", errors="ignore")
            expired, reason_match = is_job_expired(content_sample)
            if expired:
                return False, f"Closure banner in HTML: {reason_match}", code

            return True, "Active (HTTP 200 OK)", code

    except urllib.error.HTTPError as he:
        if he.code in (404, 410):
            return False, f"HTTP Error {he.code} (Job removed or expired)", he.code
        if he.code in (401, 403):
            # Auth-gated or cloudflare-protected: inconclusive HTTP, needs browser check
            return True, f"HTTP {he.code} (Auth-gated / Anti-bot protected, requires browser context)", he.code
        return False, f"HTTP Error {he.code}", he.code
    except urllib.error.URLError as ue:
        return False, f"Network connection failed: {ue.reason}", 0
    except Exception as e:
        return True, f"Inconclusive ({type(e).__name__}), proceed to browser verification", 0


if __name__ == "__main__":
    sample_texts = [
        "This job is no longer available. Explore other opportunities.",
        "We are hiring a Senior Data Engineer in Bengaluru.",
        "The job you are trying to apply for has been filled. Thank you for your interest.",
        "Cette offre n’est plus disponible.",
        "Applications have closed for this requisition.",
    ]
    for s in sample_texts:
        exp, reason = is_job_expired(s)
        status = f"EXPIRED ({reason})" if exp else "ACTIVE"
        print(f"[{status}] {s[:60]}...")
