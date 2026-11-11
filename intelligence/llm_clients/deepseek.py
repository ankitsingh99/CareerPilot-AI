"""
DeepSeek direct API wrapper.

Design: calls DeepSeek's OpenAI-compatible REST endpoint DIRECTLY
        so zero Gemini/Antigravity tokens are burned on the call.

Usage (interactive):
    python tools/deepseek.py "What is a data engineer?"

Usage (as a library):
    from intelligence.llm_clients.deepseek import ask, stream

    response = ask("Summarise the job description in 3 bullets.", model="deepseek-chat")
    print(response)
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Generator

# ---------------------------------------------------------------------------
# Key resolution  (priority: env var > .candidate_secrets.json > prompt)
# ---------------------------------------------------------------------------

_SECRETS_FILE = Path(__file__).parent.parent / ".candidate_secrets.json"
_ENV_VAR = "DEEPSEEK_API_KEY"

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"


def _load_key() -> str:
    """Return the DeepSeek API key, searching env then secrets file."""
    # 1. Environment variable (highest priority)
    key = os.environ.get(_ENV_VAR, "").strip()
    if key:
        return key

    # 2. .candidate_secrets.json
    if _SECRETS_FILE.exists():
        try:
            data = json.loads(_SECRETS_FILE.read_text(encoding="utf-8"))
            key = data.get("deepseek_api_key", "").strip()
            if key:
                return key
        except (json.JSONDecodeError, OSError):
            pass

    raise RuntimeError(
        f"DeepSeek API key not found.\n"
        f"Set the {_ENV_VAR!r} environment variable, or add "
        f'"deepseek_api_key": "<key>" to {_SECRETS_FILE}.'
    )


# ---------------------------------------------------------------------------
# Core HTTP helpers (stdlib only - no extra pip install required)
# ---------------------------------------------------------------------------

def _post(payload: dict, stream: bool = False) -> urllib.request.Response:
    """Blocked direct DeepSeek endpoint per Strict Zero-Cost Directive."""
    raise PermissionError(
        "Strict Zero-Cost Violation: Direct DeepSeek billable endpoint is disabled. "
        "Route requests through OpenRouter :free endpoints or local Ollama."
    )


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def ask(
    prompt: str,
    *,
    system: str = "You are a helpful assistant.",
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> str:
    """Send a single prompt via OpenRouter :free tier (billable DeepSeek direct API disabled)."""
    from intelligence.llm_clients.openrouter import (
        ask as or_ask,
        ask_local_ollama_if_online,
        DEFAULT_FREE_MODEL,
    )

    local_ans = ask_local_ollama_if_online(
        prompt, system=system, max_tokens=min(max_tokens, 600), temperature=temperature
    )
    if local_ans:
        return local_ans

    target_model = model if model.endswith(":free") else DEFAULT_FREE_MODEL
    print(f"[deepseek] Zero-Cost Directive: Routing call to OpenRouter free model '{target_model}'")
    return or_ask(
        prompt,
        system=system,
        model=target_model,
        task_tier="heavy",
        max_tokens=max_tokens,
        temperature=temperature,
    )


def stream(
    prompt: str,
    *,
    system: str = "You are a helpful assistant.",
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> Generator[str, None, None]:
    """Yield completion cleanly via OpenRouter :free tier (billable DeepSeek direct API disabled)."""
    yield ask(
        prompt,
        system=system,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def chat(
    messages: list[dict],
    *,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> str:
    """Multi-turn chat interface routed strictly through Zero-Cost Free Tier."""
    system_msgs = [m.get("content", "") for m in messages if m.get("role") == "system"]
    user_turns = [
        f"{m.get('role', 'user').upper()}: {m.get('content', '')}"
        for m in messages
        if m.get("role") != "system"
    ]
    return ask(
        "\n\n".join(user_turns),
        system="\n".join(system_msgs) or "You are a helpful assistant.",
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tools/deepseek.py \"<your prompt>\" [free-model]")
        sys.exit(1)

    os.environ.setdefault("OPENROUTER_ON_DEMAND_ENABLED", "1")
    _prompt = sys.argv[1]
    _model = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_MODEL

    print("[DeepSeek -> Zero-Cost Router] Running response...\n")
    for _chunk in stream(_prompt, model=_model):
        print(_chunk, end="", flush=True)
    print()
