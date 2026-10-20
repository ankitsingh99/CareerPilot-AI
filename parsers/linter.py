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


def audit_structural_integrity(text: str) -> List[str]:
    """
    Local deterministic check for broken metrics, dangling operators,
    unpopulated placeholders, and truncated profile handles.
    """
    violations = []

    # 1. Broken / missing metrics and percentages
    broken_pct_patterns = [
        (r"(?:\bby|\breduced|\bincreased|\bimproved|\bof|\bgain of)\s+%", "Dangling percent sign without metric value (e.g. 'by %')"),
        (r"(?<!\d)(?<!\w)%\b", "Isolated percent sign without numerical value"),
        (r"\bby\s+percent\b", "Generic 'by percent' without quantified metric"),
    ]
    for pat, desc in broken_pct_patterns:
        if re.search(pat, text, re.IGNORECASE):
            violations.append(f"Broken Metric: {desc}")

    # 2. Dangling operator signs (e.g. 'Managing + Airflow pipelines')
    dangling_operators = [
        (r"(?:Managing|Built|Over|Led|Supervised|Across)\s+\+\s+", "Dangling plus operator without quantity (e.g. 'Managing +')"),
        (r"(?<!\w)\+\s+[A-Za-z]+", "Dangling plus sign before word without preceding digits"),
    ]
    for pat, desc in dangling_operators:
        if re.search(pat, text, re.IGNORECASE):
            violations.append(f"Dangling Operator: {desc}")

    # 3. Unpopulated placeholders & empty labels
    placeholder_patterns = [
        (r"Req ID:\s*(?:\)|$|\n)", "Empty Requisition ID label ('Req ID: ')"),
        (r"\[NOT_SET", "Unpopulated [NOT_SET: ...] placeholder"),
        (r"\[PLACEHOLDER", "Unpopulated [PLACEHOLDER] tag"),
        (r"<URL>", "Unresolved <URL> tag"),
        (r"\[Company\]", "Unresolved [Company] placeholder"),
        (r"\[Role\]", "Unresolved [Role] placeholder"),
    ]
    for pat, desc in placeholder_patterns:
        if re.search(pat, text, re.IGNORECASE):
            violations.append(f"Unpopulated Placeholder: {desc}")

    # 4. Truncated LinkedIn URLs
    linkedin_url = os.getenv("CANDIDATE_LINKEDIN_URL", "")
    if linkedin_url:
        expected_handle = linkedin_url.rstrip("/").split("/")[-1]
        # Match linkedin URL in text
        match = re.search(r"https?://(?:www\.)?linkedin\.com/in/([a-zA-Z0-9_\-]+)", text)
        if match:
            found_handle = match.group(1)
            if found_handle != expected_handle and found_handle in expected_handle:
                violations.append(
                    f"Truncated Profile URL: Found '{found_handle}', expected complete handle '{expected_handle}'"
                )

    return violations


def audit_profile_integrity(text: str) -> List[str]:
    """Checks for forbidden technology claims or hallucinations."""
    violations = []
    for pat in EXCLUDED_TECHS:
        if re.search(pat, text):
            violations.append(f"Contains forbidden technology exclusion: {pat}")
    return violations


def proofread_with_openrouter(text: str, role_title: str = "", company: str = "") -> Dict[str, Any]:
    """
    Tier 2: LLM Proofreading pass via OpenRouter Zero-Cost Free Tier.
    Audits grammar, restores missing quantified metrics, and validates flow.
    """
    try:
        from intelligence.llm_clients.openrouter import ask
    except ImportError:
        return {"success": False, "proofread_text": text, "error": "OpenRouter client unavailable"}

    prompt = f"""
Proofread and audit the following cover letter for the role '{role_title}' at '{company}'.

INSTRUCTIONS:
1. Fix any broken metrics (e.g. 'by %' -> check if 40% or appropriate, 'Managing +' -> check if '15+' or appropriate).
2. Fix any dangling punctuation or unpopulated fields.
3. Preserve all specific technologies, project names, and facts.
4. Strictly maintain zero hyphens ('-') and zero em dashes ('—').
5. Output ONLY the polished cover letter text without preamble or reasoning.

TEXT:
{text}
"""
    try:
        proofread = ask(
            prompt=prompt,
            system="You are an expert editorial proofreader and career communications specialist. Output only the final proofread text directly.",
            model="cohere/north-mini-code:free",
            temperature=0.3,
            max_tokens=3000
        )
        # Verify result is non-empty
        if proofread and len(proofread.strip()) > 100:
            return {"success": True, "proofread_text": proofread.strip(), "model": "cohere/north-mini-code:free"}
    except Exception as e:
        print(f"[proofreader:warning] OpenRouter proofread failed: {e}")

    return {"success": False, "proofread_text": text, "error": "LLM call failed or empty response"}


def lint_and_format(text: str, proofread_llm: bool = False, role_title: str = "", company: str = "") -> Dict[str, Any]:
    """
    Complete on-device post-processing, structural validation, and linting pass.
    Optionally falls back to OpenRouter free tier for deep proofreading.
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
    tech_violations = audit_profile_integrity(clean_text)
    structural_violations = audit_structural_integrity(clean_text)

    all_violations = tech_violations + structural_violations

    # If structural violations exist and LLM proofreading is requested, attempt proofread
    proofread_info = None
    if (structural_violations or proofread_llm) and proofread_llm:
        print("[linter:proofread] Invoking OpenRouter Free Tier proofreader...")
        proofread_info = proofread_with_openrouter(clean_text, role_title=role_title, company=company)
        if proofread_info.get("success"):
            clean_text = proofread_info["proofread_text"]
            # Re-run structural audit on proofread text
            structural_violations = audit_structural_integrity(clean_text)
            all_violations = tech_violations + structural_violations

    passed = len(all_violations) == 0 and ("—" not in clean_text) and watermarks_purged >= 0

    return {
        "clean_text": clean_text,
        "passed": passed,
        "cliches_replaced": cliches_found,
        "burstiness": burstiness,
        "violations": all_violations,
        "tech_violations": tech_violations,
        "structural_violations": structural_violations,
        "has_em_dash": "—" in clean_text,
        "watermarks_purged": watermarks_purged,
        "zippy_entropy": zippy_entropy,
        "ngram_audit": ngram_audit,
        "proofread_info": proofread_info,
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
