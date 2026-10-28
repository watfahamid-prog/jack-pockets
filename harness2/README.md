# Harness² integration

Jack Pockets has an opt-in integration point for Google's open-source Harness² framework.

## What is included

- `requirements-harness2.txt` pins the upstream Harness² repository to a known commit.
- `jack_pockets_harness.json` describes the documentary pipeline, guardrails, learning memory, tool guidance, subagents, skills, scripts and plugins.
- `record_run.py` stores a structured generation outcome in a bounded experience ledger.
- `propose_improvements.py` creates proposals from repeated observations; proposals are not adopted automatically.
- GitHub Actions validates the manifest, runs the learning utility tests and runs a credential-free Harness² demo.

## Why it is isolated

Harness² currently requires Python 3.12–3.13, while the production Jack Pockets pipeline supports Python 3.11. Do not add Harness² to production requirements or force the renderer onto Python 3.12.

Create a separate Python 3.12 environment when using Harness²:

```bash
uv venv --python 3.12 .venv-harness2
source .venv-harness2/bin/activate
uv pip install -r requirements-harness2.txt
harness2-demo --output runs/harness2-demo --k 1
```

The local demo does not require model credentials. Model-backed Harness² recursion can incur API costs, so it remains opt-in.

## Adoption rule

Harness² is an optimizer for evaluating the documentary pipeline, not a replacement for that pipeline. Candidate improvements must be tested against research accuracy, footage relevance, provenance, and video-quality gates before becoming production defaults.

Run evidence and proposals are useful history, but they do not by themselves prove video quality or change production behavior. The Actions cache is best-effort history, not a permanent database.

The official framework is maintained at https://github.com/google-research/harness2.
