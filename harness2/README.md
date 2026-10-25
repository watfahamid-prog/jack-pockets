# Harness² integration

Jack Pockets has an opt-in integration point for Google's open-source Harness² framework.

## What is included

- `requirements-harness2.txt` pins the upstream Harness² repository to a known commit.
- `jack_pockets_harness.json` describes the current agent harness using Harness²'s eight editable component categories: system prompt, guardrails, memory, tool guidance, subagents, skills, scripts and plugins.
- `render_native_harness.py` translates the manifest into native instruction and skill surfaces for Codex (`AGENTS.md`, `.agents/skills/`) and Claude Code (`CLAUDE.md`, `.claude/skills/`).
- Each documentary run records a structured outcome and updates a bounded evidence ledger in the reusable GitHub Actions cache. Learning memory is overlaid into both generated instruction files and uploaded with diagnostics.
- CI validates the manifest, runs the learning utility tests and checks the generated instruction/skill files before running the credential-free Harness² demo.

## Why it is isolated

Harness² currently requires Python 3.12–3.13, while the production Jack Pockets pipeline supports Python 3.11. Do not add Harness² to production requirements or force the renderer onto Python 3.12.

Create a separate Python 3.12 environment when using Harness²:

```bash
uv venv --python 3.12 .venv-harness2
source .venv-harness2/bin/activate
uv pip install -r requirements-harness2.txt
harness2-demo --output runs/harness2-demo --k 1
```

To render both coding-agent instruction surfaces locally:

```bash
python harness2/render_native_harness.py --output harness2/native
```

The local demo does not require model credentials. Model-backed Harness² recursion can incur API costs, so it remains opt-in.

## Adoption rule

Harness² is an optimizer around the Jack Pockets agent harness, not a replacement for the documentary pipeline. Candidate improvements must be tested against existing research, relevance, provenance and video-quality gates before becoming production defaults.

The evidence-memory overlay makes run observations available to both coding-agent instruction surfaces. It does not itself invoke model-backed recursion or change production code. Generated skills, subagents, scripts and extensions remain integration aids, not permission to auto-merge changes. The Actions cache is best-effort history, not a permanent database.

The official framework is maintained at https://github.com/google-research/harness2.
