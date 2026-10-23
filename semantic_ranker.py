"""Optional local semantic scoring for footage selection.

Enable with JACKPOCKETS_SEMANTIC_RANKING=1. The sentence-transformers dependency
and model are intentionally lazy-loaded so the production path remains lightweight.
"""
from __future__ import annotations

import os
from functools import lru_cache


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer
    name = os.getenv("JACKPOCKETS_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    return SentenceTransformer(name, device=os.getenv("JACKPOCKETS_EMBEDDING_DEVICE", "cpu"))


def score_assets(sentence: str, assets: list[dict]) -> dict[str, float]:
    """Return cosine-like similarities keyed by asset id; raises if optional deps fail."""
    rows = []
    ids = []
    for asset in assets:
        asset_id = str(asset.get("id", ""))
        if not asset_id:
            continue
        metadata = " ".join(str(asset.get(field, "")) for field in ("title", "description", "tags"))
        if not metadata.strip():
            metadata = str(asset.get("filename", asset_id))
        rows.append(metadata[:1200])
        ids.append(asset_id)
    if not rows:
        return {}
    import numpy as np

    model = _model()
    vectors = model.encode([sentence[:1200], *rows], normalize_embeddings=True, convert_to_numpy=True)
    similarities = np.matmul(vectors[1:], vectors[0])
    return {asset_id: float(score) for asset_id, score in zip(ids, similarities)}
