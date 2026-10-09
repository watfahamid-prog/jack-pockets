# AutoVideo — Editorial Brain

An automated documentary editor built around editorial decisions rather than slideshow assembly.

The system uses narration as the timeline backbone, classifies each sentence, selects a visual intent, creates shot boundaries, builds layered compositions, and validates the resulting timeline before rendering.

## AI providers

Gemini is now a first-class provider.

Set:

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_key
GEMINI_MODEL=gemini-2.5-flash
GEMINI_EDITOR_MODEL=gemini-2.5-flash
```

With `LLM_PROVIDER=auto`, the pipeline tries Gemini first, then OpenAI, then Anthropic when configured.

Gemini is used for two jobs:

1. **Story architect** — builds the documentary structure and narration plan.
2. **Editorial refinement** — analyzes beats for sentence-level intent, important words and visual roles.

This is deliberately a provider layer: the renderer remains deterministic and the AI produces editorial decisions rather than directly generating arbitrary code.

## Pipeline

TOPIC → GEMINI/LLM STORY → NARRATION → WORD ALIGNMENT → EDITORIAL BRAIN → GEMINI BEAT REFINEMENT → ASSET PLAN → SHOT PLAN → QUALITY GATE → REMOTION

## Run

```bash
npm install
python -m pip install -r requirements.txt
cp .env.example .env
npm run generate -- --topic "Why abandoned malls disappeared"
```

## Profiles

```bash
npm run generate -- --topic "..." --profile youtube
npm run generate -- --topic "..." --profile shorts
npm run generate -- --topic "..." --profile square
npm run generate -- --topic "..." --profile 4k
```

No copyrighted media is bundled. Use assets you have rights to use.
