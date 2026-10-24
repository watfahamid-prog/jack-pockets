from __future__ import annotations

import os
import re

STOP = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for", "with",
    "is", "was", "are", "were", "this", "that", "it", "as", "at", "by", "from",
    "into", "about", "then", "than", "they", "their", "there", "which", "what",
    "when", "where", "who", "how", "why", "its", "his", "her", "has", "have",
    "most", "more", "very", "really", "thing", "things", "ever", "one", "ones",
    "people", "person", "time", "way", "like", "just", "can", "could", "would",
    "should", "will", "do", "does", "did", "not", "no", "yes",
}
MIN_VISUAL_RELEVANCE = 7.0
MAX_ASSET_USES_PER_BEAT = 4
STATIC_ROLES = {"map", "document", "screenshot", "chart"}


def sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text.strip()) if part.strip()]


def classify(sentence: str):
    low = sentence.lower()
    if any(word in low for word in ("however", "instead", "yet", "although", "on the other hand")):
        return "contrast", "evidence", 0.72
    if any(word in low for word in ("because", "therefore", "according to", "as a result", "which means")):
        return "explain", "evidence", 0.62
    if any(word in low for word in ("revealed", "discovered", "the truth", "what happened next", "unexpected")):
        return "reveal", "reveal", 0.88
    if any(word in low for word in ("died", "collapsed", "lost", "failed", "ended", "disappeared", "destroyed")):
        return "consequence", "consequence", 0.78
    if "?" in sentence:
        return "punchline", "punchline", 0.78
    return "setup", "setup", 0.48


def _normalize_token(token: str) -> str:
    token = token.lower()
    if len(token) > 5 and token.endswith("ies"):
        return token[:-3] + "y"
    if token.endswith("es") and len(token) > 4:
        stem = token[:-2]
        if stem.endswith(("s", "x", "z", "ch", "sh")):
            return stem
        return token[:-1]
    if len(token) > 4 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def keywords(sentence: str) -> list[str]:
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'’-]{2,}", sentence)
    return list(dict.fromkeys(_normalize_token(word) for word in words if word.lower() not in STOP))[:8]


def _value_label(sentence: str) -> str:
    numbers = re.findall(r"(?:\$|€|£)?\d+(?:[,.]\d+)*(?:%|\s*(?:million|billion|trillion|thousand|M|B|T))?", sentence, re.I)
    if not numbers:
        return ""
    cue = re.search(r"\b(total|cost|costs|worth|value|price|spent|spending|estimated|estimate|budget|valued|reached|sold|sold for)\b", sentence, re.I)
    if not cue:
        return ""
    label = numbers[0].replace(",", "")
    prefix = cue.group(1).upper()
    if prefix in {"COSTS", "SPENT", "SPENDING"}:
        prefix = "COST"
    elif prefix in {"ESTIMATED", "ESTIMATE", "VALUED"}:
        prefix = "ESTIMATE"
    return f"{prefix} = {label}"[:44]


def _span(sentence, words, position):
    target = [_normalize_token(token) for token in re.findall(r"[a-z0-9]+", sentence.lower())]
    flat = [_normalize_token(re.sub(r"[^a-z0-9]", "", str(word.get("word", "")).lower())) for word in words]
    if not target or position >= len(flat):
        return position, min(len(words), position + max(1, len(target)))
    for index in range(position, max(position, len(flat) - len(target) + 1)):
        if flat[index:index + len(target)] == target:
            return index, index + len(target)
    anchors = [token for token in target if token not in STOP]
    start = None
    for token in anchors or target:
        try:
            start = flat.index(token, position)
            break
        except ValueError:
            continue
    if start is None:
        return position, min(len(words), position + max(1, len(target)))
    end = min(len(flat), start + max(1, len(target) + 5))
    for index in range(start + 1, end):
        if flat[index] in target[-3:]:
            end = index + 1
    return start, max(start + 1, end)


def _editorial_dict(value):
    if isinstance(value, list):
        return {"sentences": [item for item in value if isinstance(item, dict)]}
    return value if isinstance(value, dict) else {}


def _tokens(value) -> set[str]:
    if isinstance(value, (list, tuple, set)):
        value = " ".join(str(item) for item in value)
    return {_normalize_token(token) for token in re.findall(r"[a-z0-9]+", str(value or "").lower()) if token not in STOP}


def _asset_relevance(asset: dict, sentence_terms: set[str], role: str) -> float:
    metadata_terms: set[str] = set()
    for field in ("title", "description", "tags"):
        metadata_terms.update(_tokens(asset.get(field, "")))
    overlap = sentence_terms & metadata_terms
    score = len(overlap) * 6.0
    kind = str(asset.get("kind", "")).lower()
    asset_role = str(asset.get("role", "")).lower()
    if kind == "video":
        score += 2.0
    elif kind == "photo":
        score += 1.0
    elif kind in {"generated", "document"}:
        score -= 2.0
    if role in STATIC_ROLES and asset_role == role:
        score += 1.0
    if role in STATIC_ROLES and kind == "generated" and role in str(asset.get("id", "")).lower():
        score += 0.5
    return score


def _asset_score(asset: dict, sentence_terms: set[str], role: str, reuse_count: int = 0, previous_id: str = "") -> float:
    score = _asset_relevance(asset, sentence_terms, role)
    score -= min(max(0, reuse_count) * 2.0, 8.0)
    if previous_id and str(asset.get("id")) == previous_id:
        score -= 4.5
    return score


def build_shots(beat, seed=42, aligned_words=None, sentences_override=None):
    sentence_list = sentences_override or sentences(str(beat.get("narration", ""))) or [str(beat.get("narration", ""))]
    total = max(0.2, float(beat["end"]) - float(beat["start"]))
    assets = [asset for asset in beat.get("assets", []) if asset.get("id")]
    shots = []
    position = 0
    used_counts: dict[str, int] = {}
    previous_asset_id = ""
    # Beat-level subject terms provide a conservative fallback for connective
    # narration ("that changed everything") when the shot itself has no nouns.
    # This keeps footage on-topic without falling back to unrelated stock.
    beat_terms = set(keywords(str(beat.get("title", ""))))
    context_keywords = beat.get("keywords") or []
    if isinstance(context_keywords, str):
        context_keywords = re.split(r"[,;|]", context_keywords)
    # keywords() intentionally caps sentence keywords to eight, but a beat's
    # search keywords are separate, curated phrases. Process each phrase
    # independently so the title cannot crowd out all of the actual subject terms.
    for keyword in context_keywords:
        beat_terms.update(keywords(str(keyword)))

    for index, sentence in enumerate(sentence_list):
        intent, reason, intensity = classify(sentence)
        if aligned_words:
            start_word, end_word = _span(sentence, aligned_words, position)
            position = max(position + 1, end_word)
            start = max(0.0, float(aligned_words[start_word]["start"]) - float(beat["start"])) if start_word < len(aligned_words) else 0.0
            end = min(total, float(aligned_words[end_word - 1]["end"]) - float(beat["start"])) if end_word > start_word else start + 0.5
        else:
            start = shots[-1]["end"] if shots else 0.0
            end = start + max(0.45, total / max(1, len(sentence_list)))
        start = min(max(0.0, total - 0.25), max(0.0, start))
        end = total if index == len(sentence_list) - 1 else min(total, max(start + 0.25, end))
        if end <= start:
            end = min(total, start + 0.25)

        terms = set(keywords(sentence))
        editorial = _editorial_dict(beat.get("editorial"))
        decisions = editorial.get("sentences") or editorial.get("shots") or editorial.get("edits") or []
        roles = editorial.get("visual_roles") or editorial.get("visuals") or []
        decision = decisions[index] if index < len(decisions) and isinstance(decisions[index], dict) else {}
        role = str(decision.get("visual_role") or decision.get("role") or (roles[index % len(roles)] if roles else "b-roll")).lower()
        motion = str(decision.get("camera_motion") or decision.get("motion") or "").lower()
        if motion not in {"push", "pull", "pan", "parallax", "whip"}:
            motion = "push" if intensity > 0.72 else ("pan" if index % 2 else "parallax")

        layers = []
        chosen = None
        if assets:
            # Build both a sentence-specific set and a beat-subject set. The
            # latter is a fallback for connective sentences but must still match
            # a concrete, curated keyword in this beat.
            sentence_videos = [
                asset for asset in assets
                if str(asset.get("kind", "")).lower() == "video"
                and _asset_relevance(asset, terms, role) >= MIN_VISUAL_RELEVANCE
            ]
            context_videos = [
                asset for asset in assets
                if str(asset.get("kind", "")).lower() == "video" and beat_terms
                and _asset_relevance(asset, beat_terms, role) >= MIN_VISUAL_RELEVANCE
            ]
            video_by_id = {str(asset["id"]): asset for asset in [*sentence_videos, *context_videos]}
            # Keep all subject-relevant clips available so a strong match for one
            # sentence cannot monopolize every shot in the beat.
            video_candidates = list(video_by_id.values())
            eligible = [
                asset for asset in video_candidates
                if used_counts.get(str(asset["id"]), 0) < MAX_ASSET_USES_PER_BEAT
                and str(asset["id"]) != previous_asset_id
            ]

            if not eligible and role in STATIC_ROLES:
                static_candidates = [
                    asset for asset in assets
                    if str(asset.get("kind", "")).lower() in {"photo", "generated", "document"}
                    and _asset_relevance(asset, terms, role) >= MIN_VISUAL_RELEVANCE
                ]
                if not static_candidates:
                    static_candidates = [
                        asset for asset in assets
                        if str(asset.get("kind", "")).lower() in {"generated", "document"}
                        and str(asset.get("role", "")).lower() == role
                    ]
                eligible = [
                    asset for asset in static_candidates
                    if used_counts.get(str(asset["id"]), 0) < MAX_ASSET_USES_PER_BEAT
                    and str(asset["id"]) != previous_asset_id
                ]

            if eligible:
                semantic_scores = {}
                if os.getenv("JACKPOCKETS_SEMANTIC_RANKING", "").strip().lower() in {"1", "true", "yes"}:
                    try:
                        from semantic_ranker import score_assets
                        semantic_scores = score_assets(sentence, eligible)
                        print("[visuals] local semantic reranking enabled", flush=True)
                    except Exception as exc:
                        print(f"[visuals] semantic reranking unavailable; using lexical ranking: {exc}", flush=True)

                # Diversity is an explicit first-class constraint: among eligible
                # subject-matched clips, use the least-reused asset next, then
                # prefer a sentence-level match, semantic/lexical score and stable ID.
                sentence_ids = {str(asset["id"]) for asset in sentence_videos}
                ranked = sorted(
                    eligible,
                    key=lambda asset: (
                        -used_counts.get(str(asset["id"]), 0),
                        str(asset["id"]) in sentence_ids,
                        _asset_score(asset, terms, role, used_counts.get(str(asset["id"]), 0), "")
                        + semantic_scores.get(str(asset["id"]), 0.0) * 10.0,
                        str(asset.get("kind", "")).lower() == "video",
                        str(asset["id"]),
                    ),
                    reverse=True,
                )
                chosen = ranked[0]
                used_counts[str(chosen["id"])] = used_counts.get(str(chosen["id"]), 0) + 1
                previous_asset_id = str(chosen["id"])
                asset_id = str(chosen["id"])
                if role in STATIC_ROLES and chosen.get("kind") == "generated":
                    x, y, width, height = 5, 8, 90, 78
                else:
                    x, y, width, height = 0, 0, 100, 100
                layers.append({
                    "id": f"visual-{index}", "kind": "image", "assetId": asset_id,
                    "x": x, "y": y, "width": width, "height": height,
                    "rotation": 0, "opacity": 1, "z": 0, "animation": motion,
                })

        value_label = _value_label(sentence)
        overlay = str(decision.get("overlay") or decision.get("text_overlay") or "").strip()
        if overlay:
            layers.append({"id": f"overlay-{index}", "kind": "label", "text": overlay[:54], "x": 6, "y": 7, "width": 48, "height": 7, "rotation": 0, "opacity": 0.94, "z": 5, "animation": "static"})
        elif value_label:
            layers.append({"id": f"value-{index}", "kind": "label", "text": value_label, "x": 6, "y": 8, "width": 54, "height": 8, "rotation": 0, "opacity": 0.96, "z": 5, "animation": "push"})
        elif reason == "reveal":
            important = [word for word in keywords(sentence) if len(word) >= 5]
            if important and len(sentence) < 105:
                layers.append({"id": f"reveal-{index}", "kind": "text", "text": important[-1].upper(), "x": 7, "y": 70, "width": 70, "height": 16, "rotation": 0, "opacity": 0.94, "z": 5, "animation": "push"})

        actions = [{"type": "zoom" if intensity > 0.72 else "pan", "at": 0.12, "duration": min(0.8, max(0.2, (end - start) * 0.45)), "intensity": min(0.7, intensity * 0.45), "reason": "pace"}]
        if reason == "reveal":
            actions.append({"type": "flash", "at": 0.82, "duration": 0.07, "intensity": 0.16, "reason": "reveal"})
        shots.append({"id": f"{beat['id']}-shot-{index}", "start": round(start, 3), "end": round(end, 3), "reason": reason, "intent": intent, "assetIds": [str(chosen["id"])] if chosen else [], "layers": layers, "actions": actions, "sfx": [], "intensity": round(intensity, 2)})

    if shots:
        # Whisper can place sentence spans close together or outside the beat when
        # a sentence cannot be matched exactly. Convert the raw spans into one
        # monotonic set of cut boundaries, instead of clamping each shot separately
        # (which can push late shots past the beat end and create overlaps).
        raw = [
            (
                max(0.0, min(total, float(shot.get("start", 0.0)))),
                max(0.0, min(total, float(shot.get("end", 0.0)))),
            )
            for shot in shots
        ]
        boundaries = [0.0]
        for index in range(1, len(shots)):
            prev_end = raw[index - 1][1]
            next_start = raw[index][0]
            candidate = (prev_end + next_start) / 2.0
            # Keep enough room for every remaining shot; short beats can use
            # shorter shots, but no boundary is allowed to move backwards.
            min_step = min(0.05, total / max(1, len(shots)))
            lower = boundaries[-1] + min_step
            upper = total - min_step * (len(shots) - index)
            candidate = max(lower, min(upper, candidate))
            boundaries.append(candidate)
        boundaries.append(total)

        for index, shot in enumerate(shots):
            shot["start"] = round(boundaries[index], 3)
            shot["end"] = round(boundaries[index + 1], 3)
            if shot["end"] <= shot["start"]:
                # Three-decimal timestamps can collapse extremely short intervals.
                # Keep the boundary stable rather than extending into the next shot.
                shot["end"] = shot["start"]
    beat["shots"] = shots
    return beat
