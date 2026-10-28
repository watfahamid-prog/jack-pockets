> **Status: dormant / not the active team workflow.** The user reported poor results from the Codex CLI test and has chosen to use Codex Desktop first. Do not run this setup or reactivate this bridge unless the user explicitly authorizes it again. Use docs/ai-coding-team-workflow.md for the current manual desktop workflow.

# ChatGPT-to-Codex local task bridge

## What this does

This is a local bridge between the ChatGPT manager in this conversation and the Codex coding agent authenticated with the user's ChatGPT plan. ChatGPT creates a GitHub issue containing a detailed task. A poller on the user's Windows computer detects that task, creates a dedicated Git worktree from origin/main, launches Codex CLI there in a workspace-write sandbox, commits its changes to a feature branch, pushes that branch and opens a draft pull request. The user's original checkout remains on main. The result is posted back on the same issue so ChatGPT can inspect the result through the GitHub connection.

This is a GitHub-mediated handoff, not direct access to the private Codex desktop conversation history. It uses the official Codex CLI non-interactive interface. The separate Codex desktop app can remain installed.

The bridge does not use Codex Cloud, an OpenAI API key, Ollama, a hosted Claude API, or a public self-hosted GitHub Actions runner. Codex must be signed in with the user's ChatGPT account, and normal Codex Free usage limits apply. The computer must be on, connected to the internet, and running the bridge window. The bridge does not run while the computer is off or asleep.

## How the manager queues a task

When the user explicitly requests a coding change in ChatGPT, the manager creates an issue in this repository. Follow this exact format:

- Title starts with [CODEX-TASK] followed by a short, specific task title.
- The body includes the exact HTML marker below as a standalone line.
- The task after the marker states the goal, concrete evidence or files where known, expected behavior, relevant tests, and constraints.
- Never place secrets, API keys, personal data, or private local paths in the issue.

Required issue-body marker:

    <!-- codex-manager-bridge-task:v1 -->

The bridge only accepts open issues from the account watfahamid-prog, with that title prefix and marker. It ignores comments as instructions and does not process pull requests as tasks. It processes the oldest eligible unprocessed issue first. An issue is marked started, completed, failed, or blocked in a comment to prevent accidental repeated execution.

ChatGPT should create a task issue only for explicit coding requests—not for ordinary questions or planning conversations. Each issue should represent one bounded coding fix.

## Windows setup

From the local Jack Pockets repository, run:

    powershell -ExecutionPolicy Bypass -File .\scripts\setup-codex-manager-bridge.ps1

The setup script installs the official Codex CLI package if missing, and installs GitHub CLI through winget if missing. It then guides the user through:
1. GitHub CLI browser login using the GitHub account that can push to this repository.
2. Codex CLI sign-in using the user's ChatGPT account (not an OpenAI API key).
3. Starting the poller.

The setup script does not create or store a personal access token, touch model storage, or change GitHub settings. It uses an isolated Codex profile under `%LOCALAPPDATA%\\JackPocketsCodexBridge\\codex-home`, separate from any existing desktop Codex profile/settings; you sign in to that profile once with ChatGPT. It removes `OPENAI_API_KEY` only from the setup process environment so this bridge does not accidentally use API-key billing. The user may stop the bridge with Ctrl+C and restart it with the same command.

To check the queue once without keeping a poller running:

    python .\scripts\codex_manager_bridge.py --repo-path .

The watch mode polls every 60 seconds. Keep the PowerShell window open and the computer awake for tasks to be processed.

## Safety behavior

- No GitHub Actions self-hosted runner is registered. The local process only makes outbound GitHub CLI requests.
- The repository folder must be the exact Jack Pockets Git checkout with origin pointing to watfahamid-prog/jack-pockets.
- The local checkout must be on main with no tracked edits. The known untracked file local_agent_test.py is allowed but is never staged or committed; its SHA-256 is checked before and after the task.
- The bridge synchronizes main with a fast-forward-only pull. It never uses reset --hard, git clean, force-push, or merge.
- Each task gets a unique branch named codex/manager-issue-NUMBER and a separate worktree under `%LOCALAPPDATA%\\JackPocketsCodexBridge\\worktrees`. Codex never runs inside the user's original checkout. If the branch or task worktree path already exists, the bridge stops rather than overwrite it.
- Codex runs in that separate task worktree with workspace-write sandbox and approval policy never. The sandbox limits file writes to the project workspace and blocks network access by default. The bridge removes API-key variables from the child process environment and refuses Codex CLI authentication that reports API-key use.
- Codex is explicitly told not to change branches, commit, push, merge, call paid providers, generate a full video, or weaken tests. The wrapper handles staging, committing and publishing.
- Obvious secret-bearing paths (.env files except example/template files, key/certificate files, credential files, .npmrc, .aws and .ssh content) are never staged. If such a file is changed/created, the bridge stops and leaves it for manual review.
- Local task output and logs are stored under the user's LocalAppData folder, not committed to the repository.
- The bridge never merges a PR. It opens a draft PR so GitHub CI can run and the manager/human can review the actual diff and outcomes.
- If preconditions fail, Codex fails, the protected local file changes, or commit/push/PR creation fails, the bridge posts a blocked/failed status when possible and stops. Inspect the local branch/status before retrying. Do not delete a failed branch or local file without reviewing it.

## Test and verification limits

Python unit tests validate task filtering, status handling, path protection, the local scratch-file exclusion, and that creating a task worktree leaves main and the untracked scratch file untouched. They do not prove the local machine's GitHub/Codex authentication is configured. Before relying on the bridge, run it with no pending tasks and verify it reports an empty queue. The first real task should be a small code change and must end in a draft PR with CI results. No merge is automated.
