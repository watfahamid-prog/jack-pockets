# Claude Code and Codex with local Ollama on Windows

This is the local development-agent setup. It is separate from Jack Pockets' documentary provider setting (`LLM_PROVIDER`).

## Setup

1. Open PowerShell in the Jack Pockets repository folder.
2. Check `ollama --version` and `npm --version`. If Ollama is missing, install the Windows app from the official Ollama site, then reopen PowerShell.
3. Run the repository script:

   ```powershell
   .\scripts\setup-local-coding-agents.ps1
   ```

4. When the script finishes, connect each CLI to a local Ollama model:

   ```powershell
   ollama launch claude
   ollama launch codex
   ```

Choose a local model, not one tagged `:cloud`, if the goal is no hosted-model API charges. Start with a model your PC can run; larger models need more memory and storage.

## Important limits

- Local Ollama inference avoids per-call charges to the Claude/OpenAI model APIs, but uses the PC's CPU/GPU, memory, storage and electricity.
- The CLI tools are not themselves the AI models. Running a local model through either CLI does not give it the full capability of the providers' hosted flagship models.
- A GitHub-hosted runner cannot reach Ollama running on your PC at `localhost`. Running local inference in GitHub Actions would require installing/running a model on that runner or using an accessible model endpoint.
- The cleanup script removes installed Qwen Ollama models and the OpenCode npm CLI if present. It moves old OpenCode configuration folders into a timestamped backup rather than deleting your settings permanently.
- The script does not change Jack Pockets source files and does not add paid API keys.

Official entry points: [Ollama](https://ollama.com/download), [Claude Code](https://docs.anthropic.com/en/docs/claude-code/overview), [Codex](https://developers.openai.com/codex/).
