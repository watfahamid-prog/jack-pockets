# Daily Jack Pockets code improvement task

You are operating in the actual checked-out Jack Pockets repository on an isolated GitHub Actions runner. Your model is a local Ollama model; you are invoked by Claude Code in non-interactive mode.

1. Read CLAUDE.md, inspect the current git status and recent history, then examine the code, tests and existing reports relevant to the most important verified defect.
2. Choose at most ONE meaningful, evidence-backed code defect or reliability improvement per run. Prioritize correctness, media/narration matching, timing, rendering reliability, captions, asset validation and reproducible failures. Do not chase style-only edits or invent work just to create a diff.
3. Make the smallest complete fix. Never claim success based only on reasoning. Let the workflow's independent verification steps decide whether the patch passes.
4. Do NOT run a full documentary generation, download model weights, call paid/provider APIs, access secrets, publish media or change production provider settings.
5. Do NOT change any tests, dependency manifests, GitHub Actions workflows, this prompt, CLAUDE.md, runner setup scripts or the local-agent setup documentation. Do not weaken gates, delete assertions, skip tests, disable validation, change permissions, or alter billing behavior.
6. Never include secrets, tokens, local user files, cache contents or generated video/audio in git changes.
7. If no real defect can be established from the repository evidence, leave the working tree unchanged and explain that no justified change was found.
8. At the end, summarize the precise files changed and why. Do not commit or push; the workflow owns verification, branching, PR creation and merge.
