# G0DM0D3 — Research Assistant

This folder contains a vendored copy of the standalone G0DM0D3 interface from the upstream project.

- Upstream project: https://github.com/elder-plinius/G0DM0D3
- Upstream hosted version: https://godmod3.ai/
- Upstream license: GNU Affero General Public License v3.0 (see [LICENSE](./LICENSE))
- Vendored upstream file: [index.html](./index.html)

## What this is for

Use it as a separate research and idea-comparison tool while developing Jack Pockets scripts, source plans, or editing approaches. It is **not connected to the video-generation workflow** and does not automatically change or improve generated videos.

## Free-only setup

For a step-by-step guide to using the free OpenRouter model router or a local model without intentionally incurring model charges, see [FREE_SETUP.md](./FREE_SETUP.md). Free model access has limits and can change; do not add credits or select paid model IDs for this test.

## Open it

Download or clone this repository and open `tools/g0dm0d3/index.html` in a modern browser. The standalone interface does not need a build step.

To use hosted model providers, configure your own provider credentials in G0DM0D3 settings. Model API usage may cost money; this repository does not include API keys. You can also configure a compatible local model server. Never commit API keys or other secrets.

## Privacy and safety notes

- The upstream project documents browser-local conversation history and provider-specific data flows. Prompts sent to a provider are handled under that provider's policies.
- Upstream app telemetry is enabled by default in the standalone interface. Review upstream documentation and enable its No-Log or Local-only controls if appropriate.
- Browser storage is not a secure secret vault. Do not enter private or sensitive information, and do not use personal or school account credentials as API keys.
- This is a vendored snapshot; upstream changes do not automatically sync into this copy. Check the upstream repository for updates and security fixes.

## Attribution

G0DM0D3 is created by the upstream project's contributors. The interface is included under AGPL-3.0. See the included license and upstream repository for the full terms and notices.
