#!/usr/bin/env python3
"""
tools/salary_gap.py
-------------------
Compensation Intelligence & Salary Gap Analyzer.
Compares job posting compensation against candidate baseline CTC (18 LPA) and
target CTC (28 LPA), calculating spreads, percentage uplifts, and reliability tiers.

Adapted from career-ops salary-gap.mjs into CareerPilot AI universal architecture.
Rule: Zero em dashes permitted. Zero financial cost.
"""

from __future__ import annotations

import argparse
import sys
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.qa_semantics_engine import load_candidate_context


def analyze_salary_gap(advertised_str: str) -> dict:
    """Analyzes salary string and computes comparison metrics."""
    cand = load_candidate_context()
    current_ctc = float(cand.get("ctc_lpa", 18.0))
    target_ctc = float(cand.get("exp_ctc_lpa", 28.0))

    # Parse numbers from advertised string
    # e.g. "25-35 LPA", "30 LPA", "$150,000"
    advertised_clean = (advertised_str or "").lower().strip()
    
    # Check LPA ranges
    lpa_matches = re.findall(r"(\d+(?:\.\d+)?)\s*(?:-|to)?\s*(\d+(?:\.\d+)?)?\s*(?:lpa|lakhs?|inr|lac)", advertised_clean)
    if lpa_matches:
        m1 = float(lpa_matches[0][0])
        m2 = float(lpa_matches[0][1]) if lpa_matches[0][1] else m1
        lo, hi = min(m1, m2), max(m1, m2)
        unit = "LPA (INR)"
    else:
        # Check raw numbers
        nums = [float(n) for n in re.findall(r"\b\d+(?:\.\d+)?\b", advertised_clean)]
        if nums:
            lo, hi = min(nums), max(nums)
            unit = "Units / As stated"
        else:
            lo, hi = target_ctc, target_ctc
            unit = "Estimated Baseline Target"

    # Evaluate spread against candidate targets
    spread_vs_current = round(hi - current_ctc, 1)
    pct_vs_current = round(((hi - current_ctc) / current_ctc) * 100, 1) if current_ctc > 0 else 0
    spread_vs_target = round(hi - target_ctc, 1)

    if hi >= target_ctc:
        tier = "Tier 1: High Comp (Meets/Exceeds 28 LPA Desired CTC)"
        recommendation = "Optimal compensation. Target top-of-band during negotiations."
    elif hi >= current_ctc:
        tier = "Tier 2: Moderate Comp (Above Current 18 LPA, Below 28 LPA Target)"
        recommendation = "Acceptable progression. Negotiate fixed base and joining bonuses."
    else:
        tier = "Tier 3: Below Current CTC (Below 18 LPA)"
        recommendation = "Below current compensation baseline. Request band adjustment or skip."

    return {
        "advertised_range": f"{lo} - {hi} {unit}",
        "current_ctc": f"{current_ctc} LPA",
        "target_ctc": f"{target_ctc} LPA",
        "spread_vs_current": f"+{spread_vs_current} LPA (+{pct_vs_current}%)" if spread_vs_current >= 0 else f"{spread_vs_current} LPA",
        "spread_vs_target": f"+{spread_vs_target} LPA" if spread_vs_target >= 0 else f"{spread_vs_target} LPA",
        "tier": tier,
        "recommendation": recommendation
    }


def main():
    parser = argparse.ArgumentParser(description="Analyze compensation spread vs candidate baseline")
    parser.add_argument("salary", help="Advertised salary string (e.g. '25-32 LPA', '28 LPA')")
    args = parser.parse_args()

    res = analyze_salary_gap(args.salary)

    print("\n" + "=" * 65)
    print("💰 COMPENSATION & SALARY GAP ANALYSIS")
    print("=" * 65)
    print(f"• Advertised Range:     {res['advertised_range']}")
    print(f"• Candidate Current:    {res['current_ctc']}")
    print(f"• Candidate Target:     {res['target_ctc']}")
    print(f"• Spread vs Current:    {res['spread_vs_current']}")
    print(f"• Spread vs Target:     {res['spread_vs_target']}")
    print(f"• Compensation Tier:    {res['tier']}")
    print(f"• Negotiation Strategy: {res['recommendation']}")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()

