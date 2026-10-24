#!/usr/bin/env python3
"""Run a small, explicit Qwen provider smoke test without rendering a video.

This calls the Qwen provider directly, so it does not change LLM_PROVIDER or
the production provider order. Use local Ollama by default; hosted endpoints
may incur charges.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from llm import MIN_NARRATION_WORDS, _qwen


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--topic",
        default="What Is the Most Expensive Thing Ever?",
        help="Documentary topic for the plan-generation smoke test.",
    )
    parser.add_argument(
        "--research",
        type=Path,
        help="Optional JSON file containing the same research packet used for a baseline comparison.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("out/qwen-smoke-test-plan.json"),
        help="Where to save the generated plan (default: out/qwen-smoke-test-plan.json).",
    )
    args = parser.parse_args()

    research = []
    if args.research:
        try:
            loaded = json.loads(args.research.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Could not read research JSON: {exc}", file=sys.stderr)
            return 2
        if not isinstance(loaded, list) or not all(isinstance(item, dict) for item in loaded):
            print("--research must point to a JSON array of research objects.", file=sys.stderr)
            return 2
        research = loaded

    if not (os.getenv("QWEN_BASE_URL") or "http://localhost:11434/v1").strip():
        print("QWEN_BASE_URL cannot be empty.", file=sys.stderr)
        return 2

    try:
        plan = _qwen(args.topic, research)
    except Exception as exc:
        print(f"Qwen smoke test failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    beats = plan.get("beats", [])
    words = sum(len(str(beat.get("narration", "")).split()) for beat in beats)
    source_urls = {
        url
        for beat in beats
        for url in beat.get("source_urls", [])
        if isinstance(url, str) and url.strip()
    }
    print(f"Qwen provider response: valid JSON plan")
    print(f"Topic: {args.topic}")
    print(f"Beats: {len(beats)}")
    print(f"Narration words: {words} (minimum {MIN_NARRATION_WORDS})")
    print(f"Distinct source URLs in plan: {len(source_urls)}")
    print(f"Saved plan: {args.output}")

    if not 8 <= len(beats) <= 14:
        print("FAIL: expected 8–14 beats.", file=sys.stderr)
        return 1
    if words < MIN_NARRATION_WORDS:
        print(f"FAIL: narration is below {MIN_NARRATION_WORDS} words.", file=sys.stderr)
        return 1

    if not research:
        print("NOTE: no research packet was supplied; this confirms model connectivity and plan structure only, not factual accuracy.")
    else:
        print("NOTE: source URLs and factual claims still require manual verification against the supplied research.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
