from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from urllib.parse import quote

import requests

HEADERS = {
    "User-Agent": "JackPocketsDocumentary/1.0 (music sourcing; https://github.com/watfahamid-prog/jack-pockets)"
}


def _prepare_audio(source: Path, out: Path, duration: float | None) -> Path:
    command = ["ffmpeg", "-y"]
    if duration and duration > 0:
        command += ["-stream_loop", "-1", "-i", str(source), "-t", f"{duration:.3f}"]
    else:
        command += ["-i", str(source)]
    command += ["-vn", "-c:a", "aac", "-b:a", "192k", str(out)]
    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as exc:
        details = exc.stderr.decode("utf-8", errors="replace")[-1200:] if exc.stderr else str(exc)
        raise RuntimeError(f"Could not prepare soundtrack: {details}") from exc
    if not out.exists() or out.stat().st_size < 2048:
        raise RuntimeError("Soundtrack preparation produced no usable audio file")
    return out


def _write_source(out: Path, metadata: dict) -> None:
    out.with_suffix(".json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def _archive_music(query: str, out: Path, duration: float | None) -> Path | None:
    """Find music with explicit CC0/public-domain or CC BY metadata only."""
    terms = [x for x in ("ambient", "cinematic", "instrumental", "orchestral", "soundtrack") if x in query.lower()]
    if not terms:
        terms = ["ambient", "cinematic", "instrumental"]
    title_clause = " OR ".join(f"title:{term}" for term in terms[:5])
    license_clause = (
        "(licenseurl:http*creativecommons.org/publicdomain/zero* "
        "OR licenseurl:http*creativecommons.org/licenses/by/*)"
    )
    params = {
        "q": f"mediatype:audio AND ({title_clause}) AND {license_clause}",
        "fl[]": ["identifier", "title", "creator", "licenseurl", "description"],
        "rows": 12,
        "page": 1,
        "output": "json",
    }
    try:
        response = requests.get("https://archive.org/advancedsearch.php", params=params, headers=HEADERS, timeout=25)
        response.raise_for_status()
        docs = response.json().get("response", {}).get("docs", [])
    except Exception as exc:
        print(f"[music] Internet Archive search unavailable: {exc}", flush=True)
        return None

    for doc in docs:
        identifier = str(doc.get("identifier") or "")
        license_url = str(doc.get("licenseurl") or "").lower()
        # Exclude non-commercial, no-derivatives, and share-alike licenses from automatic reuse.
        if not identifier or not (
            "creativecommons.org/publicdomain/zero/" in license_url
            or ("creativecommons.org/licenses/by/" in license_url and not any(x in license_url for x in ("/by-nc", "/by-nd", "/by-sa")))
        ):
            continue
        try:
            meta_response = requests.get(
                f"https://archive.org/metadata/{quote(identifier, safe='')}",
                headers=HEADERS,
                timeout=25,
            )
            meta_response.raise_for_status()
            files = meta_response.json().get("files", [])
            candidates = []
            for item in files:
                name = str(item.get("name") or "")
                ext = Path(name).suffix.lower()
                size = int(item.get("size") or 0)
                if ext not in {".mp3", ".wav", ".ogg", ".flac", ".m4a"}:
                    continue
                if size and (size < 20_000 or size > 60_000_000):
                    continue
                if item.get("source") == "original" or ext == ".mp3":
                    candidates.append((0 if ext == ".mp3" else 1, size or 10**12, name))
            if not candidates:
                continue
            candidates.sort()
            filename = candidates[0][2]
            url = f"https://archive.org/download/{quote(identifier, safe='')}/{quote(filename, safe='/')}"
            source = out.with_suffix(".source")
            with requests.get(url, headers=HEADERS, stream=True, timeout=60) as download:
                download.raise_for_status()
                content_type = download.headers.get("content-type", "").lower()
                if "text/html" in content_type:
                    continue
                with source.open("wb") as handle:
                    for chunk in download.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            handle.write(chunk)
            if source.stat().st_size < 20_000:
                source.unlink(missing_ok=True)
                continue
            _prepare_audio(source, out, duration)
            _write_source(out, {
                "provider": "Internet Archive",
                "title": str(doc.get("title") or identifier),
                "creator": str(doc.get("creator") or "Creator not listed"),
                "license": license_url,
                "source_url": f"https://archive.org/details/{identifier}",
                "license_policy": "Only metadata-labelled CC0/public domain or CC BY tracks are auto-selected.",
            })
            source.unlink(missing_ok=True)
            print(f"[music] soundtrack sourced from Internet Archive: {doc.get('title') or identifier}", flush=True)
            return out
        except Exception as exc:
            print(f"[music] skipped Archive item {identifier}: {exc}", flush=True)
            try:
                out.with_suffix(".source").unlink(missing_ok=True)
            except OSError:
                pass
    return None


def _procedural_bed(out: Path, duration: float) -> Path:
    """Create a quiet, original ambient pad when no reusable track is available."""
    duration = max(1.0, float(duration))
    # Soft, low-level chord tones; no external recording or unlicensed track is used.
    inputs = [
        f"sine=frequency={frequency}:sample_rate=44100:duration={duration:.3f}"
        for frequency in (110, 164.81, 220)
    ]
    command = ["ffmpeg", "-y"]
    for source in inputs:
        command += ["-f", "lavfi", "-i", source]
    command += [
        "-filter_complex",
        "[0:a]volume=0.018[a0];[1:a]volume=0.012[a1];[2:a]volume=0.008[a2];"
        "[a0][a1][a2]amix=inputs=3:normalize=0,lowpass=f=900,afade=t=in:st=0:d=3,"
        "afade=t=out:st=" + f"{max(0, duration - 4):.3f}" + ":d=4[out]",
        "-map", "[out]", "-t", f"{duration:.3f}", "-c:a", "aac", "-b:a", "128k", str(out),
    ]
    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as exc:
        details = exc.stderr.decode("utf-8", errors="replace")[-1200:] if exc.stderr else str(exc)
        raise RuntimeError(f"Could not create fallback ambient bed: {details}") from exc
    _write_source(out, {
        "provider": "Generated locally with FFmpeg",
        "title": "Original procedural ambient pad",
        "creator": "Generated by Jack Pockets video pipeline",
        "license": "Original procedural audio; no external recording used",
        "source_url": None,
    })
    print("[music] no suitable licensed track found; generated an original quiet ambient bed", flush=True)
    return out


def get_music(query: str, out: Path, duration: float | None = None) -> Path | None:
    """Use a user-authorized direct URL, openly licensed Archive music, then original generated ambience."""
    out.parent.mkdir(parents=True, exist_ok=True)
    url = os.getenv("MUSIC_URL", "").strip()
    if url:
        source = out.with_suffix(".source")
        try:
            with requests.get(url, stream=True, timeout=60) as response:
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").lower()
                if "text/html" in content_type:
                    raise RuntimeError("MUSIC_URL returned a web page, not a direct audio file")
                with source.open("wb") as handle:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            handle.write(chunk)
            if source.stat().st_size < 2048:
                raise RuntimeError("MUSIC_URL returned an empty or invalid audio file")
            _prepare_audio(source, out, duration)
            _write_source(out, {
                "provider": "User-supplied MUSIC_URL",
                "title": "User-supplied soundtrack",
                "creator": "Not identified by pipeline",
                "license": "User must verify authorization and licence for this URL",
                "source_url": url,
            })
            print("[music] soundtrack prepared from MUSIC_URL", flush=True)
            return out
        finally:
            source.unlink(missing_ok=True)

    archive_path = _archive_music(query, out, duration)
    if archive_path:
        return archive_path
    if duration and duration > 0:
        return _procedural_bed(out, duration)
    return None
