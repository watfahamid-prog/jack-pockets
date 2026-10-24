from __future__ import annotations

import argparse
import json
from pathlib import Path

MANIFEST = Path(__file__).with_name("jack_pockets_harness.json")


def _slug(value: str) -> str:
    return "-".join(value.lower().replace("_", "-").split())


def render(manifest_path: Path, output_dir: Path) -> None:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    components = data["components"]
    output_dir.mkdir(parents=True, exist_ok=True)

    (output_dir / "systemprompt.md").write_text(
        str(components["system_prompt"]).strip() + "\n", encoding="utf-8"
    )
    (output_dir / "guardrails.md").write_text(
        "# Jack Pockets guardrails\n\n"
        + "\n".join(f"- {item}" for item in components["guardrails"])
        + "\n",
        encoding="utf-8",
    )
    (output_dir / "LongTermMEMORY.md").write_text(
        str(components["memory"]).strip() + "\n", encoding="utf-8"
    )
    (output_dir / "tool_descriptions").mkdir(parents=True, exist_ok=True)
    (output_dir / "tool_descriptions" / "tool_guidance.md").write_text(
        "# Jack Pockets tool guidance\n\n"
        + "\n".join(f"- {item}" for item in components["tool_guidance"])
        + "\n",
        encoding="utf-8",
    )

    skills_dir = output_dir / "skills"
    for name in components["skills"]:
        skill = skills_dir / _slug(name)
        skill.mkdir(parents=True, exist_ok=True)
        (skill / "SKILL.md").write_text(
            f"---\nname: {_slug(name)}\ndescription: Jack Pockets {name} workflow.\n---\n\n"
            f"# {name}\n\nThis Harness² skill is an integration surface for the existing Jack Pockets workflow.\n",
            encoding="utf-8",
        )

    subagents_dir = output_dir / "sub_agents"
    for name in components["subagents"]:
        agent = subagents_dir / _slug(name)
        agent.mkdir(parents=True, exist_ok=True)
        (agent / "AGENT.md").write_text(
            f"---\nmode: subagent\ndescription: Jack Pockets {name} specialist.\n---\n\n"
            f"# {name}\n\nCoordinate the existing Jack Pockets {name} responsibility without bypassing quality gates.\n",
            encoding="utf-8",
        )

    scripts_dir = output_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    for name in components["scripts"]:
        (scripts_dir / name).write_text(
            "\"\"\"Harness² integration placeholder for an existing Jack Pockets script.\"\"\"\n"
            "raise SystemExit(\"Use the production Jack Pockets script; this native harness is opt-in.\")\n",
            encoding="utf-8",
        )

    plugin_dir = output_dir / "plugin"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    for name in components["plugins"]:
        (plugin_dir / f"{_slug(name)}.ts").write_text(
            "// Harness² integration placeholder. Production tooling remains authoritative.\n",
            encoding="utf-8",
        )

    (output_dir / "README.md").write_text(
        "# Jack Pockets native Harness² surface\n\n"
        "Generated from `harness2/jack_pockets_harness.json`. This tree is an opt-in "
        "Harness² optimization surface; it does not replace the production pipeline.\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    args = parser.parse_args()
    render(args.manifest, args.output)


if __name__ == "__main__":
    main()
