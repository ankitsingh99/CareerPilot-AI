#!/usr/bin/env python3
"""
Tests for OpenRouter zero-cost free models client and validation.
Uses standard library unittest.TestCase for full compatibility with GitHub CI unittest runner and pytest.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from intelligence.llm_clients.openrouter import (
    DEFAULT_FREE_MODEL,
    FREE_MODELS_POOL,
    is_free_model,
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


if __name__ == "__main__":
    unittest.main()
