#!/usr/bin/env python3
"""
tools/evaluate_job.py
---------------------
Job Evaluation CLI.
Scores a job posting 1.0 - 5.0 against the candidate profile and delivers
the full A-H block evaluation report (career-ops standard).

Adapted from career-ops oferta.md into CareerPilot AI universal architecture.
Rule: Zero em dashes permitted. Zero financial cost.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.job_evaluator import JobEvaluator
from core.job_liveness_detector import check_url_liveness
from utils.ssrf_guard import validate_url


def main():
    parser = argparse.ArgumentParser(description="Evaluate a job posting (1-5 score, A-H blocks)")
    parser.add_argument("target", nargs="?", help="Job URL or path to text/markdown JD file")
    parser.add_argument("--url", "-u", dest="url", help="Job URL to evaluate")
    parser.add_argument("--file", "-f", dest="file_path", help="Path to text or markdown file containing JD")
    parser.add_argument("--company", "-c", default="", help="Company name (optional, inferred if absent)")
    parser.add_argument("--title", "-t", default="", help="Role title (optional, inferred if absent)")
    parser.add_argument("--skip-liveness", action="store_true", help="Skip pre-flight liveness check")
    args = parser.parse_args()

    target = args.url or args.file_path or args.target
    if not target:
        parser.print_help()
        sys.exit(1)

    jd_text = ""
    url = ""
    company = args.company
    title = args.title

    # 1. Target is a local file
    file_candidate = Path(target)
    if file_candidate.is_file():
        jd_text = file_candidate.read_text(encoding="utf-8", errors="ignore")
        if not title:
            title = file_candidate.stem.replace("_", " ").replace("-", " ").title()
        if not company:
            company = "Target Organization"

    # 2. Target is a URL
    elif target.startswith("http://") or target.startswith("https://"):
        url = target
        if not args.skip_liveness:
            print(f"[*] Pre-flight liveness check on: {url}")
            is_live, reason, code = check_url_liveness(url)
            if not is_live:
                print(f"[-] Liveness check FAILED: {reason} (HTTP {code}). Aborting evaluation to save tokens.")
                sys.exit(2)
            print(f"[+] Liveness confirmed: {reason}")

        # Fetch clean content via Jina Reader or basic request
        import urllib.request
        jina_url = f"https://r.jina.ai/{url}"
        val, ssrf_reason = validate_url(jina_url)
        if val:
            try:
                req = urllib.request.Request(jina_url, headers={"User-Agent": "CareerPilotAI/1.2"})
                with urllib.request.urlopen(req, timeout=12) as resp:
                    jd_text = resp.read().decode("utf-8", errors="ignore")
            except Exception:
                pass

        if not jd_text:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    jd_text = resp.read().decode("utf-8", errors="ignore")
            except Exception as e:
                print(f"[-] Could not retrieve job description from URL: {e}")
                sys.exit(1)

        if not company:
            # Extract basic company from domain
            import urllib.parse
            domain = urllib.parse.urlparse(url).netloc
            company = domain.split(".")[-2].title() if "." in domain else "Organization"
        if not title:
            # Heuristic title from first heading
            for line in jd_text.splitlines()[:15]:
                if line.startswith("# "):
                    title = line.replace("#", "").strip()
                    break
            if not title:
                title = "Data / Technology Specialist"

    # 3. Direct raw text input
    else:
        jd_text = target
        if not company:
            company = "Target Company"
        if not title:
            title = "Data Specialist"

    print(f"\n[*] Evaluating Job: '{title}' at '{company}'...")
    res = JobEvaluator.evaluate(
        title=title,
        company=company,
        jd_text=jd_text,
        url=url
    )

    print("\n" + "=" * 60)
    print(f"📊 EVALUATION VERDICT: {res['decision'].upper()}")
    print("=" * 60)
    print(f"• Global Fit Score:       {res['score']}/5.0")
    print(f"• Detected Archetype:     {res['archetype']}")
    print(f"• Legitimacy Confidence:  {res['legitimacy']}")
    print(f"• Work Authorization:     {res['work_auth']}")
    print(f"• Advertised Salary:      {res['advertised_comp']}")
    print(f"• Matched Core Skills:    {', '.join(s.title() for s in res['matched_skills']) or 'None'}")
    if res['red_flags']:
        print(f"• Disqualifiers:          {', '.join(res['red_flags'])}")
    print(f"• Detailed Report Saved:  {res['report_path']}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()

