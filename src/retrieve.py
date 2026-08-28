from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

_DOC_METADATA_BY_ID: dict[str, dict[str, str]] = {}


def _load_document_metadata(raw_path: str | Path | None) -> dict[str, dict[str, str]]:
    if raw_path is None:
        return {}
    path = Path(raw_path)
    if not path.exists():
        return {}

    mapping: dict[str, dict[str, str]] = {}
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            doc_id = str(row.get("id") or "").strip()
            if not doc_id:
                continue
            title = str(row.get("title") or "").strip()
            abstract = str(row.get("abstract") or "").strip()
            mapping[doc_id] = {"title": title, "abstract": abstract}
    return mapping


def cosine_similarity(query_vector: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """Compute cosine similarity between a single query vector and a matrix of document vectors."""
    q = np.asarray(query_vector, dtype=np.float32)
    x = np.asarray(matrix, dtype=np.float32)
    q_norm = np.linalg.norm(q)
    x_norm = np.linalg.norm(x, axis=1)
    denom = q_norm * x_norm
    denom = np.where(denom == 0, 1e-12, denom)
    return (x @ q) / denom


def load_embeddings(embeddings_path: str | Path, ids_path: str | Path, raw_path: str | Path | None = None):
    embeddings = np.load(embeddings_path)
    ids = json.loads(Path(ids_path).read_text(encoding="utf-8"))
    global _DOC_METADATA_BY_ID
    _DOC_METADATA_BY_ID = _load_document_metadata(raw_path)
    return np.asarray(embeddings, dtype=np.float32), ids


def build_query_from_text(query: str, model_name: str = "all-MiniLM-L6-v2") -> np.ndarray:
    model = SentenceTransformer(model_name)
    vector = model.encode([query], convert_to_numpy=True, normalize_embeddings=True)[0]
    return np.asarray(vector, dtype=np.float32)


def compute_top_k(query_embedding: np.ndarray, embeddings: np.ndarray, ids: list[str], k: int = 5):
    sims = cosine_similarity(query_embedding, embeddings)
    top_indices = np.argsort(sims)[::-1][:k]
    results = []
    for index in top_indices:
        doc_id = ids[int(index)]
        metadata = _DOC_METADATA_BY_ID.get(str(doc_id), {})
        title = metadata.get("title")
        abstract = metadata.get("abstract")
        if title is None or abstract is None:
            raise KeyError(
                f"Missing title/abstract metadata for retrieved document '{doc_id}'. "
                "Load embeddings with the raw abstracts file or provide metadata for every document."
            )
        results.append(
            {
                "id": doc_id,
                "similarity": float(sims[int(index)]),
                "index": int(index),
                "title": str(title),
                "abstract": str(abstract),
            }
        )
    return results
