#!/usr/bin/env python3
"""
core/model_router.py
--------------------
Cost-Intelligent Dynamic Model Router & Real-Time Analytics Engine.
Incorporates best-of-breed architectural patterns from FreeLLMAPI:
1. Multi-tier model routing (Cheaper/Free chore models vs Frontier/Gemini for high-reasoning).
2. Dynamic task promotion based on user corrections and mistake recurrence.
3. Tool-call / JSON output rescue for malformed lower-tier responses.
4. Automatic failover and 429/5xx sliding-window cooldown ledger.
5. Real-time token conservation and routing analytics.
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

ROOT = Path(__file__).resolve().parent.parent
ANALYTICS_PATH = ROOT / "user_inputs" / "model_routing_analytics.json"

TIER_CHORE = "chore"
TIER_FRONTIER = "frontier"

# High-reasoning tasks that default to Frontier/Gemini
DEFAULT_FRONTIER_TASKS = {
    "cover_letter_drafting",
    "cover_letter_humanizing",
    "company_outreach",
    "executive_dm",
    "ats_complex_questionnaire",
    "cv_fact_audit",
    "architectural_debug",
}

# Low-reasoning tasks that default to Chore (Cheaper/Free/Local)
DEFAULT_CHORE_TASKS = {
    "regex_field_extraction",
    "job_title_classification",
    "text_trimming_compression",
    "location_normalization",
    "simple_boolean_qa",
    "duplicate_check",
    "job_posting_triage",
}

# Default Cooldown duration in seconds on 429 Rate Limit
DEFAULT_COOLDOWN_SECONDS = 60.0


class OutputRescueError(Exception):
    """Raised when output from a cheaper model cannot be parsed or rescued."""
    pass


class ModelRouter:
    """Dynamic cost-intelligent router and real-time telemetry ledger."""

    def __init__(self, analytics_path: Optional[Path] = None):
        self.analytics_path = Path(analytics_path or ANALYTICS_PATH)
        self._cooldowns: Dict[str, float] = {}
        self._ensure_file()

    def _ensure_file(self) -> None:
        if not self.analytics_path.exists():
            self.analytics_path.parent.mkdir(parents=True, exist_ok=True)
            initial = {
                "version": "1.0.0",
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "totals": {
                    "total_requests": 0,
                    "chore_requests": 0,
                    "frontier_requests": 0,
                    "rescued_outputs": 0,
                    "rate_limits_encountered": 0,
                    "tokens_conserved_est": 0,
                },
                "tier_distribution_pct": {"chore": 0.0, "frontier": 0.0},
                "model_usage": {},
                "recent_events": [],
                "active_cooldowns": {},
            }
            self.analytics_path.write_text(json.dumps(initial, indent=2), encoding="utf-8")

    def load_analytics(self) -> Dict[str, Any]:
        self._ensure_file()
        try:
            return json.loads(self.analytics_path.read_text(encoding="utf-8"))
        except Exception:
            return {"totals": {}, "model_usage": {}, "recent_events": []}

    def save_analytics(self, data: Dict[str, Any]) -> None:
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        # Clean expired cooldowns from active_cooldowns view
        now = time.time()
        active = {m: round(exp - now, 1) for m, exp in self._cooldowns.items() if exp > now}
        data["active_cooldowns"] = active
        self.analytics_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def is_model_cooling_down(self, model: str) -> bool:
        """Check if a model is currently in a 429/error cooldown window."""
        exp = self._cooldowns.get(model, 0.0)
        return time.time() < exp

    def set_model_cooldown(self, model: str, duration_sec: float = DEFAULT_COOLDOWN_SECONDS) -> None:
        """Set a cooldown expiration for a model encountering 429 or 5xx."""
        self._cooldowns[model] = time.time() + duration_sec

    def route_task(
        self,
        task_type: str,
        *,
        context: Optional[Dict[str, Any]] = None,
        default_tier: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Determine optimal model tier for a given task.
        Promotes task to Frontier/Gemini if user corrections or mistakes are elevated.
        """
        norm_task = task_type.strip().lower().replace("-", "_").replace(" ", "_")

        # 1. Check User Corrections & Mistake Ledger
        from core.user_corrections_engine import is_category_promoted
        if is_category_promoted(norm_task):
            return {
                "task_type": norm_task,
                "tier": TIER_FRONTIER,
                "target_engine": "gemini",
                "promoted": True,
                "reason": "Promoted to Gemini: elevated user halts or corrections in this category.",
            }

        # 2. Check explicitly configured high-reasoning tasks
        if norm_task in DEFAULT_FRONTIER_TASKS:
            return {
                "task_type": norm_task,
                "tier": TIER_FRONTIER,
                "target_engine": "gemini",
                "promoted": False,
                "reason": "Default frontier task: requires complex reasoning, humanization, or high-stakes precision.",
            }

        # 3. Check requested tier override
        if default_tier == TIER_FRONTIER:
            return {
                "task_type": norm_task,
                "tier": TIER_FRONTIER,
                "target_engine": "gemini",
                "promoted": False,
                "reason": "Caller explicitly requested Frontier / Gemini tier.",
            }

        # 4. Default to Chore / Low-Reasoning tier
        return {
            "task_type": norm_task,
            "tier": TIER_CHORE,
            "target_engine": "cheaper_or_free",
            "promoted": False,
            "reason": "Routed to Chore tier: low-reasoning extraction or triage task.",
        }

    @staticmethod
    def rescue_json_output(raw_text: str) -> Union[Dict[str, Any], List[Any]]:
        """
        Tool-call and JSON output rescue helper (inspired by FreeLLMAPI).
        Cleans markdown formatting, chat fluff, trailing commas, and rescues malformed text into JSON.
        """
        if not raw_text or not raw_text.strip():
            raise OutputRescueError("Empty output cannot be rescued to JSON.")

        cleaned = raw_text.strip()

        # Extract content within ```json ... ``` or ``` ... ```
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
        if fence_match:
            cleaned = fence_match.group(1).strip()

        # Extract first JSON object {...} or array [...] if surrounded by chatter
        if not (cleaned.startswith("{") or cleaned.startswith("[")):
            obj_match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", cleaned)
            if obj_match:
                cleaned = obj_match.group(1).strip()

        # Remove trailing commas before closing braces/brackets
        cleaned = re.sub(r",\s*([\]}])", r"\1", cleaned)

        # Attempt standard JSON parse
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Attempt single-quote replacement for pythonic dictionaries
        try:
            py_converted = re.sub(r"\'", '"', cleaned)
            return json.loads(py_converted)
        except Exception:
            pass

        raise OutputRescueError(f"Failed to rescue JSON from raw output: {raw_text[:200]}")

    def record_routing_event(
        self,
        task_type: str,
        tier: str,
        model_used: str,
        *,
        tokens_in: int = 0,
        tokens_out: int = 0,
        latency_ms: float = 0.0,
        success: bool = True,
        rescued: bool = False,
        error_msg: str = "",
    ) -> None:
        """Record real-time execution analytics to the persistent ledger."""
        data = self.load_analytics()
        totals = data.setdefault("totals", {
            "total_requests": 0,
            "chore_requests": 0,
            "frontier_requests": 0,
            "rescued_outputs": 0,
            "rate_limits_encountered": 0,
            "tokens_conserved_est": 0,
        })
        model_usage = data.setdefault("model_usage", {})
        recent = data.setdefault("recent_events", [])

        totals["total_requests"] = totals.get("total_requests", 0) + 1
        if tier == TIER_CHORE:
            totals["chore_requests"] = totals.get("chore_requests", 0) + 1
            # Estimate tokens conserved by offloading from expensive frontier to chore
            totals["tokens_conserved_est"] = totals.get("tokens_conserved_est", 0) + (tokens_in + tokens_out)
        else:
            totals["frontier_requests"] = totals.get("frontier_requests", 0) + 1

        if rescued:
            totals["rescued_outputs"] = totals.get("rescued_outputs", 0) + 1

        if not success and ("429" in error_msg or "rate" in error_msg.lower()):
            totals["rate_limits_encountered"] = totals.get("rate_limits_encountered", 0) + 1
            self.set_model_cooldown(model_used)

        # Update percentage distribution
        tot = max(1, totals["total_requests"])
        data["tier_distribution_pct"] = {
            "chore": round((totals.get("chore_requests", 0) / tot) * 100, 1),
            "frontier": round((totals.get("frontier_requests", 0) / tot) * 100, 1),
        }

        # Update per-model stats
        m_entry = model_usage.setdefault(model_used, {"calls": 0, "success": 0, "failures": 0, "tokens": 0})
        m_entry["calls"] += 1
        if success:
            m_entry["success"] += 1
        else:
            m_entry["failures"] += 1
        m_entry["tokens"] += (tokens_in + tokens_out)

        # Append recent event (keep last 50)
        recent.insert(0, {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "task_type": task_type,
            "tier": tier,
            "model_used": model_used,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "latency_ms": round(latency_ms, 1),
            "success": success,
            "rescued": rescued,
            "error": error_msg[:200] if error_msg else None,
        })
        data["recent_events"] = recent[:50]

        self.save_analytics(data)

    def get_realtime_analytics(self) -> Dict[str, Any]:
        """Return aggregated real-time analytics."""
        data = self.load_analytics()
        from core.user_corrections_engine import get_user_corrections_engine
        corrections_summary = get_user_corrections_engine().get_corrections_summary()

        return {
            "totals": data.get("totals", {}),
            "tier_distribution_pct": data.get("tier_distribution_pct", {}),
            "active_cooldowns": data.get("active_cooldowns", {}),
            "model_usage": data.get("model_usage", {}),
            "user_corrections": corrections_summary,
            "recent_events_count": len(data.get("recent_events", [])),
        }


# Global singleton accessors
_ROUTER_INSTANCE: Optional[ModelRouter] = None


def get_model_router() -> ModelRouter:
    global _ROUTER_INSTANCE
    if _ROUTER_INSTANCE is None:
        _ROUTER_INSTANCE = ModelRouter()
    return _ROUTER_INSTANCE


def route_task(
    task_type: str,
    *,
    context: Optional[Dict[str, Any]] = None,
    default_tier: Optional[str] = None,
) -> Dict[str, Any]:
    return get_model_router().route_task(task_type, context=context, default_tier=default_tier)


def rescue_json_output(raw_text: str) -> Union[Dict[str, Any], List[Any]]:
    return ModelRouter.rescue_json_output(raw_text)


def record_routing_event(
    task_type: str,
    tier: str,
    model_used: str,
    *,
    tokens_in: int = 0,
    tokens_out: int = 0,
    latency_ms: float = 0.0,
    success: bool = True,
    rescued: bool = False,
    error_msg: str = "",
) -> None:
    get_model_router().record_routing_event(
        task_type,
        tier,
        model_used,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        latency_ms=latency_ms,
        success=success,
        rescued=rescued,
        error_msg=error_msg,
    )
