#!/usr/bin/env python3
"""
Offer & Employment Contract Reading Companion
=============================================
Zero-token local analyzer for offer letters and employment agreements.
Extracts and structures restrictive covenants, IP assignment, notice period,
probation, and bonus clawback terms.

Adapted from career-ops modes/offer-prep.md into CareerPilot AI Python 3.15+ architecture.
Strict Posture:
- Never outputs 'safe to sign' or provides legal opinions.
- Acts as a factual reading companion that highlights operational terms and
  generates a targeted checklist of questions for legal counsel or HR.
"""

import argparse
import re
from pathlib import Path
from typing import Dict, List, Any


CLAUSE_PATTERNS = {
    "non_compete": [
        re.compile(r"\bnon-?compete\b", re.IGNORECASE),
        re.compile(r"\brestrictive\s+covenant\b", re.IGNORECASE),
        re.compile(r"\bshall\s+not(?:\s+directly\s+or\s+indirectly)?\s+engage\s+in\s+any\s+competing\b", re.IGNORECASE),
    ],
    "non_solicit": [
        re.compile(r"\bnon-?solicitation\b", re.IGNORECASE),
        re.compile(r"\bsolicit(?:\s+or\s+entice)?\s+any\s+(?:employee|customer|client)\b", re.IGNORECASE),
    ],
    "notice_period": [
        re.compile(r"\bnotice\s+period\b", re.IGNORECASE),
        re.compile(r"\btermination\s+notice\b", re.IGNORECASE),
        re.compile(r"\b(?:30|60|90)\s+days?\s+notice\b", re.IGNORECASE),
    ],
    "probation": [
        re.compile(r"\bprobation(?:ary)?\s+(?:period)?\b", re.IGNORECASE),
    ],
    "ip_assignment": [
        re.compile(r"\bintellectual\s+property\b", re.IGNORECASE),
        re.compile(r"\bassignment\s+of\s+inventions?\b", re.IGNORECASE),
        re.compile(r"\bworks?\s+made\s+for\s+hire\b", re.IGNORECASE),
    ],
    "clawback_or_bonus": [
        re.compile(r"\bclaw-?back\b", re.IGNORECASE),
        re.compile(r"\brepay(?:\s+the)?\s+(?:joining|retention|relocation)\s+bonus\b", re.IGNORECASE),
        re.compile(r"\bvesting\s+schedule\b", re.IGNORECASE),
    ]
}


def analyze_contract_text(text: str) -> Dict[str, Any]:
    """
    Extracts key contractual clauses from offer or agreement text.
    Generates a structured breakdown and a lawyer / negotiation question checklist.
    """
    lines = text.splitlines()
    findings: Dict[str, List[str]] = {k: [] for k in CLAUSE_PATTERNS}

    for i, line in enumerate(lines):
        line_clean = line.strip()
        if not line_clean:
            continue
        for category, patterns in CLAUSE_PATTERNS.items():
            if any(p.search(line_clean) for p in patterns):
                # Extract paragraph context (current line plus next line if short)
                snippet = line_clean
                if i + 1 < len(lines) and len(lines[i + 1].strip()) < 150:
                    snippet += " " + lines[i + 1].strip()
                if snippet not in findings[category]:
                    findings[category].append(snippet[:300])

    # Generate targeted questions for counsel or employer
    questions = []
    if findings["non_compete"]:
        questions.append("What is the exact post-employment duration (e.g. 6 or 12 months) and geographic territory of the non-compete clause?")
        questions.append("Under Indian contract law (Section 27 of the Indian Contract Act, 1872), post-employment non-competes are void in restraint of trade. Is this intended only during active employment?")
    if findings["notice_period"]:
        questions.append("What are the buyout options if either party decides to waive the notice period?")
    if findings["clawback_or_bonus"]:
        questions.append("Under what exact circumstances (resignation vs termination without cause) does the bonus clawback trigger?")
    if findings["ip_assignment"]:
        questions.append("Does the IP assignment clause strictly cover company projects, or does it overreach into personal projects built off-hours on private hardware?")

    return {
        "clauses_detected": {k: v for k, v in findings.items() if v},
        "questions_for_lawyer_or_hr": questions,
        "clause_count": sum(len(v) for v in findings.values()),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze offer letter or employment agreement clauses")
    parser.add_argument("file", nargs="?", help="Path to offer letter text or markdown file")
    args = parser.parse_args()

    sample_contract = (
        "1. Compensation: Total fixed CTC is INR 28,00,000.\n"
        "2. Notice Period: The employee must serve 60 days notice prior to resignation.\n"
        "3. Probation Period: Initial probation period shall be 3 months from joining date.\n"
        "4. Non-Compete: Employee shall not engage in any competing data analytics consulting business for 12 months.\n"
        "5. IP Assignment: All inventions developed during the term of employment are works made for hire.\n"
        "6. Joining Bonus: A joining bonus of INR 2,00,000 will be paid, subject to clawback if employee leaves within 1 year.\n"
    )

    if args.file and Path(args.file).exists():
        content = Path(args.file).read_text(encoding="utf-8")
    else:
        content = sample_contract

    res = analyze_contract_text(content)
    print("\n" + "=" * 60)
    print("  EMPLOYMENT CONTRACT READING COMPANION (FACTUAL AUDIT)")
    print("=" * 60)
    print(f"\n[Detected Clauses: {res['clause_count']}]")
    for cat, matches in res["clauses_detected"].items():
        print(f"\n• {cat.replace('_', ' ').upper()}:")
        for m in matches:
            print(f"    - {m}")

    print("\n" + "-" * 60)
    print("  QUESTIONS FOR YOUR LAWYER / HR CONVERSATION:")
    print("-" * 60)
    for idx, q in enumerate(res["questions_for_lawyer_or_hr"], 1):
        print(f"  [{idx}] {q}")
    print("=" * 60 + "\n")
