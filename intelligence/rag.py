#!/usr/bin/env python3
"""
Local Deep Learning & Semantic Vector RAG Engine (tools/local_rag.py)
--------------------------------------------------------------------
Runs 100% on-device using Apple Silicon Metal acceleration via Ollama:
- Dense Embeddings: nomic-embed-text (768 dimensions)
- Vector Storage: SQLite (jobs.db) with cosine similarity ranking
- Generation: qwen2.5:7b / llama3.2:3b with grounded context injection
- Post-Processing: Deterministic style_linter.py enforcement
"""

import sys
from pathlib import Path

# Enable Python 3.15 native lazy imports if available
try:
    from utils.lazy_bootstrap import enable_lazy_imports
    enable_lazy_imports()
except ImportError:
    if hasattr(sys, "set_lazy_imports"):
        try:
            sys.set_lazy_imports("all")
        except Exception:
            pass

import json
import math
import os
import re
import sqlite3
import urllib.request
import urllib.error
from typing import Dict, List, Tuple, Any, Optional

try:
    from parsers.linter import lint_and_format
except ImportError:
    try:
        from style_linter import lint_and_format
    except ImportError:
        import sys
        sys.path.append(str(Path(__file__).parent.parent))
        from parsers.linter import lint_and_format


DB_PATH = Path(__file__).parent.parent / "jobs.db"
AGENTS_MD_PATH = Path(__file__).parent.parent / "AGENTS.md"
OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"
OLLAMA_GEN_URL = "http://localhost:11434/api/generate"
EMBED_MODEL = "nomic-embed-text"
GEN_MODEL = "qwen2.5:7b"


def is_ollama_online() -> bool:
    """Check if local Ollama daemon is responsive."""
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False


def get_embedding(text: str) -> Optional[List[float]]:
    """Compute 768-dim dense embedding vector on-device via Ollama."""
    if not is_ollama_online():
        return None
    try:
        data = json.dumps({"model": EMBED_MODEL, "prompt": text.strip()}).encode("utf-8")
        req = urllib.request.Request(OLLAMA_EMBED_URL, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            return res.get("embedding")
    except Exception as e:
        print(f"[local_rag] Embedding error: {e}")
        return None


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Calculate cosine similarity between two float vectors."""
    dot = sum(a * b for a, b in zip(v1, v2))
    norm_a = math.sqrt(sum(a * a for a in v1))
    norm_b = math.sqrt(sum(b * b for b in v2))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def init_vector_db():
    """Create local vector storage tables in jobs.db if not already present."""
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS semantic_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            title TEXT,
            content TEXT,
            embedding_json TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def seed_candidate_profile_vectors():
    """Index sections of AGENTS.md into semantic_memory for on-device RAG."""
    init_vector_db()
    if not AGENTS_MD_PATH.exists() or not is_ollama_online():
        return

    text = AGENTS_MD_PATH.read_text(encoding="utf-8")
    sections = re.split(r"\n#{2,3}\s+", text)

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM semantic_memory WHERE category='candidate_profile'")
    count = cur.fetchone()[0]

    if count >= len(sections) - 1 and count > 0:
        conn.close()
        return  # Already seeded

    print(f"[local_rag] Indexing {len(sections)} profile chunks into on-device semantic memory...")
    for sec in sections:
        sec = sec.strip()
        if not sec:
            continue
        lines = sec.split("\n")
        title = lines[0].strip()
        content = "\n".join(lines[1:]).strip()
        if len(content) < 30:
            continue

        emb = get_embedding(content)
        if emb:
            cur.execute(
                "INSERT INTO semantic_memory (category, title, content, embedding_json) VALUES (?, ?, ?, ?)",
                ("candidate_profile", title, content, json.dumps(emb)),
            )

    conn.commit()
    conn.close()
    print("[local_rag] Candidate profile vector memory updated.")


def query_semantic_memory(query_text: str, top_k: int = 3, min_similarity: float = 0.50) -> List[Dict[str, Any]]:
    """Retrieve top-K most relevant profile and QA chunks using local cosine similarity."""
    seed_candidate_profile_vectors()
    q_emb = get_embedding(query_text)
    if not q_emb:
        return []

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute("SELECT id, category, title, content, embedding_json FROM semantic_memory")
    rows = cur.fetchall()
    conn.close()

    scored = []
    for r in rows:
        r_id, cat, title, content, emb_json = r
        try:
            emb = json.loads(emb_json)
            sim = cosine_similarity(q_emb, emb)
            if sim >= min_similarity:
                scored.append({
                    "id": r_id,
                    "category": cat,
                    "title": title,
                    "content": content,
                    "similarity": round(sim, 4),
                })
        except Exception:
            continue

    scored.sort(key=lambda x: x["similarity"], reverse=True)
    return scored[:top_k]


def calculate_semantic_fit(job_description: str) -> float:
    """
    Calculate mathematical cosine fit score (0.0 to 1.0) of a job posting
    against candidate master experience using on-device dense embeddings.
    """
    matches = query_semantic_memory(job_description[:2000], top_k=5, min_similarity=0.40)
    if not matches:
        return 0.70  # Default baseline
    top_sims = [m["similarity"] for m in matches]
    avg_score = sum(top_sims) / len(top_sims)
    # Scale from cosine similarity range (0.5-0.85) to percentage (70%-99%)
    scaled = min(0.99, max(0.65, (avg_score - 0.45) * 1.5 + 0.65))
    return round(scaled, 2)


def get_available_gen_model() -> Optional[str]:
    """Dynamically returns the best available generation model from local Ollama."""
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            installed = [m.get("name", "") for m in data.get("models", [])]
            for candidate in ["qwen2.5:7b", "llama3.2:3b", "llama3.2:latest", "qwen2.5:latest"]:
                for inst in installed:
                    if candidate in inst:
                        return inst
            # Fallback to any non-embedding model
            for inst in installed:
                if "embed" not in inst:
                    return inst
    except Exception:
        pass
    return GEN_MODEL


def generate_local_response(prompt: str, context: str = "", max_tokens: int = 400) -> str:
    """
    Generate on-device response using local Qwen/Llama with grounded context and
    automatic post-processing by style_linter.py.
    """
    if not is_ollama_online():
        return ""

    model_to_use = get_available_gen_model() or GEN_MODEL

    cand_name = os.getenv("CANDIDATE_NAME", "the candidate")
    system_prompt = (
        f"You are an executive career advisor and candidate representation engine for {cand_name}. "
        "Strict Guidelines:\n"
        "1. NEVER use em dashes ('—'). Use standard hyphens, commas, or colons.\n"
        "2. Avoid AI buzzwords (spearheaded, leverage, delve, synergy, testament, fostered, dynamic).\n"
        "3. Write with high sentence length variance (asymmetrical, punchy, rhythmic sentences).\n"
        "4. Rely strictly on the provided factual context.\n"
    )

    full_prompt = f"Context:\n{context}\n\nQuestion/Task:\n{prompt}\n\nResponse:" if context else prompt

    payload = {
        "model": model_to_use,
        "system": system_prompt,
        "prompt": full_prompt,
        "stream": False,
        "options": {
            "temperature": 0.35,
            "num_predict": max_tokens,
        },
    }


    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(OLLAMA_GEN_URL, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=90) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            raw_text = res.get("response", "").strip()
            # Post-process through style linter
            linted = lint_and_format(raw_text)
            return linted["clean_text"]
    except Exception as e:
        print(f"[local_rag] Local generation error: {e}")
        return ""



def answer_custom_question(question: str, company: str = "", role: str = "") -> str:
    """Answers arbitrary ATS application questions using local grounded RAG."""
    # Retrieve top 3 relevant profile sections
    memories = query_semantic_memory(f"{company} {role} {question}", top_k=3, min_similarity=0.45)
    context_str = "\n\n".join([f"[{m['title']}]\n{m['content']}" for m in memories])
    
    prompt = (
        f"Target Company: {company}\nTarget Role: {role}\n\n"
        f"Application Question: {question}\n\n"
        "Draft a direct, impactful, professional first-person response based only on the candidate's real experience. "
        "Keep it concise (1 to 2 punchy paragraphs, 80-140 words). Zero corporate buzzwords. Zero em dashes."
    )
    return generate_local_response(prompt, context=context_str, max_tokens=300)


def generate_tailored_cover_letter(company: str, role: str, jd: str, research: str = "") -> str:
    """Generates an elite tailored executive cover letter using local grounded RAG."""
    memories = query_semantic_memory(f"{role} {jd[:1000]}", top_k=4, min_similarity=0.40)
    context_str = "\n\n".join([f"[{m['title']}]\n{m['content']}" for m in memories])
    if research:
        context_str += f"\n\n[Target Company Intelligence]\n{research}"

    cand_name = os.getenv("CANDIDATE_NAME", "the candidate")
    prompt = (
        f"Target Company: {company}\nTarget Role: {role}\nJob Description Summary: {jd[:800]}\n\n"
        f"Generate a tailored, humanized executive cover letter for {cand_name}. "
        "Structure:\n"
        f"- Opening: Direct, confident hook aligning {cand_name}'s verified background with the team's mission.\n"
        "- Body 1: Concrete technical impact from verified professional experience (ETL pipelines, data governance, cloud architecture).\n"
        "- Body 2: Practical systems delivery and business outcomes (metrics, automation, dispute/cost recovery).\n"
        "- Closing: Forward-looking discussion hook, immediate availability, and sign-off.\n\n"
        "Style Constraints: High burstiness (sentence length variance), ZERO em dashes, ZERO corporate clichés (spearheaded, leverage, delve, synergy)."
    )
    return generate_local_response(prompt, context=context_str, max_tokens=600)


if __name__ == "__main__":
    print(f"Ollama Online: {is_ollama_online()}")
    if is_ollama_online():
        seed_candidate_profile_vectors()
        test_q = "Experience in Healthcare Commercial Analytics and Patient Claims data"
        print(f"\n--- Semantic Memory Query: '{test_q}' ---")
        results = query_semantic_memory(test_q, top_k=2)
        for r in results:
            print(f"[{r['similarity']}] {r['title']}:\n{r['content'][:200]}...\n")

