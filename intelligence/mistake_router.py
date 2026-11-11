"""
Mistake Ledger & Daily Frontier Routing Evaluator.

Records runtime mistakes (validation failures, formatting slop, hallucinations,
auth/API errors, and user corrections) with severity weights, then runs a daily
deterministic evaluation (0 LLM tokens) to decide which task types stay on local
or :free chore models, which step up to heavy :free models, and which must
escalate to a frontier model (Gemini / Pro).
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_MISTAKE_DB = Path.home() / ".cache" / "careerpilot" / "mistake_router.sqlite"
DEFAULT_REPORT_PATH = Path.home() / ".cache" / "careerpilot" / "daily_mistake_report.md"

SEVERITY_WEIGHTS: Dict[str, int] = {
    "low": 1,
    "medium": 3,
    "high": 7,
    "critical": 15,
}

SEVERITY_ORDER: Dict[str, int] = {
    "none": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}

TIER_FRONTIER = "frontier"
TIER_HEAVY = "openrouter_heavy"
TIER_LOCAL = "local_or_chore"

ESCALATION_THRESHOLDS = {
    "frontier_critical_min": 1,
    "frontier_high_min": 2,
    "frontier_score_min": 12,
    "frontier_count_min": 5,
    "heavy_high_min": 1,
    "heavy_score_min": 5,
    "heavy_count_min": 3,
    "deescalate_clean_severe_hours": 72,
}


def _resolve_db(db_path: Optional[Path] = None) -> Path:
    if db_path is not None:
        return Path(db_path)
    env_db = os.environ.get("CAREERPILOT_MISTAKE_DB", "").strip()
    if env_db:
        return Path(env_db)
    return DEFAULT_MISTAKE_DB


def is_auto_telemetry_enabled(db_path: Optional[Path] = None) -> bool:
    """Avoid mutating user home cache DB during unit/pytest test discovery unless explicitly configured."""
    if db_path is not None:
        return True
    if os.environ.get("CAREERPILOT_DISABLE_MISTAKE_TELEMETRY", "").strip() == "1":
        return False
    if os.environ.get("CAREERPILOT_MISTAKE_DB", "").strip():
        return True
    if os.environ.get("PYTEST_CURRENT_TEST") or "unittest" in sys.modules:
        return False
    return True


def _init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(db_path)) as conn, conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS mistake_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at REAL NOT NULL,
                event_date TEXT NOT NULL,
                task_type TEXT NOT NULL,
                model_used TEXT NOT NULL,
                severity TEXT NOT NULL,
                severity_weight INTEGER NOT NULL,
                category TEXT NOT NULL,
                source TEXT NOT NULL,
                details TEXT NOT NULL,
                context_json TEXT NOT NULL DEFAULT '{}'
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_mistake_task_time ON mistake_events(task_type, created_at)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_mistake_date ON mistake_events(event_date)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS task_routing_policy (
                task_type TEXT PRIMARY KEY,
                recommended_tier TEXT NOT NULL,
                openrouter_tier TEXT NOT NULL,
                requires_frontier INTEGER NOT NULL DEFAULT 0,
                mistake_count INTEGER NOT NULL DEFAULT 0,
                severity_score INTEGER NOT NULL DEFAULT 0,
                max_severity TEXT NOT NULL DEFAULT 'none',
                reason TEXT NOT NULL DEFAULT '',
                last_evaluated_date TEXT NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_evaluations (
                eval_date TEXT PRIMARY KEY,
                total_mistakes INTEGER NOT NULL,
                frontier_tasks_json TEXT NOT NULL,
                heavy_tasks_json TEXT NOT NULL,
                local_tasks_json TEXT NOT NULL,
                summary_json TEXT NOT NULL,
                evaluated_at REAL NOT NULL
            )
            """
        )


def _norm_task_type(task_type: str) -> str:
    cleaned = "_".join((task_type or "general").strip().lower().replace("-", "_").split())
    return cleaned or "general"


def _norm_severity(severity: str) -> str:
    sev = (severity or "medium").strip().lower()
    if sev not in SEVERITY_WEIGHTS:
        return "medium"
    return sev


def _tier_to_openrouter_tier(recommended_tier: str, default_tier: str = "chore") -> str:
    if recommended_tier in (TIER_FRONTIER, TIER_HEAVY):
        return "heavy"
    return default_tier if default_tier in ("chore", "heavy", "draft", "auto") else "chore"


def record_mistake(
    task_type: str,
    *,
    severity: str = "medium",
    category: str = "general",
    model_used: str = "unknown",
    source: str = "runtime",
    details: str = "",
    context: Optional[Dict[str, Any]] = None,
    created_at: Optional[float] = None,
    db_path: Optional[Path] = None,
) -> int:
    """Persist a mistake event; critical events immediately trip frontier escalation."""
    ts = float(created_at if created_at is not None else time.time())
    dt = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
    t_type = _norm_task_type(task_type)
    sev = _norm_severity(severity)
    weight = SEVERITY_WEIGHTS[sev]
    target_db = _resolve_db(db_path)

    _init_db(target_db)
    with closing(sqlite3.connect(target_db)) as conn, conn:
        cur = conn.execute(
            """
            INSERT INTO mistake_events (
                created_at, event_date, task_type, model_used,
                severity, severity_weight, category, source, details, context_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ts,
                dt,
                t_type,
                (model_used or "unknown").strip(),
                sev,
                weight,
                (category or "general").strip(),
                (source or "runtime").strip(),
                (details or "").strip()[:1000],
                json.dumps(context or {}, sort_keys=True),
            ),
        )
        row_id = int(cur.lastrowid or 0)

        # Real-time circuit breaker: critical mistakes escalate immediately.
        if sev == "critical":
            conn.execute(
                """
                INSERT INTO task_routing_policy (
                    task_type, recommended_tier, openrouter_tier, requires_frontier,
                    mistake_count, severity_score, max_severity, reason, last_evaluated_date, updated_at
                ) VALUES (?, ?, ?, ?, 1, ?, 'critical', ?, ?, ?)
                ON CONFLICT(task_type) DO UPDATE SET
                    recommended_tier = excluded.recommended_tier,
                    openrouter_tier = excluded.openrouter_tier,
                    requires_frontier = 1,
                    mistake_count = task_routing_policy.mistake_count + 1,
                    severity_score = task_routing_policy.severity_score + excluded.severity_score,
                    max_severity = 'critical',
                    reason = excluded.reason,
                    last_evaluated_date = excluded.last_evaluated_date,
                    updated_at = excluded.updated_at
                """,
                (
                    t_type,
                    TIER_FRONTIER,
                    "heavy",
                    1,
                    weight,
                    f"Immediate circuit-breaker escalation on critical mistake ({category})",
                    dt,
                    ts,
                ),
            )
    return row_id


def record_mistake_if_enabled(
    task_type: str,
    *,
    severity: str = "medium",
    category: str = "general",
    model_used: str = "unknown",
    source: str = "runtime",
    details: str = "",
    context: Optional[Dict[str, Any]] = None,
    db_path: Optional[Path] = None,
) -> Optional[int]:
    """Safe telemetry wrapper for automatic hooks in core/parser modules."""
    if not is_auto_telemetry_enabled(db_path):
        return None
    try:
        return record_mistake(
            task_type,
            severity=severity,
            category=category,
            model_used=model_used,
            source=source,
            details=details,
            context=context,
            db_path=db_path,
        )
    except Exception:
        return None


def _classify_task_window(
    mistake_count: int,
    severity_score: int,
    high_count: int,
    critical_count: int,
    prev_tier: Optional[str],
    recent_severe_72h: int,
) -> tuple[str, str]:
    if critical_count >= ESCALATION_THRESHOLDS["frontier_critical_min"]:
        return TIER_FRONTIER, f"critical_count={critical_count} (>=1 critical mistake)"
    if high_count >= ESCALATION_THRESHOLDS["frontier_high_min"]:
        return TIER_FRONTIER, f"high_count={high_count} (>=2 high-severity mistakes)"
    if severity_score >= ESCALATION_THRESHOLDS["frontier_score_min"]:
        return TIER_FRONTIER, f"severity_score={severity_score} (>=12 threshold)"
    if mistake_count >= ESCALATION_THRESHOLDS["frontier_count_min"]:
        return TIER_FRONTIER, f"mistake_count={mistake_count} (>=5 daily mistakes)"

    if (
        high_count >= ESCALATION_THRESHOLDS["heavy_high_min"]
        or severity_score >= ESCALATION_THRESHOLDS["heavy_score_min"]
        or mistake_count >= ESCALATION_THRESHOLDS["heavy_count_min"]
    ):
        return TIER_HEAVY, f"severity_score={severity_score}, mistakes={mistake_count} (heavy :free tier)"

    # Controlled step-down de-escalation when clean streak holds.
    if mistake_count == 0 and recent_severe_72h == 0:
        if prev_tier == TIER_FRONTIER:
            return TIER_HEAVY, "0 mistakes today and 0 severe mistakes in 72h: stepped down frontier -> openrouter_heavy"
        if prev_tier == TIER_HEAVY:
            return TIER_LOCAL, "0 mistakes today and 0 severe mistakes in 72h: stepped down openrouter_heavy -> local_or_chore"

    if prev_tier == TIER_FRONTIER and recent_severe_72h > 0:
        return TIER_FRONTIER, "Retained on frontier pending 72h clean severe-mistake streak"
    if prev_tier == TIER_HEAVY and mistake_count > 0:
        return TIER_HEAVY, f"Retained on openrouter_heavy (mistakes={mistake_count})"

    return TIER_LOCAL, f"severity_score={severity_score}, mistakes={mistake_count} (within local/chore bounds)"


def format_daily_report(evaluation: Dict[str, Any]) -> str:
    """Render concise Markdown report for the daily mistake evaluation."""
    lines = [
        f"# Daily Mistake & Frontier Routing Evaluation ({evaluation['eval_date']})",
        "",
        f"- **Window:** Last {evaluation['window_hours']}h",
        f"- **Total Mistakes Logged:** {evaluation['total_mistakes']}",
        f"- **Escalate to Frontier:** {', '.join(evaluation['frontier_tasks']) or 'None'}",
        f"- **Route to OpenRouter Heavy (:free):** {', '.join(evaluation['heavy_tasks']) or 'None'}",
        f"- **Keep Local / Chore:** {', '.join(evaluation['local_tasks']) or 'None'}",
        "",
        "| Task Type | Mistakes | Severity Score | Max Severity | Decision | Rationale |",
        "| :--- | :---: | :---: | :---: | :--- | :--- |",
    ]
    tasks = evaluation.get("tasks", {})
    if not tasks:
        lines.append("| (none) | 0 | 0 | none | local_or_chore | No mistakes recorded in window |")
    else:
        for task_type, info in sorted(
            tasks.items(),
            key=lambda kv: (-kv[1]["severity_score"], -kv[1]["mistake_count"], kv[0]),
        ):
            lines.append(
                f"| `{task_type}` | {info['mistake_count']} | {info['severity_score']} "
                f"| {info['max_severity']} | `{info['recommended_tier']}` | {info['reason']} |"
            )
    return "\n".join(lines) + "\n"


def evaluate_daily_routing(
    *,
    eval_date: Optional[str] = None,
    now_ts: Optional[float] = None,
    window_hours: int = 24,
    report_path: Optional[Path] = None,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Evaluate recorded mistakes and update per-task frontier routing policy."""
    ts = float(now_ts if now_ts is not None else time.time())
    resolved_date = eval_date or datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
    window_start = ts - (max(1, window_hours) * 3600)
    severe_window_start = ts - (ESCALATION_THRESHOLDS["deescalate_clean_severe_hours"] * 3600)

    target_db = _resolve_db(db_path)
    _init_db(target_db)

    with closing(sqlite3.connect(target_db)) as conn:
        conn.row_factory = sqlite3.Row
        prev_policies = {
            r["task_type"]: dict(r)
            for r in conn.execute("SELECT * FROM task_routing_policy").fetchall()
        }
        window_rows = conn.execute(
            """
            SELECT task_type, severity, severity_weight, category, model_used
            FROM mistake_events
            WHERE created_at >= ? AND created_at <= ?
            """,
            (window_start, ts),
        ).fetchall()
        recent_severe_rows = conn.execute(
            """
            SELECT task_type, COUNT(*) AS cnt
            FROM mistake_events
            WHERE created_at >= ? AND created_at <= ? AND severity IN ('high', 'critical')
            GROUP BY task_type
            """,
            (severe_window_start, ts),
        ).fetchall()
        recent_severe_map = {r["task_type"]: int(r["cnt"]) for r in recent_severe_rows}

    agg: Dict[str, Dict[str, Any]] = {}
    for row in window_rows:
        t_type = row["task_type"]
        entry = agg.setdefault(
            t_type,
            {
                "mistake_count": 0,
                "severity_score": 0,
                "max_severity": "none",
                "high_count": 0,
                "critical_count": 0,
                "categories": {},
            },
        )
        sev = row["severity"]
        entry["mistake_count"] += 1
        entry["severity_score"] += int(row["severity_weight"])
        if SEVERITY_ORDER.get(sev, 0) > SEVERITY_ORDER.get(entry["max_severity"], 0):
            entry["max_severity"] = sev
        if sev == "high":
            entry["high_count"] += 1
        elif sev == "critical":
            entry["critical_count"] += 1
        cat = row["category"]
        entry["categories"][cat] = entry["categories"].get(cat, 0) + 1

    all_tasks = sorted(set(prev_policies.keys()) | set(agg.keys()))
    task_results: Dict[str, Dict[str, Any]] = {}
    frontier_tasks: List[str] = []
    heavy_tasks: List[str] = []
    local_tasks: List[str] = []

    for t_type in all_tasks:
        stats = agg.get(
            t_type,
            {
                "mistake_count": 0,
                "severity_score": 0,
                "max_severity": "none",
                "high_count": 0,
                "critical_count": 0,
                "categories": {},
            },
        )
        prev_tier = prev_policies.get(t_type, {}).get("recommended_tier")
        tier, reason = _classify_task_window(
            stats["mistake_count"],
            stats["severity_score"],
            stats["high_count"],
            stats["critical_count"],
            prev_tier,
            recent_severe_map.get(t_type, 0),
        )
        requires_frontier = tier == TIER_FRONTIER
        openrouter_tier = _tier_to_openrouter_tier(tier)

        task_results[t_type] = {
            "task_type": t_type,
            "recommended_tier": tier,
            "openrouter_tier": openrouter_tier,
            "requires_frontier": requires_frontier,
            "mistake_count": stats["mistake_count"],
            "severity_score": stats["severity_score"],
            "max_severity": stats["max_severity"],
            "high_count": stats["high_count"],
            "critical_count": stats["critical_count"],
            "categories": stats["categories"],
            "reason": reason,
        }
        if tier == TIER_FRONTIER:
            frontier_tasks.append(t_type)
        elif tier == TIER_HEAVY:
            heavy_tasks.append(t_type)
        else:
            local_tasks.append(t_type)

    total_mistakes = sum(r["mistake_count"] for r in task_results.values())
    evaluation = {
        "eval_date": resolved_date,
        "window_hours": window_hours,
        "total_mistakes": total_mistakes,
        "frontier_tasks": sorted(frontier_tasks),
        "heavy_tasks": sorted(heavy_tasks),
        "local_tasks": sorted(local_tasks),
        "tasks": task_results,
    }
    report_md = format_daily_report(evaluation)
    evaluation["report_markdown"] = report_md

    with closing(sqlite3.connect(target_db)) as conn, conn:
        for t_type, info in task_results.items():
            conn.execute(
                """
                INSERT INTO task_routing_policy (
                    task_type, recommended_tier, openrouter_tier, requires_frontier,
                    mistake_count, severity_score, max_severity, reason, last_evaluated_date, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_type) DO UPDATE SET
                    recommended_tier = excluded.recommended_tier,
                    openrouter_tier = excluded.openrouter_tier,
                    requires_frontier = excluded.requires_frontier,
                    mistake_count = excluded.mistake_count,
                    severity_score = excluded.severity_score,
                    max_severity = excluded.max_severity,
                    reason = excluded.reason,
                    last_evaluated_date = excluded.last_evaluated_date,
                    updated_at = excluded.updated_at
                """,
                (
                    t_type,
                    info["recommended_tier"],
                    info["openrouter_tier"],
                    1 if info["requires_frontier"] else 0,
                    info["mistake_count"],
                    info["severity_score"],
                    info["max_severity"],
                    info["reason"],
                    resolved_date,
                    ts,
                ),
            )
        conn.execute(
            """
            INSERT OR REPLACE INTO daily_evaluations (
                eval_date, total_mistakes, frontier_tasks_json, heavy_tasks_json,
                local_tasks_json, summary_json, evaluated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                resolved_date,
                total_mistakes,
                json.dumps(evaluation["frontier_tasks"]),
                json.dumps(evaluation["heavy_tasks"]),
                json.dumps(evaluation["local_tasks"]),
                json.dumps(task_results),
                ts,
            ),
        )

    out_report = report_path if report_path is not None else (DEFAULT_REPORT_PATH if target_db == DEFAULT_MISTAKE_DB else None)
    if out_report is not None:
        out_report.parent.mkdir(parents=True, exist_ok=True)
        out_report.write_text(report_md, encoding="utf-8")

    return evaluation


def evaluate_if_due(
    *,
    now_ts: Optional[float] = None,
    window_hours: int = 24,
    db_path: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    """Run daily evaluation automatically at most once per calendar day (UTC)."""
    ts = float(now_ts if now_ts is not None else time.time())
    today = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
    target_db = _resolve_db(db_path)
    _init_db(target_db)

    with closing(sqlite3.connect(target_db)) as conn:
        row = conn.execute(
            "SELECT 1 FROM daily_evaluations WHERE eval_date = ?",
            (today,),
        ).fetchone()
    if row is not None:
        return None
    return evaluate_daily_routing(eval_date=today, now_ts=ts, window_hours=window_hours, db_path=target_db)


def get_task_route(
    task_type: str,
    default_tier: str = "chore",
    *,
    auto_evaluate: bool = False,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Return the active routing policy for a task_type based on evaluated mistake history."""
    t_type = _norm_task_type(task_type)
    target_db = _resolve_db(db_path)

    if auto_evaluate and is_auto_telemetry_enabled(db_path):
        try:
            evaluate_if_due(db_path=target_db)
        except Exception:
            pass

    if not target_db.exists():
        return {
            "task_type": t_type,
            "recommended_tier": TIER_LOCAL,
            "openrouter_tier": _tier_to_openrouter_tier(TIER_LOCAL, default_tier=default_tier),
            "requires_frontier": False,
            "mistake_count": 0,
            "severity_score": 0,
            "max_severity": "none",
            "reason": "No mistake history yet; using default local/chore tier",
        }

    try:
        with closing(sqlite3.connect(target_db)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM task_routing_policy WHERE task_type = ?",
                (t_type,),
            ).fetchone()
        if row:
            rec_tier = row["recommended_tier"]
            return {
                "task_type": t_type,
                "recommended_tier": rec_tier,
                "openrouter_tier": row["openrouter_tier"],
                "requires_frontier": bool(row["requires_frontier"]),
                "mistake_count": int(row["mistake_count"]),
                "severity_score": int(row["severity_score"]),
                "max_severity": row["max_severity"],
                "reason": row["reason"],
                "last_evaluated_date": row["last_evaluated_date"],
            }
    except Exception:
        pass

    return {
        "task_type": t_type,
        "recommended_tier": TIER_LOCAL,
        "openrouter_tier": _tier_to_openrouter_tier(TIER_LOCAL, default_tier=default_tier),
        "requires_frontier": False,
        "mistake_count": 0,
        "severity_score": 0,
        "max_severity": "none",
        "reason": "No policy override; using default tier",
    }

