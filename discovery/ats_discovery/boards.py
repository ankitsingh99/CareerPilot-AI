"""Pollers for public ATS job-board JSON APIs."""
import re
import time
try:
    import requests
except ImportError:
    requests = None
from typing import Iterator, Dict, Any, Tuple, Optional

from .normalize import html_to_text

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
    )
}

SALARY_USD_RE = re.compile(
    r"\$\s?(\d{2,3})[,.]?(\d{3})(?:\s*(?:-|to)\s*\$?\s?(\d{2,3})[,.]?(\d{3}))?"
)

SALARY_INR_RE = re.compile(
    r"(?:₹|rs\.?|inr)?\s*(\d{1,3})(?:[,.](\d{2}))?(?:[,.](\d{3}))(?:\s*(?:-|to)\s*(?:₹|rs\.?|inr)?\s*(\d{1,3})(?:[,.](\d{2}))?(?:[,.](\d{3})))?",
    re.I,
)

SALARY_LPA_RE = re.compile(
    r"(\d{1,2}(?:\.\d{1,2})?)\s*(?:-|to)\s*(\d{1,2}(?:\.\d{1,2})?)\s*(?:lpa|lakhs?|lac?s?)",
    re.I,
)

SALARY_LPA_SINGLE_RE = re.compile(
    r"(\d{1,2}(?:\.\d{1,2})?)\s*(?:lpa|lakhs?|lac?s?)",
    re.I,
)


def extract_salary(text: str) -> Tuple[Optional[int], Optional[int]]:
    """Extract (min, max) annual USD or INR from text."""
    if not text:
        return (None, None)
    best = (None, None)
    text_slice = text[:12000]

    # Check USD
    for m in SALARY_USD_RE.finditer(text_slice):
        lo = int(m.group(1) + m.group(2))
        hi = int(m.group(3) + m.group(4)) if m.group(3) else lo
        if 40000 <= lo <= 900000:
            if best[1] is None or hi > best[1]:
                best = (lo, hi)

    # Check INR full numbers
    for m in SALARY_INR_RE.finditer(text_slice):
        part1, part2, part3 = m.group(1), m.group(2) or "", m.group(3)
        lo = int(part1 + part2 + part3)
        if m.group(4):
            part4, part5, part6 = m.group(4), m.group(5) or "", m.group(6)
            hi = int(part4 + part5 + part6)
        else:
            hi = lo
        if 100000 <= lo <= 100000000:
            if best[1] is None or hi > best[1]:
                best = (lo, hi)

    # Check INR LPA range (e.g. 18-25 LPA)
    for m in SALARY_LPA_RE.finditer(text_slice):
        lo = int(float(m.group(1)) * 100000)
        hi = int(float(m.group(2)) * 100000)
        if 100000 <= lo <= 100000000:
            if best[1] is None or hi > best[1]:
                best = (lo, hi)

    # Check INR LPA single (e.g. 18 LPA)
    for m in SALARY_LPA_SINGLE_RE.finditer(text_slice):
        lo = int(float(m.group(1)) * 100000)
        hi = lo
        if 100000 <= lo <= 100000000:
            if best[1] is None or hi > best[1]:
                best = (lo, hi)

    return best


def _get(url: str, timeout: int = 15, params: Optional[Dict[str, Any]] = None, **kw) -> Any:
    if params:
        import urllib.parse
        url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    
    if requests is not None:
        r = requests.get(url, headers=UA, timeout=timeout, **kw)
        r.raise_for_status()
        return r
    else:
        import urllib.request
        import json as _json
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read().decode("utf-8")
            class _MockResponse:
                def __init__(self, text):
                    self.text = text
                def json(self):
                    return _json.loads(self.text)
            return _MockResponse(data)


def poll_greenhouse(slug: str, timeout: int = 15) -> Iterator[Dict[str, Any]]:
    r = _get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs", timeout, params={"content": "true"})
    data = r.json()
    for j in data.get("jobs", []):
        jd = html_to_text(j.get("content", ""))
        lo, hi = extract_salary(jd)
        yield {
            "company": j.get("company_name") or slug,
            "company_slug": slug,
            "title": (j.get("title") or "").strip(),
            "url": j.get("absolute_url"),
            "apply_url": j.get("absolute_url"),
            "ats": "greenhouse",
            "location": (j.get("location") or {}).get("name", ""),
            "workplace_type": "",
            "salary_min": lo,
            "salary_max": hi,
            "posted_at": j.get("first_published") or j.get("updated_at"),
            "jd_text": jd,
            "source": "boards:greenhouse",
        }


def poll_lever(slug: str, timeout: int = 15) -> Iterator[Dict[str, Any]]:
    r = _get(f"https://api.lever.co/v0/postings/{slug}", timeout, params={"mode": "json"})
    for j in r.json():
        cats = j.get("categories") or {}
        jd = j.get("descriptionPlain") or html_to_text(j.get("description", ""))
        for lst in j.get("lists") or []:
            jd += "\n" + html_to_text(lst.get("content", ""), 4000)
        sal = j.get("salaryRange") or {}
        lo, hi = sal.get("min"), sal.get("max")
        if not lo:
            lo, hi = extract_salary(jd)
        posted = j.get("createdAt")
        if isinstance(posted, (int, float)):
            posted = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(posted / 1000))
        yield {
            "company": slug,
            "company_slug": slug,
            "title": (j.get("text") or "").strip(),
            "url": j.get("hostedUrl"),
            "apply_url": j.get("applyUrl") or j.get("hostedUrl"),
            "ats": "lever",
            "location": cats.get("location", "") or j.get("country", ""),
            "workplace_type": (j.get("workplaceType") or "").lower(),
            "salary_min": lo,
            "salary_max": hi,
            "posted_at": posted,
            "jd_text": jd[:20000],
            "source": "boards:lever",
        }


def poll_ashby(slug: str, timeout: int = 15) -> Iterator[Dict[str, Any]]:
    r = _get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}", timeout, params={"includeCompensation": "true"})
    for j in r.json().get("jobs", []):
        if j.get("isListed") is False:
            continue
        comp = j.get("compensation") or {}
        summary = comp.get("scrapeableCompensationSalarySummary") or ""
        lo, hi = extract_salary(summary)
        jd = html_to_text(j.get("descriptionHtml", ""))
        if not lo:
            lo, hi = extract_salary(jd)
        yield {
            "company": slug,
            "company_slug": slug,
            "title": (j.get("title") or "").strip(),
            "url": j.get("jobUrl"),
            "apply_url": j.get("applyUrl") or j.get("jobUrl"),
            "ats": "ashby",
            "location": j.get("location", "") or j.get("address", {}).get("addressLocality", ""),
            "workplace_type": (j.get("workplaceType") or "").lower(),
            "salary_min": lo,
            "salary_max": hi,
            "posted_at": j.get("publishedAt"),
            "jd_text": jd[:20000],
            "source": "boards:ashby",
        }


def poll_smartrecruiters(slug: str, timeout: int = 15) -> Iterator[Dict[str, Any]]:
    r = _get(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings", timeout)
    for j in r.json().get("content", []):
        loc = j.get("location", {})
        loc_str = f"{loc.get('city', '')}, {loc.get('region', '')}, {loc.get('country', '')}".strip(", ")
        yield {
            "company": slug,
            "company_slug": slug,
            "title": (j.get("name") or "").strip(),
            "url": f"https://jobs.smartrecruiters.com/{slug}/{j.get('id')}",
            "apply_url": f"https://jobs.smartrecruiters.com/{slug}/{j.get('id')}",
            "ats": "smartrecruiters",
            "location": loc_str,
            "workplace_type": "remote" if j.get("workplaceType") == "REMOTE" else "",
            "salary_min": None,
            "salary_max": None,
            "posted_at": j.get("releasedDate"),
            "jd_text": "",
            "source": "boards:smartrecruiters",
        }


def poll_workable(slug: str, timeout: int = 15) -> Iterator[Dict[str, Any]]:
    """Poll public Workable job board API."""
    url = f"https://apply.workable.com/api/v1/widget/accounts/{slug}"
    r = _get(url, timeout)
    data = r.json()
    jobs = data.get("jobs", [])
    for j in jobs:
        loc = j.get("city") or ""
        country = j.get("country") or ""
        loc_full = f"{loc}, {country}".strip(", ")
        desc = html_to_text(j.get("description", ""))
        lo, hi = extract_salary(desc)
        yield {
            "company": slug,
            "company_slug": slug,
            "title": (j.get("title") or "").strip(),
            "url": j.get("url") or j.get("shortlink"),
            "apply_url": j.get("url") or j.get("shortlink"),
            "ats": "workable",
            "location": loc_full,
            "workplace_type": "remote" if j.get("telecommuting") else "",
            "salary_min": lo,
            "salary_max": hi,
            "posted_at": j.get("published_on"),
            "jd_text": desc[:20000],
            "source": "boards:workable",
        }


POLLERS = {
    "greenhouse": poll_greenhouse,
    "lever": poll_lever,
    "ashby": poll_ashby,
    "smartrecruiters": poll_smartrecruiters,
    "workable": poll_workable,
}
