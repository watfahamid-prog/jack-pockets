from __future__ import annotations

import re


def _asset_relevance(query: str, beat: dict, asset: dict) -> tuple[bool, list[str]]:
    """Match stock media to the beat's actual visual subject, not a long narration prompt."""
    stopwords = {
        "the", "and", "for", "with", "from", "into", "onto", "over", "under",
        "about", "after", "again", "also", "because", "been", "before", "being",
        "could", "did", "does", "during", "have", "more", "most", "other", "same",
        "some", "such", "than", "that", "their", "them", "then", "there", "these",
        "they", "this", "those", "through", "very", "what", "when", "where", "which",
        "while", "would", "your", "you", "are", "was", "were", "has", "had", "its",
        "documentary", "story", "mistake", "forever", "bizarre", "internet",
        "footage", "video", "shot", "scene", "show", "showing", "clip", "visualization",
        "animation", "visual", "moment", "opens", "exposed",
    }
    # Use compact editorial metadata; long narration strings contain incidental words.
    target_text = " ".join([
        str(beat.get("title", "")),
        " ".join(str(x) for x in beat.get("keywords", [])),
    ])
    target = {
        token for token in re.findall(r"[a-z0-9]{3,}", target_text.lower())
        if token not in stopwords and not token.isdigit()
    }
    metadata = " ".join(str(asset.get(key, "")) for key in (
        "title", "description", "tags",
    )).lower().replace("-", " ").replace("_", " ")
    # Compare whole tokens. Substring matching falsely treats terms like "car"
    # as matches for "carpet", allowing unrelated footage through the gate.
    metadata_terms = set(re.findall(r"[a-z0-9]{3,}", metadata))
    found = sorted(target & metadata_terms)
    # A strong match on one specific subject noun is enough to keep useful stock
    # footage (for example, a library-catalog clip for a library-archive beat).
    # Broad production/history words alone are not specific enough.
    broad_terms = {
        "historical", "history", "archive", "archives", "manuscript",
        "manuscripts", "documentary", "footage", "visualization",
        "cinematic", "modern", "ancient", "scene", "video",
    }
    strong_hits = [term for term in found if len(term) >= 6 and term not in broad_terms]
    required = 2 if len(target) >= 5 else 1
    return len(found) >= required or bool(strong_hits), found

def _relevant_sources(topic: str, beat: dict, sources: list[dict], limit: int = 3) -> list[str]:
    """Return only sources whose title/content overlaps the actual beat subject."""
    stopwords = {
        "about", "after", "again", "also", "because", "been", "before", "being",
        "could", "did", "does", "during", "from", "have", "into", "more", "most",
        "other", "over", "same", "some", "such", "than", "that", "their", "them",
        "then", "there", "these", "they", "this", "those", "through", "under",
        "very", "what", "when", "where", "which", "while", "with", "would",
        "documentary", "story", "mistake", "forever", "bizarre", "internet",
    }
    subject = f"{topic} {beat.get('title', '')} {str(beat.get('narration', ''))[:260]}"
    terms = {
        token for token in re.findall(r"[a-z0-9]{3,}", subject.lower())
        if token not in stopwords and not token.isdigit()
    }
    ranked = []
    for item in sources:
        if not isinstance(item, dict) or not item.get("url"):
            continue
        searchable = " ".join((
            str(item.get("title", "")),
            str(item.get("content", ""))[:1800],
            str(item.get("url", "")),
        )).lower()
        # Token-level matching avoids accidental evidence matches such as "net"
        # inside "planet" or "router" inside a longer unrelated word.
        searchable_terms = set(re.findall(r"[a-z0-9]{3,}", searchable))
        hits = terms & searchable_terms
        # Avoid assigning generic or unrelated search results as evidence.
        if len(hits) < 2:
            continue
        ranked.append((len(hits), str(item["url"])))
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    return list(dict.fromkeys(url for _, url in ranked))[:limit]

def _asset_search_queries(beat: dict, limit: int = 4) -> list[str]:
    """Create short, subject-first stock-media queries without generic prose."""
    if limit < 1:
        return []
    title = str(beat.get("title", "")).strip()
    raw_keywords = beat.get("keywords", [])
    if isinstance(raw_keywords, str):
        raw_keywords = re.split(r"[,;|]", raw_keywords)
    keywords = [str(item).strip() for item in (raw_keywords or []) if str(item).strip()]
    visual_intent = str(beat.get("visual_intent") or beat.get("visual") or "").strip()

    # Stock providers respond poorly to full narration/production directions
    # ("cinematic sequence", "sweeping view"). Search concrete subject phrases.
    # Some editorial plans provide complete six-to-eight-word keyword phrases.
    # Joining two such phrases creates one broad, low-quality query and pushes the
    # actual subject out of the useful search terms. Keep long phrases separate
    # (and bounded) so providers can return relevant clips for each visual idea.
    candidates = []

    stopwords = {
        "the", "and", "for", "with", "from", "that", "this", "then", "they",
        "their", "there", "into", "about", "after", "before", "what", "when",
        "where", "which", "while", "would", "could", "should", "have", "been",
        "were", "was", "are", "has", "had", "most", "more", "than", "true",
        "cost", "story", "conclusion", "emerging", "frontier", "explained",
        "revealed", "reveals", "secret", "secrets", "journey", "future", "human",
        "ambition", "footage", "video", "scene", "cinematic", "beautiful",
        "dramatic", "sequence", "sweeping", "view", "views", "shot", "shots",
        "archival", "contemporary", "establishing", "contrasted", "generated",
    }

    def concise_phrase(value: str) -> str:
        tokens = re.findall(r"[a-zA-Z0-9]{3,}", value)
        concrete = [token for token in tokens if token.lower() not in stopwords and not token.isdigit()]
        return " ".join(concrete[:5])

    concise_keywords = [concise_phrase(keyword) for keyword in keywords]
    concise_keywords = [keyword for keyword in concise_keywords if keyword]
    has_long_keyword_phrase = any(len(keyword.split()) > 3 for keyword in concise_keywords)
    if has_long_keyword_phrase:
        # Prefer one bounded query per concrete visual subject before trying a
        # combined query or a chapter title that may be poetic rather than visual.
        candidates.extend(concise_keywords)
    else:
        if len(keywords) >= 2:
            candidates.append(" ".join(keywords[:2]))
        if len(keywords) >= 3:
            candidates.append(" ".join([keywords[0], keywords[-1]]))
        if len(keywords) >= 4:
            candidates.append(" ".join(keywords[-2:]))
        elif len(keywords) == 3:
            candidates.append(" ".join(keywords[1:]))
    candidates.extend([title, visual_intent])

    stopwords = {
        "the", "and", "for", "with", "from", "that", "this", "then", "they",
        "their", "there", "into", "about", "after", "before", "what", "when",
        "where", "which", "while", "would", "could", "should", "have", "been",
        "were", "was", "are", "has", "had", "most", "more", "than", "true",
        "cost", "story", "conclusion", "emerging", "frontier", "explained",
        "revealed", "reveals", "secret", "secrets", "journey", "future", "human",
        "ambition", "footage", "video", "scene", "cinematic", "beautiful",
        "dramatic", "sequence", "sweeping", "view", "views", "shot", "shots",
        "archival", "contemporary", "establishing", "contrasted", "generated",
    }
    normalized = []
    for candidate in candidates:
        query = re.sub(r"\s+", " ", candidate).strip(" ,.;:-")
        tokens = re.findall(r"[a-zA-Z0-9]{3,}", query.lower())
        concrete = [token for token in tokens if token not in stopwords and not token.isdigit()]
        if len(concrete) < 1:
            continue
        # Keep long visual directions from turning into poor search queries.
        if candidate == visual_intent and len(tokens) > 8:
            query = " ".join(concrete[:6])
        if query and query.casefold() not in {item.casefold() for item in normalized}:
            normalized.append(query[:120])
        if len(normalized) >= limit:
            break
    return normalized

