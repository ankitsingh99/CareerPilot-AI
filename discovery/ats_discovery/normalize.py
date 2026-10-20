"""URL canonicalization, ATS detection, and text cleaning for job feeds."""
import re
import html as html_mod
from urllib.parse import urlparse, urlunparse

ATS_PATTERNS = [
    ("greenhouse", r"(boards|job-boards)\.greenhouse\.io/(?:embed/job_app\?[^ ]*for=)?([a-z0-9-_]+)"),
    ("greenhouse", r"boards-api\.greenhouse\.io/v1/boards/([a-z0-9-_]+)"),
    ("lever", r"jobs\.lever\.co/([a-zA-Z0-9-_]+)"),
    ("ashby", r"jobs\.ashbyhq\.com/([a-zA-Z0-9-_.%]+)"),
    ("smartrecruiters", r"jobs\.smartrecruiters\.com/([a-zA-Z0-9-_]+)"),
    ("workday", r"([a-z0-9-]+)\.wd\d+\.myworkdayjobs\.com"),
    ("icims", r"([a-z0-9-]+)\.icims\.com"),
    ("workable", r"apply\.workable\.com/([a-zA-Z0-9-_]+)"),
    ("recruitee", r"([a-z0-9-]+)\.recruitee\.com"),
    ("bamboohr", r"([a-z0-9-]+)\.bamboohr\.com"),
    ("jobvite", r"jobs\.jobvite\.com/([a-zA-Z0-9-_]+)"),
    ("taleo", r"([a-z0-9-]+)\.taleo\.net"),
    ("phenom", r"careers\.([a-z0-9-]+)\.com"),
    ("eightfold", r"([a-z0-9-]+)\.eightfold\.ai"),
    ("avature", r"([a-z0-9-]+)\.avature\.net"),
    ("linkedin", r"linkedin\.com/jobs"),
]


def detect_ats(url: str):
    """Returns (ats, slug_or_None)."""
    if not url:
        return ("other", None)
    for ats, pat in ATS_PATTERNS:
        m = re.search(pat, url, re.I)
        if m:
            slug = m.group(1).lower() if m.groups() else None
            return (ats, slug)
    return ("other", None)


def canonical_url(url: str) -> str:
    """Stable identity for a posting: scheme+host+path, no query/fragment."""
    if not url:
        return url
    p = urlparse(url.strip())
    host = p.netloc.lower().replace("www.", "")
    path = re.sub(r"/+$", "", p.path)
    if "linkedin.com" in host:
        jid = re.search(r"(?:currentJobId=|/jobs/view/)(\d+)", url)
        if jid:
            return f"https://www.linkedin.com/jobs/view/{jid.group(1)}/"
    if "indeed.com" in host:
        jk = re.search(r"[?&]jk=([a-f0-9]+)", url)
        if jk:
            return f"https://www.indeed.com/viewjob?jk={jk.group(1)}"
    return urlunparse(("https", host, path, "", "", ""))


TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"[ \t\r\f\v]+")


def html_to_text(s: str, limit: int = 20000) -> str:
    if not s:
        return ""
    s = html_mod.unescape(s)
    s = re.sub(r"<(br|/p|/div|/li|/h\d)[^>]*>", "\n", s, flags=re.I)
    s = TAG_RE.sub(" ", s)
    s = WS_RE.sub(" ", s)
    s = re.sub(r"\n\s+", "\n", s).strip()
    return s[:limit]
