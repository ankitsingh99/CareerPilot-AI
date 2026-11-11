#!/usr/bin/env python3
"""
CLI for CareerPilot AI Mistake Ledger & Daily Frontier Routing Evaluator.

Usage:
    python tools/evaluate_mistakes.py evaluate
    python tools/evaluate_mistakes.py record --task cover_letter --severity high --category broken_metric --details "Dangling % found"
    python tools/evaluate_mistakes.py route --task ats_qa
    python tools/evaluate_mistakes.py status
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from intelligence.mistake_router import (
    DEFAULT_MISTAKE_DB,
    DEFAULT_REPORT_PATH,
    evaluate_daily_routing,
    evaluate_if_due,
    get_task_route,
    record_mistake,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Record mistakes and run daily deterministic evaluation for frontier model routing."
    )
    parser.add_argument("--db", type=Path, default=None, help=f"Optional SQLite DB path (default: {DEFAULT_MISTAKE_DB})")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_eval = sub.add_parser("evaluate", help="Run daily mistake evaluation and print Markdown/JSON summary")
    p_eval.add_argument("--window-hours", type=int, default=24, help="Rolling mistake window in hours (default: 24)")
    p_eval.add_argument("--if-due", action="store_true", help="Only evaluate if today's daily evaluation has not run yet")
    p_eval.add_argument("--json", action="store_true", help="Print JSON instead of Markdown")
    p_eval.add_argument("--report-out", type=Path, default=None, help=f"Optional Markdown report path (default: {DEFAULT_REPORT_PATH})")

    p_rec = sub.add_parser("record", help="Record a mistake event")
    p_rec.add_argument("--task", required=True, help="Task category (e.g. ats_qa, cover_letter, outreach, form_audit)")
    p_rec.add_argument("--severity", default="medium", choices=["low", "medium", "high", "critical"])
    p_rec.add_argument("--category", default="general", help="Mistake defect category")
    p_rec.add_argument("--model", default="unknown", help="Model or engine that made the mistake")
    p_rec.add_argument("--source", default="cli", help="Originating component or user feedback")
    p_rec.add_argument("--details", default="", help="Concise description of what went wrong")

    p_route = sub.add_parser("route", help="Inspect current routing decision for a task type")
    p_route.add_argument("--task", required=True, help="Task category to inspect")
    p_route.add_argument("--default-tier", default="chore", choices=["chore", "heavy", "draft", "auto"])

    p_status = sub.add_parser("status", help="Show latest daily evaluation summary across all task types")
    p_status.add_argument("--json", action="store_true", help="Print JSON instead of Markdown")

    args = parser.parse_args(argv)

    if args.cmd == "record":
        row_id = record_mistake(
            args.task,
            severity=args.severity,
            category=args.category,
            model_used=args.model,
            source=args.source,
            details=args.details,
            db_path=args.db,
        )
        route = get_task_route(args.task, db_path=args.db)
        print(json.dumps({"recorded_id": row_id, "route": route}, indent=2))
        return 0

    if args.cmd == "route":
        route = get_task_route(args.task, default_tier=args.default_tier, db_path=args.db)
        print(json.dumps(route, indent=2))
        return 0

    if args.cmd == "evaluate":
        if args.if_due:
            res = evaluate_if_due(window_hours=args.window_hours, db_path=args.db)
            if res is None:
                print(json.dumps({"status": "already_evaluated_today"}))
                return 0
        else:
            res = evaluate_daily_routing(
                window_hours=args.window_hours,
                report_path=args.report_out,
                db_path=args.db,
            )
        if args.json:
            print(json.dumps({k: v for k, v in res.items() if k != "report_markdown"}, indent=2))
        else:
            print(res["report_markdown"], end="")
        return 0

    if args.cmd == "status":
        res = evaluate_daily_routing(window_hours=24, report_path=None, db_path=args.db)
        if args.json:
            print(json.dumps({k: v for k, v in res.items() if k != "report_markdown"}, indent=2))
        else:
            print(res["report_markdown"], end="")
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

