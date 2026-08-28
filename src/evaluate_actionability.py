from __future__ import annotations

import re
from pathlib import Path
from statistics import mean
from typing import Any

import pandas as pd


def heuristic_actionability(text: str) -> int:
    """A simple rubric heuristic: more concrete operational language yields a higher score."""
    cleaned = text.lower()
    score = 1
    evidence_terms = [
        "prototype",
        "measure",
        "compare",
        "design",
        "recommend",
        "deploy",
        "optimize",
        "evaluate",
        "assess",
        "experiment",
        "iterate",
    ]
    for term in evidence_terms:
        if term in cleaned:
            score += 1
    if len(re.findall(r"\b\w+\b", cleaned)) > 40:
        score += 1
    if score > 5:
        score = 5
    return score


def _extract_insight_texts(output: dict[str, Any]) -> list[str]:
    insights = output.get("insights")
    if isinstance(insights, list):
        texts = []
        for insight in insights:
            if not isinstance(insight, dict):
                continue
            claim = str(insight.get("claim") or "").strip()
            reasoning = str(insight.get("reasoning") or "").strip()
            support_ids = insight.get("supporting_paper_ids") or []
            support_block = " ".join(str(item) for item in support_ids)
            if claim or reasoning:
                texts.append(f"{claim} {reasoning} {support_block}".strip())
        if texts:
            return texts

    trend = str(output.get("trend", "")).strip()
    if trend:
        return [trend]
    return []


def evaluate_actionability(generated_outputs: list[dict[str, Any]]) -> dict[str, Any]:
    scores = []
    for output in generated_outputs:
        for text in _extract_insight_texts(output):
            scores.append(heuristic_actionability(text))
    return {"scores": scores, "mean_score": float(mean(scores)) if scores else 0.0}


def prepare_manual_rating_template(output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(
        columns=["query_id", "generation_run", "insight_text", "manual_rating", "rationale"]
    )
    df.to_csv(path, index=False)
    return path
