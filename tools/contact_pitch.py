#!/usr/bin/env python3
"""
tools/contact_pitch.py
----------------------
Recruiter & Hiring Manager Pitch Generator.
Generates high-burstiness, humanized networking pitches:
1. LinkedIn Connection Request (<=300 chars, free tier safe)
2. LinkedIn InMail / Direct Message (short, punchy value prop)
3. Cold Outreach Email (concise 3-paragraph format)

Adapted from career-ops contacto.md and followup.md into CareerPilot AI universal architecture.
Rule: Zero em dashes permitted. Zero corporate slop. Zero financial cost.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.qa_semantics_engine import load_candidate_context
from tools.contact_pitch_generator import generate_connection_note


def generate_inmail_pitch(recipient_name: str, company: str, role: str) -> str:
    """Generates a concise 1-paragraph InMail value proposition."""
    cand = load_candidate_context()
    first_name = recipient_name.strip().split()[0] if recipient_name.strip() else "there"

    return f"""Subject: Applied for {role} at {company} - Data Engineering Background

Hi {first_name},

I recently submitted my application for the {role} position at {company} and wanted to reach out directly. Over the last 4.8 years as a Technology Consultant, I have specialized in building high-throughput PySpark and Snowflake data pipelines, optimizing SQL queries, and automating enterprise workflows using Apache Airflow.

Given my immediate availability (0 days notice) and experience delivering scalable data infrastructure across life sciences and retail sectors, I would welcome the opportunity to connect and discuss how I can contribute to the team.

Best regards,
{cand['name']}
{cand['linkedin']}"""


def generate_followup_note(recipient_name: str, company: str, role: str, days_ago: int = 7) -> str:
    """Generates a polite follow-up message after application submission."""
    cand = load_candidate_context()
    first_name = recipient_name.strip().split()[0] if recipient_name.strip() else "there"

    return f"""Hi {first_name},

Following up briefly on my application for the {role} role at {company} submitted about {days_ago} days ago. 

I remain very interested in the team's engineering goals. With 4.8 years of experience building Snowflake, PySpark, and Airflow systems with immediate joining availability, I am available at your convenience if any additional details would be helpful.

Best regards,
{cand['name']}"""


def main():
    parser = argparse.ArgumentParser(description="Generate targeted networking and recruiter pitches")
    parser.add_argument("--name", "-n", default="Hiring Lead", help="Recipient name")
    parser.add_argument("--company", "-c", required=True, help="Company name")
    parser.add_argument("--role", "-r", required=True, help="Role title")
    parser.add_argument("--type", "-t", choices=["invite", "inmail", "followup", "all"], default="all", help="Pitch format")
    args = parser.parse_args()

    print("\n" + "=" * 65)
    print(f"🎯 OUTREACH PITCH GENERATOR: {args.company} - {args.role}")
    print("=" * 65)

    if args.type in ("invite", "all"):
        invite_recruiter = generate_connection_note(args.name, "Recruiter", args.company, args.role, persona="recruiter")
        invite_manager = generate_connection_note(args.name, "Engineering Lead", args.company, args.role, persona="manager")
        print("\n[1] LINKEDIN CONNECTION INVITE (<=300 chars, free tier):")
        print("  • For Recruiter:")
        print(f"    \"{invite_recruiter}\" ({len(invite_recruiter)} chars)")
        print("  • For Engineering Manager:")
        print(f"    \"{invite_manager}\" ({len(invite_manager)} chars)")

    if args.type in ("inmail", "all"):
        inmail = generate_inmail_pitch(args.name, args.company, args.role)
        print("\n[2] LINKEDIN INMAIL / COLD EMAIL DRAFT:")
        print("-" * 55)
        print(inmail)
        print("-" * 55)

    if args.type in ("followup", "all"):
        followup = generate_followup_note(args.name, args.company, args.role)
        print("\n[3] POLITE POST-APPLICATION FOLLOW-UP:")
        print("-" * 55)
        print(followup)
        print("-" * 55)

    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()

