#!/usr/bin/env python3
"""
Tests for OpenRouter zero-cost free models client and validation.
Uses standard library unittest.TestCase for full compatibility with GitHub CI unittest runner and pytest.
"""
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from intelligence.llm_clients.openrouter import (
    DEFAULT_FREE_MODEL,
    FREE_MODELS_POOL,
    CHORE_FREE_MODELS,
    HEAVY_FREE_MODELS,
    is_free_model,
    is_on_demand_enabled,
    select_free_models_for_tier,
    fetch_free_models,
    get_free_models,
    ask,
)


class TestOpenRouter(unittest.TestCase):
    def test_default_free_model_is_valid(self):
        self.assertTrue(is_free_model(DEFAULT_FREE_MODEL))
        self.assertTrue(DEFAULT_FREE_MODEL.endswith(":free"))

    def test_is_free_model(self):
        # Valid free tier endpoints
        self.assertTrue(is_free_model("cohere/north-mini-code:free"))
        self.assertTrue(is_free_model("google/gemma-4-31b-it:free"))
        self.assertTrue(is_free_model("openrouter/free"))
        self.assertTrue(is_free_model("auto"))
        self.assertTrue(is_free_model("any"))

        # Disallowed billable / non-free endpoints
        self.assertFalse(is_free_model("openai/gpt-4o"))
        self.assertFalse(is_free_model("anthropic/claude-3.5-sonnet"))
        self.assertFalse(is_free_model("meta-llama/llama-3-70b-instruct"))
        self.assertFalse(is_free_model(""))

    def test_fetch_free_models_structure(self):
        models = fetch_free_models()
        self.assertIsInstance(models, list)
        self.assertGreater(len(models), 0)
        for model in models:
            self.assertTrue(is_free_model(model), f"Model {model} must satisfy zero-cost free endpoint rule")

    def test_ask_blocks_paid_models(self):
        with self.assertRaises(ValueError) as ctx:
            ask("test prompt", model="openai/gpt-4o")
        self.assertIn("Strict Zero-Cost Violation", str(ctx.exception))

        with self.assertRaises(ValueError) as ctx:
            ask("test prompt", model="anthropic/claude-3-opus")
        self.assertIn("Strict Zero-Cost Violation", str(ctx.exception))

    def test_fetch_free_models_caching(self):
        m1 = fetch_free_models()
        m2 = fetch_free_models()
        self.assertEqual(m1, m2)

    def test_sync_free_models_generates_file(self):
        from tools.sync_free_models import sync
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "test_models.txt"
            ret = sync(output_path=target)
            self.assertEqual(ret, 0)
            self.assertTrue(target.exists())
            content = target.read_text(encoding="utf-8")
            self.assertIn("OpenRouter Zero-Cost Free Models Catalog", content)
            self.assertIn("cohere/north-mini-code:free", content)
            self.assertIn("openrouter/free", content)

    def test_select_free_models_for_tier_orders_chore_vs_heavy(self):
        pool = list(dict.fromkeys(CHORE_FREE_MODELS + HEAVY_FREE_MODELS + ["misc/other:free"]))
        chore_order = select_free_models_for_tier("auto", pool, task_tier="chore")
        heavy_order = select_free_models_for_tier("auto", pool, task_tier="heavy")
        self.assertEqual(chore_order[0], CHORE_FREE_MODELS[0])
        self.assertEqual(heavy_order[0], HEAVY_FREE_MODELS[0])

    def test_on_demand_gate_blocks_unprompted_openrouter_call(self):
        with patch.dict(os.environ, {"OPENROUTER_ON_DEMAND_ENABLED": "0", "OPENROUTER_API_KEY": "test-key"}, clear=False):
            self.assertFalse(is_on_demand_enabled())
            with patch("intelligence.llm_clients.openrouter.get_cached_response", return_value=None):
                with self.assertRaises(PermissionError):
                    ask("Unique uncached prompt 12345", model="auto", task_tier="chore")

    def test_extract_cover_letter_only_when_requested(self):
        sample_resp = {
            "choices": [{"message": {"content": "Prefix explanation\nDear Hiring Team,\nLetter body."}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 8, "total_tokens": 13},
        }

        class FakeResp:
            def __init__(self, body: bytes):
                self._bio = io.BytesIO(body)
            def read(self):
                return self._bio.read()
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False

        raw_bytes = json.dumps(sample_resp).encode("utf-8")
        with patch.dict(os.environ, {"OPENROUTER_ON_DEMAND_ENABLED": "1", "OPENROUTER_API_KEY": "test-key"}, clear=False), \
             patch("intelligence.llm_clients.openrouter.get_cached_response", return_value=None), \
             patch("intelligence.llm_clients.openrouter.save_cached_response"), \
             patch("intelligence.llm_clients.openrouter.fetch_free_models", return_value=[CHORE_FREE_MODELS[0], HEAVY_FREE_MODELS[0]]), \
             patch("urllib.request.urlopen", side_effect=[FakeResp(raw_bytes), FakeResp(raw_bytes)]):
            plain = ask("Classify this text", model="auto", task_tier="chore", extract_letter=False)
            self.assertTrue(plain.startswith("Prefix explanation"))
            extracted = ask("Write cover letter", model="auto", task_tier="draft", extract_letter=True)
            self.assertTrue(extracted.startswith("Dear Hiring Team,"))

    def test_deepseek_never_falls_back_to_paid_endpoint(self):
        from intelligence.llm_clients import deepseek
        with self.assertRaises(PermissionError):
            deepseek._post({"model": "deepseek-chat"})
        with patch.dict(os.environ, {"OPENROUTER_ON_DEMAND_ENABLED": "0"}, clear=False), \
             patch("intelligence.llm_clients.openrouter.ask_local_ollama_if_online", return_value=""), \
             patch("intelligence.llm_clients.openrouter.get_cached_response", return_value=None):
            with self.assertRaises(PermissionError):
                deepseek.ask("Summarize JD")

    def test_qa_semantics_uses_local_ollama_and_gates_openrouter(self):
        from core.qa_semantics_engine import ask_openrouter_free_llm
        with patch.dict(os.environ, {"OPENROUTER_ON_DEMAND_ENABLED": "0"}, clear=False):
            with patch("intelligence.llm_clients.openrouter.ask_local_ollama_if_online", return_value="4"):
                ans = ask_openrouter_free_llm("How many years of Snowflake experience?", field_type="number")
                self.assertEqual(ans, "4")
            with patch("intelligence.llm_clients.openrouter.ask_local_ollama_if_online", return_value=""):
                ans2 = ask_openrouter_free_llm("Unique novel question xyz?", field_type="text")
                self.assertEqual(ans2, "")

    def test_check_career_sites_deterministic_and_gated(self):
        from tools.check_career_sites import query_model
        self.assertTrue(query_model("boards.greenhouse.io"))
        self.assertTrue(query_model("careers.example.com"))
        with patch.dict(os.environ, {"OPENROUTER_ON_DEMAND_ENABLED": "0"}, clear=False), \
             patch("intelligence.llm_clients.openrouter.ask_local_ollama_if_online", return_value=""):
            with self.assertRaises(PermissionError):
                query_model("unknown-vendor-portal.org")


if __name__ == "__main__":
    unittest.main()
