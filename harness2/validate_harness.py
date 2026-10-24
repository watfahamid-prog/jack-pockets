from __future__ import annotations

import json
from pathlib import Path

REQUIRED_COMPONENTS = {
    "system_prompt",
    "guardrails",
    "memory",
    "tool_guidance",
    "subagents",
    "skills",
    "scripts",
    "plugins",
}

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "jack_pockets_harness.json"
REQUIREMENTS = ROOT.parent / "requirements-harness2.txt"
EXPECTED_FRAMEWORK = "google-research/harness2"


def main() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert data.get("framework") == EXPECTED_FRAMEWORK
    assert data.get("version") == 1
    components = data.get("components")
    assert isinstance(components, dict)
    missing = REQUIRED_COMPONENTS - components.keys()
    extra = components.keys() - REQUIRED_COMPONENTS
    assert not missing, f"missing Harness² components: {sorted(missing)}"
    assert not extra, f"unknown Harness² components: {sorted(extra)}"

    requirement = REQUIREMENTS.read_text(encoding="utf-8")
    expected = data.get("framework_commit")
    assert expected and f"@{expected}" in requirement, (
        "requirements-harness2.txt must pin the same Harness² commit as the manifest"
    )

    policy = data.get("integration_policy", {})
    assert policy.get("mode") == "opt-in"
    assert policy.get("production_pipeline_unchanged_until_validated") is True
    assert policy.get("never_auto_adopt_unvalidated_harness_changes") is True

    print(f"Harness² manifest valid: {MANIFEST}")
    print(f"Pinned framework commit: {expected}")


if __name__ == "__main__":
    main()
