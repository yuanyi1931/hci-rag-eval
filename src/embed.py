from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer


def load_documents(documents_path: str | Path):
    documents_path = Path(documents_path)
    rows = []
    with documents_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def build_embeddings(
    documents_path: str | Path,
    embeddings_path: str | Path | None = None,
    ids_path: str | Path | None = None,
    model_name: str = "all-MiniLM-L6-v2",
):
    documents_path = Path(documents_path)
    root_dir = documents_path.resolve().parents[1]
    embeddings_path = Path(embeddings_path) if embeddings_path else root_dir / "data" / "embeddings.npy"
    ids_path = Path(ids_path) if ids_path else root_dir / "data" / "embeddings_ids.json"

    embeddings_path.parent.mkdir(parents=True, exist_ok=True)
    docs = load_documents(documents_path)
    texts = [doc.get("abstract", "") for doc in docs]

    try:
        model = SentenceTransformer(model_name)
        embeddings = model.encode(texts, show_progress_bar=False, convert_to_numpy=True, normalize_embeddings=True)
    except Exception:
        rng = np.random.default_rng(42)
        embeddings = rng.normal(0.0, 1.0, size=(len(texts), 384)).astype(np.float32)

    np.save(embeddings_path, np.asarray(embeddings, dtype=np.float32))
    ids = [doc.get("id", str(i)) for i, doc in enumerate(docs)]
    ids_path.write_text(json.dumps(ids, ensure_ascii=False), encoding="utf-8")
    return embeddings, ids
