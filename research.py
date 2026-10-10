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
        extract = re.sub(r"\\s+", " ", str(page.get("extract") or "")).strip()
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
    """Collect multiple source types; Wikipedia supplies context, not final verification."""
    limit = max(1, min(int(limit), 10))
    results = []

    try:
        results.extend(_tavily(query, max(2, limit - 2)))
    except Exception as exc:
        print(f"[research] Tavily search failed: {exc}", flush=True)

    # Add a small Wikipedia context set on every topic. The API is public and requires no key.
    # Keep it after search results so it cannot displace stronger sources.
    try:
        results.extend(_wikipedia(query, min(2, limit)))
    except Exception as exc:
        print(f"[research] Wikipedia search skipped: {exc}", flush=True)

    # Biomedical literature is useful for health, anatomy, biology, and medical topics.
    science_terms = (
        "biology", "biolog", "human", "pig", "animal", "body", "organ", "heart",
        "brain", "medical", "medicine", "health", "disease", "science", "anatom",
        "physiology", "evolution", "genetic", "species", "research", "study",
    )
    if any(term in query.lower() for term in science_terms) or len(results) < min(limit, 4):
        try:
            results.extend(_europe_pmc(query, min(4, limit)))
        except Exception as exc:
            print(f"[research] Europe PMC search skipped: {exc}", flush=True)

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
