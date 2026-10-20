"""ATS Discovery package for fast, direct JSON API job board polling."""
from .boards import POLLERS, poll_greenhouse, poll_lever, poll_ashby, poll_smartrecruiters, extract_salary
from .normalize import detect_ats, canonical_url, html_to_text
from .filters import evaluate_posting, matches_role, matches_location

__all__ = [
    "POLLERS",
    "poll_greenhouse",
    "poll_lever",
    "poll_ashby",
    "poll_smartrecruiters",
    "extract_salary",
    "detect_ats",
    "canonical_url",
    "html_to_text",
    "evaluate_posting",
    "matches_role",
    "matches_location",
]
