#!/usr/bin/env python3
"""
tools/contact_pitch.py
----------------------
Universal LinkedIn Message & Email Outreach Engine for CareerPilot AI.

Synthesizes JD-aware, CV-grounded, high-burstiness outreach across formats:
1. LinkedIn Referral Request (concise, warm ask + role link + tailored hook)
2. LinkedIn Direct Message (confident peer outreach for posts & recruiters)
3. LinkedIn Connection Request (<=300 chars, free tier safe)
4. Cold / Recruiter Outreach Email (soft or technical, JD-mapped CV bullets)
5. LinkedIn InMail & Polite Post-Application Follow-up (legacy compatible)

Architecture:
- 100% local deterministic execution (zero paid or unprompted LLM calls).
- SSRF-guarded JD fetching via Jina Reader (`https://r.jina.ai/<url>`).
- Mandatory anti-hallucination and style validation via `CVFactChecker` and `parsers.linter`.
- Zero em dashes, zero AI cliches, zero hardcoded PII (loaded dynamically from `.env`).
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.cv_fact_checker import CVFactChecker
from core.qa_semantics_engine import load_candidate_context
from parsers.linter import lint_and_format
from tools.contact_pitch_generator import generate_connection_note
from utils.ssrf_guard import validate_url

# Strictly verified skills mapped to regex triggers in JDs (exclusions honored)
VERIFIED_SKILL_MATCHERS: List[Tuple[str, List[str]]] = [
    ("SQL", [r"\bsql\b", r"\bpostgresql\b", r"\bpostgres\b", r"\bsnowflake\b", r"\btrino\b", r"\boracle\b", r"\bcte", r"window function"]),
    ("Python", [r"\bpython\b"]),
    ("Snowflake", [r"\bsnowflake\b", r"cloud data platform", r"cloud warehouse"]),
    ("PySpark", [r"\bpyspark\b", r"\bspark\b"]),
    ("Apache Airflow", [r"\bairflow\b", r"orchestrat"]),
    ("AWS", [r"\baws\b", r"\bs3\b", r"\bsns\b", r"cloud platform", r"amazon web services"]),
    ("Dimensional Modeling", [r"dimensional", r"star schema", r"slowly changing", r"\bscd\b", r"data model"]),
    ("Data Quality & HIPAA", [r"data quality", r"\bhipaa\b", r"governance", r"masking", r"de-identif"]),
    ("Advanced Excel", [r"\bexcel\b", r"\bvlookup\b", r"\bxlookup\b", r"\bpivot"]),
    ("Tableau / Power BI", [r"power\s*bi", r"\btableau\b", r"\bbi tool\b", r"\bdashboard", r"\bmis\b"]),
    ("Scikit-learn", [r"scikit-learn", r"anomaly", r"forecast", r"predictive", r"machine learning"]),
    ("AI Agents & Webhooks", [r"webhook", r"whatsapp", r"ai agent", r"ai tool", r"power automate", r"automate"]),
]

# Verified domain experience profiles anchored strictly in Ankit_Resume_v4.pdf
DOMAIN_PROFILES: Dict[str, Dict[str, Any]] = {
    "pharma_commercial": {
        "weight": 2,
        "triggers": (
            "pharma", "pharmaceutical", "life sciences", "clinical", "patient", "hcp", "hco",
            "claims", "iqvia", "symphony", "npp", "incentive", "payout", "field force",
            "commercial enablement", "commercial data", "territor", "veeva", "hipaa",
            "abbott", "sanofi", "eversana", "indegene", "axtria",
        ),
        "referral_clause": (
            "including 3+ years at ZS Associates building pharma commercial pipelines for "
            "field force incentives, sales/HCP data modeling, and automated SQL data quality checks "
            "(cutting production issues by 40%)"
        ),
        "dm_clause": (
            "at ZS Associates building pharma commercial analytics across patient, HCP/HCO, "
            "claims, NPP, and field force incentive pipelines under HIPAA compliance"
        ),
        "email_bullet": (
            "- Healthcare Commercial Data & Anomaly Modeling (ZS Associates): Managed 15+ Apache Airflow "
            "pipelines and 8+ Spark/Snowflake workflows ingesting terabytes of HIPAA-masked HCP/HCO "
            "and sales (SPP & BnB) feeds from S3 and SFTP. Built a SQL data quality framework backed by "
            "Scikit-learn anomaly detection that cut production incidents by 40% (Super Innova award) "
            "and reduced weekly manual touchpoints from 7 to 3 (35% less effort)."
        ),
        "impact_focus": "field force tracking, commercial data modeling, and automated data quality",
    },
    "d2c_ops_ai": {
        "triggers": (
            "d2c", "e-commerce", "ecommerce", "shopify", "whatsapp", "webhook",
            "carrier", "shipping", "cohort", "restock", "retention", "meta ads",
            "pixel", "home healthcare", "dispatch", "ai agent",
        ),
        "referral_clause": (
            "most recently engineering automated audit pipelines, demand forecasting workflows, "
            "and WhatsApp webhook agents that lifted conversion by 15% and sales by 30%"
        ),
        "dm_clause": (
            "engineering automated vendor audit pipelines (-25% shipping leakage), demand forecasting, "
            "and cohort analytics with WhatsApp webhook agents (+15% conversion, +30% sales)"
        ),
        "email_bullet": (
            "- Predictive Modeling & D2C Automation (Rush by Kira): Built a demand-forecasting restock "
            "pipeline on buyer SKU metadata alongside WhatsApp webhook agents and cohort analytics, "
            "lifting conversion by 15% and sales by 30%. Engineered an automated AWB weight-audit "
            "pipeline to flag carrier billing errors, cutting annual shipping leakage by 25%."
        ),
        "impact_focus": "cohort retention, predictive modeling, and automated MIS workflows",
    },
    "data_engineering": {
        "triggers": (
            "data engineer", "ingestion", "etl", "elt", "pipeline", "warehouse",
            "snowflake", "spark", "pyspark", "airflow", "dimensional", "star schema",
            "batch", "s3", "monitoring", "root cause", "production",
        ),
        "referral_clause": (
            "including 3+ years at ZS Associates running 15+ Airflow and PySpark/Snowflake pipelines "
            "and building SQL data quality checks that cut production issues by 40%"
        ),
        "dm_clause": (
            "running 15+ Airflow and 8+ PySpark/Snowflake pipelines across vendor feeds with automated "
            "SQL data quality monitoring that cut production incidents by 40%"
        ),
        "email_bullet": (
            "- Production Pipelines & Event-Driven ETL (ZS Associates): Orchestrated 8+ Spark/Snowflake "
            "and 15+ Apache Airflow pipelines integrating multi-vendor data via S3, SFTP, AWS SNS, and "
            "Microsoft Power Automate. Automated failure alerting and SQL reconciliation checks, cutting "
            "production server incidents by 40% and weekly operational effort by 35%."
        ),
        "impact_focus": "reliable batch pipelines, dimensional modeling, and automated data quality",
    },
    "bi_analytics": {
        "triggers": (
            "business analyst", "mis", "excel", "power bi", "tableau", "kpi",
            "variance", "financial", "economics", "forecast", "reporting",
        ),
        "referral_clause": (
            "combining SQL, Python, Advanced Excel, and BI dashboarding with Business Economics "
            "training from Delhi University and econometric/financial modeling experience"
        ),
        "dm_clause": (
            "pairing SQL, Python, Advanced Excel, and BI reporting with predictive modeling and "
            "Business Economics training from Delhi University"
        ),
        "email_bullet": (
            "- Event-Driven Reporting & Econometrics: Automated cross-channel attribution pipelines across "
            "DSPs and ad platforms (Meta, Google Ads, DeepIntent, Lasso) using Snowflake, Hive, AWS SNS, "
            "and Power Automate. Backed by Python/API financial models (TresVista) and published SSRN "
            "panel-data econometric research from Delhi University (BA Hons. Business Economics)."
        ),
        "impact_focus": "automated MIS reporting, KPI variance tracking, and predictive analytics",
    },
}


def fetch_jd_markdown(url: str, timeout: int = 15, cache_ttl_seconds: int = 86400) -> str:
    """Safely fetches clean markdown from a public job posting URL with local SQLite+L1 cache."""
    if not url or not url.strip():
        return ""
    clean_url = url.strip()
    ok, reason = validate_url(clean_url)
    if not ok:
        print(f"[contact_pitch:ssrf_guard] Blocked unsafe URL ({reason}).", file=sys.stderr)
        return ""

    try:
        from intelligence.fast_recall_cache import get_cached_text, put_cached_text
        cached_md = get_cached_text(clean_url, max_age_seconds=cache_ttl_seconds)
        if cached_md:
            return cached_md
    except Exception:
        put_cached_text = None

    jina_url = f"https://r.jina.ai/{clean_url}"
    req = urllib.request.Request(
        jina_url,
        headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X) CareerPilotAI/1.2"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read().decode("utf-8", errors="ignore")
            if content and put_cached_text is not None:
                try:
                    put_cached_text(clean_url, content, category="jd_markdown")
                except Exception:
                    pass
            return content
    except Exception as exc:
        print(f"[contact_pitch:fetch_warning] Could not fetch JD via Jina Reader: {exc}", file=sys.stderr)
        return ""


def _sanitize_title(text: str) -> str:
    """Normalizes role titles and removes em/en dashes cleanly."""
    clean = text.replace("—", "-").replace("–", "-")
    return re.sub(r"\s{2,}", " ", clean).strip()


def analyze_jd_fit(jd_text: str, role: str = "") -> Dict[str, Any]:
    """Deterministically matches JD text against verified skills and CV domain blocks."""
    combined = f"{role}\n{jd_text}".lower()
    matched_skills: List[str] = []
    for canonical, patterns in VERIFIED_SKILL_MATCHERS:
        if any(re.search(pat, combined) for pat in patterns):
            matched_skills.append(canonical)

    if not matched_skills:
        matched_skills = ["SQL", "Python", "Snowflake", "PySpark", "Apache Airflow"]

    domain_scores: Dict[str, int] = {}
    for key, spec in DOMAIN_PROFILES.items():
        hits = sum(1 for kw in spec["triggers"] if kw in combined)
        if hits > 0:
            domain_scores[key] = hits * spec.get("weight", 1)

    ranked_domains = [
        k for k, _ in sorted(domain_scores.items(), key=lambda kv: kv[1], reverse=True)
    ]
    if not ranked_domains:
        ranked_domains = ["data_engineering", "bi_analytics"]

    return {
        "matched_skills": matched_skills,
        "ranked_domains": ranked_domains,
        "primary_domain": ranked_domains[0],
    }


def audit_and_finalize_outreach(text: str) -> Dict[str, Any]:
    """Runs deterministic linting, em-dash removal, and CV fact-checking on draft output."""
    lint_res = lint_and_format(text, proofread_llm=False)
    clean_text = lint_res["clean_text"]
    fact_res = CVFactChecker.audit_text(clean_text)

    combined_violations = list(dict.fromkeys(lint_res["violations"] + fact_res["violations"]))
    passed = len(combined_violations) == 0 and not lint_res["has_em_dash"]
    if not passed:
        try:
            from intelligence.mistake_router import record_mistake_if_enabled
            sev = "high" if fact_res["violations"] else "medium"
            record_mistake_if_enabled(
                "outreach",
                severity=sev,
                category="outreach_audit_violation",
                model_used="outreach_pipeline",
                source="contact_pitch",
                details="; ".join((combined_violations or ["em_dash_detected"])[:3]),
            )
        except Exception:
            pass

    return {
        "text": clean_text,
        "passed": passed,
        "violations": combined_violations,
        "burstiness": lint_res["burstiness"],
        "cliches_replaced": lint_res["cliches_replaced"],
    }


def _format_skill_list(skills: List[str], limit: int = 5) -> str:
    """Formats matched skills naturally without introducing awkward punctuation."""
    picked = skills[:limit]
    if not picked:
        return "SQL and Python"
    if len(picked) == 1:
        return picked[0]
    if len(picked) == 2:
        return f"{picked[0]} and {picked[1]}"
    return ", ".join(picked[:-1]) + f", and {picked[-1]}"


def generate_linkedin_referral(
    company: str,
    role: str,
    url: str = "",
    recipient_name: str = "",
    jd_text: str = "",
) -> str:
    """
    Generates a crisp LinkedIn referral request matching the candidate's proven pattern:
    Warm opener -> role + key stack + referral ask -> 1-sentence domain fit -> URL -> CV offer.
    """
    cand = load_candidate_context()
    fit = analyze_jd_fit(jd_text, role)
    primary = DOMAIN_PROFILES[fit["primary_domain"]]
    clean_role = _sanitize_title(role)
    first_name = recipient_name.strip().split()[0] if recipient_name and recipient_name.strip() else ""

    greeting = f"Hi {first_name}, hope you are doing well!" if first_name else "Hope you are doing well!"
    top_hint = ", ".join(fit["matched_skills"][:3])
    pitch_skills = _format_skill_list(fit["matched_skills"], limit=6)
    track = "data engineering" if "data engineer" in clean_role.lower() else "data analytics and engineering"

    lines = [
        greeting,
        (
            f"I saw {company} is hiring for a {clean_role} ({top_hint}) and wanted to check if you "
            f"would be open to referring me."
        ),
        "",
        f"I have {cand['yoe_int']} years of {track} experience across {pitch_skills}, {primary['referral_clause']}.",
    ]
    if url and url.strip():
        lines.extend(["", f"Role link: {url.strip()}"])
    lines.extend(["", "Happy to share my CV if you would like to take a quick look. Thanks!"])

    audited = audit_and_finalize_outreach("\n".join(lines))
    return audited["text"]


def generate_linkedin_dm(
    company: str,
    role: str,
    recipient_name: str = "",
    url: str = "",
    jd_text: str = "",
) -> str:
    """Generates a confident, non-desperate LinkedIn DM tailored to hiring posts or leads."""
    cand = load_candidate_context()
    fit = analyze_jd_fit(jd_text, role)
    primary = DOMAIN_PROFILES[fit["primary_domain"]]
    clean_role = _sanitize_title(role)
    first_name = recipient_name.strip().split()[0] if recipient_name and recipient_name.strip() else ""

    greeting = f"Hi {first_name}," if first_name else "Hey,"
    pitch_skills = _format_skill_list(fit["matched_skills"], limit=4)

    lines = [
        greeting,
        (
            f"Saw your update for the {clean_role} opening at {company}. I have {cand['yoe_int']} years "
            f"of experience across {pitch_skills}, {primary['dm_clause']}."
        ),
    ]
    if url and url.strip():
        lines.extend(["", f"Role link: {url.strip()}"])
    lines.extend(["", "Happy to send over my CV or connect briefly if this matches what your team needs."])

    audited = audit_and_finalize_outreach("\n".join(lines))
    return audited["text"]


def generate_outreach_email(
    recipient_name: str,
    company: str,
    role: str,
    recipient_email: str = "",
    url: str = "",
    jd_text: str = "",
    location: str = "",
    tone: str = "soft",
    include_hr_fields: bool = False,
) -> str:
    """
    Generates a polished recruiter/hiring-manager outreach email grounded strictly in CV facts.
    Supports soft polite HR openings ('soft') or direct engineering openings ('technical').
    """
    cand = load_candidate_context()
    fit = analyze_jd_fit(jd_text, role)
    primary = DOMAIN_PROFILES[fit["primary_domain"]]
    clean_role = _sanitize_title(role)
    first_name = recipient_name.strip().split()[0] if recipient_name and recipient_name.strip() else "Hiring Team"
    loc_tag = f"{location.strip()}, " if location and location.strip() else ""

    subject = f"{clean_role} ({loc_tag}Immediate Joiner, {cand['yoe_int']} Yrs Exp) | {cand['name']}"

    if tone == "technical":
        opener = (
            f"Reaching out regarding the {clean_role} opening at {company}. "
            f"My work centers on {primary['impact_focus']} backed by production SQL, Python, "
            f"and cloud pipelines rather than static manual reporting."
        )
    else:
        opener = (
            f"Hope you are having a good week. I came across the {clean_role} opening at {company} "
            f"and wanted to share my profile for your consideration. My background pairs analytics "
            f"and engineering execution directly suited to {primary['impact_focus']}."
        )

    # Pick up to 3 unique domain bullets in ranked JD relevance order
    selected_bullets: List[str] = []
    for dom in fit["ranked_domains"][:3]:
        bullet = DOMAIN_PROFILES[dom]["email_bullet"]
        if bullet not in selected_bullets:
            selected_bullets.append(bullet)
    if "bi_analytics" not in fit["ranked_domains"][:3] and len(selected_bullets) < 3:
        selected_bullets.append(DOMAIN_PROFILES["bi_analytics"]["email_bullet"])

    core_stack = (
        "Core Stack: Python, PySpark, SQL (PostgreSQL, Snowflake, Trino, Oracle), Scikit-learn, "
        "Apache Airflow, Tableau / Power BI, Advanced Excel, AWS (S3, SNS), and REST/Webhook AI Agents."
    )

    body_parts: List[str] = []
    if recipient_email:
        body_parts.append(f"To: {recipient_email}")
    body_parts.extend([
        f"Subject: {subject}",
        "",
        f"Hi {first_name},",
        "",
        opener,
        "",
        "How my experience maps directly to your team:",
        "",
        *selected_bullets,
        "",
        core_stack,
    ])

    if url and url.strip():
        body_parts.extend(["", f"Reference Role: {url.strip()}"])

    if include_hr_fields:
        loc_note = f"{cand['city']} (Ready for {location})" if location else cand["city"]
        body_parts.extend([
            "",
            "My CV is attached. Requested details:",
            "",
            f"Total exp: {cand['yoe_int']} years",
            f"Current ctc: {cand['ctc_lpa']} LPA",
            f"Expected ctc: {cand['exp_ctc_lpa']} LPA",
            f"Location: {loc_note}",
            f"Notice period: {cand['notice_period']}",
            "",
            "I can join immediately and am available for a call or an in-person discussion.",
        ])
    else:
        body_parts.extend([
            "",
            "My CV is attached. I can join immediately and would welcome a brief call this week.",
        ])

    body_parts.extend([
        "",
        "Best regards,",
        cand["name"],
        cand["phone"],
        f"LinkedIn: {cand['linkedin']}",
    ])

    audited = audit_and_finalize_outreach("\n".join(body_parts))
    return audited["text"]


def generate_inmail_pitch(recipient_name: str, company: str, role: str) -> str:
    """Generates a concise 1-paragraph InMail value proposition (backward compatible)."""
    cand = load_candidate_context()
    first_name = recipient_name.strip().split()[0] if recipient_name.strip() else "there"

    draft = (
        f"Subject: Applied for {_sanitize_title(role)} at {company} - Data Engineering Background\n\n"
        f"Hi {first_name},\n\n"
        f"I recently submitted my application for the {_sanitize_title(role)} position at {company} and wanted "
        f"to reach out directly. Over the last {cand['yoe_int']} years as a Technology Consultant, I have "
        f"specialized in building high-throughput PySpark and Snowflake data pipelines, optimizing SQL queries, "
        f"and automating enterprise workflows using Apache Airflow.\n\n"
        f"Given my immediate availability (0 days notice) and experience delivering scalable data infrastructure "
        f"across life sciences and retail sectors, I would welcome the opportunity to connect and discuss how "
        f"I can contribute to the team.\n\n"
        f"Best regards,\n"
        f"{cand['name']}\n"
        f"{cand['linkedin']}"
    )
    return audit_and_finalize_outreach(draft)["text"]


def generate_followup_note(recipient_name: str, company: str, role: str, days_ago: int = 7) -> str:
    """Generates a polite follow-up message after application submission (backward compatible)."""
    cand = load_candidate_context()
    first_name = recipient_name.strip().split()[0] if recipient_name.strip() else "there"

    draft = (
        f"Hi {first_name},\n\n"
        f"Following up briefly on my application for the {_sanitize_title(role)} role at {company} "
        f"submitted about {days_ago} days ago.\n\n"
        f"I remain very interested in the team's engineering goals. With {cand['yoe_int']} years of experience "
        f"building Snowflake, PySpark, and Airflow systems with immediate joining availability, I am available "
        f"at your convenience if any additional details would be helpful.\n\n"
        f"Best regards,\n"
        f"{cand['name']}"
    )
    return audit_and_finalize_outreach(draft)["text"]


def _resolve_output_path(company: str, recipient_name: str, custom_out: str) -> Path:
    """Resolves gitignored outreach artifact destination under documents/."""
    if custom_out:
        return Path(custom_out)
    safe_comp = re.sub(r"[^A-Za-z0-9]+", "", company.title()) or "Company"
    safe_rec = re.sub(r"[^A-Za-z0-9]+", "_", recipient_name.strip()) or "Contact"
    return ROOT / "documents" / f"{safe_comp}_Outreach_{safe_rec}.md"


def main():
    parser = argparse.ArgumentParser(description="Universal JD-aware LinkedIn & Email Outreach Generator")
    parser.add_argument("--url", default="", help="Public job posting URL (fetched safely via Jina Reader)")
    parser.add_argument("--jd-file", default="", help="Optional local file containing job description or post text")
    parser.add_argument("--name", "-n", default="", help="Recipient name (optional)")
    parser.add_argument("--email", "-e", default="", help="Recipient email address (optional)")
    parser.add_argument("--company", "-c", required=True, help="Company name")
    parser.add_argument("--role", "-r", required=True, help="Target role title")
    parser.add_argument("--location", "-l", default="", help="Job location (optional)")
    parser.add_argument(
        "--type", "-t",
        choices=["referral", "dm", "email", "invite", "inmail", "followup", "all"],
        default="all",
        help="Outreach channel/template",
    )
    parser.add_argument("--tone", choices=["soft", "technical"], default="soft", help="Email opening tone")
    parser.add_argument("--include-hr-fields", action="store_true", help="Include Total exp / CTC / Location / Notice block")
    parser.add_argument("--save", action="store_true", help="Save generated outreach markdown to documents/*Outreach*.md")
    parser.add_argument("--output", "-o", default="", help="Custom output markdown file path")
    args = parser.parse_args()

    jd_text = ""
    if args.jd_file and Path(args.jd_file).exists():
        jd_text = Path(args.jd_file).read_text(encoding="utf-8", errors="ignore")
    elif args.url:
        jd_text = fetch_jd_markdown(args.url)

    sections: List[str] = []
    fit = analyze_jd_fit(jd_text, args.role)

    print("\n" + "=" * 68)
    print(f"OUTREACH ENGINE: {args.company} - {_sanitize_title(args.role)}")
    print(f"Primary Domain Match: {fit['primary_domain']} | Matched Skills: {', '.join(fit['matched_skills'][:7])}")
    print("=" * 68)

    if args.type in ("referral", "all"):
        ref_msg = generate_linkedin_referral(args.company, args.role, args.url, args.name, jd_text)
        print("\n[1] LINKEDIN REFERRAL MESSAGE:")
        print("-" * 55)
        print(ref_msg)
        print("-" * 55)
        sections.append(f"## LinkedIn Referral Message\n\n```text\n{ref_msg}\n```")

    if args.type in ("dm", "all"):
        dm_msg = generate_linkedin_dm(args.company, args.role, args.name, args.url, jd_text)
        print("\n[2] LINKEDIN DIRECT MESSAGE:")
        print("-" * 55)
        print(dm_msg)
        print("-" * 55)
        sections.append(f"## LinkedIn Direct Message\n\n```text\n{dm_msg}\n```")

    if args.type in ("email", "all"):
        email_msg = generate_outreach_email(
            recipient_name=args.name,
            company=args.company,
            role=args.role,
            recipient_email=args.email,
            url=args.url,
            jd_text=jd_text,
            location=args.location,
            tone=args.tone,
            include_hr_fields=args.include_hr_fields,
        )
        print("\n[3] OUTREACH EMAIL:")
        print("-" * 55)
        print(email_msg)
        print("-" * 55)
        sections.append(f"## Outreach Email\n\n```text\n{email_msg}\n```")

    if args.type in ("invite", "all"):
        rec_name = args.name or "Hiring Lead"
        invite_recruiter = generate_connection_note(rec_name, "Recruiter", args.company, args.role, persona="recruiter")
        invite_manager = generate_connection_note(rec_name, "Engineering Lead", args.company, args.role, persona="manager")
        print("\n[4] LINKEDIN CONNECTION INVITE (<=300 chars):")
        print(f"  * Recruiter ({len(invite_recruiter)} chars): {invite_recruiter}")
        print(f"  * Engineering Lead ({len(invite_manager)} chars): {invite_manager}")
        sections.append(
            f"## LinkedIn Connection Invites\n\n- **Recruiter:** {invite_recruiter}\n- **Lead:** {invite_manager}"
        )

    if args.type == "inmail":
        inmail = generate_inmail_pitch(args.name or "Hiring Lead", args.company, args.role)
        print("\n[INMAIL DRAFT]:")
        print("-" * 55)
        print(inmail)
        print("-" * 55)
        sections.append(f"## InMail Pitch\n\n```text\n{inmail}\n```")

    if args.type == "followup":
        followup = generate_followup_note(args.name or "Hiring Lead", args.company, args.role)
        print("\n[FOLLOW-UP DRAFT]:")
        print("-" * 55)
        print(followup)
        print("-" * 55)
        sections.append(f"## Follow-Up Note\n\n```text\n{followup}\n```")

    if args.save or args.output:
        out_path = _resolve_output_path(args.company, args.name, args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        md_content = f"# Outreach Drafts - {args.company} ({_sanitize_title(args.role)})\n\n" + "\n\n".join(sections) + "\n"
        out_path.write_text(md_content, encoding="utf-8")
        print(f"\n[Saved] Wrote outreach markdown to: {out_path}")


if __name__ == "__main__":
    main()
