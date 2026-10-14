from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

CACHE_VERSION = 1


def cache_root() -> Path:
    configured = os.getenv("JACKPOCKETS_CACHE_DIR", "").strip()
    root = Path(configured).expanduser() if configured else Path.home() / ".cache" / "jack-pockets"
    root.mkdir(parents=True, exist_ok=True)
    return root


def cache_ttl_seconds() -> int:
    try:
        return max(0, int(os.getenv("JACKPOCKETS_CACHE_TTL_SECONDS", "604800")))
    except ValueError:
        return 604800


def cache_key(namespace: str, payload: Any) -> str:
    canonical = json.dumps(
        {"version": CACHE_VERSION, "namespace": namespace, "payload": payload},
        sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_json_cache(namespace: str, payload: Any, ttl_seconds: int | None = None) -> Any | None:
    if os.getenv("JACKPOCKETS_DISABLE_CACHE", "").lower() in {"1", "true", "yes"}:
        return None
    ttl = cache_ttl_seconds() if ttl_seconds is None else max(0, ttl_seconds)
    if ttl == 0:
        return None
    path = cache_root() / "json" / namespace / (cache_key(namespace, payload) + ".json")
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        created = float(record["created_at"])
        if time.time() - created > ttl:
            return None
        return record["value"]
    except (OSError, ValueError, TypeError, KeyError):
        return None


def save_json_cache(namespace: str, payload: Any, value: Any) -> None:
    if os.getenv("JACKPOCKETS_DISABLE_CACHE", "").lower() in {"1", "true", "yes"}:
        return
    path = cache_root() / "json" / namespace / (cache_key(namespace, payload) + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    try:
        temporary.write_text(
            json.dumps({"created_at": time.time(), "value": value}, ensure_ascii=False),
            encoding="utf-8",
        )
        temporary.replace(path)
    except OSError as exc:
        # Caching is an optimization: a read-only/full cache must never break generation.
        print(f"[cache] unable to save {namespace} cache: {exc}", flush=True)
