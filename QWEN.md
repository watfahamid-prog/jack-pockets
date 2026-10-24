# Qwen experiment for Jack Pockets

## Status

This is an **opt-in experiment**, not a production default. The existing Gemini/OpenAI/Anthropic provider order remains unchanged when `LLM_PROVIDER=auto`. Selecting `LLM_PROVIDER=qwen` uses only the configured Qwen endpoint; it will not silently fall back to a paid provider.

## First test: local and free

1. Install Ollama on your Windows PC from https://ollama.com/download.
2. In a terminal, run `ollama pull qwen3:4b`.
3. Ensure Ollama is running. Its local service should be available at `http://localhost:11434`.
4. In a local copy of this repository, set these variables in `.env`:

   ```dotenv
   LLM_PROVIDER=auto
   QWEN_BASE_URL=http://localhost:11434/v1
   QWEN_MODEL=qwen3:4b
   QWEN_API_KEY=
   ```

5. From the repository root, install only the small dependency set needed for this plan-only test:

   ```powershell
   python -m pip install -r requirements-qwen.txt
   ```

   This avoids installing the full pipeline dependencies (such as transcription/TTS libraries) just to test Qwen.

6. Run the dedicated plan-only smoke test:

   ```powershell
   python qwen_smoke_test.py --topic "What Is the Most Expensive Thing Ever?"
   ```

   This calls Qwen directly, saves the plan to `out/qwen-smoke-test-plan.json`, and does not render a video or change the production provider selection. It checks that the model returns a structurally valid plan with 8–14 beats and at least 1,400 narration words. Without a research packet, it tests connectivity and structure only—not factual accuracy.

7. For a meaningful baseline comparison, supply the same research packet used by the existing provider:

   ```powershell
   python qwen_smoke_test.py --topic "What Is the Most Expensive Thing Ever?" --research path\to\research.json --output out\qwen-plan.json
   ```

   Inspect source support, factual accuracy, narration repetition, and visual keyword specificity before trying a full documentary.

The Qwen model runs on your own machine; no Qwen API key or paid API call is required for local Ollama. It uses your computer's memory, processing power, storage, and electricity. A 4B model is a small baseline for testing, not a claim that it will outperform the current production model.


### Windows troubleshooting: `ollama` is not recognized

If PowerShell says `ollama` is not recognized after installation, close and reopen PowerShell first. Then check the standard per-user install path:

```powershell
Test-Path "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"
```

If it returns `True`, invoke Ollama by its full path while Windows PATH is being refreshed or repaired:

```powershell
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" --version
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" pull qwen3:4b
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" run qwen3:4b "Explain what makes a documentary interesting."
```

If the test returns `False`, check **Settings → Apps → Installed apps** for Ollama and install it from the official Windows download page before continuing.

## Hosted Qwen endpoint (optional)

If later using a hosted OpenAI-compatible Qwen endpoint, set `QWEN_BASE_URL`, `QWEN_MODEL`, and store the endpoint's key in your local `.env` or a GitHub Actions secret. Hosted inference may cost money. Do not commit keys or put them in this file.

## Safety and acceptance gate

- Never enable Qwen by default until it passes the existing unit tests and a real-task comparison.
- Compare the same research packet/topic against the current production provider.
- Check factual support, source URLs, 8–14 beats, 1,400+ narration words, keyword specificity, repeated narration, and plan validity.
- Then compare a rendered documentary's actual scene relevance, audio, timing, and quality gates.
- Keep Qwen experimental if it is slower, fails schema/quality checks, or does not improve the baseline.
- Do not add Qwen to the normal GitHub Actions generation workflow: the default local URL is not available to GitHub-hosted runners, and hosted inference could incur cost.
