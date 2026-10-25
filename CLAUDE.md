# Jack Pockets — Claude Code instructions

## Mission
Maintain an original, footage-led long-form documentary generator. Protect factual accuracy, source/media provenance, visual relevance, narration synchronization, render reliability and low-cost operation.

## Working method
- Inspect the current branch, working tree, relevant source and existing tests before editing.
- Make the smallest complete patch that addresses the demonstrated problem. Avoid unrelated refactors or new dependencies.
- Prefer deterministic tests and free/local inference when that fits the task. Never use cloud-tagged Ollama models or hosted API providers without explicit authorization.
- Do not trigger full documentary generation, large model downloads or paid API calls for a code-only task unless the user explicitly asks.
- For Python changes, run `python -m compileall -q .` and relevant tests. Run `python -m unittest discover -s tests -v` for broad Python changes. Run `npm run typecheck` for Remotion/TypeScript changes.
- Review the actual diff and CI logs. Report exact tests and their outcomes; never claim a command succeeded without evidence.
- Unit tests do not prove the video is visually correct. Do not claim video acceptance unless the MP4, representative frames, narration/audio alignment, shot relevance and provenance were inspected.
- For substantial changes, use an isolated branch and pull request. Never bypass quality gates or blindly merge agent-written code.
- Keep credentials in environment/secrets; never print or commit secret values.

## Project boundaries
- Documentary providers are Gemini, OpenAI and Anthropic. Do not silently change provider order, model names or billing behavior.
- Preserve the existing Remotion + FFmpeg pipeline and quality gates unless the task specifically asks to change them.
- Harness² output is an opt-in development aid; proposals are not production code until independently checked and tested.
- Prefer changes that reduce operational risk and user effort without sacrificing evidence or reproducibility.
