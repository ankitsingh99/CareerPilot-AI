#!/usr/bin/env python3
"""
tools/model_analytics.py
------------------------
CLI Dashboard & Inspector for Cost-Intelligent Model Routing,
User Correction Tracking, and Adaptive Frontier Promotion.

Usage:
  python tools/model_analytics.py --status
  python tools/model_analytics.py --log-correction --category <cat> --directive "<instruction>"
  python tools/model_analytics.py --test-routing
  python tools/model_analytics.py --reset-cooldowns
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.model_router import (
    get_model_router,
    route_task,
    rescue_json_output,
    TIER_CHORE,
    TIER_FRONTIER,
)
from core.user_corrections_engine import (
    get_user_corrections_engine,
    log_user_correction,
)


def print_status() -> None:
    router = get_model_router()
    engine = get_user_corrections_engine()

    analytics = router.get_realtime_analytics()
    corrections_summary = engine.get_corrections_summary()

    totals = analytics.get("totals", {})
    tier_dist = analytics.get("tier_distribution_pct", {})
    cooldowns = analytics.get("active_cooldowns", {})
    model_usage = analytics.get("model_usage", {})

    print("================================================================================")
    print("           CAREERPILOT AI: REAL-TIME MODEL ROUTING & ANALYTICS           ")
    print("================================================================================")
    print(f"Total Requests Processed:     {totals.get('total_requests', 0):,}")
    print(f"  - Chore (Cheaper/Free Tier): {totals.get('chore_requests', 0):,} ({tier_dist.get('chore', 0.0)}%)")
    print(f"  - Frontier (Gemini/Pro):     {totals.get('frontier_requests', 0):,} ({tier_dist.get('frontier', 0.0)}%)")
    print(f"Tokens Conserved (Offloaded):  ~{totals.get('tokens_conserved_est', 0):,} tokens")
    print(f"Outputs Rescued (Text -> JSON):{totals.get('rescued_outputs', 0):,}")
    print(f"Rate Limits Encountered (429): {totals.get('rate_limits_encountered', 0):,}")
    print("--------------------------------------------------------------------------------")

    # Active Cooldowns
    if cooldowns:
        print("ACTIVE MODEL COOLDOWNS (429 / 5xx Failover):")
        for m, remaining in cooldowns.items():
            print(f"  - {m}: {remaining}s remaining")
    else:
        print("ACTIVE MODEL COOLDOWNS: None (All provider endpoints healthy)")
    print("--------------------------------------------------------------------------------")

    # Model Usage Breakdown
    print("MODEL USAGE BREAKDOWN:")
    if model_usage:
        for m, stats in sorted(model_usage.items(), key=lambda kv: -kv[1]["calls"]):
            print(f"  - {m:40} | Calls: {stats['calls']:<4} | Success: {stats['success']:<4} | Tokens: {stats['tokens']:,}")
    else:
        print("  - No direct model calls recorded yet in current cycle.")
    print("--------------------------------------------------------------------------------")

    # User Corrections & Promoted Tasks
    print("ADAPTIVE TASK PROMOTION (Rising Mistakes / User Halts):")
    promoted = corrections_summary.get("promoted_categories", [])
    if promoted:
        print(f"Active Promoted Categories ({len(promoted)} tasks escalated to Gemini):")
        for cat in promoted:
            cat_info = corrections_summary.get("categories", {}).get(cat, {})
            print(f"  * {cat:30} | Recurrence: {cat_info.get('recurrence', 1)} | Reason: {cat_info.get('reason', '')}")
    else:
        print("  - No categories currently promoted to Frontier.")

    print(f"\nTotal User Corrections Logged: {corrections_summary.get('total_corrections', 0)}")
    print("================================================================================")


def main() -> None:
    parser = argparse.ArgumentParser(description="Model routing analytics & user corrections inspector")
    parser.add_argument("--status", action="store_true", help="Display real-time model routing and analytics dashboard")
    parser.add_argument("--log-correction", action="store_true", help="Log a user halt, correction, or guidance directive")
    parser.add_argument("--category", type=str, default="general", help="Category of the correction (e.g. phone_formatting, notice_period)")
    parser.add_argument("--directive", type=str, default="", help="Exact guidance/directive from the user")
    parser.add_argument("--context", type=str, default="", help="Prompt or form context where correction occurred")
    parser.add_argument("--previous-mistake", type=str, default="", help="What previous mistake occurred")
    parser.add_argument("--severity", type=str, default="high", choices=["low", "medium", "high", "critical"])
    parser.add_argument("--test-routing", action="store_true", help="Run test assertions for routing and rescue")
    parser.add_argument("--reset-cooldowns", action="store_true", help="Clear all active rate-limit cooldowns")

    args = parser.parse_args()

    if args.log_correction:
        if not args.directive:
            print("Error: --directive is required when logging a correction.", file=sys.stderr)
            sys.exit(1)
        entry = log_user_correction(
            category=args.category,
            user_directive=args.directive,
            prompt_or_context=args.context,
            previous_mistake=args.previous_mistake,
            severity=args.severity,
        )
        print(f"Logged user correction for '{args.category}'. Promoted to Frontier: {entry.get('promoted_to_frontier')}")
        return

    if args.reset_cooldowns:
        router = get_model_router()
        router._cooldowns.clear()
        data = router.load_analytics()
        data["active_cooldowns"] = {}
        router.save_analytics(data)
        print("All model rate-limit cooldowns have been cleared.")
        return

    if args.test_routing:
        print("[test] Verifying chore routing...")
        r_chore = route_task("regex_field_extraction")
        assert r_chore["tier"] == TIER_CHORE, f"Expected chore, got {r_chore['tier']}"

        print("[test] Verifying promoted task routing...")
        r_promoted = route_task("phone_formatting")
        assert r_promoted["tier"] == TIER_FRONTIER, f"Expected frontier, got {r_promoted['tier']}"
        assert r_promoted["promoted"] is True

        print("[test] Verifying tool-call / JSON rescue helper...")
        malformed = "Here is the result:\n```json\n{'status': 'ok', 'score': 99,}\n```\nDone."
        rescued = rescue_json_output(malformed)
        assert rescued.get("status") == "ok", f"Rescue failed: {rescued}"

        print("All test assertions passed successfully!")
        return

    # Default to status view
    print_status()


if __name__ == "__main__":
    main()
