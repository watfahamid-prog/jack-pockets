# Claude Code and Codex with local Ollama on Windows

This is the local development-agent setup. It is separate from Jack Pockets' documentary provider setting (`LLM_PROVIDER`).

## Local setup

1. Open PowerShell in the Jack Pockets repository folder.
2. Check `ollama --version` and `npm --version`. If Ollama is missing, install the Windows app from the official Ollama site, then reopen PowerShell.
3. Run the repository script:

   ```powershell
   .\scripts\setup-local-coding-agents.ps1
   ```

4. To open Claude Code using your local Ollama model, run:

   ```powershell
   ollama launch claude
   ```

Choose a local model, not one tagged `:cloud`, if the goal is no hosted-model API charges.

## Automatic daily coding improvements (no daily prompts)

Jack Pockets has a scheduled workflow, `.github/workflows/claude-code-local-polish.yml`. Once the one-time runner setup below is complete, it runs at 08:00 in the laptop's local time and can be manually dispatched from the repository's Actions page. Its prompt is stored in `.github/prompts/claude-code-local-polish.md`; you do not have to type a prompt each morning.

The workflow connects Claude Code to the local Ollama server with:

- `ANTHROPIC_BASE_URL=http://127.0.0.1:11434`
- `ANTHROPIC_AUTH_TOKEN=ollama`
- The local model selected by repository variable `OLLAMA_CODING_MODEL`, defaulting to `gemma4:e2b-it-q4_K_M`.

It runs Python compilation and unit tests, the TypeScript typecheck, caption tests and diff checks. It allows up to two repair passes. For a real change, it creates an isolated branch and pull request and attempts to merge only after those checks pass. If repository rules block unattended merging, it leaves the pull request open. Workflow logs are saved as a GitHub artifact.

### One-time self-hosted runner setup

A GitHub-hosted runner cannot reach Ollama at `127.0.0.1` on your laptop. The job therefore needs a self-hosted Windows runner on the same machine as Ollama.

1. On GitHub, open the `watfahamid-prog/jack-pockets` repository, then go to **Settings → Actions → Runners → New self-hosted runner → Windows → x64**.
2. Follow GitHub's displayed instructions to download and extract the runner into a folder such as `C:\actions-runner`. Use the short-lived token shown on that page only in the local PowerShell window. Never paste it into ChatGPT or commit it.
3. Configure the runner for this repository and add the custom label `jack-pockets-ollama` (keep GitHub's default `self-hosted`, `Windows` and `X64` labels too).
4. Run the runner as a Windows service under the same Windows account that has Claude Code, Git for Windows/Git Bash and access to the local Ollama server. Start Ollama automatically at sign-in/boot and make sure the PC does not sleep during the scheduled run. GitHub's generated setup page provides the correct runner download and configuration commands for your account.
5. In **Settings → Actions → Runners**, confirm the runner shows **Idle** while the laptop is powered on and connected.

After this one-time setup, the prompt and checks run automatically; you do not need to open Claude Code or type prompts every day. If the laptop is off or asleep at run time, the local agent cannot run.

### Current limits

- Local Ollama inference avoids per-call charges to the Claude/Anthropic model APIs, but uses the PC's CPU/GPU, memory, storage and electricity.
- Claude Code is the coding interface; the local Ollama model generates the responses. It is not the same as running Anthropic's hosted Claude model.
- A successful code test suite is not proof that the final documentary looks good. The actual MP4, frames, narration/shot match and audio still need to be inspected independently.
- **Video delivery is separate from code polishing.** `.github/workflows/generate-video.yml` supports the existing manual `workflow_dispatch` and a daily 10:00 UTC scheduled run. Scheduled runs are deliberately **paused by default**: the job is skipped until the repository Actions variable `DAILY_VIDEO_AUTOMATION_ENABLED` is set to the exact string `true`. This protects against unexpected provider/API charges because the existing generator uses whichever configured provider secrets are available.
- Once enabled, the scheduled workflow selects a rotating subject from `topics/auto_topics.txt`, runs the existing quality gates, uploads the MP4 and diagnostics as a GitHub Actions artifact for 14 days, and puts a download link in the run summary. Failures get a run-log link instead of a “video ready” message. Review the actual MP4 before publishing.
- To enable daily video creation, open **Settings → Secrets and variables → Actions → Variables → New repository variable** and create `DAILY_VIDEO_AUTOMATION_ENABLED=true` only after checking that your configured LLM/TTS provider usage is within a free allowance or that you accept any charges. This is a one-time switch; no daily topic prompt is needed.
- The workflow does not change production provider keys or add paid API keys.
