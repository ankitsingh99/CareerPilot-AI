#!/usr/bin/env python3
"""Tests for local L1 + SQLite FTS5 fast recall and caching engine."""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from intelligence import fast_recall_cache as frc


class TestFastRecallCache(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.db_path = Path(self.td.name) / "recall.sqlite"
        frc.clear_l1_cache()
        frc.reset_recall_stats()

    def test_qa_exact_l1_and_sqlite_l2_recall(self):
        frc.put_qa_answer(
            "What is your Apache Airflow proficiency?",
            "Expert",
            field_type="select",
            options=["Beginner", "Intermediate", "Expert"],
            db_path=self.db_path,
        )
        # 1. L1 memory hit
        ans1 = frc.get_qa_answer(
            "What is your Apache Airflow proficiency?",
            field_type="select",
            options=["Beginner", "Intermediate", "Expert"],
            db_path=self.db_path,
        )
        self.assertEqual(ans1, "Expert")
        self.assertGreaterEqual(frc.get_recall_stats()["l1_hits"], 1)

        # 2. Clear L1 and confirm SQLite L2 recall
        frc.clear_l1_cache()
        ans2 = frc.get_qa_answer(
            "What is your Apache Airflow proficiency?",
            field_type="select",
            options=["Beginner", "Intermediate", "Expert"],
            db_path=self.db_path,
        )
        self.assertEqual(ans2, "Expert")
        self.assertGreaterEqual(frc.get_recall_stats()["db_exact_hits"], 1)

    def test_qa_fuzzy_fts_recall_for_rephrased_question(self):
        frc.put_qa_answer(
            "Years of experience with Apache Airflow",
            "4",
            field_type="number",
            db_path=self.db_path,
        )
        frc.clear_l1_cache()
        ans = frc.get_qa_answer(
            "Apache Airflow experience years",
            field_type="number",
            min_similarity=0.75,
            db_path=self.db_path,
        )
        self.assertEqual(ans, "4")
        self.assertGreaterEqual(frc.get_recall_stats()["fuzzy_hits"], 1)

    def test_text_cache_and_fetch_jd_markdown_avoids_network(self):
        url = "https://boards.greenhouse.io/acme/jobs/999"
        frc.put_cached_text(url, "Cached Role Description", category="jd_markdown", db_path=self.db_path)

        with patch("intelligence.fast_recall_cache.DEFAULT_RECALL_DB", self.db_path), \
             patch("urllib.request.urlopen") as mock_open:
            from tools.contact_pitch import fetch_jd_markdown
            content = fetch_jd_markdown(url)
            self.assertEqual(content, "Cached Role Description")
            mock_open.assert_not_called()

        # Expired TTL returns None
        stale = frc.get_cached_text(url, max_age_seconds=0, db_path=self.db_path)
        self.assertEqual(stale, "Cached Role Description")
        with patch("time.time", return_value=9999999999.0):
            expired = frc.get_cached_text(url, max_age_seconds=60, db_path=self.db_path)
            self.assertIsNone(expired)

    def test_chunk_fts_retrieval_and_offline_rag_fallback(self):
        n = frc.index_text_chunks(
            [
                {
                    "title": "Healthcare Commercial Analytics",
                    "category": "candidate_profile",
                    "content": "ZS Associates HIPAA HCP data masking Snowflake PySpark Airflow pipelines.",
                },
                {
                    "title": "D2C Logistics Automation",
                    "category": "candidate_profile",
                    "content": "Rush by Kira Shopify webhooks carrier weight audit shipping disputes.",
                },
            ],
            db_path=self.db_path,
        )
        self.assertEqual(n, 2)
        hits = frc.retrieve_relevant_chunks("Snowflake HIPAA masking pipelines", top_k=2, db_path=self.db_path)
        self.assertGreaterEqual(len(hits), 1)
        self.assertEqual(hits[0]["title"], "Healthcare Commercial Analytics")

        # Offline RAG fallback should return lexical hits instead of []
        from intelligence import rag
        with patch.object(rag, "is_ollama_online", return_value=False), \
             patch.object(rag, "get_embedding", return_value=None), \
             patch.object(rag, "DB_PATH", Path(self.td.name) / "jobs.db"), \
             patch("intelligence.fast_recall_cache.DEFAULT_RECALL_DB", self.db_path):
            offline_hits = rag.query_semantic_memory("Snowflake HIPAA masking", top_k=2)
            self.assertGreaterEqual(len(offline_hits), 1)

    def test_qa_engine_mtime_cached_kb_and_recall(self):
        from core.qa_semantics_engine import QASemanticsEngine
        import core.qa_semantics_engine as qse

        kb_file = Path(self.td.name) / "kb.json"
        kb_file.write_text(
            json.dumps({
                "qa_database": [
                    {
                        "category": "test",
                        "question_patterns": ["years of experience with dbt core"],
                        "standard_response": "2",
                    }
                ]
            }),
            encoding="utf-8",
        )
        with patch.object(qse, "KB_PATH", kb_file), \
             patch.dict(qse._KB_MEM_CACHE, {"mtime": None, "entries": [], "pattern_tokens": []}):
            self.assertEqual(
                QASemanticsEngine.lookup_knowledge_base("How many years of experience do you have with dbt core?"),
                "2",
            )
            # Reworded query resolved via normalized KB token overlap
            self.assertEqual(
                QASemanticsEngine.lookup_knowledge_base("dbt core experience years"),
                "2",
            )


if __name__ == "__main__":
    unittest.main()

