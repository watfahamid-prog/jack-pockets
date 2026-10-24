from __future__ import annotations
import json
import os
import re
import time

from dotenv import load_dotenv

load_dotenv()

MIN_NARRATION_WORDS = 1400
MIN_BEAT_KEYWORDS = 2

SYSTEM = """You are the editorial brain for an automated premium documentary editor.
Create an ORIGINAL factual long-form documentary plan. Do not copy any existing creator's script, wording, or finished video.

The house visual language is based on the Jack Pockets reference film: narration-driven, faceless documentary storytelling with real subject-specific footage, archival/news imagery when useful, crowds and real environments, recognizable institutions/places, and simple hand-drawn or evidence graphics. The reference uses restrained short value labels such as TOTAL = $50B rather than large permanent captions or boxed text cards. Match that editorial principle, not any specific footage, script, or creator wording.

The result must feel like a professionally researched cinematic YouTube documentary, not a ranking list, slideshow, AI summary, or sequence of generic text cards. Do not default to Top 5/Top 10 formats. Build a compelling story around a specific question, stakes, surprising details, and a satisfying answer. Use a vivid cold open in the first 2-3 sentences, then context, escalating curiosity, evidence and competing explanations, a meaningful reveal, consequences, and a memorable conclusion. Write conversational narration that sounds natural aloud. Never invent quotes, statistics, dates, or events. Treat supplied research as evidence, not decoration: do not claim a source supports a point unless its title/snippet/abstract actually relates to that point. Prefer peer-reviewed research, government/university sources, primary documents, and reputable reporting over unsourced summaries. If the evidence is uncertain or sources disagree, say so in the narration. Never turn an unverified internet claim into a confident fact. Every beat must include a "source_urls" array containing URLs from the supplied research that directly support its factual claims; use an empty array rather than inventing a source. Give every beat concrete, searchable visual subjects (real places, people, objects, actions, archival material), specific footage keywords rather than vague mood words, and restrained overlays only for essential names, dates, figures, or short reveals. Prefer moving B-roll and evidence-led visuals; do not make every beat a title card.

Visual rules: every sentence should have a visual reason. Prefer footage that literally shows the subject being discussed. Use archival/news footage for historical claims, public events, institutions, crowds, transport, cities, or older technology when available. Use simple generated maps/charts/line drawings only when they explain something that footage cannot. Avoid generic laboratory, computer, machinery, explosion, landscape, or stock-people filler unless the narration explicitly describes that subject. Do not repeat the same visual in adjacent shots. Do not use permanent subtitles or a progress bar as part of the house style; those remain optional and off by default. Keep on-screen text short and sparse, especially numeric/value labels.

Target a finished documentary around 8-14 minutes. Aim for roughly 1,500-1,900 spoken words at a natural documentary pace so the finished narration reliably clears the 8-minute minimum. Each of the 8-14 beats should contain substantial narration (usually 140-200 words); do not return a short summary. Do not pad the story just to hit a runtime.

Use a strong narrative arc: cinematic cold-open, context, escalation, evidence and competing explanations, reveal, fallout, and a memorable ending. Every beat must advance the story. Every sentence should have a visual reason, and factual claims should be specific enough to research.

Return ONLY valid JSON with 8-14 beats. Each beat needs a concise title, narration, intensity 0-1, at least 2 specific searchable keywords, source_urls, and visual intent. Narration must be detailed, natural, and original. Do not write placeholder narration, repeated filler, or generic one-line beats. Do not wrap the JSON in Markdown fences. Do not add commentary before or after the JSON."""


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

    normalized = []
    for index, beat in enumerate(valid_beats, start=1):
        item = dict(beat)
        item["title"] = str(item.get("title") or f"Chapter {index}").strip()
        item["narration"] = str(item.get("narration", "")).strip()
        try:
            item["intensity"] = min(1.0, max(0.0, float(item.get("intensity", 0.5))))
        except (TypeError, ValueError):
            item["intensity"] = 0.5
        raw_keywords = item.get("keywords", [])
        if isinstance(raw_keywords, str):
            raw_keywords = re.split(r"[,;|]", raw_keywords)
        item["keywords"] = list(dict.fromkeys(
            str(keyword).strip().lower()
            for keyword in raw_keywords or []
            if str(keyword).strip()
        ))[:10]
        raw_sources = item.get("source_urls", [])
        if isinstance(raw_sources, str):
            raw_sources = [raw_sources]
        item["source_urls"] = list(dict.fromkeys(
            str(url).strip() for url in raw_sources or [] if str(url).strip()
        ))
        item["overlays"] = item.get("overlays") if isinstance(item.get("overlays"), list) else []
        item["visual_intent"] = str(item.get("visual_intent") or item.get("visual") or "").strip()
        item["editorial"] = item.get("editorial") if isinstance(item.get("editorial"), dict) else {}
        normalized.append(item)

    plan["beats"] = normalized
    words = sum(len(str(beat.get("narration", "")).split()) for beat in normalized)
    if words < MIN_NARRATION_WORDS:
        raise ValueError(f"LLM returned only {words} narration words; a long-form plan needs at least {MIN_NARRATION_WORDS}")

    weak_keywords = [
        str(beat.get("title", f"beat-{index}"))
        for index, beat in enumerate(normalized, start=1)
        if len(beat.get("keywords", [])) < MIN_BEAT_KEYWORDS
    ]
    if weak_keywords:
        raise ValueError(
            "beats need at least 2 specific searchable keywords: " + ", ".join(weak_keywords[:4])
        )

    sentences = []
    for beat in normalized:
        sentences.extend(
            part.strip().lower()
            for part in re.split(r"(?<=[.!?])\s+", beat["narration"])
            if part.strip()
        )
    duplicate_count = len(sentences) - len(set(sentences))
    if sentences and duplicate_count / len(sentences) > 0.12:
        raise ValueError("LLM repeated too much narration; regenerate a more original story")
    return plan


def _research_prompt(topic: str, research: list[dict] | None) -> str:
    safe_sources = []
    for item in (research or [])[:10]:
        if not isinstance(item, dict) or not item.get("url"):
            continue
        safe_sources.append({
            "title": str(item.get("title", ""))[:240],
            "url": str(item.get("url", ""))[:500],
            "source_type": str(item.get("source_type", "web_search")),
            "content": str(item.get("content", ""))[:1000],
        })
    return (
        f"{SYSTEM}\n\nBuild a complete long-form documentary plan about: {topic}\n\n"
        "RESEARCH MATERIAL (use only relevant material; do not claim sources prove more than they say):\n"
        + json.dumps(safe_sources, ensure_ascii=False)
        + "\n\nReturn source_urls on every beat, using only exact URLs listed above. "
          "When this material is insufficient, keep the claim modest or omit it; never fabricate citations."
    )


def _gemini(topic: str, research: list[dict] | None = None) -> dict:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    primary = (os.getenv("GEMINI_MODEL") or "gemini-3.8-flash").strip()
    fallback_text = os.getenv(
        "GEMINI_FALLBACK_MODELS",
        "gemini-3.6-flash,gemini-3.5-flash-lite",
    )
    models = list(dict.fromkeys(
        [primary] + [item.strip() for item in fallback_text.split(",") if item.strip()]
    ))
    prompt = _research_prompt(topic, research)
    last_error = None

    for model in models:
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.65 if attempt == 0 else 0.25,
                        response_mime_type="application/json",
                        max_output_tokens=12000,
                    ),
                )
                plan = _normalize_plan(_parse_json(response.text), topic)
                print(f"[llm] Gemini succeeded with model {model}", flush=True)
                return plan
            except Exception as exc:
                last_error = exc
                message = str(exc).lower()
                transient = any(marker in message for marker in (
                    "503", "unavailable", "429", "resource_exhausted",
                    "rate limit", "temporarily", "timeout", "deadline",
                    "500 internal", "502", "504",
                ))
                too_short = "narration words" in message or "usable beats" in message
                if attempt == 0 and too_short:
                    prompt += (
                        "\n\nLENGTH REPAIR — your previous response was too short. "
                        "Return a complete revised JSON plan, not a summary. Include 10-12 beats, "
                        "each with about 150-190 words of narration, for at least 1,500 spoken words "
                        "total. Keep claims tied to supplied research, retain exact source URLs, "
                        "provide at least 2 specific searchable keywords per beat, "
                        "and do not pad with repeated ideas. Output JSON only."
                    )
                    print(
                        f"[llm] Gemini model {model} returned a short plan; retrying with explicit length targets",
                        flush=True,
                    )
                    time.sleep(1)
                    continue
                if transient and attempt < 2:
                    delay = 2 if attempt == 0 else 5
                    print(
                        f"[llm] Gemini model {model} transient failure; retrying in {delay}s "
                        f"(attempt {attempt + 2}/3): {exc}",
                        flush=True,
                    )
                    time.sleep(delay)
                    continue
                print(
                    f"[llm] Gemini model {model} failed"
                    + (" after retry" if attempt else "")
                    + f"; trying next configured model if available: {exc}",
                    flush=True,
                )
                break

    raise RuntimeError(
        "Gemini model rotation exhausted ("
        + ", ".join(models)
        + "). Last error: "
        + str(last_error)
    ) from last_error


def _openai(topic: str, research: list[dict] | None = None) -> dict:
    from openai import OpenAI
    client = OpenAI()
    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL") or "gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": _research_prompt(topic, research)},
        ],
        temperature=0.65,
    )
    return _normalize_plan(_parse_json(response.choices[0].message.content), topic)


def _anthropic(topic: str, research: list[dict] | None = None) -> dict:
    from anthropic import Anthropic
    client = Anthropic()
    response = client.messages.create(
        model=os.getenv("ANTHROPIC_MODEL") or "claude-sonnet-5-5",
        max_tokens=9000,
        system=SYSTEM,
        messages=[{"role": "user", "content": _research_prompt(topic, research)}],
    )
    return _normalize_plan(_parse_json(response.content[0].text), topic)



def _qwen(topic: str, research: list[dict] | None = None) -> dict:
    """Use an OpenAI-compatible Qwen endpoint; defaults to local Ollama with no paid fallback."""
    from openai import OpenAI

    base_url = (os.getenv("QWEN_BASE_URL") or "http://localhost:11434/v1").strip()
    model = (os.getenv("QWEN_MODEL") or "qwen3:4b").strip()
    api_key = (os.getenv("QWEN_API_KEY") or "ollama").strip()
    client = OpenAI(
        base_url=base_url,
        api_key=api_key,
        timeout=float(os.getenv("QWEN_TIMEOUT_SECONDS", "300")),
        max_retries=0,
    )
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": _research_prompt(topic, research)},
        ],
        temperature=0.4,
    )
    content = response.choices[0].message.content
    plan = _normalize_plan(_parse_json(content), topic)
    print(f"[llm] Qwen succeeded with model {model} at {base_url}", flush=True)
    return plan


def generate(topic: str, research: list[dict] | None = None) -> dict:
    from cache_utils import load_json_cache, save_json_cache

    provider = os.getenv("LLM_PROVIDER", "auto").lower()
    order = {"gemini": ["gemini"], "openai": ["openai"], "anthropic": ["anthropic"], "qwen": ["qwen"], "auto": ["gemini", "openai", "anthropic"]}.get(provider, ["gemini", "openai", "anthropic"])
    cache_payload = {
        "topic": topic.strip(),
        "research": research or [],
        "provider_order": order,
        "configured_providers": {
            "gemini": bool(os.getenv("GEMINI_API_KEY", "").strip()),
            "openai": bool(os.getenv("OPENAI_API_KEY", "").strip()),
            "anthropic": bool(os.getenv("ANTHROPIC_API_KEY", "").strip()),
            "qwen": bool(os.getenv("QWEN_API_KEY", "").strip()) or (os.getenv("QWEN_BASE_URL", "http://localhost:11434/v1").startswith(("http://localhost", "http://127.0.0.1"))),
        },
        "models": {
            "gemini": os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
            "gemini_fallbacks": os.getenv("GEMINI_FALLBACK_MODELS", "gemini-3.6-flash,gemini-3.5-flash-lite"),
            "openai": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            "anthropic": os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5"),
            "qwen": os.getenv("QWEN_MODEL", "qwen3:4b"),
            "qwen_base_url": os.getenv("QWEN_BASE_URL", "http://localhost:11434/v1"),
        },
        "editorial_prompt_version": 4,
    }
    cached = load_json_cache("documentary-plan", cache_payload)
    if isinstance(cached, dict):
        try:
            valid_cached = _normalize_plan(cached, topic)
            print("[llm] reused cached documentary plan; set JACKPOCKETS_DISABLE_CACHE=1 to force a fresh draft", flush=True)
            return valid_cached
        except Exception as exc:
            print(f"[llm] ignoring invalid cached plan: {exc}", flush=True)

    attempted = []
    for name in order:
        try:
            if name == "gemini" and os.getenv("GEMINI_API_KEY"):
                plan = _gemini(topic, research)
            elif name == "openai" and os.getenv("OPENAI_API_KEY"):
                plan = _openai(topic, research)
            elif name == "anthropic" and os.getenv("ANTHROPIC_API_KEY"):
                plan = _anthropic(topic, research)
            elif name == "qwen":
                plan = _qwen(topic, research)
            else:
                continue
            save_json_cache("documentary-plan", cache_payload, plan)
            return plan
        except Exception as exc:
            attempted.append(f"{name}: {exc}")
            print(f"[llm] {name} failed: {exc}", flush=True)
    if attempted:
        raise RuntimeError("No configured LLM produced a valid long-form plan. " + " | ".join(attempted))
    raise RuntimeError("No LLM provider is configured. Set GEMINI_API_KEY or another supported provider; for local Qwen, set LLM_PROVIDER=qwen and start the configured OpenAI-compatible local server.")
