from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

MANIFEST = Path(__file__).with_name("jack_pockets_harness.json")


def _slug(value: str) -> str:
    value = re.sub(r"[^a-z0-9_-]+", "-", value.lower())
    return value.strip("-_") or "component"


def _render_instructions(agent: str, components: dict, memory_text: str) -> str:
    lines = [
        f"# Jack Pockets instructions for {agent}", "",
        "## Project goal", str(components["system_prompt"]).strip(), "",
        "## Guardrails", *[f"- {item}" for item in components["guardrails"]], "",
        "## Tool guidance", *[f"- {item}" for item in components["tool_guidance"]], "",
        "## Skills", *[f"- When the {name} workflow applies, load the {_slug(name)} skill." for name in components["skills"]], "",
        "## Subagent responsibilities", *[f"- {name}" for name in components["subagents"]], "",
        "## Run-learning memory", memory_text.strip(), "",
        "## Development workflow",
        "- Inspect the current branch, working tree, relevant source files and existing tests before editing.",
        "- Keep changes scoped to the task; do not replace functioning components merely to simplify an experiment.",
        "- Prefer free/local inference when that fits the task. Do not switch to hosted APIs or cloud-tagged models without explicit authorization.",
        "- Do not run a full documentary generation or spend hosted API quota for a code-only task unless the user explicitly asks.",
        "- Run relevant regression tests, inspect their actual output, review the complete diff, and report failures honestly.",
        "- Never claim the finished video is visually verified unless the actual MP4, representative frames, audio and shot relevance were inspected.",
        "- Use an isolated branch and pull request for non-trivial changes. Do not bypass quality gates or blindly merge agent-written code.",
        "- Keep credentials in the environment/secrets; never print or commit secret values.", ""
    ]
    return "\n".join(lines)


def _write_skill(parent: Path, name: str) -> None:
    skill_name = _slug(name)
    skill_dir = parent / skill_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {skill_name}\ndescription: Jack Pockets {name} workflow.\n---\n\n"
        f"# {name}\n\nUse the existing Jack Pockets implementation where possible. Inspect relevant files first, "
        "make a scoped patch, run targeted tests, and report verifiable evidence. Preserve source "
        "provenance, video-quality gates, and the project's cost limits.\n",
        encoding="utf-8",
    )


def render(manifest_path: Path, output_dir: Path, memory_path: Path | None = None) -> None:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    components = data["components"]
    output_dir.mkdir(parents=True, exist_ok=True)

    memory_text = str(components["memory"]).strip()
    if memory_path is not None:
        if not memory_path.exists():
            raise FileNotFoundError(f"Harness² memory overlay not found: {memory_path}")
        memory_text = memory_path.read_text(encoding="utf-8").strip()

    (output_dir / "AGENTS.md").write_text(_render_instructions("Codex", components, memory_text), encoding="utf-8")
    (output_dir / "CLAUDE.md").write_text(_render_instructions("Claude Code", components, memory_text), encoding="utf-8")
    (output_dir / "memory.md").write_text(memory_text + "\n", encoding="utf-8")

    for relative_parent in (Path(".agents") / "skills", Path(".claude") / "skills"):
        for name in components["skills"]:
            _write_skill(output_dir / relative_parent, name)

    subagents_dir = output_dir / "subagents"
    subagents_dir.mkdir(parents=True, exist_ok=True)
    for name in components["subagents"]:
        (subagents_dir / f"{_slug(name)}.md").write_text(
            f"# {name}\n\nSpecialist responsibility for the Jack Pockets development workflow. "
            "Coordinate with the main agent, keep changes isolated, and never bypass quality gates.\n",
            encoding="utf-8",
        )

    scripts_dir = output_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    for name in components["scripts"]:
        (scripts_dir / name).write_text(
            '"""Harness² integration placeholder for an existing Jack Pockets script."""\n'
            'raise SystemExit("Use the production Jack Pockets script; this generated agent surface is opt-in.")\n',
            encoding="utf-8",
        )

    extensions_dir = output_dir / "extensions"
    extensions_dir.mkdir(parents=True, exist_ok=True)
    for name in components["plugins"]:
        (extensions_dir / f"{_slug(name)}.md").write_text(
            f"# {name}\n\nIntegration placeholder only. Production Jack Pockets tools remain authoritative.\n",
            encoding="utf-8",
        )

    (output_dir / "README.md").write_text(
        "# Jack Pockets Claude Code and Codex surfaces\n\n"
        "Generated from harness2/jack_pockets_harness.json. "
        "This is an opt-in instruction/skill surface; it does not replace the production pipeline "
        "or install either coding agent.\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--memory", type=Path, help="Optional evidence-backed memory file to overlay into both generated agent instruction files.")
    args = parser.parse_args()
    render(args.manifest, args.output, args.memory)


if __name__ == "__main__":
    main()
