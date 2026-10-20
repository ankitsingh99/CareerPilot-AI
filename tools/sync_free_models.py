#!/usr/bin/env python3
"""
Sync OpenRouter Free Models Catalog.

Queries OpenRouter's public models endpoint and writes out an up-to-date
plain text catalog of all zero-cost (:free) models to `openrouter_free_models.txt`.
Scheduled to run weekly via GitHub Actions and the Antigravity cron scheduler.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FILE = WORKSPACE_ROOT / "openrouter_free_models.txt"
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"


def fetch_free_models_metadata(timeout: int = 15) -> list[dict]:
    """Fetch all zero-cost models with metadata directly from OpenRouter API."""
    req = urllib.request.Request(
        OPENROUTER_MODELS_URL,
        headers={
            "User-Agent": "CareerPilot-AI (OpenRouter Free Models Catalog Syncer)",
            "Accept": "application/json",
        },
    )
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    raw_models = data.get("data", [])
    free_models: list[dict] = []

    for m in raw_models:
        model_id = m.get("id", "")
        # Zero-Cost Directive: Must end with :free or be openrouter/free
        if not (model_id.endswith(":free") or model_id == "openrouter/free"):
            continue

        pricing = m.get("pricing", {})
        prompt_cost = str(pricing.get("prompt", "0"))
        completion_cost = str(pricing.get("completion", "0"))
        if prompt_cost not in ("0", "0.0") or completion_cost not in ("0", "0.0"):
            continue

        # Exclude moderation/safety classifiers that don't generate text completions
        if any(term in model_id.lower() for term in ("content-safety", "moderation", "guard")):
            continue

        arch = m.get("architecture", {})
        out_modalities = arch.get("output_modalities", [])
        modality = arch.get("modality", "")
        if out_modalities and "text" not in out_modalities:
            continue
        if modality and "->text" not in modality:
            continue

        free_models.append(
            {
                "id": model_id,
                "name": m.get("name") or model_id,
                "context_length": m.get("context_length") or 0,
                "description": (m.get("description") or "").replace("\n", " ").strip()[:90],
                "created": m.get("created"),
            }
        )

    # Sort: default model first, then alphabetically
    def sort_key(item: dict) -> tuple[int, str]:
        mid = item["id"]
        if mid == "cohere/north-mini-code:free":
            return (0, mid)
        if mid == "openrouter/free":
            return (1, mid)
        return (2, mid)

    free_models.sort(key=sort_key)
    return free_models


def format_models_text(models: list[dict], generated_at: datetime) -> str:
    """Format models list as a clean, human-readable and machine-parseable text file."""
    timestamp_str = generated_at.strftime("%Y-%m-%d %H:%M:%S UTC")
    lines: list[str] = [
        "# OpenRouter Zero-Cost Free Models Catalog",
        f"# Generated: {timestamp_str}",
        f"# Total Active Free Models: {len(models)}",
        "# Update Frequency: Weekly (Scheduled via GitHub Actions & Antigravity Cron)",
        "# Zero-Cost Policy: $0.00 / prompt token, $0.00 / completion token (100% Free)",
        "",
        "=" * 88,
        f"{'MODEL ID':<46} | {'CONTEXT':<9} | {'NAME / PROVIDER'}",
        "=" * 88,
    ]

    for m in models:
        mid = m["id"]
        ctx = f"{m['context_length']:,}" if m["context_length"] else "Unknown"
        name = m["name"]
        if mid == "cohere/north-mini-code:free":
            name += " [Default]"
        lines.append(f"{mid:<46} | {ctx:>9} | {name}")

    lines.extend([
        "=" * 88,
        "",
        "# -----------------------------------------------------------------------------",
        "# PLAIN MODEL IDS LIST (For automation, scripts, and direct parsing):",
        "# -----------------------------------------------------------------------------",
    ])

    for m in models:
        lines.append(m["id"])

    lines.append("")
    return "\n".join(lines)


def sync(output_path: Path = OUTPUT_FILE, check_only: bool = False) -> int:
    """Fetch free models and write to output file."""
    print(f"[sync_free_models] Fetching active free models from OpenRouter...")
    models = fetch_free_models_metadata()
    now = datetime.now(timezone.utc)
    content = format_models_text(models, now)

    if check_only:
        if not output_path.exists():
            print(f"[sync_free_models] File {output_path} does not exist.")
            return 1
        existing = output_path.read_text(encoding="utf-8")
        # Compare model IDs lists
        existing_ids = [line.strip() for line in existing.splitlines() if line.strip() and not line.startswith("#") and not line.startswith("=")]
        new_ids = [m["id"] for m in models]
        if set(existing_ids) == set(new_ids):
            print(f"[sync_free_models] Up to date ({len(models)} free models).")
            return 0
        else:
            print(f"[sync_free_models] Changes detected in free models list.")
            return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    print(f"[sync_free_models] Successfully wrote {len(models)} free models to {output_path}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync OpenRouter Free Models Catalog to text file")
    parser.add_argument("--output", "-o", type=Path, default=OUTPUT_FILE, help="Target text file path")
    parser.add_argument("--check", action="store_true", help="Check if file is up to date without modifying")
    args = parser.parse_args()

    sys.exit(sync(output_path=args.output, check_only=args.check))
