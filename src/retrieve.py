from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer


def cosine_similarity(query_vector: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """Compute cosine similarity between a single query vector and a matrix of document vectors."""
    q = np.asarray(query_vector, dtype=np.float32)
    x = np.asarray(matrix, dtype=np.float32)
    q_norm = np.linalg.norm(q)
    x_norm = np.linalg.norm(x, axis=1)
    denom = q_norm * x_norm
    denom = np.where(denom == 0, 1e-12, denom)
    return (x @ q) / denom


def load_embeddings(embeddings_path: str | Path, ids_path: str | Path):
    embeddings = np.load(embeddings_path)
    ids = json.loads(Path(ids_path).read_text(encoding="utf-8"))
    return np.asarray(embeddings, dtype=np.float32), ids


def build_query_from_text(query: str, model_name: str = "all-MiniLM-L6-v2") -> np.ndarray:
    model = SentenceTransformer(model_name)
    vector = model.encode([query], convert_to_numpy=True, normalize_embeddings=True)[0]
    return np.asarray(vector, dtype=np.float32)


def compute_top_k(query_embedding: np.ndarray, embeddings: np.ndarray, ids: list[str], k: int = 5):
    sims = cosine_similarity(query_embedding, embeddings)
    top_indices = np.argsort(sims)[::-1][:k]
    return [
        {
            "id": ids[int(index)],
            "similarity": float(sims[int(index)]),
            "index": int(index),
        }
        for index in top_indices
    ]
