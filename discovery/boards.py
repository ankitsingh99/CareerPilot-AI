#!/usr/bin/env python3
"""High-speed parallel ATS job board poller.

Queries public JSON APIs (Greenhouse, Lever, Ashby, SmartRecruiters)
across 2,000+ seed companies without browser overhead.
"""
import os
import sys
import json
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Dict, Any

from discovery.ats_discovery.boards import POLLERS
from discovery.ats_discovery.filters import evaluate_posting

REPO_ROOT = Path(__file__).resolve().parent.parent
SEEDS_DIR = REPO_ROOT / "seeds"


def load_seeds(ats_filter: str = None) -> List[Dict[str, str]]:
    seeds = []
    
    # Load all verified seeds if available
    all_ver = SEEDS_DIR / "all-verified.json"
    if all_ver.exists():
        with open(all_ver, "r", encoding="utf-8") as f:
            data = json.load(f)
            for item in data:
                # format: [ats, slug] or dict
                if isinstance(item, list) and len(item) >= 2:
                    ats, slug = item[0], item[1]
                    if not ats_filter or ats == ats_filter:
                        seeds.append({"ats": ats, "slug": slug})
                elif isinstance(item, dict):
                    ats = item.get("ats")
                    slug = item.get("slug")
                    if ats and slug and (not ats_filter or ats == ats_filter):
                        seeds.append({"ats": ats, "slug": slug})
    
    # Fallback to specific files
    if not seeds:
        files = {
            "greenhouse": SEEDS_DIR / "gh_companies.json",
            "lever": SEEDS_DIR / "lever_companies.json",
            "ashby": SEEDS_DIR / "ashby_companies.json",
        }
        for ats, path in files.items():
            if ats_filter and ats != ats_filter:
                continue
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    for slug in json.load(f):
                        seeds.append({"ats": ats, "slug": slug})
                        
    if not seeds:
        seeds = [
            {"ats": "greenhouse", "slug": "stripe"},
            {"ats": "lever", "slug": "figma"},
            {"ats": "ashby", "slug": "openai"}
        ]
    return seeds


def poll_single_company(seed: Dict[str, str]) -> List[Dict[str, Any]]:
    ats = seed["ats"]
    slug = seed["slug"]
    poller = POLLERS.get(ats)
    if not poller:
        return []
    
    matches = []
    try:
        for job in poller(slug, timeout=12):
            eval_res = evaluate_posting(job)
            if eval_res["passed"]:
                job["location_tier"] = eval_res["location_tier"]
                matches.append(job)
    except Exception:
        pass
    return matches


def main():
    parser = argparse.ArgumentParser(description="Poll public ATS job boards for matching positions.")
    parser.add_argument("--ats", choices=["greenhouse", "lever", "ashby", "smartrecruiters"], help="Filter by ATS")
    parser.add_argument("--limit-seeds", type=int, default=None, help="Limit number of company seeds to poll")
    parser.add_argument("--workers", type=int, default=25, help="Concurrent worker threads")
    parser.add_argument("--output", type=str, default=None, help="Save matches to JSON or CSV file")
    parser.add_argument("--format", choices=["table", "json", "csv"], default="table", help="Output format")
    args = parser.parse_args()

    seeds = load_seeds(args.ats)
    if args.limit_seeds:
        seeds = seeds[:args.limit_seeds]

    print(f"Polling {len(seeds)} company boards with {args.workers} concurrent workers...")

    all_matches = []
    completed = 0
    total = len(seeds)

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(poll_single_company, seed): seed for seed in seeds}
        for future in as_completed(futures):
            completed += 1
            if completed % 100 == 0 or completed == total:
                sys.stdout.write(f"\rProgress: {completed}/{total} boards scanned | Found {len(all_matches)} matches")
                sys.stdout.flush()
            try:
                res = future.result()
                if res:
                    all_matches.extend(res)
            except Exception:
                pass

    print(f"\nScan complete! Found {len(all_matches)} matched positions across {total} boards.")

    # Deduplicate by URL
    seen_urls = set()
    deduped = []
    for m in all_matches:
        if m["url"] not in seen_urls:
            seen_urls.add(m["url"])
            deduped.append(m)

    # Sort by Location Tier (Remote > Delhi NCR > Bangalore > Hyderabad > etc.)
    tier_order = {"100% Remote": 0, "Delhi NCR (Preferred)": 1, "Bangalore": 2, "Hyderabad": 3, "Pune / Mumbai": 4, "India (General)": 5}
    deduped.sort(key=lambda x: tier_order.get(x.get("location_tier", ""), 99))

    if args.output:
        out_path = Path(args.output)
        if out_path.suffix == ".json" or args.format == "json":
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(deduped, f, indent=2)
        elif out_path.suffix == ".csv" or args.format == "csv":
            import csv
            with open(out_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["company", "title", "location", "location_tier", "ats", "url", "posted_at"])
                for j in deduped:
                    writer.writerow([j["company"], j["title"], j["location"], j.get("location_tier", ""), j["ats"], j["url"], j.get("posted_at", "")])
        print(f"Results saved to {args.output}")
    else:
        for idx, j in enumerate(deduped[:30], 1):
            print(f"[{idx}] {j['company']} - {j['title']} | {j['location']} ({j.get('location_tier', '')}) | {j['url']}")


if __name__ == "__main__":
    main()
