from __future__ import annotations

import argparse
import json
from pathlib import Path

RULES = [
    {
        "id": "footage-relevance",
        "matches": ("no relevant moving video", "no sufficiently relevant source found", "rejected unrelated result"),
        "lesson": "Keep strict relevance checks; search with short, concrete visual subjects and do not substitute unrelated footage.",
        "experiment": "Compare concise per-beat search phrases against the current search terms on a fixed topic set; measure relevant moving clips accepted and rejected.",
        "test": "Add or extend a regression test proving unrelated clips remain rejected and concise queries are used.",
    },
    {
        "id": "provider-reliability",
        "matches": ("provider search failed", "timed out"),
        "lesson": "Treat provider failures as recoverable acquisition problems; retain provenance and do not bypass source-quality checks.",
        "experiment": "Measure provider fallback order and retry behavior against mocked timeout/failure cases.",
        "test": "Add deterministic mocked tests for timeout, fallback, and provenance preservation.",
    },
    {
        "id": "source-provenance",
        "matches": ("no supporting source urls", "manifest exists but could not be parsed"),
        "lesson": "A documentary beat needs traceable supporting sources; malformed or missing provenance is a failure, not a warning to ignore.",
        "experiment": "Add a fixture-driven source-provenance audit for every beat before render.",
        "test": "Add tests for missing URLs, malformed manifests, and valid source references.",
    },
    {
        "id": "quality-gate",
        "matches": (
            "quality gate failed", "final qc failed", "static-image gate",
            "distinct real video clips", "motion gate", "shot has no visual asset",
            "shot has no asset", "shot has no visual layers", "visual coverage gap",
            "video qc technical check failed",
            "video qc report is stale",
            "video qc report is missing",
        ),
        "lesson": "Preserve the existing visual quality gates; diagnose the failing condition instead of weakening thresholds.",
        "experiment": "Generate a targeted diagnostic report identifying failing beats and the exact gate evidence before rerunning.",
        "test": "Add or extend a regression fixture that reproduces the failure while asserting the gate still rejects it.",
    },
    {
        "id": "alignment",
        "matches": ("could not map", "alignment"),
        "lesson": "Keep narration-to-visual timing explicit and verify every scene against its narration interval.",
        "experiment": "Compare beat-to-narration alignment diagnostics against a fixed known-good fixture.",
        "test": "Add deterministic tests for missing, overlapping, and out-of-range alignment segments.",
    },
]


def build_proposals(ledger: dict) -> dict:
    runs = ledger.get("runs", [])
    observed = []
    for run in runs:
        observed.extend(str(item).lower() for item in run.get("observations", []))
    proposals = []
    for rule in RULES:
        matches = [item for item in observed if any(term in item for term in rule["matches"])]
        if len(matches) >= 2:
            proposals.append({
                "id": rule["id"],
                "evidence_count": len(matches),
                "evidence": matches[-10:],
                "lesson": rule["lesson"],
                "experiment": rule["experiment"],
                "required_test": rule["test"],
                "status": "proposed_not_adopted",
                "safety": "No production code or quality threshold changes are applied automatically.",
            })
    return {
        "schema_version": 1,
        "runs_considered": len(runs),
        "proposals": proposals,
        "policy": "Evidence can propose a testable experiment; adoption requires a code change, regression tests, and existing production quality gates.",
    }


def render_candidate_memory(base_memory: str, proposals: dict) -> str:
    lines = [base_memory.rstrip(), "", "## Candidate experiments (not adopted)"]
    if not proposals["proposals"]:
        lines.append("No rule has enough repeated evidence yet to propose an experiment.")
    else:
        for proposal in proposals["proposals"]:
            lines.extend([
                "",
                f"- {proposal['id']}: {proposal['experiment']}",
                f"  - Evidence observations: {proposal['evidence_count']}",
                f"  - Required test: {proposal['required_test']}",
                "  - Status: proposed only; production behavior unchanged.",
            ])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Turn repeated Harness² run evidence into safe, testable proposals.")
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--memory", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("harness2-learning-proposals.json"))
    args = parser.parse_args()
    ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
    proposals = build_proposals(ledger)
    base_memory = args.memory.read_text(encoding="utf-8")
    args.memory.write_text(render_candidate_memory(base_memory, proposals), encoding="utf-8")
    args.output.write_text(json.dumps(proposals, indent=2) + "\n", encoding="utf-8")
    print(f"[harness2-learning] candidate_experiments={len(proposals['proposals'])} runs_considered={proposals['runs_considered']}")


if __name__ == "__main__":
    main()
