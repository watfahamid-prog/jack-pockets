$ErrorActionPreference = "Stop"

function Get-OllamaCommand {
    $cmd = Get-Command ollama -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $candidate = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
    if (Test-Path -LiteralPath $candidate) { return $candidate }
    return $null
}

$ollamaExe = Get-OllamaCommand
if (-not $ollamaExe) {
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) { throw "Ollama is not installed and winget is unavailable. Install Ollama for Windows, reopen PowerShell, and run this script again." }
    Write-Host "Installing Ollama for Windows..."
    & $winget.Source install --id Ollama.Ollama -e --source winget --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) { throw "Ollama installation did not complete. Install it manually and rerun this script." }
    $ollamaExe = Get-OllamaCommand
    if (-not $ollamaExe) { throw "Ollama was installed, but PowerShell cannot locate it yet. Reopen PowerShell and rerun this script." }
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "npm was not found. Install Node.js 20 or newer, reopen PowerShell, and run this script again."
}

Write-Host "Checking Ollama..."
& $ollamaExe --version
if ($LASTEXITCODE -ne 0) { throw "Ollama did not respond successfully." }

Write-Host "Removing the retired OpenCode npm CLI, if present..."
$globalPackages = (& npm list --global --depth=0 2>$null | Out-String)
if ($globalPackages -match "opencode-ai@") {
    & npm uninstall --global opencode-ai
    if ($LASTEXITCODE -ne 0) { throw "Could not uninstall the retired OpenCode CLI package." }
}

# Preserve settings in a timestamped backup rather than destroying user configuration.
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupRoot = Join-Path $env:LOCALAPPDATA "JackPocketsCleanup\retired-agent-configs\$stamp"
$configPaths = @(
    (Join-Path $HOME ".config\opencode"),
    (Join-Path $env:APPDATA "opencode"),
    (Join-Path $env:LOCALAPPDATA "opencode")
)
$backupIndex = 0
foreach ($path in ($configPaths | Select-Object -Unique)) {
    if (Test-Path -LiteralPath $path) {
        New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
        $backupIndex++
        Move-Item -LiteralPath $path -Destination (Join-Path $backupRoot "config-$backupIndex")
        Write-Host "Archived retired settings under $backupRoot"
    }
}

Write-Host "Removing local Qwen models, if any..."
$modelListing = (& $ollamaExe list 2>&1 | Out-String)
if ($LASTEXITCODE -eq 0) {
    $modelNames = @($modelListing -split '\r?\n' | Select-Object -Skip 1 | ForEach-Object {
        $line = $_.Trim()
        if ($line) { ($line -split '\s+')[0] }
    } | Where-Object { $_ -match '(?i)^qwen' } | Select-Object -Unique)
    foreach ($modelName in $modelNames) {
        Write-Host "Removing local model $modelName"
        & $ollamaExe rm $modelName
        if ($LASTEXITCODE -ne 0) { throw "Could not remove local model $modelName." }
    }
} else {
    Write-Warning "Could not list local models; no Qwen model was removed. Run 'ollama list' to inspect the result."
}

Write-Host "Installing Claude Code and Codex CLI..."
& npm install --global @anthropic-ai/claude-code @openai/codex
if ($LASTEXITCODE -ne 0) { throw "Could not install the coding-agent CLIs." }

Write-Host "Verifying CLI versions..."
& claude --version
if ($LASTEXITCODE -ne 0) { throw "Claude Code version check failed." }
& codex --version
if ($LASTEXITCODE -ne 0) { throw "Codex version check failed." }

Write-Host "Setup finished. Next run these two commands and select a local model (not a :cloud model):"
Write-Host "  ollama launch claude"
Write-Host "  ollama launch codex"
Write-Host "This script preserves old OpenCode settings in a backup and does not modify Jack Pockets source files."
