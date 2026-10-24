# Harness² integration

Jack Pockets now has an opt-in integration point for Google's open-source Harness² framework.

## What is added

- `requirements-harness2.txt` pins the upstream Harness² repository to a known commit.
- `jack_pockets_harness.json` describes the current Jack Pockets agent harness using Harness²'s eight editable component categories: system prompt, guardrails, memory, tool guidance, subagents, skills, scripts, and plugins.
- `render_native_harness.py` deterministically translates that manifest into an OpenCode-compatible Harness² c1-c8 surface under `harness2/native`.
- CI installs the pinned Harness² checkout and validates that generated surface with Harness²'s own OpenCode surface validator before running its credential-free demo.

## Why it is isolated

Harness² currently requires Python 3.12–3.13, while the production Jack Pockets pipeline supports Python 3.11. Do not add Harness² to the main production requirements or force the documentary renderer onto Python 3.12.

Create a separate Python 3.12 environment when using Harness²:

```bash
uv venv --python 3.12 .venv-harness2
source .venv-harness2/bin/activate
uv pip install -r requirements-harness2.txt
harness2-demo --output runs/harness2-demo --k 1
```

To render the Jack Pockets native Harness² surface locally:

```bash
python harness2/render_native_harness.py --output harness2/native
```

The local demo does not require model credentials. Model-backed Harness² recursion can incur API costs, so it remains opt-in.

## Adoption rule

Harness² is an optimizer around the Jack Pockets agent harness, not a replacement for the documentary pipeline. Candidate improvements must be tested against Jack Pockets' existing research, relevance, provenance, and video quality gates before becoming production defaults.

The native surface is deliberately an integration boundary: generated skills, subagents, scripts, and plugins do not alter production behavior by themselves. Production adoption remains a separate, validated step.

The official framework is maintained at https://github.com/google-research/harness2.
