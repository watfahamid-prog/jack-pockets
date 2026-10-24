from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:55] or "run"


def summarize(log_text: str, manifest_path: Path | None) -> dict:
    errors: list[str] = []
    gate = re.search(r"QUALITY GATE FAILED:\\s*([\\s\\S]*?)(?=\\n(?:Traceback|Error:)|\\Z)", log_text)
    if gate:
        errors.extend(line.strip() for line in gate.group(1).splitlines() if line.strip())
    final_qc_failed = re.findall(r"(?:FINAL QC FAILED|FINAL QC FAILED:)[^\\n]*", log_text)
    errors.extend(x.strip() for x in final_qc_failed)
    if not errors:
        errors.extend(
            line.strip() for line in log_text.splitlines()
            if any(token in line.lower() for token in (
                "no sufficiently relevant source found",
                "no relevant moving video",
                "rejected unrelated result",
                "provider search failed",
                "could not map",
                "timed out",
            ))
        )
    manifest_info = {"found": False, "beats": 0, "sources": 0, "duration_seconds": None}
    if manifest_path and manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest_info = {
                "found": True,
                "beats": len(manifest.get("beats") or []),
                "sources": len(manifest.get("sources") or []),
                "duration_seconds": manifest.get("duration"),
            }
            errors.extend(
                f"beat {beat.get('id', '?')} has no supporting source URLs"
                for beat in manifest.get("beats", [])
                if not beat.get("source_urls")
            )
        except (OSError, json.JSONDecodeError):
            errors.append("manifest exists but could not be parsed")
    rendered = bool(re.search(r"FINAL QC PASSED:", log_text))
    quality_failed = "QUALITY GATE FAILED" in log_text or "FINAL QC FAILED" in log_text
    return {
        "status": "passed" if rendered and not quality_failed else "failed" if quality_failed else "incomplete",
        "render_verified_by_log": rendered,
        "manifest": manifest_info,
        "observations": list(dict.fromkeys(errors))[:40],
    }


def update_ledger(ledger_path: Path, event: dict) -> dict:
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        if not isinstance(ledger, dict) or not isinstance(ledger.get("runs", []), list):
            raise ValueError("invalid ledger shape")
    except (OSError, json.JSONDecodeError, ValueError):
        ledger = {"schema_version": 1, "runs": []}
    event["recurring_observations"] = {}
    previous = ledger["runs"]
    for observation in event["observations"]:
        event["recurring_observations"][observation] = sum(
            1 for run in previous if observation in run.get("observations", [])
        ) + 1
    ledger["runs"].append(event)
    ledger["runs"] = ledger["runs"][-100:]
    ledger["schema_version"] = 1
    ledger_path.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    return ledger


def render_memory(ledger: dict) -> str:
    counts: dict[str, int] = {}
    for run in ledger.get("runs", []):
        for observation in run.get("observations", []):
            counts[observation] = counts.get(observation, 0) + 1
    recurring = sorted(
        ((count, text) for text, count in counts.items() if count >= 2),
        reverse=True,
    )[:10]
    lines = [
        "# Harness² run evidence memory",
        "",
        "Generated from recorded production-run evidence. This is observational memory, not permission to change production behavior.",
        "",
        f"Runs recorded: {len(ledger.get('runs', []))}",
    ]
    if not recurring:
        lines.extend(["", "No repeated failure/quality observation has been confirmed yet."])
    else:
        lines.extend(["", "## Repeated observations"])
        lines.extend(f"- Observed {count} times: {observation}" for count, observation in recurring)
    lines.extend([
        "",
        "Adoption rule: propose a targeted change, add a regression test, and pass existing quality gates before adopting it. Never relax gates to turn a failure into a pass.",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Record evidence from a Jack Pockets run for Harness².")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-number", default="")
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, default=Path.home() / ".cache/jack-pockets/harness2/experience-ledger.json")
    parser.add_argument("--report", type=Path, default=Path("harness2-learning-report.json"))
    parser.add_argument("--memory", type=Path, default=Path("harness2-learning-memory.md"))
    args = parser.parse_args()

    log_text = args.log.read_text(encoding="utf-8", errors="replace") if args.log.exists() else ""
    manifest = args.run_dir / "manifest.json"
    result = summarize(log_text, manifest)
    event = {
        "run_id": args.run_id,
        "run_number": args.run_number,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "topic": args.topic,
        **result,
    }
    ledger = update_ledger(args.ledger, event)
    args.report.write_text(json.dumps(event, indent=2) + "\n", encoding="utf-8")
    args.memory.write_text(render_memory(ledger), encoding="utf-8")
    print(f"[harness2-learning] status={result['status']} runs_recorded={len(ledger['runs'])}")
    print(f"[harness2-learning] manifest_found={result['manifest']['found']} observations={len(result['observations'])}")
    for observation, count in event["recurring_observations"].items():
        if count >= 2:
            print(f"[harness2-learning] recurring_observation_count={count}: {observation}")


if __name__ == "__main__":
    main()
