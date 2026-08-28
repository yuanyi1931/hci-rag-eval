from __future__ import annotations

import json
from pathlib import Path
import xml.etree.ElementTree as ET

import requests


def fetch_arxiv_abstracts(output_path: str | Path, max_results: int = 100, category: str = "cs.HC") -> bool:
    """Fetch a small set of recent HCI papers from arXiv and save JSONL rows."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    url = "https://export.arxiv.org/api/query"
    params = {"search_query": f"cat:{category}", "start": 0, "max_results": max_results}

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        ns = {"a": "http://www.w3.org/2005/Atom"}

        records = []
        for entry in root.findall("a:entry", ns):
            paper_id = entry.findtext("a:id", default="", namespaces=ns)
            title = entry.findtext("a:title", default="", namespaces=ns).strip().replace("\n", " ")
            abstract = entry.findtext("a:summary", default="", namespaces=ns).strip().replace("\n", " ")
            published = entry.findtext("a:published", default="", namespaces=ns)
            if not paper_id or not title or not abstract:
                continue
            records.append(
                {
                    "id": paper_id.split("/")[-1],
                    "title": title,
                    "abstract": abstract,
                    "published_date": published[:10] if published else None,
                }
            )

        with out.open("w", encoding="utf-8") as fh:
            for row in records:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")

        print(f"Saved {len(records)} abstracts to {out}")
        return len(records) > 0
    except Exception as exc:  # pragma: no cover - network failure path
        sample_path = Path(__file__).resolve().parents[1] / "data" / "raw" / "sample_abstracts.jsonl"
        if sample_path.exists():
            out.write_text(sample_path.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"arXiv fetch failed ({exc}). Falling back to sample dataset: {sample_path}")
            return True
        print(f"arXiv fetch failed and no sample dataset is available: {exc}")
        return False
