"""
Token-Optimized OpenRouter API Wrapper.

Features & Token Optimization Best Practices Built-in:
1. Zero-Cost Enforcement: Uses strictly `:free` models by default (AGENTS.md compliance).
2. Automatic Text Trimming & Compression: Strips HTML boilerplate and redundant whitespace before sending.
3. Prompt Caching Layout: Structures system context at message index 0 for max caching reuse on OpenRouter.
4. Strict Output Token Caps: Enforces max_tokens bounds (default 1500) to stop completion bloat.
5. JSON Mode Support: Option to enforce raw JSON schema outputs without conversational fluff.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

_SECRETS_FILE = Path(__file__).parent.parent / ".candidate_secrets.json"
_ENV_VAR = "OPENROUTER_API_KEY"

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_FREE_MODEL = "cohere/north-mini-code:free"

FREE_MODELS_POOL = [
    "cohere/north-mini-code:free",
    "poolside/laguna-s-2.1:free",
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
    "qwen/qwen3.8-27b:free",
    "nvidia/nemotron-3.5-lightning:free",
]


def _load_key() -> str:
    """Return the OpenRouter API key from env or secrets file."""
    key = os.environ.get(_ENV_VAR, "").strip()
    if key:
        return key

    user_secret = Path.home() / ".config" / "job-agent" / "client_secret.json"
    if user_secret.exists():
        try:
            data = json.loads(user_secret.read_text(encoding="utf-8"))
            key = (data.get("api_keys", {}).get("openrouter_api_key", "").strip() or 
                   data.get("openrouter_api_key", "").strip() or
                   data.get("OPENROUTER_API_KEY", "").strip())
            if key:
                return key
        except (json.JSONDecodeError, OSError):
            pass

    if _SECRETS_FILE.exists():
        try:
            data = json.loads(_SECRETS_FILE.read_text(encoding="utf-8"))
            key = data.get("openrouter_api_key", "").strip() or data.get("OPENROUTER_API_KEY", "").strip()
            if key:
                return key
        except (json.JSONDecodeError, OSError):
            pass

    return ""


def trim_text_content(text: str, max_chars: int = 6000) -> str:
    """Optimize tokens by stripping HTML tags, removing excess whitespace, and bounding size."""
    if not text:
        return ""
    # Remove HTML tags if present
    clean = re.sub(r"<[^>]+>", " ", text)
    # Collapse multiple whitespaces/newlines
    clean = re.sub(r"\s+", " ", clean).strip()
    if len(clean) > max_chars:
        clean = clean[:max_chars] + "... [truncated for token optimization]"
    return clean


def ask(
    prompt: str,
    *,
    system: str = "You are a concise, structured data assistant.",
    model: str = DEFAULT_FREE_MODEL,
    temperature: float = 0.7,
    max_tokens: int = 1500,
    json_mode: bool = False,
    trim_input: bool = True,
    timeout: int = 60,
) -> str:
    """Send a token-optimized chat completion request to OpenRouter with zero-cost fallback."""
    if not model.endswith(":free"):
        raise ValueError(f"Strict Zero-Cost Violation: Model '{model}' is not a free-tier endpoint (:free).")

    api_key = _load_key()
    cleaned_prompt = trim_text_content(prompt) if trim_input else prompt
    cleaned_system = trim_text_content(system, max_chars=1500) if trim_input else system

    messages = [
        {"role": "system", "content": cleaned_system},
        {"role": "user", "content": cleaned_prompt},
    ]

    headers = {
        "Content-Type": "application/json",
        "HTTP-Referer": os.getenv("CANDIDATE_PORTFOLIO_URL", "https://github.com/ankitsingh99/ai-job-search"),
        "X-Title": "AI-Job-Search-Agent",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    # Build candidate models list starting with requested model
    candidate_models = [model] + [m for m in FREE_MODELS_POOL if m != model]
    last_error = None

    for current_model in candidate_models:
        if not current_model.endswith(":free"):
            continue

        print(f"\n[openrouter] 🤖 Model in use: '{current_model}' (Zero-Cost Free Tier)")

        payload: dict = {
            "model": current_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            data=body,
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                choice_msg = data.get("choices", [{}])[0].get("message", {})
                content = (choice_msg.get("content") or "").strip()
                if not content and choice_msg.get("reasoning"):
                    content = choice_msg.get("reasoning").strip()
                # Strip think tags or chain of thought intros if present
                content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
                match = re.search(r"(Dear Hiring Team.*)", content, flags=re.DOTALL | re.IGNORECASE)
                if match:
                    content = match.group(1).strip()
                elif "Here's a thinking process" in content or "Here is a thinking process" in content:
                    parts = re.split(r"(?:Here is the letter|Here is the cover letter|Dear Hiring Team|Dear Hiring Manager)", content, flags=re.IGNORECASE)
                    if len(parts) > 1:
                        content = "Dear Hiring Team,\n\n" + parts[-1].strip()
                return content
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            last_error = RuntimeError(f"OpenRouter API Error {exc.code} for '{current_model}': {detail}")
            print(f"[openrouter] ⚠️ '{current_model}' returned {exc.code}. Attempting next free model...")
        except Exception as exc:
            last_error = RuntimeError(f"OpenRouter request failed for '{current_model}': {exc}")
            print(f"[openrouter] ⚠️ Error with '{current_model}': {exc}. Attempting next free model...")

    if last_error:
        raise last_error
    raise RuntimeError("No free tier models available.")


def ask_with_usage(
    prompt: str,
    *,
    system: str = "You are a concise, structured data assistant.",
    model: str = DEFAULT_FREE_MODEL,
    temperature: float = 0.7,
    max_tokens: int = 1500,
    json_mode: bool = False,
    trim_input: bool = True,
    timeout: int = 60,
) -> tuple[str, dict]:
    """Send request and return (content, usage_dict) for token quantification."""
    if not model.endswith(":free"):
        raise ValueError(f"Strict Zero-Cost Violation: Model '{model}' is not a free-tier endpoint (:free).")

    api_key = _load_key()
    cleaned_prompt = trim_text_content(prompt) if trim_input else prompt
    cleaned_system = trim_text_content(system, max_chars=1500) if trim_input else system

    messages = [
        {"role": "system", "content": cleaned_system},
        {"role": "user", "content": cleaned_prompt},
    ]

    headers = {
        "Content-Type": "application/json",
        "HTTP-Referer": os.getenv("CANDIDATE_PORTFOLIO_URL", "https://github.com/ankitsingh99/ai-job-search"),
        "X-Title": "AI-Job-Search-Agent",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    candidate_models = [model] + [m for m in FREE_MODELS_POOL if m != model]
    last_error = None

    for current_model in candidate_models:
        if not current_model.endswith(":free"):
            continue

        print(f"\n[openrouter] 🤖 Model in use: '{current_model}' (Zero-Cost Free Tier)")

        payload: dict = {
            "model": current_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            data=body,
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                usage = data.get("usage", {})
                choice_msg = data.get("choices", [{}])[0].get("message", {})
                content = (choice_msg.get("content") or choice_msg.get("reasoning") or "").strip()
                return content, usage
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            last_error = RuntimeError(f"OpenRouter API Error {exc.code} for '{current_model}': {detail}")
            print(f"[openrouter] ⚠️ '{current_model}' returned {exc.code}. Attempting next free model...")
        except Exception as exc:
            last_error = RuntimeError(f"OpenRouter request failed for '{current_model}': {exc}")
            print(f"[openrouter] ⚠️ Error with '{current_model}': {exc}. Attempting next free model...")

    if last_error:
        raise last_error
    raise RuntimeError("No free tier models available.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Token-Optimized OpenRouter Client")
    parser.add_argument("prompt", nargs="?", help="Prompt to send to OpenRouter")
    parser.add_argument("--model", default=DEFAULT_FREE_MODEL, help="Free OpenRouter model endpoint")
    parser.add_argument("--json", action="store_true", help="Enforce JSON mode output")
    parser.add_argument("--max-tokens", type=int, default=1500, help="Max completion tokens")
    args = parser.parse_args()

    if not args.prompt:
        parser.print_help()
        sys.exit(0)

    key = _load_key()
    if not key:
        print("Note: No OPENROUTER_API_KEY found in env or .candidate_secrets.json.")
        print(f"Token-optimization pre-processing complete. Prompt target size: {len(trim_text_content(args.prompt))} chars.")
        sys.exit(0)

    print(f"Sending prompt (token-optimized)...")
    res = ask(args.prompt, model=args.model, max_tokens=args.max_tokens, json_mode=args.json)
    print("Response:\n", res)
