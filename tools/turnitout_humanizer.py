#!/usr/bin/env python3
"""
Turnitout Humanizer CLI & Tool (tools/turnitout_humanizer.py)
-------------------------------------------------------------
Zero-generative-AI, programmatic threat erasure and stylometric optimizer.
Purges AI watermarks/Unicode, computes ZipPy entropy, breaks 5-gram chains,
and applies deterministic linguistic transformations.

Usage:
  # Check file metrics (watermarks, entropy, n-grams) without mutating:
  python tools/turnitout_humanizer.py --input cover_letter.md --check-only

  # Humanize text in-place or write to output file:
  python tools/turnitout_humanizer.py --input cover_letter.md --output humanized.md --aggressiveness 0.75

  # Pipe directly from stdin / stdout:
  cat cover_letter.md | python tools/turnitout_humanizer.py --aggressiveness 0.8
"""

import sys
import argparse
import json
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parsers.turnitout_engine import TurnitoutEngine


def main():
    parser = argparse.ArgumentParser(
        description="Turnitout Humanizer: Programmatic Footprint Removal & ZipPy Entropy Optimizer"
    )
    parser.add_argument("--input", "-i", type=str, help="Path to input text or markdown file")
    parser.add_argument("--output", "-o", type=str, help="Path to write transformed output file")
    parser.add_argument(
        "--aggressiveness", "-a", type=float, default=0.75, help="Transformation aggressiveness (0.1 to 1.0, default: 0.75)"
    )
    parser.add_argument(
        "--check-only", "-c", action="store_true", help="Audit file for watermarks and ZipPy entropy without modifying"
    )
    parser.add_argument(
        "--json-report", "-j", action="store_true", help="Output audit report as JSON to stdout"
    )

    args = parser.parse_args()

    # Read input from file or stdin
    if args.input:
        in_path = Path(args.input)
        if not in_path.exists():
            print(f"[Error] Input file not found: {args.input}", file=sys.stderr)
            sys.exit(1)
        with open(in_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    else:
        if not sys.stdin.isatty():
            content = sys.stdin.read()
        else:
            parser.print_help()
            sys.exit(0)

    engine = TurnitoutEngine(seed=42)

    if args.check_only:
        clean, watermark_count = engine.purge_watermarks(content)
        entropy = engine.compute_zippy_entropy(clean)
        ngrams = engine.audit_ngrams(clean, k=5)

        report = {
            "watermarks_detected": watermark_count,
            "raw_bytes": entropy["raw_bytes"],
            "zlib_compression_ratio": entropy["zlib_ratio"],
            "lzma_compression_ratio": entropy["lzma_ratio"],
            "entropy_score": entropy["entropy_score"],
            "ai_likelihood": entropy["ai_likelihood"],
            "total_words": ngrams["total_words"],
            "unique_5grams": ngrams["unique_k_grams"],
            "redundancy_pct": ngrams["redundancy_pct"],
        }

        if args.json_report:
            print(json.dumps(report, indent=2))
        else:
            print("\n=== TURNITOUT THREAT & ENTROPY AUDIT ===")
            print(f"  Watermarks / Invisible Unicode Detected : {watermark_count}")
            print(f"  Total Words                             : {ngrams['total_words']}")
            print(f"  Zlib Compression Ratio (ZipPy)          : {entropy['zlib_ratio']} (Higher = more human)")
            print(f"  LZMA Compression Ratio                  : {entropy['lzma_ratio']}")
            print(f"  Normalized Entropy Score                : {entropy['entropy_score']} / 1.0")
            print(f"  AI Detector Vulnerability Assessment    : {entropy['ai_likelihood']}")
            print(f"  5-Gram Redundancy Index                 : {ngrams['redundancy_pct']}%")
            print("=========================================\n")
        return

    # Execute full humanization pipeline
    result = engine.humanize(content, aggressiveness=args.aggressiveness)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(result["humanized_text"])
        print(f"[Turnitout] Transformed text saved to: {out_path}", file=sys.stderr)
    elif not args.json_report:
        print(result["humanized_text"])

    if args.json_report:
        report = {
            "total_transforms": result["total_transforms"],
            "watermarks_purged": result["watermarks_purged"],
            "phrases_rewritten": result["phrases_rewritten"],
            "synonyms_swapped": result["synonyms_swapped"],
            "determiners_cycled": result["determiners_cycled"],
            "voice_inverted": result["voice_inverted"],
            "sentences_fused": result["sentences_fused"],
            "nominalizations_made": result["nominalizations_made"],
            "discourse_rotated": result["discourse_rotated"],
            "clause_reordered": result["clause_reordered"],
            "initial_entropy": result["initial_entropy"],
            "final_entropy": result["final_entropy"],
            "ngram_audit": result["ngram_audit"],
        }
        print(json.dumps(report, indent=2))
    elif args.output:
        print("\n=== TURNITOUT EXECUTION TELEMETRY ===")
        print(f"  Total Mathematical Transforms : {result['total_transforms']}")
        print(f"  Zero-Width Watermarks Purged  : {result['watermarks_purged']}")
        print(f"  AI Phrases Rewritten          : {result['phrases_rewritten']}")
        print(f"  Rare Synonyms Substituted     : {result['synonyms_swapped']}")
        print(f"  Determiners Cycled            : {result['determiners_cycled']}")
        print(f"  Voice Inversions (Active/Pass): {result['voice_inverted']}")
        print(f"  Sentence Fusions (Burstiness) : {result['sentences_fused']}")
        print(f"  Discourse Markers Rotated     : {result['discourse_rotated']}")
        print(f"  Initial ZipPy Entropy Score   : {result['initial_entropy']['entropy_score']}")
        print(f"  Final ZipPy Entropy Score     : {result['final_entropy']['entropy_score']}")
        print("=====================================\n")


if __name__ == "__main__":
    main()
