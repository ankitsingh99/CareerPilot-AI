#!/usr/bin/env python3
"""
Contact Outreach Pitch Generator (Contacto Engine)
==================================================
Generates high-impact, humanized networking and connection-request messages
for recruiters and engineering hiring managers.

Adapted from career-ops modes/contacto.md into CareerPilot AI Python 3.15+ architecture.
Strict Guardrails:
1. Hard limit: <= 300 characters for LinkedIn free connection requests.
2. Persona tuning:
   - Recruiter: focus on hard skills, immediate joining (0 days notice), authorized.
   - Hiring Manager: focus on engineering impact, scale, and data architecture.
3. Zero em dashes, zero AI buzzwords/slop.
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional

# Ensure repo root is on sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.qa_semantics_engine import load_candidate_context


def generate_connection_note(
    recipient_name: str,
    recipient_title: str,
    company: str,
    target_role: str,
    persona: str = "recruiter",
    char_limit: int = 300
) -> str:
    """
    Generates a personalized, concise connection invite message <= char_limit chars.
    """
    cand = load_candidate_context()
    first_name = recipient_name.strip().split()[0] if recipient_name.strip() else "there"
    
    persona_norm = persona.lower().strip()
    
    if "recruit" in persona_norm or "talent" in persona_norm or "sourcer" in persona_norm or "hr" in persona_norm:
        # Recruiter persona: Hard requirements, notice period (0 days), stack
        note = (
            f"Hi {first_name}, applied to {target_role} at {company}. "
            f"{cand['yoe_int']}y exp across PySpark, Python, Snowflake & Airflow. "
            f"Immediate joiner (0d notice) based in India. Would love to connect!"
        )
    else:
        # Hiring Manager / Engineering Lead persona: Tech impact, pipeline scale
        note = (
            f"Hi {first_name}, saw your work leading {company}'s data team. "
            f"Applied for {target_role}: built sub-second PySpark ETL pipelines & Snowflake warehouses at scale. "
            f"Immediate availability. Would value connecting!"
        )
    
    # Strictly enforce character limit
    if len(note) > char_limit:
        # Compact version
        if "recruit" in persona_norm:
            note = f"Hi {first_name}, applied for {target_role} at {company}. {cand['yoe_int']}y exp with PySpark, SQL & Airflow. Immediate joiner. Great to connect!"
        else:
            note = f"Hi {first_name}, applied for {target_role} at {company}. {cand['yoe_int']}y exp scaling PySpark & Snowflake data platforms. Would value connecting!"

    # Final trim safety guard
    if len(note) > char_limit:
        note = note[:char_limit - 1] + "."

    # Ensure zero em dashes
    note = note.replace("—", "-")
    return note


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate targeted LinkedIn connection notes (<=300 chars)")
    parser.add_argument("--name", default="Sarah", help="Recipient first name or full name")
    parser.add_argument("--title", default="Technical Recruiter", help="Recipient title")
    parser.add_argument("--company", default="Zinnia", help="Target company")
    parser.add_argument("--role", default="Data Engineer", help="Target job role")
    parser.add_argument("--persona", default="recruiter", choices=["recruiter", "manager"], help="Recipient persona")
    args = parser.parse_args()

    pitch = generate_connection_note(
        recipient_name=args.name,
        recipient_title=args.title,
        company=args.company,
        target_role=args.role,
        persona=args.persona
    )
    print(f"\n[Outreach Pitch - {args.persona.upper()}] ({len(pitch)}/300 chars):")
    print("-" * 50)
    print(pitch)
    print("-" * 50 + "\n")
