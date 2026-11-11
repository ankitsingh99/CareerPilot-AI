#!/usr/bin/env python3
"""
Fast Local Recall & Caching Engine (SQLite + FTS5 + L1 Memory Cache).

Provides sub-millisecond in-memory and persistent disk caching plus offline
lexical/FTS5 similarity recall for:
1. ATS screening Q&A answers (exact + fuzzy normalized question recall).
2. Retrieved job descriptions & web markdown (TTL-bounded URL/key text cache).
3. Candidate profile/document chunks (offline FTS5/BM25 + token retrieval).

Zero external network calls, zero LLM tokens, and safe across Python 3.10+.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
from collections import OrderedDict
from contextlib import closing
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

DEFAULT_RECALL_DB = Path.home() / ".cache" / "careerpilot" / "fast_recall_cache.sqlite"
_MAX_L1_ITEMS = 2048

_STOP_WORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "does",
    "for", "from", "have", "how", "i", "if", "in", "into", "is", "it",
    "many", "much", "my", "of", "on", "or", "our", "please", "the", "their",
    "this", "to", "us", "was", "what", "when", "where", "which", "who",
    "will", "with", "work", "working", "you", "your",
})

_L1_QA_CACHE: OrderedDict[str, str] = OrderedDict()
_L1_TEXT_CACHE: OrderedDict[str, Tuple[float, str]] = OrderedDict()
_INITIALIZED_DBS: set[str] = set()
_FTS5_SUPPORTED_DBS: dict[str, bool] = {}

_RECALL_STATS = {
    "l1_hits": 0,
    "db_exact_hits": 0,
    "fuzzy_hits": 0,
    "text_cache_hits": 0,
    "misses": 0,
    "writes": 0,
}


def get_recall_stats() -> Dict[str, int]:
    """Return copy of in-process recall & cache hit counters."""
    return dict(_RECALL_STATS)


def reset_recall_stats() -> None:
    """Reset in-process recall counters."""
    for key in _RECALL_STATS:
        _RECALL_STATS[key] = 0


def clear_l1_cache() -> None:
    """Clear in-process L1 LRU caches (useful in tests and after profile updates)."""
    _L1_QA_CACHE.clear()
    _L1_TEXT_CACHE.clear()


def _l1_put(cache: OrderedDict, key: str, value: Any) -> None:
    if key in cache:
        cache.move_to_end(key)
    cache[key] = value
    if len(cache) > _MAX_L1_ITEMS:
        cache.popitem(last=False)


def normalize_text(text: str) -> str:
    """Normalize punctuation and spacing for deterministic cache keying."""
    cleaned = re.sub(r"[^\w\s+#/.-]", " ", (text or "").lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def normalize_tokens(text: str) -> List[str]:
    """Extract informative lowercase tokens while stripping stop words."""
    raw = re.findall(r"[a-z0-9+#.]{2,}", (text or "").lower())
    seen: list[str] = []
    for tok in raw:
        if tok in _STOP_WORDS:
            continue
        if tok not in seen:
            seen.append(tok)
    return seen


def token_jaccard(tokens_a: Sequence[str], tokens_b: Sequence[str]) -> float:
    """Return symmetric Jaccard similarity in [0.0, 1.0]."""
    set_a = set(tokens_a)
    set_b = set(tokens_b)
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def _options_signature(options: Optional[Sequence[str]]) -> str:
    if not options:
        return ""
    norm = sorted({normalize_text(o) for o in options if o and o.strip()})
    return hashlib.sha1("|".join(norm).encode("utf-8")).hexdigest()[:12]


def _qa_cache_key(question: str, field_type: str = "text", options: Optional[Sequence[str]] = None) -> str:
    return f"{(field_type or 'text').strip().lower()}::{normalize_text(question)}::{_options_signature(options)}"


def _text_cache_key(key: str) -> str:
    return hashlib.sha256((key or "").strip().encode("utf-8")).hexdigest()


def _connect(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return closing(sqlite3.connect(str(db_path), timeout=5.0))


def _resolve_db(db_path: Optional[Path]) -> Path:
    return db_path if db_path is not None else DEFAULT_RECALL_DB


def _ensure_db(db_path: Optional[Path] = None) -> bool:
    """Initialize SQLite schema and optional FTS5 virtual tables once per DB path."""
    target_db = _resolve_db(db_path)
    db_key = str(target_db)
    if db_key in _INITIALIZED_DBS and target_db.exists():
        return _FTS5_SUPPORTED_DBS.get(db_key, False)

    fts_ok = False
    with _connect(target_db) as conn, conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS qa_cache (
                cache_key TEXT PRIMARY KEY,
                field_type TEXT NOT NULL,
                norm_question TEXT NOT NULL,
                tokens_json TEXT NOT NULL,
                options_sig TEXT NOT NULL,
                answer TEXT NOT NULL,
                source TEXT DEFAULT 'local',
                hits INTEGER DEFAULT 1,
                updated_at REAL NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_qa_ft ON qa_cache(field_type, norm_question)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS text_cache (
                url_hash TEXT PRIMARY KEY,
                source_key TEXT NOT NULL,
                category TEXT DEFAULT 'url',
                content TEXT NOT NULL,
                updated_at REAL NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chunk_cache (
                chunk_id TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                tokens_json TEXT NOT NULL,
                updated_at REAL NOT NULL
            )
        """)
        try:
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS qa_fts
                USING fts5(cache_key UNINDEXED, field_type UNINDEXED, norm_question)
            """)
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS chunk_fts
                USING fts5(chunk_id UNINDEXED, category UNINDEXED, title, content)
            """)
            fts_ok = True
        except sqlite3.OperationalError:
            fts_ok = False

    _INITIALIZED_DBS.add(db_key)
    _FTS5_SUPPORTED_DBS[db_key] = fts_ok
    return fts_ok


def _match_option_if_needed(answer: str, options: Optional[Sequence[str]]) -> Optional[str]:
    if not options:
        return answer
    ans_l = answer.strip().lower()
    for opt in options:
        if opt.strip().lower() == ans_l:
            return opt.strip()
    for opt in options:
        opt_c = opt.strip().lower()
        if not opt_c or opt_c in ("select", "select an option", "please select", "choose one"):
            continue
        if len(ans_l) >= 2 and (ans_l in opt_c or opt_c in ans_l):
            return opt.strip()
    return None


def put_qa_answer(
    question: str,
    answer: str,
    *,
    field_type: str = "text",
    options: Optional[Sequence[str]] = None,
    source: str = "local",
    db_path: Optional[Path] = None,
) -> None:
    """Persist QA answer in both L1 memory cache and SQLite/FTS5 store."""
    if not question or not answer or answer == "N/A":
        return
    norm_q = normalize_text(question)
    if not norm_q:
        return

    ft = (field_type or "text").strip().lower()
    opt_sig = _options_signature(options)
    key = f"{ft}::{norm_q}::{opt_sig}"
    _l1_put(_L1_QA_CACHE, key, answer)
    # Also store option-agnostic fallback key when plain text/number matches directly
    if opt_sig:
        _l1_put(_L1_QA_CACHE, f"{ft}::{norm_q}::", answer)

    try:
        target_db = _resolve_db(db_path)
        fts_ok = _ensure_db(target_db)
        tokens = normalize_tokens(question)
        now = time.time()
        with _connect(target_db) as conn, conn:
            conn.execute(
                """
                INSERT INTO qa_cache (cache_key, field_type, norm_question, tokens_json, options_sig, answer, source, hits, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    answer = excluded.answer,
                    tokens_json = excluded.tokens_json,
                    source = excluded.source,
                    hits = qa_cache.hits + 1,
                    updated_at = excluded.updated_at
                """,
                (key, ft, norm_q, json.dumps(tokens), opt_sig, answer, source, now),
            )
            if fts_ok:
                conn.execute("DELETE FROM qa_fts WHERE cache_key = ?", (key,))
                conn.execute(
                    "INSERT INTO qa_fts (cache_key, field_type, norm_question) VALUES (?, ?, ?)",
                    (key, ft, " ".join(tokens) or norm_q),
                )
        _RECALL_STATS["writes"] += 1
    except Exception:
        pass


def get_qa_answer(
    question: str,
    *,
    field_type: str = "text",
    options: Optional[Sequence[str]] = None,
    fuzzy: bool = True,
    min_similarity: float = 0.80,
    db_path: Optional[Path] = None,
) -> Optional[str]:
    """Recall cached QA answer in order: L1 exact -> DB exact -> FTS5/Jaccard fuzzy."""
    if not question or not question.strip():
        return None
    ft = (field_type or "text").strip().lower()
    norm_q = normalize_text(question)
    opt_sig = _options_signature(options)
    exact_key = f"{ft}::{norm_q}::{opt_sig}"

    # 1. L1 in-memory exact lookup
    if exact_key in _L1_QA_CACHE:
        _L1_QA_CACHE.move_to_end(exact_key)
        _RECALL_STATS["l1_hits"] += 1
        return _L1_QA_CACHE[exact_key]

    if opt_sig:
        generic_key = f"{ft}::{norm_q}::"
        if generic_key in _L1_QA_CACHE:
            matched = _match_option_if_needed(_L1_QA_CACHE[generic_key], options)
            if matched is not None:
                _RECALL_STATS["l1_hits"] += 1
                return matched

    # 2. SQLite exact + fuzzy recall
    try:
        target_db = _resolve_db(db_path)
        fts_ok = _ensure_db(target_db)
        with _connect(target_db) as conn:
            cur = conn.cursor()
            cur.execute("SELECT answer FROM qa_cache WHERE cache_key = ?", (exact_key,))
            row = cur.fetchone()
            if row:
                ans = row[0]
                _l1_put(_L1_QA_CACHE, exact_key, ans)
                _RECALL_STATS["db_exact_hits"] += 1
                return ans

            # Exact question match regardless of prior options signature
            cur.execute(
                "SELECT answer FROM qa_cache WHERE field_type = ? AND norm_question = ? ORDER BY updated_at DESC LIMIT 1",
                (ft, norm_q),
            )
            row2 = cur.fetchone()
            if row2:
                matched = _match_option_if_needed(row2[0], options)
                if matched is not None:
                    _l1_put(_L1_QA_CACHE, exact_key, matched)
                    _RECALL_STATS["db_exact_hits"] += 1
                    return matched

            if not fuzzy:
                _RECALL_STATS["misses"] += 1
                return None

            q_tokens = normalize_tokens(question)
            if not q_tokens:
                _RECALL_STATS["misses"] += 1
                return None

            candidates: List[Tuple[str, str, str]] = []
            if fts_ok:
                fts_query = " OR ".join(f'"{t}"' for t in q_tokens[:10] if t.isalnum())
                if fts_query:
                    try:
                        cur.execute(
                            """
                            SELECT q.cache_key, q.tokens_json, q.answer
                            FROM qa_fts f
                            JOIN qa_cache q ON q.cache_key = f.cache_key
                            WHERE qa_fts MATCH ? AND q.field_type = ?
                            ORDER BY bm25(qa_fts)
                            LIMIT 25
                            """,
                            (fts_query, ft),
                        )
                        candidates = cur.fetchall()
                    except sqlite3.OperationalError:
                        candidates = []

            if not candidates:
                cur.execute(
                    "SELECT cache_key, tokens_json, answer FROM qa_cache WHERE field_type = ? ORDER BY updated_at DESC LIMIT 100",
                    (ft,),
                )
                candidates = cur.fetchall()

            best_score = 0.0
            best_ans: Optional[str] = None
            for _, tok_json, cand_ans in candidates:
                try:
                    c_tokens = json.loads(tok_json)
                except Exception:
                    continue
                sim = token_jaccard(q_tokens, c_tokens)
                if sim >= min_similarity and sim > best_score:
                    matched = _match_option_if_needed(cand_ans, options)
                    if matched is not None:
                        best_score = sim
                        best_ans = matched

            if best_ans is not None:
                _l1_put(_L1_QA_CACHE, exact_key, best_ans)
                _RECALL_STATS["fuzzy_hits"] += 1
                return best_ans
    except Exception:
        pass

    _RECALL_STATS["misses"] += 1
    return None


def put_cached_text(
    key: str,
    content: str,
    *,
    category: str = "url",
    db_path: Optional[Path] = None,
) -> None:
    """Cache raw page text or job description markdown locally."""
    if not key or not content:
        return
    target_db = _resolve_db(db_path)
    h = _text_cache_key(key)
    now = time.time()
    _l1_put(_L1_TEXT_CACHE, f"{target_db}::{h}", (now, content))
    try:
        _ensure_db(target_db)
        with _connect(target_db) as conn, conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO text_cache (url_hash, source_key, category, content, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (h, key[:500], category, content, now),
            )
        _RECALL_STATS["writes"] += 1
    except Exception:
        pass


def get_cached_text(
    key: str,
    *,
    max_age_seconds: int = 86400,
    db_path: Optional[Path] = None,
) -> Optional[str]:
    """Retrieve cached page text / JD markdown if within TTL."""
    if not key:
        return None
    target_db = _resolve_db(db_path)
    h = _text_cache_key(key)
    l1_key = f"{target_db}::{h}"
    now = time.time()

    if l1_key in _L1_TEXT_CACHE:
        ts, content = _L1_TEXT_CACHE[l1_key]
        if max_age_seconds <= 0 or (now - ts) <= max_age_seconds:
            _L1_TEXT_CACHE.move_to_end(l1_key)
            _RECALL_STATS["text_cache_hits"] += 1
            return content
        del _L1_TEXT_CACHE[l1_key]

    try:
        _ensure_db(target_db)
        with _connect(target_db) as conn:
            cur = conn.cursor()
            cur.execute("SELECT content, updated_at FROM text_cache WHERE url_hash = ?", (h,))
            row = cur.fetchone()
            if row:
                content, updated_at = row
                if max_age_seconds <= 0 or (now - float(updated_at)) <= max_age_seconds:
                    _l1_put(_L1_TEXT_CACHE, l1_key, (float(updated_at), content))
                    _RECALL_STATS["text_cache_hits"] += 1
                    return content
    except Exception:
        pass
    return None


def index_text_chunks(
    chunks: Sequence[Dict[str, str]],
    *,
    db_path: Optional[Path] = None,
) -> int:
    """Index structured text chunks locally for fast offline FTS5 + token retrieval."""
    if not chunks:
        return 0
    target_db = _resolve_db(db_path)
    fts_ok = _ensure_db(target_db)
    now = time.time()
    count = 0
    with _connect(target_db) as conn, conn:
        for ch in chunks:
            title = (ch.get("title") or "").strip()
            content = (ch.get("content") or "").strip()
            category = (ch.get("category") or "general").strip()
            if not content:
                continue
            chunk_id = ch.get("chunk_id") or hashlib.sha1(f"{category}:{title}".encode("utf-8")).hexdigest()[:16]
            tokens = normalize_tokens(f"{title} {content}")
            conn.execute(
                """
                INSERT OR REPLACE INTO chunk_cache (chunk_id, category, title, content, tokens_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (chunk_id, category, title, content, json.dumps(tokens), now),
            )
            if fts_ok:
                conn.execute("DELETE FROM chunk_fts WHERE chunk_id = ?", (chunk_id,))
                conn.execute(
                    "INSERT INTO chunk_fts (chunk_id, category, title, content) VALUES (?, ?, ?, ?)",
                    (chunk_id, category, title, content),
                )
            count += 1
    return count


def retrieve_relevant_chunks(
    query: str,
    *,
    top_k: int = 3,
    min_similarity: float = 0.12,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Fast offline chunk retrieval using SQLite FTS5 BM25 + normalized token overlap."""
    q_tokens = normalize_tokens(query)
    if not q_tokens:
        return []
    target_db = _resolve_db(db_path)
    fts_ok = _ensure_db(target_db)
    results: List[Dict[str, Any]] = []
    q_set = set(q_tokens)

    with _connect(target_db) as conn:
        cur = conn.cursor()
        rows: List[Tuple[str, str, str, str, str]] = []
        if fts_ok:
            fts_terms = " OR ".join(f'"{t}"' for t in q_tokens[:12] if t.isalnum())
            if fts_terms:
                try:
                    cur.execute(
                        """
                        SELECT c.chunk_id, c.category, c.title, c.content, c.tokens_json
                        FROM chunk_fts f
                        JOIN chunk_cache c ON c.chunk_id = f.chunk_id
                        WHERE chunk_fts MATCH ?
                        ORDER BY bm25(chunk_fts)
                        LIMIT ?
                        """,
                        (fts_terms, max(top_k * 4, 20)),
                    )
                    rows = cur.fetchall()
                except sqlite3.OperationalError:
                    rows = []
        if not rows:
            cur.execute("SELECT chunk_id, category, title, content, tokens_json FROM chunk_cache")
            rows = cur.fetchall()

    for cid, cat, title, content, tok_json in rows:
        try:
            c_tokens = set(json.loads(tok_json))
        except Exception:
            c_tokens = set(normalize_tokens(f"{title} {content}"))
        if not c_tokens:
            continue
        overlap = len(q_set & c_tokens) / max(1, min(len(q_set), len(c_tokens)))
        if overlap >= min_similarity:
            results.append({
                "chunk_id": cid,
                "category": cat,
                "title": title,
                "content": content,
                "similarity": round(overlap, 4),
            })

    results.sort(key=lambda r: r["similarity"], reverse=True)
    return results[:top_k]
