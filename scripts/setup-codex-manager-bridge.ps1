param(
    [switch]$EnableDeprecatedCliBridge
)

if (!$EnableDeprecatedCliBridge) {
    Write-Host "The legacy Codex CLI bridge is dormant and disabled by default." -ForegroundColor Yellow
    Write-Host "Use the ChatGPT desktop app's Codex view for the active workflow."
    Write-Host "No installation or sign-in was started."
    Write-Host "Only rerun with -EnableDeprecatedCliBridge if you explicitly decide to reactivate the legacy CLI bridge."
    exit 2
}

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot

# Keep automation authentication/config separate from any existing desktop Codex profile.
$bridgeHome = Join-Path $env:LOCALAPPDATA "JackPocketsCodexBridge"
$env:CODEX_HOME = Join-Path $bridgeHome "codex-home"
New-Item -ItemType Directory -Force -Path $env:CODEX_HOME | Out-Null

# Ensure a previously configured API key is not used for this ChatGPT-plan bridge.
Remove-Item Env:OPENAI_API_KEY -ErrorAction SilentlyContinue

Write-Host "Jack Pockets ChatGPT-to-Codex bridge setup" -ForegroundColor Cyan
Write-Host "Repository: $repoRoot"
Write-Host "This setup uses Codex signed in with your ChatGPT account; it does not configure an API key."

$git = Get-Command git -ErrorAction SilentlyContinue
if (!$git) { throw "Git was not found. Install Git for Windows first." }
if (!(Test-Path (Join-Path $repoRoot ".git"))) { throw "This folder is not a Git repository." }

$npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
$codex = Get-Command codex -ErrorAction SilentlyContinue
if (!$codex) {
    if (!$npm) { throw "npm.cmd was not found. Install Node.js, reopen PowerShell, then rerun this script." }
    Write-Host ""
    Write-Host "Installing the official Codex CLI adapter (not an Ollama model)..." -ForegroundColor Cyan
    & $npm.Source install -g @openai/codex
    if ($LASTEXITCODE -ne 0) { throw "Codex CLI installation failed." }
    $env:PATH = "$env:APPDATA\npm;$env:PATH"
    $codex = Get-Command codex -ErrorAction SilentlyContinue
}
if (!$codex) { throw "Codex CLI was installed but is not visible. Close and reopen PowerShell, then rerun setup." }
$codexPath = $codex.Source

$gh = Get-Command gh -ErrorAction SilentlyContinue
if ($gh) {
    $ghPath = $gh.Source
} else {
    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (!$winget) { throw "GitHub CLI (gh) is required. Install it from https://cli.github.com/ and rerun setup." }
    Write-Host ""
    Write-Host "Installing GitHub CLI..." -ForegroundColor Cyan
    & $winget.Source install --id GitHub.cli --exact --source winget --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) { throw "GitHub CLI installation did not complete. Install GitHub CLI, reopen PowerShell, and rerun setup." }
    $candidatePaths = @(
        (Join-Path $env:ProgramFiles "GitHub CLI\gh.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\GitHub CLI\gh.exe")
    )
    $ghPath = $candidatePaths | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (!$ghPath) { throw "GitHub CLI installed or attempted but is not visible. Close and reopen PowerShell, then rerun setup." }
}
if (!(Test-Path $ghPath)) { throw "GitHub CLI executable was not found at the expected location." }

Write-Host ""
Write-Host "Checking GitHub CLI authentication..." -ForegroundColor Cyan
& $ghPath auth status --hostname github.com
if ($LASTEXITCODE -ne 0) {
    Write-Host "A browser sign-in is needed. Sign in to the GitHub account that can push to this repository." -ForegroundColor Yellow
    & $ghPath auth login --hostname github.com --git-protocol https --web
    if ($LASTEXITCODE -ne 0) { throw "GitHub sign-in did not complete." }
}
& $ghPath auth status --hostname github.com
if ($LASTEXITCODE -ne 0) { throw "GitHub CLI is not authenticated." }

Write-Host ""
Write-Host "Checking Codex sign-in..." -ForegroundColor Cyan
$loginText = (& $codexPath login status 2>&1 | Out-String)
$loginCode = $LASTEXITCODE
if ($loginText -match "(?i)api key|apikey") {
    throw "Codex reports API-key authentication. To avoid API billing, run 'codex logout', then 'codex login' and choose Sign in with ChatGPT; rerun setup afterward."
}
if ($loginCode -ne 0) {
    Write-Host "Sign in with your ChatGPT account (not an API key)." -ForegroundColor Yellow
    & $codexPath login
    if ($LASTEXITCODE -ne 0) { throw "Codex sign-in did not complete." }
}
$loginText = (& $codexPath login status 2>&1 | Out-String)
if ($LASTEXITCODE -ne 0 -or $loginText -match "(?i)api key|apikey") {
    throw "Could not confirm ChatGPT-plan Codex authentication. No task was started."
}

$python = Get-Command python -ErrorAction SilentlyContinue
if (!$python) {
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if (!$py) { throw "Python 3 is required for the bridge. Install Python 3.11+, reopen PowerShell, then rerun setup." }
    $pythonArgs = @("-3", (Join-Path $repoRoot "scripts\codex_manager_bridge.py"), "--enable-deprecated-cli-bridge", "--watch", "--repo-path", $repoRoot)
} else {
    $pythonArgs = @((Join-Path $repoRoot "scripts\codex_manager_bridge.py"), "--enable-deprecated-cli-bridge", "--watch", "--repo-path", $repoRoot)
}

Write-Host ""
Write-Host "Starting the bridge. Leave this window open and keep the PC awake to receive tasks." -ForegroundColor Green
Write-Host "Only issues created by watfahamid-prog with the [CODEX-TASK] prefix and required marker are accepted."
Write-Host "Codex will create draft PRs; it will never merge them. Press Ctrl+C to stop."
if ($python) {
    & $python.Source @pythonArgs
} else {
    & $py.Source @pythonArgs
}
