# Claude Code and Codex with local Ollama on Windows

This is the local development-agent setup. It is separate from Jack Pockets' documentary provider setting (LLM_PROVIDER).

## Local setup

1. Open PowerShell in the Jack Pockets repository folder.
2. Check ollama --version and npm --version. If Ollama is missing, install the Windows app from the official Ollama site, then reopen PowerShell.
3. Run the repository script:

   ~~~powershell
   .\scripts\setup-local-coding-agents.ps1
   ~~~

4. To open Claude Code using your local Ollama model, run:

   ~~~powershell
   ollama launch claude
   ~~~

Choose a local model, not one tagged :cloud, if the goal is no hosted-model API charges.

## Daily read-only code audit (no daily prompts)

The intended daily audit workflow is .github/workflows/claude-code-local-polish.yml. It is being changed to be a **read-only review**, not a coding/auto-merge agent. Its report should rate overall system quality and major subsystems from 1 to 10, cite exact code evidence, list gaps in inspection coverage, and propose improvements for later approval. The report is saved as a GitHub Actions summary/artifact, not committed into the repository.

The workflow connects Claude Code to the local Ollama server with:

- ANTHROPIC_BASE_URL=http://127.0.0.1:11434
- ANTHROPIC_AUTH_TOKEN=ollama
- The local model selected by repository variable OLLAMA_CODING_MODEL, defaulting to gemma4:e2b-it-q4_K_M.

Claude Code is invoked in plan/read-only mode with only read/search/list tools allowed. It has no repository write permissions and no permission to run Bash commands; the workflow checks that the checkout remains unchanged. This is the Claude Code CLI using the local Ollama model, **not** Anthropic's hosted Claude model. It does not automatically patch, commit, push, open PRs, or merge code.

### Security requirement before the daily agent can run

**Do not register a self-hosted runner against the public watfahamid-prog/jack-pockets repository.** GitHub warns against using self-hosted runners with public repositories because workflow code may expose the runner's machine. This repository is public, so the local Ollama runner must first be arranged through a separate **private controller repository**. The current workflow is not operational until that secure controller setup is completed and the runner is registered there. Do not use any runner registration token that has previously been pasted into a chat; generate a fresh token from the eventual private controller repository's runner settings when setup is ready, and enter it only in the local setup terminal.

A GitHub-hosted runner cannot reach Ollama at 127.0.0.1 on your laptop. For the local model to run daily, the machine hosting Ollama must be on, awake, connected, and have the runner service available at the scheduled time. Keep runner registration tokens and any repository tokens private.

## Documentary generation: manual only for now

The daily trigger has been removed from .github/workflows/generate-video.yml. Documentary generation is **manual-only** until the generated footage, narration match, timing, audio and final quality gate are satisfactory. Do not enable any automated video schedule. A manual run can still call configured provider APIs and may incur charges, so do not trigger one until the providers' pricing/allowances have been checked and the user has explicitly approved the run. Do not publish an MP4 until the actual file has been inspected.

## Current limits

- Local Ollama inference avoids per-call charges to the Claude/Anthropic model APIs, but uses the PC's CPU/GPU, memory, storage and electricity.
- A code-quality score is an inspection opinion based on evidence, not proof of runtime behavior.
- Passing CI or type checks is not proof the final documentary looks good. The actual MP4, frames, narration/shot match and audio still need to be inspected independently.
