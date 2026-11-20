#!/usr/bin/env python3
"""
core/user_corrections_engine.py
-------------------------------
User Correction, Halt & Adaptive Task Promotion Engine.

Tracks instances where the user has halted, corrected, or guided the agent.
Maintains a persistent JSON ledger and SQLite records.
Automatically promotes tasks with rising mistakes or recurring user corrections
to be handled by higher-reasoning frontier models (Gemini / Pro).
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOG_PATH = ROOT / "user_inputs" / "user_corrections_log.json"

SEVERITY_ORDER = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


class UserCorrectionsEngine:
    """Manages the user correction ledger and adaptive model promotion."""

    def __init__(self, log_path: Optional[Path] = None):
        self.log_path = Path(log_path or DEFAULT_LOG_PATH)
        self._ensure_file()

    def _ensure_file(self) -> None:
        if not self.log_path.exists():
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            initial = {
                "version": "1.0.0",
                "description": "Persistent ledger of user halts, corrections, and explicit directives.",
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "promotion_threshold": {
                    "min_critical_corrections": 1,
                    "min_high_corrections": 2,
                    "min_total_corrections": 3,
                },
                "corrections": [],
            }
            self.log_path.write_text(json.dumps(initial, indent=2), encoding="utf-8")

    def load_log(self) -> Dict[str, Any]:
        self._ensure_file()
        try:
            return json.loads(self.log_path.read_text(encoding="utf-8"))
        except Exception:
            return {"corrections": [], "promotion_threshold": {}}

    def save_log(self, data: Dict[str, Any]) -> None:
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.log_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def log_user_correction(
        self,
        category: str,
        user_directive: str,
        *,
        prompt_or_context: str = "",
        previous_mistake: str = "",
        resolved_action: str = "",
        severity: str = "high",
        corr_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record or update a user correction. Evaluates adaptive promotion immediately."""
        data = self.load_log()
        corrections = data.get("corrections", [])
        thresholds = data.get("promotion_threshold", {
            "min_critical_corrections": 1,
            "min_high_corrections": 2,
            "min_total_corrections": 3,
        })

        norm_cat = category.strip().lower().replace(" ", "_")
        sev = severity.strip().lower()
        if sev not in SEVERITY_ORDER:
            sev = "high"

        # Check if an existing correction for this category exists
        target_entry = None
        for entry in corrections:
            if (corr_id and entry.get("id") == corr_id) or entry.get("category") == norm_cat:
                target_entry = entry
                break

        now_iso = datetime.now(timezone.utc).isoformat()

        if target_entry:
            target_entry["recurrence_count"] = target_entry.get("recurrence_count", 1) + 1
            target_entry["timestamp"] = now_iso
            target_entry["user_directive"] = user_directive
            if prompt_or_context:
                target_entry["prompt_or_context"] = prompt_or_context
            if previous_mistake:
                target_entry["previous_mistake"] = previous_mistake
            if resolved_action:
                target_entry["resolved_action"] = resolved_action
            if SEVERITY_ORDER[sev] > SEVERITY_ORDER.get(target_entry.get("severity", "medium"), 1):
                target_entry["severity"] = sev
        else:
            cid = corr_id or f"{norm_cat}_{int(time.time())}"
            target_entry = {
                "id": cid,
                "category": norm_cat,
                "timestamp": now_iso,
                "prompt_or_context": prompt_or_context,
                "previous_mistake": previous_mistake,
                "user_directive": user_directive,
                "resolved_action": resolved_action or "Recorded candidate directive.",
                "severity": sev,
                "recurrence_count": 1,
                "promoted_to_frontier": False,
                "promotion_reason": "",
            }
            corrections.append(target_entry)

        # Evaluate promotion status
        crit_count = sum(1 for c in corrections if c.get("category") == norm_cat and c.get("severity") == "critical")
        high_count = sum(1 for c in corrections if c.get("category") == norm_cat and c.get("severity") == "high")
        tot_count = target_entry.get("recurrence_count", 1)

        should_promote = (
            crit_count >= thresholds.get("min_critical_corrections", 1)
            or high_count >= thresholds.get("min_high_corrections", 2)
            or tot_count >= thresholds.get("min_total_corrections", 3)
        )

        if should_promote:
            target_entry["promoted_to_frontier"] = True
            target_entry["promotion_reason"] = (
                f"Escalated to higher reasoning: {tot_count} user corrections/halts "
                f"(severity: {target_entry.get('severity')})"
            )
        else:
            target_entry["promoted_to_frontier"] = False
            target_entry["promotion_reason"] = "Within standard tolerance."

        data["corrections"] = corrections
        self.save_log(data)

        # Synchronize with mistake_router telemetry if available
        try:
            from intelligence.mistake_router import record_mistake_if_enabled
            record_mistake_if_enabled(
                task_type=norm_cat,
                severity=sev,
                category="user_correction",
                model_used="agent_prompt",
                source="user_halt",
                details=f"{user_directive} | Context: {prompt_or_context[:200]}",
            )
        except Exception:
            pass

        return target_entry

    def is_category_promoted(self, category: str) -> bool:
        """Check if a task category is currently promoted to higher reasoning."""
        norm_cat = category.strip().lower().replace(" ", "_")
        data = self.load_log()
        for entry in data.get("corrections", []):
            if entry.get("category") == norm_cat and entry.get("promoted_to_frontier"):
                return True
        return False

    def get_promoted_categories(self) -> List[str]:
        """Return all categories currently promoted to higher reasoning."""
        data = self.load_log()
        promoted = []
        for entry in data.get("corrections", []):
            if entry.get("promoted_to_frontier"):
                promoted.append(entry.get("category"))
        return sorted(list(set(promoted)))

    def get_corrections_summary(self) -> Dict[str, Any]:
        """Return summary of all logged user corrections and their promotion states."""
        data = self.load_log()
        corrections = data.get("corrections", [])
        promoted = [c for c in corrections if c.get("promoted_to_frontier")]

        by_cat = {}
        for c in corrections:
            cat = c.get("category", "general")
            by_cat[cat] = {
                "recurrence": c.get("recurrence_count", 1),
                "severity": c.get("severity", "medium"),
                "promoted": c.get("promoted_to_frontier", False),
                "reason": c.get("promotion_reason", ""),
            }

        return {
            "total_corrections": len(corrections),
            "total_promoted": len(promoted),
            "promoted_categories": self.get_promoted_categories(),
            "categories": by_cat,
        }


# Global singleton accessors
_ENGINE_INSTANCE: Optional[UserCorrectionsEngine] = None


def get_user_corrections_engine() -> UserCorrectionsEngine:
    global _ENGINE_INSTANCE
    if _ENGINE_INSTANCE is None:
        _ENGINE_INSTANCE = UserCorrectionsEngine()
    return _ENGINE_INSTANCE


def is_category_promoted(category: str) -> bool:
    return get_user_corrections_engine().is_category_promoted(category)


def log_user_correction(
    category: str,
    user_directive: str,
    *,
    prompt_or_context: str = "",
    previous_mistake: str = "",
    resolved_action: str = "",
    severity: str = "high",
    corr_id: Optional[str] = None,
) -> Dict[str, Any]:
    return get_user_corrections_engine().log_user_correction(
        category,
        user_directive,
        prompt_or_context=prompt_or_context,
        previous_mistake=previous_mistake,
        resolved_action=resolved_action,
        severity=severity,
        corr_id=corr_id,
    )
