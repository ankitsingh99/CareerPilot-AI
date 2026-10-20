"""Filtering and scoring criteria for candidate profile matches."""
import re
from typing import Dict, Any, Tuple

# Target role patterns (Data Engineering, Analytics Engineering, AI Agents, Solutions, Analytics)
INCLUDE_ROLE_PATTERNS = [
    r"\bdata\s+engineer\b",
    r"\banalytics\s+engineer\b",
    r"\bdata\s+governance\b",
    r"\bdata\s+observability\b",
    r"\bdata\s+quality\b",
    r"\bdata\s+reliability\b",
    r"\bai\s+(systems|agent|platform|automation|engineer)\b",
    r"\bapplied\s+ai\b",
    r"\bllm\b",
    r"\bbusiness\s+technology\b",
    r"\bsolutions?\s+architect\b",
    r"\bsolutions?\s+analyst\b",
    r"\btechnical\s+consultant\b",
    r"\btechnical\s+product\s+manager\b",
    r"\bbig\s+data\b",
    r"\bdata\s+analyst\b",
    r"\bbusiness\s+intelligence\b",
    r"\bbi\s+(engineer|lead|developer|analyst)\b",
    r"\bdata\s+architect\b",
    r"\banalytics\s+consultant\b",
    r"\banalytics\s+lead\b",
    r"\bhealthcare\s+analytics\b",
    r"\bcommercial\s+analytics\b",
    r"\bbusiness\s+analyst\b",
    r"\bproduct\s+analyst\b",
    r"\bgrowth\s+analyst\b",
    r"\bmarketing\s+analyst\b",
    r"\bdata\s+scientist\b",
    r"\bdata\s+science\b",
    r"\bforward\s+deployed\b",
]

# Roles to exclude
EXCLUDE_ROLE_PATTERNS = [
    r"\bintern\b",
    r"\binternship\b",
    r"\bco-op\b",
    r"\bfrontend\s+developer\b",
    r"\bios\s+developer\b",
    r"\bandroid\s+developer\b",
    r"\bgraphic\s+designer\b",
    r"\bcontent\s+writer\b",
    r"\bhr\s+(specialist|generalist|manager)\b",
    r"\brecruiter\b",
    r"\btalent\s+acquisition\b",
    r"\baccount\s+executive\b",
    r"\bsales\s+executive\b",
    r"\blegal\s+counsel\b",
    r"\bhardware\s+engineer\b",
    r"\bfirmware\b",
    r"\bjava\s+(developer|engineer|backend)\b",
]

# Locations accepted (Remote, Delhi NCR, Bangalore, Hyderabad, Pune, Mumbai, India)
LOCATION_PATTERNS = [
    r"\bremote\b",
    r"\banywhere\b",
    r"\bwork\s+from\s+home\b",
    r"\bindia\b",
    r"\bdelhi\b",
    r"\bnoida\b",
    r"\bgurgaon\b",
    r"\bgurugram\b",
    r"\bncr\b",
    r"\bbangalore\b",
    r"\bbengaluru\b",
    r"\bhyderabad\b",
    r"\bpune\b",
    r"\bmumbai\b",
    r"\bchennai\b",
]


def matches_role(title: str) -> bool:
    if not title:
        return False
    title_lower = title.lower()
    for pat in EXCLUDE_ROLE_PATTERNS:
        if re.search(pat, title_lower, re.I):
            return False
    for pat in INCLUDE_ROLE_PATTERNS:
        if re.search(pat, title_lower, re.I):
            return True
    return False


def matches_location(location: str, workplace_type: str = "", jd_text: str = "") -> Tuple[bool, str]:
    loc_text = f"{location} {workplace_type}".lower()
    
    if "remote" in loc_text or "remote" in workplace_type.lower():
        if "us only" in loc_text or "us only" in jd_text[:2000].lower() or "united states only" in loc_text:
            return (False, "Remote (US Only)")
        return (True, "100% Remote")
    
    if any(re.search(pat, loc_text, re.I) for pat in LOCATION_PATTERNS):
        if "delhi" in loc_text or "noida" in loc_text or "gurgaon" in loc_text or "gurugram" in loc_text:
            return (True, "Delhi NCR (Preferred)")
        if "bangalore" in loc_text or "bengaluru" in loc_text:
            return (True, "Bangalore")
        if "hyderabad" in loc_text:
            return (True, "Hyderabad")
        if "pune" in loc_text or "mumbai" in loc_text:
            return (True, "Pune / Mumbai")
        return (True, "India (General)")
    
    return (False, "Non-matching location")


try:
    from intelligence.rag import calculate_semantic_fit
except ImportError:
    try:
        from local_rag import calculate_semantic_fit
    except ImportError:
        calculate_semantic_fit = None


def evaluate_posting(job: Dict[str, Any]) -> Dict[str, Any]:
    title = job.get("title", "")
    location = job.get("location", "")
    workplace_type = job.get("workplace_type", "")
    jd = job.get("jd_text", "")
    
    role_ok = matches_role(title)
    loc_ok, loc_tier = matches_location(location, workplace_type, jd)
    
    fit_score = 0.85
    if jd and calculate_semantic_fit:
        try:
            fit_score = calculate_semantic_fit(f"{title}\n{jd[:1500]}")
        except Exception:
            fit_score = 0.85

    passed = role_ok and loc_ok
    return {
        "passed": passed,
        "role_match": role_ok,
        "location_match": loc_ok,
        "location_tier": loc_tier,
        "semantic_fit": fit_score,
    }


def filter_job(job: Dict[str, Any]) -> bool:
    """Convenience boolean filter checking both role and location match."""
    return evaluate_posting(job)["passed"]


