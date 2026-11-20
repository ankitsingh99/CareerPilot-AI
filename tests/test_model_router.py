#!/usr/bin/env python3
"""Unit tests for core/model_router.py."""

import json
import tempfile
import unittest
from pathlib import Path

from core.model_router import (
    ModelRouter,
    OutputRescueError,
    TIER_CHORE,
    TIER_FRONTIER,
)


class TestModelRouter(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.analytics_path = Path(self.td.name) / "test_analytics.json"
        self.router = ModelRouter(analytics_path=self.analytics_path)

    def tearDown(self):
        self.td.cleanup()

    def test_route_chore_vs_frontier(self):
        r_chore = self.router.route_task("regex_field_extraction")
        self.assertEqual(r_chore["tier"], TIER_CHORE)

        r_frontier = self.router.route_task("cover_letter_drafting")
        self.assertEqual(r_frontier["tier"], TIER_FRONTIER)

    def test_rescue_json_markdown_code_fence(self):
        raw = """Here is your JSON response:
```json
{
  "key": "value",
  "score": 100,
}
```
Thanks!"""
        rescued = self.router.rescue_json_output(raw)
        self.assertEqual(rescued, {"key": "value", "score": 100})

    def test_rescue_json_unfenced_with_chatter(self):
        raw = "Output: [1, 2, 3,] and that is all."
        rescued = self.router.rescue_json_output(raw)
        self.assertEqual(rescued, [1, 2, 3])

    def test_rescue_json_raises_on_invalid(self):
        with self.assertRaises(OutputRescueError):
            self.router.rescue_json_output("No json whatsoever in this output.")

    def test_cooldown_on_rate_limit(self):
        model = "test-provider/test-model:free"
        self.assertFalse(self.router.is_model_cooling_down(model))

        self.router.record_routing_event(
            "test_task",
            TIER_CHORE,
            model,
            success=False,
            error_msg="HTTP 429 Too Many Requests: Rate limit exceeded",
        )
        self.assertTrue(self.router.is_model_cooling_down(model))

    def test_analytics_recording_and_conservation(self):
        self.router.record_routing_event(
            "regex_field_extraction",
            TIER_CHORE,
            "fast-model:free",
            tokens_in=100,
            tokens_out=50,
            latency_ms=80.0,
            success=True,
        )
        self.router.record_routing_event(
            "cover_letter_drafting",
            TIER_FRONTIER,
            "gemini-pro",
            tokens_in=500,
            tokens_out=250,
            latency_ms=900.0,
            success=True,
        )
        analytics = self.router.get_realtime_analytics()
        self.assertEqual(analytics["totals"]["total_requests"], 2)
        self.assertEqual(analytics["totals"]["chore_requests"], 1)
        self.assertEqual(analytics["totals"]["frontier_requests"], 1)
        self.assertEqual(analytics["totals"]["tokens_conserved_est"], 150)
        self.assertEqual(analytics["tier_distribution_pct"]["chore"], 50.0)


if __name__ == "__main__":
    unittest.main()
