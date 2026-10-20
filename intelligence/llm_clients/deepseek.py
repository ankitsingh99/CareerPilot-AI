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
    """POST to DeepSeek chat completions endpoint."""
    api_key = _load_key()
    url = f"{DEEPSEEK_BASE_URL}/v1/chat/completions"
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        return urllib.request.urlopen(req)  # noqa: S310
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(
            f"DeepSeek API error {exc.code}: {detail}"
        ) from exc


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
    """Send a single prompt and return the full response string.

    Enforces STRICT ZERO-COST DIRECTIVE: Automatically routes to OpenRouter free-tier (:free) models.
    """
    try:
        from intelligence.llm_clients.openrouter import ask as or_ask, DEFAULT_FREE_MODEL
        print(f"[deepseek] Zero-Cost Directive: Routing call to OpenRouter free model '{DEFAULT_FREE_MODEL}'")
        return or_ask(prompt, system=system, model=DEFAULT_FREE_MODEL, max_tokens=max_tokens, temperature=temperature)
    except Exception as exc:
        print(f"[deepseek] Note: Could not route to OpenRouter free tier: {exc}. Attempting direct endpoint...")

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    resp = _post(payload, stream=False)
    data = json.loads(resp.read().decode())
    return data["choices"][0]["message"]["content"]


def stream(
    prompt: str,
    *,
    system: str = "You are a helpful assistant.",
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> Generator[str, None, None]:
    """Stream the response token-by-token, yielding text chunks.

    Example:
        for chunk in stream("Tell me about Snowflake."):
            print(chunk, end="", flush=True)
    """
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }
    resp = _post(payload, stream=True)
    for raw_line in resp:
        line: str = raw_line.decode().strip()
        if not line or line == "data: [DONE]":
            continue
        if line.startswith("data: "):
            try:
                chunk = json.loads(line[6:])
                delta = chunk["choices"][0]["delta"].get("content", "")
                if delta:
                    yield delta
            except (json.JSONDecodeError, KeyError):
                continue


def chat(
    messages: list[dict],
    *,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> str:
    """Multi-turn chat interface. Pass the full messages list directly."""
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    resp = _post(payload, stream=False)
    data = json.loads(resp.read().decode())
    return data["choices"][0]["message"]["content"]


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tools/deepseek.py \"<your prompt>\" [model]")
        print(f"Default model: {DEFAULT_MODEL}")
        sys.exit(1)

    _prompt = sys.argv[1]
    _model = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_MODEL

    print(f"[DeepSeek / {_model}] Streaming response...\n")
    for _chunk in stream(_prompt, model=_model):
        print(_chunk, end="", flush=True)
    print()
