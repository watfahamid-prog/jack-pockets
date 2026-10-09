from __future__ import annotations

import re

STOP = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for", "with",
    "is", "was", "are", "were", "this", "that", "it", "as", "at", "by", "from",
    "into", "about", "then", "than", "they", "their", "there", "which", "what",
    "when", "where", "who", "how", "why", "its", "his", "her", "has", "have",
}


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


def keywords(sentence: str) -> list[str]:
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'’-]{2,}", sentence)
    return list(dict.fromkeys(word.lower() for word in words if word.lower() not in STOP))[:8]


def _span(sentence, words, position):
    target = re.findall(r"[a-z0-9]+", sentence.lower())
    flat = [re.sub(r"[^a-z0-9]", "", str(word.get("word", "")).lower()) for word in words]
    for index in range(position, max(position, len(flat) - len(target) + 1)):
        if flat[index:index + len(target)] == target:
            return index, index + len(target)
    return position, min(len(words), position + max(1, len(target)))


def _editorial_dict(value):
    if isinstance(value, list):
        return {"sentences": [item for item in value if isinstance(item, dict)]}
    return value if isinstance(value, dict) else {}


def _asset_score(asset: dict, sentence_terms: set[str], role: str) -> float:
    query_terms = set(re.findall(r"[a-z0-9]+", str(asset.get("query", "")).lower())) - STOP
    metadata_terms = set()
    for value in asset.get("keywords", []) or []:
        metadata_terms.update(re.findall(r"[a-z0-9]+", str(value).lower()))
    overlap = len(sentence_terms & (query_terms | metadata_terms))
    score = overlap * 2.0
    kind = str(asset.get("kind", "")).lower()
    asset_role = str(asset.get("role", "")).lower()
    if kind == "video":
        score += 5.0
    elif kind == "photo":
        score += 2.0
    elif kind in {"generated", "document"}:
        score += 0.5
    if role in {"map", "document", "screenshot", "chart"} and asset_role == role:
        score += 6.0
    if role in {"map", "document", "screenshot", "chart"} and kind == "generated" and role in str(asset.get("id", "")).lower():
        score += 4.0
    return score


def build_shots(beat, seed=42, aligned_words=None, sentences_override=None):
    sentence_list = sentences_override or sentences(str(beat.get("narration", ""))) or [str(beat.get("narration", ""))]
    total = max(0.2, float(beat["end"]) - float(beat["start"]))
    assets = [asset for asset in beat.get("assets", []) if asset.get("id")]
    shots = []
    position = 0
    used_counts: dict[str, int] = {}

    for index, sentence in enumerate(sentence_list):
        intent, reason, intensity = classify(sentence)
        if aligned_words:
            start_word, end_word = _span(sentence, aligned_words, position)
            position = max(position, end_word)
            start = max(0.0, float(aligned_words[start_word]["start"]) - float(beat["start"])) if start_word < len(aligned_words) else 0.0
            end = min(total, float(aligned_words[end_word - 1]["end"]) - float(beat["start"])) if end_word > start_word else start + 0.5
        else:
            start = shots[-1]["end"] if shots else 0.0
            end = start + max(0.45, total / max(1, len(sentence_list)))
        start = min(total - 0.25, max(0.0, start))
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
            ranked = sorted(
                assets,
                key=lambda asset: (
                    _asset_score(asset, terms, role) - used_counts.get(str(asset["id"]), 0) * 7.0,
                    str(asset["id"]),
                ),
                reverse=True,
            )
            chosen = ranked[0]
            used_counts[str(chosen["id"])] = used_counts.get(str(chosen["id"]), 0) + 1
            asset_id = str(chosen["id"])
            if role in {"document", "screenshot", "chart", "map"} and chosen.get("kind") == "generated":
                x, y, width, height = 5, 8, 90, 78
            else:
                x, y, width, height = 0, 0, 100, 100
            layers.append({
                "id": f"visual-{index}", "kind": "image", "assetId": asset_id,
                "x": x, "y": y, "width": width, "height": height,
                "rotation": 0, "opacity": 1, "z": 0, "animation": motion,
            })

        # Keep on-screen text deliberate: no repeated keyword stickers or generic evidence labels.
        important = [word for word in keywords(sentence) if len(word) >= 5]
        overlay = str(decision.get("overlay") or decision.get("text_overlay") or "").strip()
        if overlay:
            layers.append({
                "id": f"overlay-{index}", "kind": "label", "text": overlay[:54],
                "x": 6, "y": 7, "width": 48, "height": 7,
                "rotation": 0, "opacity": 0.92, "z": 5, "animation": "static",
            })
        elif reason == "reveal" and important and len(sentence) < 105:
            layers.append({
                "id": f"reveal-{index}", "kind": "text", "text": important[-1].upper(),
                "x": 7, "y": 70, "width": 70, "height": 16,
                "rotation": 0, "opacity": 0.94, "z": 5, "animation": "push",
            })

        actions = [{"type": "zoom" if intensity > 0.72 else "pan", "at": 0.12, "duration": min(0.8, max(0.2, (end - start) * 0.45)), "intensity": min(0.7, intensity * 0.45), "reason": "pace"}]
        if reason == "reveal":
            actions.append({"type": "flash", "at": 0.82, "duration": 0.07, "intensity": 0.16, "reason": "reveal"})

        shots.append({
            "id": f"{beat['id']}-shot-{index}", "start": round(start, 3), "end": round(end, 3),
            "reason": reason, "intent": intent, "assetIds": [str(chosen["id"])] if chosen else [],
            "layers": layers, "actions": actions, "sfx": [], "intensity": round(intensity, 2),
        })

    beat["shots"] = shots
    return beat
