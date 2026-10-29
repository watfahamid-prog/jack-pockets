from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path



EXPECTED_WIDTH = 1920
EXPECTED_HEIGHT = 1080
EXPECTED_FPS = 30.0
MIN_DURATION_SECONDS = 480.0
MAX_DURATION_SECONDS = 1800.0


def _rendered_path(log_text: str) -> Path | None:
    """Return the artifact path claimed by the mandatory FINAL QC log line."""
    for line in log_text.splitlines():
        marker = "FINAL QC PASSED:"
        if marker in line:
            value = line.split(marker, 1)[1].strip().split("|", 1)[0].strip()
            if value:
                return Path(value)
    return None


def _load_qc_report(path: Path) -> tuple[dict | None, str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        return None, f"video QC report is missing: {path}"
    except json.JSONDecodeError:
        return None, f"video QC report is malformed: {path}"
    if not isinstance(payload, dict):
        return None, "video QC report must be a JSON object"
    return payload, None


def _verify_artifact(log_text: str, manifest_path: Path | None) -> dict:
    result = {
        "verified": False,
        "claimed_path": None,
        "qc_report_path": None,
        "checks": {},
        "warnings": [],
        "video_qc_warnings": [],
    }
    logged_path = _rendered_path(log_text)
    if logged_path is None:
        result["checks"]["final_qc_log_claim"] = False
        result["warnings"].append("No FINAL QC PASSED artifact path found in the generation log")
        return result
    result["checks"]["final_qc_log_claim"] = True
    artifact = logged_path.resolve()
    result["claimed_path"] = str(artifact)
    exists = artifact.is_file()
    result["checks"]["artifact_exists"] = exists
    if not exists:
        result["warnings"].append(f"render log claims an MP4 that is not present: {artifact}")
        return result

    if manifest_path is None:
        result["warnings"].append("No run directory is available to locate video-qc.json")
        return result
    qc_path = manifest_path.parent / "video-qc.json"
    result["qc_report_path"] = str(qc_path)
    qc, error = _load_qc_report(qc_path)
    result["checks"]["qc_report_present_and_parseable"] = error is None
    if error:
        result["warnings"].append(error)
        return result

    try:
        qc_artifact = Path(str(qc.get("file", ""))).resolve()
        same_file = bool(qc.get("file")) and qc_artifact == artifact
    except (OSError, ValueError):
        same_file = False
    result["checks"]["qc_report_matches_artifact_path"] = same_file
    if not same_file:
        result["warnings"].append("video QC report does not identify the MP4 claimed by the render log")

    try:
        stat = artifact.stat()
    except OSError as exc:
        result["warnings"].append(f"could not stat rendered MP4 during ledger verification: {exc}")
        return result
    size_matches = isinstance(qc.get("file_size_bytes"), int) and qc["file_size_bytes"] == stat.st_size
    mtime_matches = isinstance(qc.get("file_mtime_ns"), int) and qc["file_mtime_ns"] == stat.st_mtime_ns
    result["checks"]["qc_report_matches_current_file_size"] = size_matches
    result["checks"]["qc_report_matches_current_file_mtime"] = mtime_matches
    if not size_matches or not mtime_matches:
        result["warnings"].append("video QC report is stale or lacks a verifiable MP4 file signature")

    try:
        duration = float(qc.get("duration_seconds") or 0)
    except (TypeError, ValueError):
        duration = 0.0
    try:
        fps = float(qc.get("fps") or 0)
    except (TypeError, ValueError):
        fps = 0.0
    technical_checks = {
        "duration_in_8_to_30_minute_range": MIN_DURATION_SECONDS <= duration <= MAX_DURATION_SECONDS,
        "resolution_is_1920x1080": qc.get("width") == EXPECTED_WIDTH and qc.get("height") == EXPECTED_HEIGHT,
        "frame_rate_is_30fps": abs(fps - EXPECTED_FPS) <= 0.1,
        "audio_stream_present": qc.get("has_audio") is True,
    }
    result["checks"].update(technical_checks)
    for name, passed in technical_checks.items():
        if not passed:
            result["warnings"].append(f"video QC technical check failed: {name}")

    raw_warnings = qc.get("warnings", [])
    if not isinstance(raw_warnings, list):
        raw_warnings = ["video QC warnings field is not a list"]
    result["video_qc_warnings"] = [str(item) for item in raw_warnings if str(item).strip()]
    result["warnings"].extend(f"video QC warning: {warning}" for warning in result["video_qc_warnings"])

    identity_checks = (same_file, size_matches, mtime_matches)
    result["verified"] = all(identity_checks) and all(technical_checks.values()) and not error
    return result


def summarize(log_text: str, manifest_path: Path | None) -> dict:
    errors: list[str] = []
    if "QUALITY GATE FAILED:" in log_text:
        tail = log_text.split("QUALITY GATE FAILED:", 1)[1]
        for line in tail.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith(("Traceback", "Error:")):
                break
            errors.append(line)
    errors.extend(line.strip() for line in log_text.splitlines() if "FINAL QC FAILED" in line)
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
    render_claimed = "FINAL QC PASSED:" in log_text
    quality_failed = "QUALITY GATE FAILED" in log_text or "FINAL QC FAILED" in log_text
    artifact = _verify_artifact(log_text, manifest_path) if render_claimed else {
        "verified": False, "claimed_path": None, "qc_report_path": None,
        "checks": {"final_qc_log_claim": False}, "warnings": [], "video_qc_warnings": [],
    }
    if render_claimed:
        errors.extend(artifact["warnings"])
    warnings = list(dict.fromkeys(artifact.get("video_qc_warnings", [])))
    if quality_failed:
        status = "failed"
    elif not render_claimed or not artifact["verified"]:
        status = "incomplete"
    elif warnings:
        status = "passed_with_warnings"
    else:
        status = "passed"
    return {
        "status": status,
        "render_claimed_by_log": render_claimed,
        "render_verified_by_log": bool(artifact["verified"]),
        "render_verification": artifact,
        "video_qc_warnings": warnings,
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
    recurring = sorted(((count, text) for text, count in counts.items() if count >= 2), reverse=True)[:10]
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
    result = summarize(log_text, args.run_dir / "manifest.json")
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
