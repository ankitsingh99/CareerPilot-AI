"""Unit tests for Mistake Ledger & Daily Frontier Routing Evaluator."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from intelligence import mistake_router


class TestMistakeRouter(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "mistake_router.sqlite"
        self.report_path = Path(self._tmp.name) / "daily_report.md"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_daily_evaluation_tiers_by_severity_and_count(self) -> None:
        now = 1_760_000_000.0
        # 1. Low-severity single mistake -> stays local_or_chore
        mistake_router.record_mistake(
            "domain_classification",
            severity="low",
            category="minor_typo",
            created_at=now - 60,
            db_path=self.db_path,
        )
        # 2. One high mistake (weight=7) -> steps up to openrouter_heavy
        mistake_router.record_mistake(
            "ats_textarea",
            severity="high",
            category="weak_answer",
            created_at=now - 60,
            db_path=self.db_path,
        )
        # 3. Five medium mistakes (count=5, score=15) -> escalates to frontier
        for idx in range(5):
            mistake_router.record_mistake(
                "ats_qa",
                severity="medium",
                category=f"mismatch_{idx}",
                created_at=now - 30 - idx,
                db_path=self.db_path,
            )
        # 4. Single critical mistake -> immediate frontier escalation
        mistake_router.record_mistake(
            "form_audit",
            severity="critical",
            category="ZERO_REFERENCE_FABRICATION",
            created_at=now - 10,
            db_path=self.db_path,
        )

        # Critical circuit breaker works even before daily run
        pre_eval_route = mistake_router.get_task_route("form_audit", db_path=self.db_path)
        self.assertTrue(pre_eval_route["requires_frontier"])
        self.assertEqual(pre_eval_route["recommended_tier"], mistake_router.TIER_FRONTIER)

        res = mistake_router.evaluate_daily_routing(
            eval_date="2026-11-11",
            now_ts=now,
            report_path=self.report_path,
            db_path=self.db_path,
        )
        self.assertEqual(res["total_mistakes"], 8)
        self.assertIn("domain_classification", res["local_tasks"])
        self.assertIn("ats_textarea", res["heavy_tasks"])
        self.assertIn("ats_qa", res["frontier_tasks"])
        self.assertIn("form_audit", res["frontier_tasks"])
        self.assertTrue(self.report_path.exists())
        self.assertIn("Daily Mistake & Frontier Routing Evaluation", self.report_path.read_text(encoding="utf-8"))

    def test_deescalation_and_daily_idempotency(self) -> None:
        day1 = 1_760_000_000.0
        mistake_router.record_mistake(
            "outreach",
            severity="high",
            category="tone_issue",
            created_at=day1 - 100,
            db_path=self.db_path,
        )
        mistake_router.record_mistake(
            "outreach",
            severity="high",
            category="fact_issue",
            created_at=day1 - 50,
            db_path=self.db_path,
        )
        r1 = mistake_router.evaluate_if_due(now_ts=day1, db_path=self.db_path)
        self.assertIsNotNone(r1)
        self.assertIn("outreach", r1["frontier_tasks"])

        # Same day: evaluate_if_due returns None (runs once per day)
        self.assertIsNone(mistake_router.evaluate_if_due(now_ts=day1 + 120, db_path=self.db_path))

        # 4 days (>72h) later with 0 mistakes -> steps down frontier -> openrouter_heavy
        day5 = day1 + (4 * 86400)
        r2 = mistake_router.evaluate_if_due(now_ts=day5, db_path=self.db_path)
        self.assertIsNotNone(r2)
        self.assertIn("outreach", r2["heavy_tasks"])

        # Next day still 0 mistakes -> steps down openrouter_heavy -> local_or_chore
        day6 = day5 + 86400
        r3 = mistake_router.evaluate_if_due(now_ts=day6, db_path=self.db_path)
        self.assertIsNotNone(r3)
        self.assertIn("outreach", r3["local_tasks"])

    def test_hooks_in_evaluator_linter_and_openrouter_escalation(self) -> None:
        from core.adaptive_evaluator import AdaptiveEvaluator
        from parsers.linter import lint_and_format
        from intelligence.llm_clients import openrouter

        with patch.dict(os.environ, {"CAREERPILOT_MISTAKE_DB": str(self.db_path)}):
            audit = AdaptiveEvaluator.audit_form_state(
                {"references": [{"name": "Fake Boss", "phone": "999", "email": "x@y.com"}]}
            )
            self.assertFalse(audit["passed"])

            lint_res = lint_and_format("Reduced production defects by % across Snowflake pipelines.")
            self.assertFalse(lint_res["passed"])

        form_route = mistake_router.get_task_route("form_audit", db_path=self.db_path)
        self.assertTrue(form_route["requires_frontier"])

        eval_res = mistake_router.evaluate_daily_routing(
            eval_date="2026-11-11",
            db_path=self.db_path,
        )
        self.assertIn("cover_letter", eval_res["heavy_tasks"])
        self.assertIn("form_audit", eval_res["frontier_tasks"])

        # Verify OpenRouter dispatcher honors escalated tier when task_type is passed
        captured_tiers = []

        def fake_select(model, pool, task_tier="auto"):
            captured_tiers.append(task_tier)
            return ["google/gemma-4-31b-it:free"]

        class DummyResp:
            def read(self):
                return json.dumps({
                    "choices": [{"message": {"content": "Escalated answer"}}],
                    "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
                }).encode("utf-8")

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        with (
            patch.dict(os.environ, {
                "CAREERPILOT_MISTAKE_DB": str(self.db_path),
                "OPENROUTER_ON_DEMAND_ENABLED": "1",
            }),
            patch.object(openrouter, "get_cached_response", return_value=None),
            patch.object(openrouter, "save_cached_response"),
            patch.object(openrouter, "_load_key", return_value="sk-or-test"),
            patch.object(openrouter, "fetch_free_models", return_value=["google/gemma-4-31b-it:free"]),
            patch.object(openrouter, "select_free_models_for_tier", side_effect=fake_select),
            patch("urllib.request.urlopen", return_value=DummyResp()),
        ):
            out = openrouter.ask(
                "Draft letter check",
                model="auto",
                task_tier="chore",
                task_type="cover_letter",
            )
            self.assertEqual(out, "Escalated answer")
            self.assertEqual(captured_tiers, ["heavy"])

    def test_cli_record_and_evaluate(self) -> None:
        from tools.evaluate_mistakes import main as cli_main

        rc1 = cli_main([
            "--db", str(self.db_path),
            "record", "--task", "outreach", "--severity", "high",
            "--category", "fact_mismatch", "--details", "Wrong company metric",
        ])
        self.assertEqual(rc1, 0)
        rc2 = cli_main([
            "--db", str(self.db_path),
            "evaluate", "--json", "--report-out", str(self.report_path),
        ])
        self.assertEqual(rc2, 0)
        self.assertTrue(self.report_path.exists())


if __name__ == "__main__":
    unittest.main()

