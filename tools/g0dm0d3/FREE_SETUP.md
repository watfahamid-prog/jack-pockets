# G0DM0D3 — free-only setup

This guide is for trying G0DM0D3 without intentionally using paid model inference. The vendored HTML does not include an API key, and adding this guide does not configure your personal browser automatically.

## Option A: OpenRouter's free-model router

1. Create a free account at https://openrouter.ai/ and create an API key. Do not add credits or choose a paid plan.
2. Open G0DM0D3 and its provider/settings panel.
3. Configure the OpenRouter provider with your own key.
4. Select the model ID `openrouter/free` if the interface supports entering a model ID. This router selects from available free models; it is not a fixed model and availability can change.
5. Send a tiny test prompt. Confirm the selected model is `openrouter/free` before sending it.
6. Stop if the interface selects a paid model, asks to add credits, or the provider dashboard shows a charge.

OpenRouter currently describes `openrouter/free` as a zero-token-price router and lists a free plan with request limits. Limits and available models may change: check https://openrouter.ai/openrouter/free and https://openrouter.ai/pricing before use. A free model can still have rate limits or be unavailable.

**Important:** Do not use a generic paid model ID and assume it is free. Do not add a payment method or credits just to make this test work. Never put your API key in this repository, a screenshot, or a chat message.

## Option B: Local model (no cloud inference bill)

Run a compatible local model server such as Ollama or LM Studio on your own computer, then configure G0DM0D3 to use its OpenAI-compatible endpoint. This uses your computer's CPU/RAM/GPU and electricity instead of a hosted model charge. If using the hosted https://godmod3.ai/ page, the local server must permit the page's browser origin (CORS); otherwise use the vendored interface locally and follow the upstream local-model instructions.

Guide: https://godmod3.ai/LOCAL_MODELS.md

## What this does not change

- It does not connect G0DM0D3 to the Jack Pockets video workflow.
- It does not install a local model on your computer.
- It does not guarantee permanent free access; free-model availability and limits can change.
- It does not change any OpenRouter account settings or credentials for you.

## Safest recommendation

Start with Option A only if you can select `openrouter/free` explicitly and keep the account at zero credits. If the interface cannot select that model or the setup asks for payment, stop and use Option B instead.
