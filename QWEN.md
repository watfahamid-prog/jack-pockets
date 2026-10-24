# Qwen experiment for Jack Pockets

## Status

This is an **opt-in experiment**, not a production default. The existing Gemini/OpenAI/Anthropic provider order remains unchanged when `LLM_PROVIDER=auto`. Selecting `LLM_PROVIDER=qwen` uses only the configured Qwen endpoint; it will not silently fall back to a paid provider.

## First test: local and free

1. Install Ollama on your Windows PC from https://ollama.com/download.
2. In a terminal, run `ollama pull qwen3:4b`.
3. Ensure Ollama is running, then check `http://localhost:11434` is available locally.
4. In a local copy of this repository, set these variables in `.env`:

   ```dotenv
   LLM_PROVIDER=qwen
   QWEN_BASE_URL=http://localhost:11434/v1
   QWEN_MODEL=qwen3:4b
   QWEN_API_KEY=
   ```

5. Run the pipeline's existing validation/tests first, then run a small generation locally and inspect the plan before trying a full documentary.

The Qwen model runs on your own machine; no Qwen API key or paid API call is required for local Ollama. It will use your computer's memory, processing power, storage, and electricity. A 4B model is a small baseline for testing, not a claim that it will outperform the current production model.

## Hosted Qwen endpoint (optional)

If later using a hosted OpenAI-compatible Qwen endpoint, set `QWEN_BASE_URL`, `QWEN_MODEL`, and store the endpoint's key in your local `.env` or a GitHub Actions secret. Hosted inference may cost money. Do not commit keys or put them in this file.

## Safety and acceptance gate

- Never enable Qwen by default until it passes the existing unit tests and a real-task comparison.
- Compare the same research packet/topic against the current production provider.
- Check factual support, source URLs, 8–14 beats, 1,400+ narration words, keyword specificity, repeated narration, and plan validity.
- Then compare a rendered documentary's actual scene relevance, audio, timing, and quality gates.
- Keep Qwen experimental if it is slower, fails schema/quality checks, or does not improve the baseline.
- Do not add Qwen to the normal GitHub Actions generation workflow: the default local URL is not available to GitHub-hosted runners, and hosted inference could incur cost.
