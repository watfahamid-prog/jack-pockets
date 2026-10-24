from __future__ import annotations

import re
from urllib.parse import urlparse


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
        # Descriptive modifiers often appear in stock titles but are not proof
        # of the actual subject (e.g. "vintage telephone" for a computer query).
        "vintage", "retro", "classic", "antique", "historic", "historical",
        "1980s", "1990s", "2000s", "2010s", "2020s", "abstract", "dynamic",
        "colorful", "futuristic", "digital", "luminous", "blinking", "glowing",
        "close", "high", "tech",
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
    # Score against the *query that produced this candidate*, not every keyword
    # in the beat. Otherwise a clip found for "ethernet cable disconnected"
    # can pass just because its description happens to mention another beat
    # keyword such as "terminal" or "network".
    metadata_terms = set(re.findall(r"[a-z0-9]{3,}", metadata))
    query_terms = {
        token for token in re.findall(r"[a-z0-9]{3,}", str(query).lower())
        if token not in stopwords and not token.isdigit()
    }
    query_hits = sorted(query_terms & metadata_terms)
    # Most stock clips are titled around one concrete subject, not every
    # modifier in the search phrase. Accept two query-term hits, or one
    # sufficiently specific subject term; never let a match from a different
    # beat keyword substitute for a match to the active query.
    broad_terms = {
        "historical", "history", "archive", "archives", "manuscript",
        "manuscripts", "documentary", "footage", "visualization", "cinematic",
        "modern", "ancient", "scene", "video", "office", "room", "person", "people",
        "system", "data", "lights",
    }
    strong_hits = [term for term in query_hits if len(term) >= 5 and term not in broad_terms]
    if len(query_terms) >= 3 and len(query_hits) < 2 and not strong_hits:
        return False, query_hits
    # Require the match to be relevant to the beat as well as to the exact query.
    found = sorted(target & metadata_terms)
    return bool(query_hits) and bool(found), query_hits

def _source_authority_score(url: str) -> int:
    """Prefer primary/technical authorities and established journalism over scraped blogs."""
    host = (urlparse(str(url)).hostname or "").lower().removeprefix("www.")
    if (
        host.endswith(".gov")
        or host.endswith(".edu")
        or host.endswith(".ac.uk")
        or host.endswith(".ac.jp")
        or host.endswith(".ac.nz")
        or host.endswith(".edu.au")
        or host in {
            "nanog.org", "ietf.org", "rfc-editor.org", "arin.net",
            "ripe.net", "apnic.net", "ieice.org", "stanford.edu",
        }
        or host.endswith(".nanog.org")
        or host.endswith(".ietf.org")
        or host.endswith(".rfc-editor.org")
    ):
        return 4
    if host in {
        "wired.com", "reuters.com", "apnews.com", "bbc.com", "arstechnica.com",
        "nytimes.com", "theguardian.com", "technologyreview.com", "cnet.com",
    } or any(host.endswith("." + domain) for domain in (
        "wired.com", "reuters.com", "apnews.com", "bbc.com", "arstechnica.com",
        "nytimes.com", "theguardian.com", "technologyreview.com", "cnet.com",
    )):
        return 3
    if host.endswith("wikipedia.org"):
        return 1
    return 0


def _relevant_sources(topic: str, beat: dict, sources: list[dict], limit: int = 3) -> list[str]:
    """Return relevant sources, prioritizing trustworthy technical and editorial authorities."""
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
        url = str(item["url"])
        ranked.append((_source_authority_score(url), len(hits), url))
    if not ranked:
        return []
    # When the search found any authoritative sources, do not fill the shortlist
    # with weaker blogs or encyclopedia mirrors just to reach the requested count.
    if any(authority >= 2 for authority, _, _ in ranked):
        ranked = [entry for entry in ranked if entry[0] >= 2]
    # Relevance is the primary ordering among sources that already meet the
    # authority threshold: a contemporary incident report should outrank a
    # general protocol paper for the incident-specific beat. Authority breaks
    # ties and still excludes low-trust sources when better candidates exist.
    ranked.sort(key=lambda item: (item[1], item[0]), reverse=True)
    return list(dict.fromkeys(url for _, _, url in ranked))[:limit]

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
        "dramatic", "sequence", "sweeping", "shot", "shots",
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
        "dramatic", "sequence", "sweeping", "shot", "shots",
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

