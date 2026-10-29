from __future__ import annotations
import html, os, re, requests
from pathlib import Path
from urllib.parse import quote, urlparse
from dotenv import load_dotenv
from relevance import _asset_relevance

load_dotenv()

_PEXELS_DISABLED = False


def _pexels_key()->str:
    key=os.getenv("PEXELS_API_KEY","").strip()
    print(f"[pexels] key configured={'yes' if key else 'no'}")
    return key

def _get(url:str,key:str,params:dict)->dict:
    global _PEXELS_DISABLED
    if _PEXELS_DISABLED:
        raise RuntimeError("Pexels disabled after an authentication/authorization failure")
    r=requests.get(url,headers={"Authorization":key},params=params,timeout=45)
    if r.status_code in (401, 403):
        _PEXELS_DISABLED = True
    if not r.ok:
        raise RuntimeError(f"Pexels HTTP {r.status_code}: {r.text[:240].replace(chr(10), ' ')}")
    return r.json()

MAX_ASSET_DOWNLOAD_BYTES = 125_000_000
MAX_TOTAL_ASSET_DOWNLOAD_BYTES = max(
    1,
    int(os.getenv("JACKPOCKETS_MAX_TOTAL_ASSET_DOWNLOAD_BYTES", "1000000000")),
)
_ASSET_BYTES_DOWNLOADED = 0


def reset_asset_download_budget() -> None:
    """Reset the episode-wide download counter at the start of a generation run."""
    global _ASSET_BYTES_DOWNLOADED
    _ASSET_BYTES_DOWNLOADED = 0




def _archive_title_is_non_broll(title: str, query: str = "") -> bool:
    """Reject archive results that are clearly tutorials, shows, or demos."""
    patterns = (
        r"\btutorial\b", r"\bhow\s+to\b", r"\bfailsafe\b", r"\breflash\b",
        r"\bwalkthrough\b", r"\bpodcast\b", r"\bepisode\b", r"\bCES\s+20\d{2}\b",
        r"\bdemo\b", r"\breview\b", r"\bcourse\b", r"\bclass\s+materials\b",
        r"\btraining\b", r"\blecture\b", r"\bwebinar\b", r"\bsetup\b",
        r"\bDIY\b", r"\bfirmware\b", r"\bconfigure\b", r"\bconfiguration\b",
        r"\bguide\b", r"\bmake\s+(?:an?\s+)?(?:ethernet|network|router|server|cable)\b",
        r"\bpart\s+\d+\b", r"\bTV\s+\d+\b",
    )
    if any(re.search(pattern, str(title), re.IGNORECASE) for pattern in patterns):
        # A tutorial may be relevant only when the query itself explicitly asks
        # for one; otherwise it is usually a branded demo rather than documentary b-roll.
        query_terms = set(re.findall(r"[a-z0-9]+", str(query).lower()))
        if not query_terms.intersection({"tutorial", "guide", "walkthrough", "demo", "review"}):
            return True
    # Internet Archive also indexes music-game playthroughs and entertainment
    # episodes. They can match technical words accidentally (e.g. "Rock Band
    # Network" for a network-switch query), so reject them unless the query is
    # explicitly about games/music.
    entertainment = (
        r"\brock\s+band\b", r"\bgameplay\b", r"\bplaythrough\b",
        r"\bvideo\s+game\b", r"\bnintendo\b", r"\bxbox\b",
        r"\bplaystation\b", r"\bexpert\s+keys\b", r"\bvocals\b",
        r"\bharmonies\b", r"\bmusic\b", r"\bsong\b",
    )
    query_text = str(query).lower()
    asks_for_entertainment = any(
        token in query_text for token in ("game", "gaming", "music", "song", "band", "console")
    )
    return not asks_for_entertainment and any(
        re.search(pattern, str(title), re.IGNORECASE) for pattern in entertainment
    )


def _download(url, path, max_bytes: int = MAX_ASSET_DOWNLOAD_BYTES):
    """Download media within both per-file and episode-wide byte budgets."""
    global _ASSET_BYTES_DOWNLOADED
    remaining = MAX_TOTAL_ASSET_DOWNLOAD_BYTES - _ASSET_BYTES_DOWNLOADED
    if remaining <= 0:
        raise ValueError(
            f"episode asset download budget exhausted ({MAX_TOTAL_ASSET_DOWNLOAD_BYTES} bytes)"
        )
    effective_limit = min(int(max_bytes), remaining)
    headers = {
        "User-Agent": "JackPocketsDocumentary/1.0 (open-media downloader; https://github.com/watfahamid-prog/jack-pockets)"
    }
    try:
        with requests.get(url, headers=headers, timeout=(15, 25), stream=True) as response:
            response.raise_for_status()
            content_length = response.headers.get("content-length")
            if content_length:
                try:
                    if int(content_length) > effective_limit:
                        raise ValueError(
                            f"media file exceeds size limit ({content_length} > {effective_limit} bytes)"
                        )
                except ValueError as exc:
                    if "exceeds size limit" in str(exc):
                        raise
            written = 0
            with path.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    written += len(chunk)
                    if written > effective_limit:
                        raise ValueError(
                            f"media download exceeded size limit ({written} > {effective_limit} bytes)"
                        )
                    handle.write(chunk)
        _ASSET_BYTES_DOWNLOADED += written
        print(
            f"[assets] downloaded={written} bytes episode_total={_ASSET_BYTES_DOWNLOADED}/"
            f"{MAX_TOTAL_ASSET_DOWNLOAD_BYTES}",
            flush=True,
        )
    except Exception:
        path.unlink(missing_ok=True)
        raise

def search_pexels_videos(query:str,out:Path,limit:int=4,beat:dict|None=None)->list[dict]:
    if _PEXELS_DISABLED:
        print("[pexels] skipping after earlier authentication/authorization failure", flush=True)
        return []
    key=_pexels_key()
    if not key:
        print("[pexels] no API key; skipping video search")
        return []
    out.mkdir(parents=True,exist_ok=True)
    print(f"[pexels] video search: {query[:120]!r}")
    data=_get("https://api.pexels.com/videos/search",key,{"query":query[:180],"per_page":max(8,limit*3),"orientation":"landscape","size":"medium","locale":"en-US"})
    videos=data.get("videos",[])
    print(f"[pexels] video results={len(videos)} total={data.get('total_results',0)}")
    result=[]
    for video in videos:
        files=[f for f in video.get("video_files",[]) if f.get("file_type")=="video/mp4" and f.get("link")]
        # Prefer full-HD sources for the 1080p output, but never choose 4K just
        # because it has the most pixels; the download-size guard is a second limit.
        capped = [f for f in files if int(f.get("width") or 0) <= 1920]
        files = capped or files
        files.sort(key=lambda f:(
            abs(int(f.get("width") or 1920) - 1920),
            abs(int(f.get("height") or 1080) - 1080),
            -float(f.get("fps") or 0),
        ))
        chosen=files[0] if files else None
        if not chosen: continue
        vid=str(video.get("id"))
        video_url = str(video.get("url") or "")
        candidate_title = video_url.rstrip("/").rsplit("/",1)[-1].replace("-"," ")
        candidate = {"title": candidate_title, "description": video_url, "tags": []}
        if beat is not None:
            relevant, matched_terms = _asset_relevance(query, beat, candidate)
            if not relevant:
                print(
                    f"[pexels] rejected before download title={candidate_title[:100]!r} matched={matched_terms}",
                    flush=True,
                )
                continue
        path=out/f"video-{vid}.mp4"
        try:
            if not path.exists(): _download(chosen["link"],path)
            print(f"[pexels] selected video={vid} {chosen.get('width')}x{chosen.get('height')} duration={video.get('duration')}s bytes={path.stat().st_size}")
            result.append({"id":f"pexels-video-{vid}","kind":"video","src":str(path),"title":str(video.get("url") or "").rstrip("/").rsplit("/",1)[-1].replace("-"," "),"description":str(video.get("url") or ""),"credit":(video.get("user") or {}).get("name"),"license":"Pexels","license_url":"https://www.pexels.com/license/","source_url":video.get("url"),"creator_url":(video.get("user") or {}).get("url"),"score":1.0,"role":"b-roll","duration":float(video.get("duration") or 0),"width":chosen.get("width"),"height":chosen.get("height"),"fps":chosen.get("fps")})
            if len(result)>=limit: break
        except Exception as e:
            print(f"[pexels] download failed video={vid}: {e}")
    return result

def search_pexels(query:str,out:Path,limit:int=3)->list[dict]:
    if _PEXELS_DISABLED:
        print("[pexels] skipping photo search after earlier authentication/authorization failure", flush=True)
        return []
    key=_pexels_key()
    if not key:
        print("[pexels] no API key; skipping photo search")
        return []
    out.mkdir(parents=True,exist_ok=True)
    print(f"[pexels] photo search: {query[:120]!r}")
    data=_get("https://api.pexels.com/v1/search",key,{"query":query[:180],"per_page":max(1,limit),"orientation":"landscape","locale":"en-US"})
    result=[]
    for p in data.get("photos",[]):
        src=p.get("src",{}).get("large2x") or p.get("src",{}).get("large")
        if not src: continue
        path=out/f"photo-{p['id']}.jpg"
        try:
            _download(src,path)
            result.append({"id":str(p["id"]),"kind":"photo","src":str(path),"title":str(p.get("url") or "").rstrip("/").rsplit("/",1)[-1].replace("-"," "),"description":str(p.get("alt") or ""),"credit":p.get("photographer"),"license":"Pexels","license_url":"https://www.pexels.com/license/","source_url":p.get("url"),"creator_url":p.get("photographer_url"),"score":1.0,"role":"b-roll"})
        except Exception as e:
            print(f"[pexels] photo download failed id={p.get('id')}: {e}")
    return result


def _pixabay_key()->str:
    key=os.getenv("PIXABAY_API_KEY","").strip()
    print(f"[pixabay] key configured={'yes' if key else 'no'}")
    return key

def search_pixabay_videos(query:str,out:Path,limit:int=4,beat:dict|None=None)->list[dict]:
    """Search and download a small set of Pixabay videos as a Pexels fallback."""
    key=_pixabay_key()
    if not key:
        print("[pixabay] no API key; skipping video search")
        return []
    out.mkdir(parents=True,exist_ok=True)
    clean_query=query[:100]
    print(f"[pixabay] video search: {clean_query[:120]!r}")
    response=requests.get("https://pixabay.com/api/videos/",params={
        "key":key,"q":clean_query,"per_page":max(3,min(60,limit*3)),
        "safesearch":"true","lang":"en","video_type":"film",
    },timeout=45)
    if not response.ok:
        raise RuntimeError(f"Pixabay video API HTTP {response.status_code}: {response.text[:240]}")
    hits=response.json().get("hits",[])
    print(f"[pixabay] video results={len(hits)}")
    result=[]
    for video in hits:
        variants=video.get("videos") or {}
        chosen=None
        for size in ("large","medium","small","tiny"):
            candidate=variants.get(size) or {}
            if candidate.get("url"):
                chosen=candidate
                break
        if not chosen:
            continue
        vid=str(video.get("id",""))
        if not vid:
            continue
        tags = str(video.get("tags") or "").split(", ")
        candidate = {"title": str(video.get("tags") or ""), "tags": tags, "description": str(video.get("tags") or "")}
        if beat is not None:
            relevant, matched_terms = _asset_relevance(query, beat, candidate)
            if not relevant:
                print(
                    f"[pixabay] rejected before download tags={str(video.get('tags') or '')[:100]!r} matched={matched_terms}",
                    flush=True,
                )
                continue
        path=out/f"pixabay-video-{vid}.mp4"
        try:
            if not path.exists():
                _download(chosen["url"],path)
            result.append({
                "id":f"pixabay-video-{vid}","kind":"video","src":str(path),
                "credit":video.get("user"),"title":str(video.get("tags") or ""),"tags":tags,"description":str(video.get("tags") or ""),"license":"Pixabay","source_url":video.get("pageURL"),
                "score":1.0,"role":"b-roll","duration":float(video.get("duration") or 0),
                "width":chosen.get("width"),"height":chosen.get("height"),
            })
            print(f"[pixabay] selected video={vid} {chosen.get('width')}x{chosen.get('height')}")
            if len(result)>=limit:
                break
        except Exception as exc:
            print(f"[pixabay] video download failed id={vid}: {exc}")
    return result

def search_pixabay(query:str,out:Path,limit:int=3)->list[dict]:
    """Search and download Pixabay photos when Pexels photo results are unavailable."""
    key=_pixabay_key()
    if not key:
        print("[pixabay] no API key; skipping photo search")
        return []
    out.mkdir(parents=True,exist_ok=True)
    clean_query=query[:100]
    print(f"[pixabay] photo search: {clean_query[:120]!r}")
    response=requests.get("https://pixabay.com/api/",params={
        "key":key,"q":clean_query,"image_type":"photo","orientation":"horizontal",
        "per_page":max(3,min(60,limit*2)),"safesearch":"true","lang":"en",
    },timeout=45)
    if not response.ok:
        raise RuntimeError(f"Pixabay photo API HTTP {response.status_code}: {response.text[:240]}")
    result=[]
    for photo in response.json().get("hits",[]):
        src=photo.get("fullHDURL") or photo.get("largeImageURL") or photo.get("webformatURL")
        if not src:
            continue
        photo_id=str(photo.get("id",""))
        if not photo_id:
            continue
        path=out/f"pixabay-photo-{photo_id}.jpg"
        try:
            if not path.exists():
                _download(src,path)
            result.append({
                "id":f"pixabay-photo-{photo_id}","kind":"photo","src":str(path),
                "credit":photo.get("user"),"title":str(photo.get("tags") or ""),"tags":str(photo.get("tags") or "").split(", "),"description":str(photo.get("tags") or ""),"license":"Pixabay","source_url":photo.get("pageURL"),
                "score":1.0,"role":"b-roll",
            })
            if len(result)>=limit:
                break
        except Exception as exc:
            print(f"[pixabay] photo download failed id={photo_id}: {exc}")
    return result


def _archive_license_is_usable(license_url: str) -> bool:
    """Allow licences suitable for edited/commercial video; reject NC/ND and unknown terms."""
    parsed = urlparse(str(license_url).strip().lower())
    host = (parsed.hostname or "").removeprefix("www.")
    if host != "creativecommons.org":
        return False

    path = parsed.path.rstrip("/") + "/"
    if re.fullmatch(r"/publicdomain/(?:zero|mark)/[0-9.]+/", path):
        return True

    # CC BY and CC BY-SA permit commercial reuse and adaptations when attribution
    # and applicable share-alike terms are respected. NC and ND variants are not
    # acceptable defaults for a monetized, edited documentary pipeline.
    return bool(re.fullmatch(r"/licenses/(?:by|by-sa)/[0-9.]+(?:/[a-z-]+)?/", path))


def search_archive_videos(query:str,out:Path,limit:int=3,beat:dict|None=None)->list[dict]:
    """Search Internet Archive for openly licensed documentary b-roll; no API key required."""
    out.mkdir(parents=True, exist_ok=True)
    terms = re.findall(r"[a-zA-Z0-9]{3,}", str(query).lower())[:7]
    if not terms:
        return []
    # Search multiple levels of specificity so a long editorial query doesn't return zero hits.
    variants = [terms[:4], terms[:2]]
    seen = set()
    result = []
    # Search endpoints can return unrelated films because terms like "terminal",
    # "black", or "architecture" have multiple meanings. Reject assets whose own
    # metadata does not match the requested visual subject.
    stopwords = {"the", "and", "for", "with", "from", "that", "this", "into", "onto",
                 "over", "under", "near", "shot", "close", "view", "show", "showing",
                 "footage", "video", "image", "scene", "cinematic", "modern", "vintage"}
    query_terms = {term for term in re.findall(r"[a-zA-Z]{4,}", str(query).lower())
                   if term not in stopwords}
    headers = {"User-Agent": "JackPocketsDocumentary/1.0 (open-media search; https://github.com/watfahamid-prog/jack-pockets)"}
    for selected in variants:
        if not selected:
            continue
        expression = " AND ".join(f'"{term}"' for term in selected)
        try:
            response = requests.get(
                "https://archive.org/advancedsearch.php",
                params={"q": f"mediatype:movies AND ({expression})",
                        "fl[]": ["identifier", "title", "description", "licenseurl"],
                        "rows": 8, "page": 1, "output": "json"},
                headers=headers, timeout=20)
            response.raise_for_status()
            docs = response.json().get("response", {}).get("docs", [])
        except Exception as exc:
            print(f"[archive] search failed: {exc}", flush=True)
            continue
        print(f"[archive] search results={len(docs)} query={' '.join(selected)!r}", flush=True)
        for doc in docs:
            identifier = str(doc.get("identifier") or "")
            license_url = str(doc.get("licenseurl") or "").lower()
            if not identifier or identifier in seen:
                continue
            title = str(doc.get("title") or "")
            if _archive_title_is_non_broll(title, query):
                print(
                    f"[archive] rejected program/tutorial result title={title[:100]!r}",
                    flush=True,
                )
                continue
            metadata_text = (title + " " +
                             str(doc.get("description") or "")[:1800]).lower()
            matched_terms = {term for term in query_terms if term in metadata_text}
            if len(query_terms) >= 3 and len(matched_terms) < 2:
                print(
                    f"[archive] rejected low-relevance result={identifier!r} "
                    f"title={str(doc.get('title') or '')[:100]!r} matched={sorted(matched_terms)}",
                    flush=True,
                )
                continue
            if beat is not None:
                candidate = {
                    "title": str(doc.get("title") or ""),
                    "description": str(doc.get("description") or "")[:1800],
                    "tags": [],
                }
                relevant, beat_matches = _asset_relevance(query, beat, candidate)
                if not relevant:
                    print(
                        f"[archive] rejected before metadata/download title={candidate['title'][:100]!r} matched={beat_matches}",
                        flush=True,
                    )
                    continue
            # The previous broad URL check also accepted CC-NC/CC-ND, which can
            # block monetization or adaptations. Only accept known commercial/adaptation-
            # friendly Creative Commons options or public-domain markers.
            if not _archive_license_is_usable(license_url):
                print(f"[archive] rejected unsupported license={license_url!r}", flush=True)
                continue
            seen.add(identifier)
            try:
                meta_response = requests.get(
                    f"https://archive.org/metadata/{quote(identifier, safe='')}",
                    headers=headers, timeout=35)
                meta_response.raise_for_status()
                files = meta_response.json().get("files", [])
                candidates = []
                for item in files:
                    name = str(item.get("name") or "")
                    fmt = str(item.get("format") or "").lower()
                    size = int(item.get("size") or 0)
                    ext = os.path.splitext(name)[1].lower()
                    if ext not in {".mp4", ".webm", ".ogv", ".mov"}:
                        continue
                    if size and size < 500_000:
                        continue
                    if size and size > 125_000_000:
                        continue
                    if "mpeg4" in fmt or "h.264" in fmt or ext in {".mp4", ".webm", ".ogv", ".mov"}:
                        candidates.append((0 if ext == ".mp4" else 1, size or 10**12, name))
                if not candidates:
                    continue
                candidates.sort()
                filename = candidates[0][2]
                media_url = f"https://archive.org/download/{quote(identifier, safe='')}/{quote(filename, safe='/')}"
                path = out / f"archive-{re.sub(r'[^a-zA-Z0-9_-]+','-',identifier)}{os.path.splitext(filename)[1].lower()}"
                if not path.exists():
                    _download(media_url, path)
                if path.stat().st_size < 500_000:
                    path.unlink(missing_ok=True)
                    continue
                result.append({
                    "id": f"archive-video-{identifier}", "kind": "video", "src": str(path),
                    "credit": "Internet Archive: " + str(doc.get("title") or identifier),
                    "title": str(doc.get("title") or identifier), "description": str(doc.get("description") or ""),
                    "license": "Internet Archive / " + license_url,
                    "source_url": f"https://archive.org/details/{identifier}",
                    "score": 0.85, "role": "b-roll", "query": query,
                })
                print(f"[archive] selected video={identifier} bytes={path.stat().st_size}", flush=True)
                if len(result) >= limit:
                    return result
            except Exception as exc:
                print(f"[archive] item failed id={identifier}: {exc}", flush=True)
    print(f"[archive] usable video results={len(result)} query={query[:100]!r}", flush=True)
    return result


def _commons_search(query:str,out:Path,limit:int=3,kind:str="video",beat:dict|None=None)->list[dict]:
    """Find openly licensed Wikimedia Commons media without requiring an API key."""
    out.mkdir(parents=True, exist_ok=True)
    clean = re.sub(r"[^a-zA-Z0-9 \"'-]", " ", str(query))
    clean = re.sub(r"\s+", " ", clean).strip()[:110]
    if not clean:
        return []
    # Search broadly: Commons generator search does not reliably support filetype operators.
    params = {
        "action": "query", "format": "json", "generator": "search",
        "gsrnamespace": 6, "gsrsearch": clean,
        "gsrlimit": max(8, limit * 5), "prop": "imageinfo",
        "iiprop": "url|mime|extmetadata", "iiurlwidth": 1280,
    }
    headers = {"User-Agent": "JackPocketsDocumentary/1.0 (media search; https://github.com/watfahamid-prog/jack-pockets)"}
    response = requests.get("https://commons.wikimedia.org/w/api.php", params=params, headers=headers, timeout=45)
    if not response.ok:
        raise RuntimeError(f"Wikimedia Commons API HTTP {response.status_code}: {response.text[:240]}")
    pages = (response.json().get("query") or {}).get("pages") or {}
    result = []
    for page in pages.values():
        info_list = page.get("imageinfo") or []
        if not info_list:
            continue
        info = info_list[0]
        mime = str(info.get("mime") or "").lower()
        original = info.get("url") or ""
        thumb = info.get("thumburl") or ""
        if kind == "video":
            if not (mime.startswith("video/") or re.search(r"\.(mp4|webm|ogv|ogg|mov)(?:$|\?)", original, re.I)):
                continue
            src = thumb if str(info.get("thumbmime") or "").startswith("video/") else original
            ext = os.path.splitext(urlparse(src).path)[1].lower() or ".webm"
            if ext not in {".mp4", ".webm", ".ogv", ".ogg", ".mov"}:
                ext = ".webm"
        else:
            if not mime.startswith("image/") or mime == "image/svg+xml":
                continue
            src = thumb or original
            ext = os.path.splitext(urlparse(src).path)[1].lower() or ".jpg"
            if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
                ext = ".jpg"
        metadata = info.get("extmetadata") or {}
        title = str(page.get("title") or "").replace("File:","").replace("_"," ")
        description = str(metadata.get("ImageDescription", {}).get("value", "") if isinstance(metadata.get("ImageDescription"), dict) else "")
        candidate = {"title": title, "description": description, "tags": []}
        if beat is not None:
            relevant, matched_terms = _asset_relevance(query, beat, candidate)
            if not relevant:
                print(
                    f"[commons] rejected before download title={title[:100]!r} matched={matched_terms}",
                    flush=True,
                )
                continue
        page_id = str(page.get("pageid") or re.sub(r"[^a-zA-Z0-9]+", "-", page.get("title", "commons")).strip("-"))
        asset_id = f"commons-{kind}-{page_id}"
        path = out / f"{asset_id}{ext}"
        try:
            if not path.exists():
                _download(src, path)
            if path.stat().st_size < 5000:
                path.unlink(missing_ok=True)
                continue
            artist_value = metadata.get("Artist", {}).get("value", "") if isinstance(metadata.get("Artist"), dict) else ""
            artist = re.sub(r"<[^>]+>", " ", str(artist_value)).strip()[:180]
            license_value = metadata.get("LicenseShortName", {}).get("value", "Wikimedia Commons") if isinstance(metadata.get("LicenseShortName"), dict) else "Wikimedia Commons"
            result.append({
                "id": asset_id, "kind": kind, "src": str(path), "title": str(page.get("title") or "").replace("File:","").replace("_"," "), "description": str(metadata.get("ImageDescription", {}).get("value", "") if isinstance(metadata.get("ImageDescription"), dict) else ""), "credit": artist or "Wikimedia Commons contributor",
                "license": f"Wikimedia Commons / {license_value}", "source_url": "https://commons.wikimedia.org/wiki/" + str(page.get("title", "")).replace(" ", "_"),
                "score": 1.0, "role": "b-roll", "query": clean,
            })
            print(f"[commons] selected {kind}={page.get('title')} bytes={path.stat().st_size}", flush=True)
            if len(result) >= limit:
                break
        except Exception as exc:
            print(f"[commons] download failed title={page.get('title')}: {exc}", flush=True)
    print(f"[commons] {kind} results={len(result)} query={clean!r}", flush=True)
    return result


def search_commons_videos(query:str,out:Path,limit:int=4,beat:dict|None=None)->list[dict]:
    return _commons_search(query, out, limit, "video", beat)


def search_commons_photos(query:str,out:Path,limit:int=3,beat:dict|None=None)->list[dict]:
    return _commons_search(query, out, limit, "photo", beat)


def make_asset_plan(sentence:str,editorial:dict|None=None)->list[dict]:
    low=sentence.lower();roles=[]
    if editorial:
        roles.extend(str(x).lower() for x in (editorial.get("visual_roles") or editorial.get("visuals") or []) if x)
    if any(x in low for x in ["map","country","city","where","location","border","north","south","east","west"]): roles.append("map")
    if any(x in low for x in ["according","report","document","letter","record","court","file","study","paper"]): roles.append("document")
    if any(x in low for x in ["percent","million","billion","number","statistic","rate","times","increase","decrease"]): roles.append("chart")
    if any(x in low for x in ["tweet","post","website","message","app","screenshot","online"]): roles.append("screenshot")
    roles=[r for r in dict.fromkeys(roles) if r in {"map","document","chart","screenshot","quote card","headline","texture","b-roll","photo","archival photo"}]
    if not roles:roles=["b-roll","photo"]
    return [{"role":x,"query":sentence[:180]} for x in roles[:3]]

def _safe(s:str)->str:
    return html.escape(re.sub(r"\s+"," ",str(s)).strip())

def _svg(kind:str,title:str,body:str,accent:str="#f5d76e")->str:
    title=_safe(title)[:36];body=_safe(body)[:210]
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#161616"/><stop offset="1" stop-color="#050505"/></linearGradient><filter id="s"><feDropShadow dx="0" dy="16" stdDeviation="20" flood-opacity=".55"/></filter></defs>
<rect width="1920" height="1080" fill="url(#g)"/><rect x="70" y="70" width="1780" height="940" rx="28" fill="#111" stroke="#444" stroke-width="2" filter="url(#s)"/>
<rect x="70" y="70" width="12" height="940" fill="{accent}"/><text x="130" y="170" fill="#fff" font-family="Arial,sans-serif" font-size="34" font-weight="800" letter-spacing="5">{kind.upper()}</text>
<text x="130" y="270" fill="#fff" font-family="Arial,sans-serif" font-size="72" font-weight="900">{title}</text>
<foreignObject x="130" y="330" width="1500" height="520"><div xmlns="http://www.w3.org/1999/xhtml" style="font:32px Arial;color:#bbb;line-height:1.45">{body}</div></foreignObject>
<circle cx="1710" cy="190" r="44" fill="{accent}" opacity=".9"/><circle cx="1710" cy="190" r="18" fill="#111"/>
</svg>'''

def generate_role_asset(role:str,narration:str,out:Path,research:list[dict]|None=None,index:int=0)->dict|None:
    role=role.lower();out.mkdir(parents=True,exist_ok=True)
    key=re.sub(r"[^a-z0-9]+","-",narration.lower()).strip("-")[:42] or "scene"
    path=out/f"{index}-{role.replace(' ','-')}-{key}.svg"
    snippet=(research or [{}])[0].get("content","") if research else ""
    if role in {"document","quote card","headline"}:
        source=(research or [{}])[0]
        source_title=source.get("title","Research source") if source else "Research source"
        source_url=source.get("url","") if source else ""
        body=(snippet[:420] or "Evidence treatment generated from the research context.")
        body += f"\n\nSOURCE: {source_title}"
        if source_url: body += f"\n{source_url}"
        svg=_svg("SOURCE / DOCUMENT",narration[:72],body)
    elif role=="screenshot":
        svg=_svg("SCREEN / ONLINE",narration[:72],"A stylized source surface used to visualize an online claim or interface without fabricating a real screenshot.")
    elif role=="chart":
        nums=re.findall(r"\d+(?:\.\d+)?%?|\$?\d+(?:\.\d+)?\s*(?:million|billion|thousand)",narration,re.I)
        bar_parts=[]
        for i,n in enumerate(nums[:6]):
            raw=re.sub(r"[^0-9.]","",n)
            value=float(raw or 10)
            height=min(500,int(value*3))
            y=780-height
            bar_parts.append(f'<rect x="{260+i*250}" y="{y}" width="110" height="{height}" rx="12" fill="#f5d76e"/>')
        bars="".join(bar_parts)
        fallback='<rect x="300" y="500" width="900" height="180" rx="20" fill="#f5d76e" opacity=".8"/>'
        svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080"><rect width="1920" height="1080" fill="#090909"/><text x="150" y="150" fill="#fff" font-family="Arial" font-size="40" font-weight="800">DATA / SCALE</text><text x="150" y="235" fill="#fff" font-family="Arial" font-size="62" font-weight="900">{_safe(narration[:38])}</text><line x1="220" y1="820" x2="1700" y2="820" stroke="#555" stroke-width="3"/>{bars or fallback}</svg>'
    elif role=="map":
        svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080"><rect width="1920" height="1080" fill="#0a0a0a"/><path d="M220 700 L400 430 L690 300 L980 390 L1210 270 L1510 470 L1680 730 L1450 870 L1040 820 L710 900 L390 820 Z" fill="#171717" stroke="#777" stroke-width="5"/><circle cx="980" cy="520" r="24" fill="#f5d76e"/><circle cx="980" cy="520" r="55" fill="none" stroke="#f5d76e" stroke-opacity=".35" stroke-width="5"/><text x="150" y="160" fill="#fff" font-family="Arial" font-size="40" font-weight="800">LOCATION</text><text x="150" y="235" fill="#fff" font-family="Arial" font-size="62" font-weight="900">{_safe(narration[:38])}</text></svg>'
    else:
        # Always provide a real visual fallback when stock footage is unavailable.
        # This prevents a valid render from becoming a completely black video.
        label = role.upper().replace("-", " ")
        title = _safe(narration[:38])
        body = _safe("Editorial visual generated from the narration. Stock footage can replace this asset when Pexels is configured.")
        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">
<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#151515"/><stop offset="1" stop-color="#050505"/></linearGradient><radialGradient id="glow"><stop stop-color="#f5d76e" stop-opacity=".22"/><stop offset="1" stop-color="#f5d76e" stop-opacity="0"/></radialGradient></defs>
<rect width="1920" height="1080" fill="url(#bg)"/><circle cx="1540" cy="280" r="560" fill="url(#glow)"/>
<rect x="92" y="92" width="1736" height="896" rx="34" fill="#0d0d0d" fill-opacity=".72" stroke="#555" stroke-width="2"/>
<rect x="92" y="92" width="14" height="896" fill="#f5d76e"/>
<text x="150" y="190" fill="#f5d76e" font-family="Arial,sans-serif" font-size="34" font-weight="800" letter-spacing="6">{label}</text>
<text x="150" y="330" fill="#fff" font-family="Arial,sans-serif" font-size="68" font-weight="900">{title}</text>
<text x="150" y="900" fill="#999" font-family="Arial,sans-serif" font-size="28">{body}</text>
<circle cx="1530" cy="600" r="150" fill="none" stroke="#f5d76e" stroke-opacity=".45" stroke-width="5"/><circle cx="1530" cy="600" r="70" fill="#f5d76e" fill-opacity=".15" stroke="#f5d76e" stroke-width="3"/>
</svg>'''
    path.write_text(svg,encoding="utf-8")
    return {"id":f"generated-{index}-{role.replace(' ','-')}","kind":"generated","src":str(path),"role":role,"score":1.0,"credit":"Generated editorial graphic"}
