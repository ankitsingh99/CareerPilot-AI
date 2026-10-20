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
import time
from pathlib import Path

_SECRETS_FILE = Path(__file__).parent.parent / ".candidate_secrets.json"
_ENV_VAR = "OPENROUTER_API_KEY"

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_FREE_MODEL = "cohere/north-mini-code:free"

DEFAULT_FALLBACK_FREE_MODELS = [
    "cohere/north-mini-code:free",
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
    "nvidia/nemotron-3.5-lightning:free",
    "poolside/laguna-s-2.1:free",
    "minimax/minimax-m3.1-flash:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
]

# Mutable pool populated dynamically from OpenRouter live models catalog
FREE_MODELS_POOL: list[str] = list(DEFAULT_FALLBACK_FREE_MODELS)

_CACHE_FILE = Path.home() / ".cache" / "careerpilot" / "openrouter_free_models.json"
_CACHE_TTL_SECONDS = 3600  # 1 hour
_IN_MEMORY_CACHE: dict = {"timestamp": 0.0, "models": []}


def is_free_model(model_name: str) -> bool:
    """Return True if model is an authorized zero-cost endpoint."""
    if not model_name:
        return False
    return model_name.endswith(":free") or model_name in ("openrouter/free", "auto", "any")


def fetch_free_models(force_refresh: bool = False, timeout: int = 5) -> list[str]:
    """Dynamically discover all active zero-cost (:free) models from OpenRouter API.

    Queries OpenRouter's `/api/v1/models` endpoint to automatically detect all newly
    listed and active free models, caching results for 1 hour to prevent redundant requests.
    """
    global FREE_MODELS_POOL
    now = time.time()

    # 1. Check in-memory cache
    if (
        not force_refresh
        and _IN_MEMORY_CACHE.get("models")
        and (now - _IN_MEMORY_CACHE.get("timestamp", 0) < _CACHE_TTL_SECONDS)
    ):
        return list(_IN_MEMORY_CACHE["models"])

    # 2. Check disk cache
    if not force_refresh and _CACHE_FILE.exists():
        try:
            cached_data = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
            if now - cached_data.get("timestamp", 0) < _CACHE_TTL_SECONDS:
                models = cached_data.get("models", [])
                if models:
                    _IN_MEMORY_CACHE["models"] = models
                    _IN_MEMORY_CACHE["timestamp"] = cached_data["timestamp"]
                    FREE_MODELS_POOL[:] = models
                    return list(models)
        except Exception:
            pass

    # 3. Live query OpenRouter models API
    try:
        req = urllib.request.Request(
            f"{OPENROUTER_BASE_URL}/models",
            headers={
                "User-Agent": "CareerPilot-AI (Zero-Cost Free Model Discovery)",
                "Accept": "application/json",
            },
        )
        api_key = _load_key()
        if api_key:
            req.add_header("Authorization", f"Bearer {api_key}")

        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw_models = data.get("data", [])

        discovered: list[str] = []
        for m in raw_models:
            model_id = m.get("id", "")
            # Strict Zero-Cost Directive: Must end with :free or be openrouter/free
            if not (model_id.endswith(":free") or model_id == "openrouter/free"):
                continue

            # Verify zero-cost pricing
            pricing = m.get("pricing", {})
            prompt_cost = str(pricing.get("prompt", "0"))
            completion_cost = str(pricing.get("completion", "0"))
            if prompt_cost not in ("0", "0.0") or completion_cost not in ("0", "0.0"):
                continue

            # Exclude non-conversational/safety moderation classifiers
            if any(term in model_id.lower() for term in ("content-safety", "moderation", "guard")):
                continue

            # Ensure text output capability if architecture is specified
            arch = m.get("architecture", {})
            out_modalities = arch.get("output_modalities", [])
            modality = arch.get("modality", "")
            if out_modalities and "text" not in out_modalities:
                continue
            if modality and "->text" not in modality:
                continue

            discovered.append(model_id)

        if discovered:
            _IN_MEMORY_CACHE["models"] = discovered
            _IN_MEMORY_CACHE["timestamp"] = now
            FREE_MODELS_POOL[:] = discovered

            try:
                _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
                _CACHE_FILE.write_text(
                    json.dumps({"timestamp": now, "models": discovered}, indent=2),
                    encoding="utf-8",
                )
            except Exception:
                pass
            return list(discovered)
    except Exception as exc:
        print(f"[openrouter] Note: Could not fetch dynamic models list ({exc}). Using cached/fallback pool.")

    return list(FREE_MODELS_POOL)


def get_free_models(force_refresh: bool = False) -> list[str]:
    """Return all currently available free models from OpenRouter."""
    return fetch_free_models(force_refresh=force_refresh)


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
    if not is_free_model(model):
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

    # Build candidate models list dynamically from live free models pool
    available_pool = fetch_free_models()
    if model in ("auto", "any"):
        candidate_models = list(available_pool)
    else:
        candidate_models = [model] + [m for m in available_pool if m != model]
    last_error = None

    for current_model in candidate_models:
        if not is_free_model(current_model):
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
    if not is_free_model(model):
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

    available_pool = fetch_free_models()
    if model in ("auto", "any"):
        candidate_models = list(available_pool)
    else:
        candidate_models = [model] + [m for m in available_pool if m != model]
    last_error = None

    for current_model in candidate_models:
        if not is_free_model(current_model):
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
    parser = argparse.ArgumentParser(description="Token-Optimized OpenRouter Client (Zero-Cost Free Tier)")
    parser.add_argument("prompt", nargs="?", help="Prompt to send to OpenRouter")
    parser.add_argument("--model", default=DEFAULT_FREE_MODEL, help="Free OpenRouter model endpoint or 'auto'/'any'")
    parser.add_argument("--json", action="store_true", help="Enforce JSON mode output")
    parser.add_argument("--max-tokens", type=int, default=1500, help="Max completion tokens")
    parser.add_argument("--list-models", action="store_true", help="List all dynamically discovered free models from OpenRouter")
    parser.add_argument("--refresh-models", action="store_true", help="Force refresh cached free models from OpenRouter API")
    args = parser.parse_args()

    if args.list_models or args.refresh_models:
        models = fetch_free_models(force_refresh=True)
        print(f"\n[openrouter] Discovered {len(models)} Zero-Cost Free Models on OpenRouter:")
        for idx, m in enumerate(models, 1):
            star = " (default)" if m == DEFAULT_FREE_MODEL else ""
            print(f"  {idx:2d}. {m}{star}")
        print("\nAll models listed above cost $0.00 and comply with AGENTS.md Zero-Cost Directive.")
        if not args.prompt:
            sys.exit(0)

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
