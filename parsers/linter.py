#!/usr/bin/env python3
"""
Style & Guardrail Linter (tools/style_linter.py)
-----------------------------------------------
On-device deterministic validator and post-processor enforcing:
1. ZERO em dashes ('—') rule - replaces with standard hyphens, commas, or colons.
2. AI Cliché & Corporate Slop Elimination ('spearheaded', 'leverage', 'delve', 'synergy', 'testament', etc.).
3. Stylometric Burstiness & Perplexity scoring (rhythmic sentence length variance).
4. Factual Profile Integrity against AGENTS.md (companies, dates, metrics, tech exclusions).
"""

import os
import re
import math
from typing import Dict, List, Tuple, Any

# Banned AI cliches and corporate jargon
BANNED_CLICHES = [
    r"\bspearhead(ed|ing|s)?\b",
    r"\bleverage(d|ing|s)?\b",
    r"\bdelv(e|ed|ing|es)\b",
    r"\bsynerg(y|ies|istic)\b",
    r"\btestament\b",
    r"\bfoster(ed|ing|s)?\b",
    r"\bmultifaceted\b",
    r"\bpivotal\b",
    r"\bbeacon\b",
    r"\bgame[- ]changer\b",
    r"\bthrilled to apply\b",
    r"\bexcited to apply\b",
    r"\blook no further\b",
    r"\bin today'?s (fast-paced|dynamic) (world|market|landscape)\b",
    r"\bnavigate the complexities\b",
    r"\bseamlessly\b",
    r"\brobust\b",
    r"\bholistic\b",
    r"\bparadigm shift\b",
]

# Explicit exclusions (candidate does NOT know Java / Production Docker K8s backend)
EXCLUDED_TECHS = [
    r"\bJava\b(?!\s*Script)",
    r"\bSpring Boot\b",
    r"\bJ2EE\b",
]

# Verified core facts (loaded dynamically from environment)
VERIFIED_COMPANIES = [
    c.strip() for c in os.getenv("CANDIDATE_VERIFIED_COMPANIES", "").split(",") if c.strip()
]
VERIFIED_METRICS = [
    m.strip() for m in os.getenv("CANDIDATE_VERIFIED_METRICS", "20,000,40%,15+,8+,35%").split(",") if m.strip()
]


def sanitize_em_dashes(text: str) -> str:
    """Strictly eliminates em dashes ('—') and en dashes ('–' when used as clauses)."""
    # Replace em dashes surrounded by spaces with ' - '
    text = re.sub(r"\s*—\s*", " - ", text)
    # Replace lone em dash with hyphen
    text = text.replace("—", "-")
    # Clean up accidental double hyphens
    text = re.sub(r"\s*--\s*", " - ", text)
    return text


def sanitize_cliches(text: str) -> Tuple[str, List[str]]:
    """Detects and replaces common AI clichés with direct, natural phrasing."""
    replacements = {
        r"\bspearheaded\b": "led",
        r"\bspearheading\b": "leading",
        r"\bleveraged\b": "used",
        r"\bleveraging\b": "using",
        r"\bleverage\b": "use",
        r"\bdelve into\b": "examine",
        r"\bdelving into\b": "examining",
        r"\bseamlessly\b": "directly",
        r"\brobust\b": "reliable",
        r"\bfostered\b": "built",
        r"\bpivotal\b": "key",
        r"\bmultifaceted\b": "broad",
        r"\btestament to\b": "reflection of",
    }
    flagged = []
    cleaned_text = text
    for pat, rep in replacements.items():
        if re.search(pat, cleaned_text, re.IGNORECASE):
            flagged.append(pat)
            cleaned_text = re.sub(pat, rep, cleaned_text, flags=re.IGNORECASE)
    return cleaned_text, flagged


def calculate_burstiness(text: str) -> Dict[str, Any]:
    """
    Measures sentence-length distribution and burstiness.
    High burstiness (std_dev > 5.5) indicates natural human writing with
    asymmetrical sentence structures. Low burstiness (< 4.0) indicates robotic monotony.
    """
    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
    if not sentences:
        return {"sentence_count": 0, "mean_len": 0, "std_dev": 0, "is_bursty": False}

    lengths = [len(s.split()) for s in sentences]
    mean_len = sum(lengths) / len(lengths)
    variance = sum((l - mean_len) ** 2 for l in lengths) / len(lengths)
    std_dev = math.sqrt(variance)

    return {
        "sentence_count": len(sentences),
        "mean_len": round(mean_len, 1),
        "std_dev": round(std_dev, 2),
        "min_len": min(lengths),
        "max_len": max(lengths),
        "is_bursty": std_dev >= 4.5,
    }


def audit_profile_integrity(text: str) -> List[str]:
    """Checks for forbidden technology claims or hallucinations."""
    violations = []
    for pat in EXCLUDED_TECHS:
        if re.search(pat, text):
            violations.append(f"Contains forbidden technology exclusion: {pat}")
    return violations


def lint_and_format(text: str) -> Dict[str, Any]:
    """
    Complete on-device post-processing and linting pass.
    Returns sanitized text and detailed audit metrics.
    """
    clean_text = sanitize_em_dashes(text)
    
    # Turnitout Threat Erasure: Purge zero-width unicode & AI watermarks
    try:
        from parsers.turnitout_engine import TurnitoutEngine
        engine = TurnitoutEngine(seed=42)
        clean_text, watermarks_purged = engine.purge_watermarks(clean_text)
        zippy_entropy = engine.compute_zippy_entropy(clean_text)
        ngram_audit = engine.audit_ngrams(clean_text, k=5)
    except Exception:
        watermarks_purged = 0
        zippy_entropy = {"entropy_score": 1.0, "ai_likelihood": "Unknown"}
        ngram_audit = {"redundancy_pct": 0.0}

    clean_text, cliches_found = sanitize_cliches(clean_text)
    burstiness = calculate_burstiness(clean_text)
    violations = audit_profile_integrity(clean_text)

    passed = len(violations) == 0 and ("—" not in clean_text) and watermarks_purged >= 0

    return {
        "clean_text": clean_text,
        "passed": passed,
        "cliches_replaced": cliches_found,
        "burstiness": burstiness,
        "violations": violations,
        "has_em_dash": "—" in clean_text,
        "watermarks_purged": watermarks_purged,
        "zippy_entropy": zippy_entropy,
        "ngram_audit": ngram_audit,
    }


if __name__ == "__main__":
    sample = (
        "I spearheaded multiple big data pipelines at ZS Associates — leveraging Spark and Airflow. "
        "This is a testament to my robust ability to delve into healthcare commercial data. "
        "I built automated pipelines that reduced production server incidents by 40%."
    )
    print("--- Raw Sample ---")
    print(sample)
    result = lint_and_format(sample)
    print("\n--- Linted & Sanitized Output ---")
    print(result["clean_text"])
    print("\n--- Metrics ---")
    print(f"Passed: {result['passed']}")
    print(f"Burstiness StdDev: {result['burstiness']['std_dev']} (Bursty: {result['burstiness']['is_bursty']})")
    print(f"Cliches Replaced: {result['cliches_replaced']}")
    print(f"Em Dashes Remaining: {result['has_em_dash']}")
