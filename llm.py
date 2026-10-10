from __future__ import annotations
import json
import os
import re

from dotenv import load_dotenv

load_dotenv()

MIN_NARRATION_WORDS = 1400

SYSTEM = """You are the editorial brain for an automated premium documentary editor.
Create an ORIGINAL factual long-form documentary plan. Do not copy any existing creator's script, wording, or finished video.

The result must feel like a professionally researched cinematic YouTube documentary, not a ranking list, slideshow, AI summary, or sequence of generic text cards. Do not default to Top 5/Top 10 formats. Build a compelling story around a specific question, stakes, surprising details, and a satisfying answer. Use a vivid cold open in the first 2-3 sentences, then context, escalating curiosity, evidence and competing explanations, a meaningful reveal, consequences, and a memorable conclusion. Write conversational narration that sounds natural aloud. Never invent quotes, statistics, dates, or events. Give every beat concrete, searchable visual subjects (real places, people, objects, actions, archival material), specific footage keywords rather than vague mood words, and restrained overlays only for essential names, dates, figures, or short reveals. Prefer moving B-roll and evidence-led visuals; do not make every beat a title card.

Target a finished documentary around 8-14 minutes. Aim for roughly 1,500-2,100 spoken words at a natural documentary pace. Do not pad the story just to hit a runtime.

Use a strong narrative arc: cinematic cold-open, context, escalation, evidence and competing explanations, reveal, fallout, and a memorable ending. Every beat must advance the story. Every sentence should have a visual reason, and factual claims should be specific enough to research.

Return ONLY valid JSON with 8-14 beats. Each beat needs a concise title, narration, intensity 0-1, keywords, overlays, and visual intent. Narration must be detailed, natural, and original. Do not write placeholder narration, repeated filler, or generic one-line beats. Do not wrap the JSON in Markdown fences. Do not add commentary before or after the JSON."""

def _parse_json(text: str):
    raw = str(text or "").strip()
    if not raw:
        raise ValueError("LLM returned an empty response")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as first_error:
        cleaned = re.sub(r"^\s*```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```\s*$", "", cleaned).strip()
        if cleaned != raw:
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                pass
        decoder = json.JSONDecoder()
        for start in (index for index, char in enumerate(raw) if char in "[{"):
            try:
                value, _ = decoder.raw_decode(raw[start:])
                return value
            except json.JSONDecodeError:
                continue
        raise ValueError(f"LLM returned invalid JSON: {first_error.msg} at line {first_error.lineno} column {first_error.colno}") from first_error

def _normalize_plan(value, topic: str) -> dict:
    if isinstance(value, list):
        plan = {"title": topic, "beats": value}
    elif isinstance(value, dict):
        beats = value.get("beats")
        if isinstance(beats, list):
            plan = dict(value)
            plan.setdefault("title", topic)
        else:
            plan = None
            for key in ("plan", "script", "sections", "scenes"):
                candidate = value.get(key)
                if isinstance(candidate, list):
                    plan = {"title": value.get("title", topic), "beats": candidate}
                    break
            if plan is None:
                raise ValueError("LLM JSON did not contain a beats/plan/sections/scenes list")
    else:
        raise ValueError("LLM returned an unsupported documentary plan shape")

    valid_beats = [beat for beat in plan["beats"] if isinstance(beat, dict) and str(beat.get("narration", "")).strip()]
    if len(valid_beats) < 8:
        raise ValueError(f"LLM returned only {len(valid_beats)} usable beats; need at least 8")
    plan["beats"] = valid_beats
    words = sum(len(str(beat.get("narration", "")).split()) for beat in valid_beats)
    if words < MIN_NARRATION_WORDS:
        raise ValueError(f"LLM returned only {words} narration words; a long-form plan needs at least {MIN_NARRATION_WORDS}")
    return plan

def _gemini(topic: str) -> dict:
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    model = os.getenv("GEMINI_MODEL") or "gemini-3.8-flash"
    prompt = f"{SYSTEM}\n\nBuild a complete long-form documentary plan about: {topic}"
    last_error = None
    for attempt in range(2):
        try:
            response = client.models.generate_content(
                model=model, contents=prompt,
                config=types.GenerateContentConfig(temperature=0.65 if attempt == 0 else 0.25, response_mime_type="application/json"),
            )
            return _normalize_plan(_parse_json(response.text), topic)
        except Exception as exc:
            last_error = exc
            if attempt == 0:
                print(f"[llm] Gemini plan attempt 1 failed; retrying: {exc}", flush=True)
    raise last_error

def _openai(topic: str) -> dict:
    from openai import OpenAI
    client = OpenAI()
    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL") or "gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Build a complete long-form documentary plan about: {topic}"},
        ],
        temperature=0.65,
    )
    return _normalize_plan(_parse_json(response.choices[0].message.content), topic)

def _anthropic(topic: str) -> dict:
    from anthropic import Anthropic
    client = Anthropic()
    response = client.messages.create(
        model=os.getenv("ANTHROPIC_MODEL") or "claude-3-5-sonnet-latest",
        max_tokens=9000,
        system=SYSTEM,
        messages=[{"role": "user", "content": f"Build a complete long-form documentary plan about: {topic}"}],
    )
    return _normalize_plan(_parse_json(response.content[0].text), topic)

def generate(topic: str) -> dict:
    provider = os.getenv("LLM_PROVIDER", "auto").lower()
    order = {"gemini": ["gemini"], "openai": ["openai"], "anthropic": ["anthropic"], "auto": ["gemini", "openai", "anthropic"]}.get(provider, ["gemini", "openai", "anthropic"])
    attempted = []
    for name in order:
        try:
            if name == "gemini" and os.getenv("GEMINI_API_KEY"):
                return _gemini(topic)
            if name == "openai" and os.getenv("OPENAI_API_KEY"):
                return _openai(topic)
            if name == "anthropic" and os.getenv("ANTHROPIC_API_KEY"):
                return _anthropic(topic)
        except Exception as exc:
            attempted.append(f"{name}: {exc}")
            print(f"[llm] {name} failed: {exc}", flush=True)
    if attempted:
        raise RuntimeError("No configured LLM produced a valid long-form plan. " + " | ".join(attempted))
    raise RuntimeError("No LLM API key is configured. Set GEMINI_API_KEY or another supported provider secret.")
