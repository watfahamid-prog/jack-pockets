from __future__ import annotations

import os
import re
import requests

HEADERS = {
    "User-Agent": "JackPocketsDocumentary/1.0 (research and source attribution; https://github.com/watfahamid-prog/jack-pockets)"
}


def _tavily(query: str, limit: int) -> list[dict]:
    key = os.getenv("TAVILY_API_KEY", "").strip()
    if not key:
        return []
    response = requests.post(
        "https://api.tavily.com/search",
        json={"api_key": key, "query": query, "max_results": limit, "search_depth": "advanced"},
        timeout=35,
    )
    response.raise_for_status()
    results = []
    for item in response.json().get("results", []):
        url = item.get("url")
        if not url:
            continue
        results.append({
            "title": item.get("title") or url,
            "url": url,
            "content": item.get("content", ""),
            "source_type": "web_search",
        })
    return results


def _europe_pmc(query: str, limit: int) -> list[dict]:
    # Peer-reviewed biomedical literature; particularly useful for anatomy, health, and biology.
    try:
        response = requests.get(
            "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
            params={"query": query, "format": "json", "pageSize": min(limit, 8), "resultType": "core"},
            headers=HEADERS,
            timeout=25,
        )
        response.raise_for_status()
        records = response.json().get("resultList", {}).get("result", [])
    except Exception as exc:
        print(f"[research] Europe PMC unavailable: {exc}", flush=True)
        return []
    results = []
    for item in records:
        title = item.get("title")
        if not title:
            continue
        pmcid = item.get("pmcid")
        pmid = item.get("pmid")
        doi = item.get("doi")
        url = (f"https://europepmc.org/articles/{pmcid}" if pmcid else
               f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else
               f"https://doi.org/{doi}" if doi else "")
        if not url:
            continue
        abstract = item.get("abstractText") or ""
        results.append({
            "title": re.sub(r"<[^>]+>", " ", title),
            "url": url,
            "content": re.sub(r"<[^>]+>", " ", abstract)[:1800],
            "source_type": "peer_reviewed_literature",
            "authors": item.get("authorString"),
            "journal": item.get("journalTitle"),
            "year": item.get("firstPublicationDate"),
            "doi": doi,
        })
    return results


def _wikipedia(query: str, limit: int) -> list[dict]:
    # Broad fallback if Tavily is not configured; label it as background, not primary evidence.
    try:
        response = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={"action": "query", "list": "search", "srsearch": query, "format": "json", "srlimit": min(limit, 5)},
            headers=HEADERS,
            timeout=20,
        )
        response.raise_for_status()
        hits = response.json().get("query", {}).get("search", [])
    except Exception as exc:
        print(f"[research] Wikipedia fallback unavailable: {exc}", flush=True)
        return []
    results = []
    for hit in hits:
        title = hit.get("title", "")
        if not title:
            continue
        extract = re.sub(r"<[^>]+>", " ", hit.get("snippet", ""))
        results.append({
            "title": title,
            "url": "https://en.wikipedia.org/wiki/" + requests.utils.quote(title.replace(" ", "_"), safe="()'"),
            "content": extract,
            "source_type": "encyclopedia_background",
        })
    return results


def search_web(query: str, limit: int = 6) -> list[dict]:
    """Find traceable sources; prefer web search and biomedical literature, never invent citations."""
    limit = max(1, min(int(limit), 10))
    results = []
    try:
        results.extend(_tavily(query, limit))
    except Exception as exc:
        print(f"[research] Tavily search failed: {exc}", flush=True)

    # Add peer-reviewed biomedical sources for scientific topics, even when general search works.
    if len(results) < min(limit, 4):
        results.extend(_europe_pmc(query, limit))
    if len(results) < min(limit, 4):
        results.extend(_wikipedia(query, limit))

    unique = []
    seen = set()
    for item in results:
        url = str(item.get("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        unique.append(item)
        if len(unique) >= limit:
            break
    return unique
