from __future__ import annotations

import os
import re
from urllib.parse import urlparse

import requests

from cache_utils import load_json_cache, save_json_cache

HEADERS = {
    "User-Agent": "JackPocketsDocumentary/1.0 (research and source attribution; https://github.com/watfahamid-prog/jack-pockets)"
}


def _valid_http_url(url: object) -> bool:
    if not isinstance(url, str):
        return False
    parsed = urlparse(url.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _perplexity(query: str, limit: int) -> list[dict]:
    """Fetch ranked, structured web results from Perplexity Search."""
    key = os.getenv("PERPLEXITY_API_KEY", "").strip()
    if not key:
        return []
    response = requests.post(
        "https://api.perplexity.ai/search",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"query": query, "max_results": max(1, min(int(limit), 10)), "search_type": "fast"},
        timeout=30,
    )
    response.raise_for_status()
    results = []
    for item in response.json().get("results", []):
        url = str(item.get("url") or "").strip()
        if not _valid_http_url(url):
            continue
        results.append({
            "title": str(item.get("title") or url).strip(),
            "url": url,
            "content": str(item.get("snippet") or "")[:2200],
            "source_type": "perplexity_search",
            "published_date": item.get("date"),
            "last_updated": item.get("last_updated"),
        })
        if len(results) >= limit:
            break
    return results


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
    """Use Wikipedia as a free, keyless starting point; never treat it as final proof."""
    try:
        response = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "generator": "search",
                "gsrsearch": query,
                "gsrnamespace": 0,
                "gsrlimit": min(limit, 5),
                "prop": "extracts|info",
                "exintro": 1,
                "explaintext": 1,
                "inprop": "url",
                "format": "json",
            },
            headers=HEADERS,
            timeout=20,
        )
        response.raise_for_status()
        pages = response.json().get("query", {}).get("pages", {})
    except Exception as exc:
        print(f"[research] Wikipedia API unavailable: {exc}", flush=True)
        return []

    # The MediaWiki API returns pages keyed by page ID; sort by search rank.
    ranked = sorted(pages.values(), key=lambda page: page.get("index", 10_000))
    results = []
    for page in ranked:
        title = page.get("title", "")
        url = page.get("fullurl")
        extract = re.sub(r"\s+", " ", str(page.get("extract") or "")).strip()
        if not title or not url:
            continue
        results.append({
            "title": title,
            "url": url,
            "content": extract[:2200],
            "source_type": "encyclopedia_background",
            "verification_note": (
                "Wikipedia is a starting point only. Verify factual claims against "
                "the article's cited references and preferably primary, academic, "
                "government, or university sources before using them in narration."
            ),
        })
    return results

def search_web(query: str, limit: int = 6) -> list[dict]:
    """Prefer Perplexity live search, fall back to existing sources, and cache successful results."""
    limit = max(1, min(int(limit), 10))
    cache_payload = {
        "query": " ".join(query.lower().split()),
        "limit": limit,
        "perplexity_enabled": bool(os.getenv("PERPLEXITY_API_KEY", "").strip()),
        "tavily_enabled": bool(os.getenv("TAVILY_API_KEY", "").strip()),
    }
    cached = load_json_cache("research-search", cache_payload)
    if isinstance(cached, list) and cached:
        print(f"[research] cache hit for query={query[:100]!r} results={len(cached)}", flush=True)
        return cached

    results = []
    try:
        results.extend(_perplexity(query, limit))
        if results:
            print(f"[research] Perplexity returned {len(results)} web sources.", flush=True)
    except Exception as exc:
        print(f"[research] Perplexity search failed; trying fallbacks: {exc}", flush=True)

    # Only call Tavily if Perplexity is unavailable or yields no usable results.
    if not results:
        try:
            results.extend(_tavily(query, max(2, limit - 2)))
        except Exception as exc:
            print(f"[research] Tavily search failed: {exc}", flush=True)

    # Wikipedia provides background context, not final verification.
    if len(results) < limit:
        try:
            results.extend(_wikipedia(query, min(2, limit - len(results))))
        except Exception as exc:
            print(f"[research] Wikipedia search skipped: {exc}", flush=True)

    science_terms = (
        "biology", "biolog", "human", "pig", "animal", "body", "organ", "heart",
        "brain", "medical", "medicine", "health", "disease", "science", "anatom",
        "physiology", "evolution", "genetic", "species", "research", "study",
    )
    if (any(term in query.lower() for term in science_terms) or len(results) < min(limit, 4)) and len(results) < limit:
        try:
            results.extend(_europe_pmc(query, min(4, limit - len(results))))
        except Exception as exc:
            print(f"[research] Europe PMC search skipped: {exc}", flush=True)

    unique = []
    seen = set()
    for item in results:
        url = str(item.get("url") or "").strip()
        if not _valid_http_url(url) or url in seen:
            continue
        seen.add(url)
        unique.append(item)
        if len(unique) >= limit:
            break
    if unique:
        save_json_cache("research-search", cache_payload, unique)
    return unique
