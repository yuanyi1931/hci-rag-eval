from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from statistics import mean, median
from typing import Any

import pandas as pd

from src.config import load_config


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


def _get_judge_n_votes() -> int:
    config = load_config()
    evaluation_cfg = config.get("evaluation", {}) if isinstance(config, dict) else {}
    value = evaluation_cfg.get("judge_n_votes", 3)
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return 3


def _normalize_actionability_vote(value: Any) -> int:
    try:
        score = int(value)
    except (TypeError, ValueError):
        text = str(value).strip().lower()
        if text.isdigit():
            return int(text)
        if text in {"one", "1"}:
            return 1
        if text in {"two", "2"}:
            return 2
        if text in {"three", "3"}:
            return 3
        if text in {"four", "4"}:
            return 4
        if text in {"five", "5"}:
            return 5
        return 3
    return max(1, min(5, score))


def _majority_score(votes: list[int]) -> tuple[int, float]:
    if not votes:
        return 1, 0.0
    counts = Counter(votes)
    majority_value, majority_count = max(counts.items(), key=lambda item: (item[1], item[0]))
    return majority_value, majority_count / len(votes)


def _judge_actionability_item(
    text: str,
    judge_fn: Any | None = None,
    n_votes: int | None = None,
) -> dict[str, Any]:
    vote_count = _get_judge_n_votes() if n_votes is None else max(1, int(n_votes))
    votes: list[int] = []
    if judge_fn is None:
        for _ in range(vote_count):
            votes.append(heuristic_actionability(text))
    else:
        for _ in range(vote_count):
            vote = judge_fn(text=text)
            votes.append(_normalize_actionability_vote(vote))

    majority_value, judge_consistency = _majority_score(votes)
    final_score = int(median(votes))
    return {
        "votes": votes,
        "final_score": final_score,
        "majority_score": majority_value,
        "judge_consistency": judge_consistency,
        "n_votes": len(votes),
    }


def evaluate_actionability(
    generated_outputs: list[dict[str, Any]],
    judge_fn: Any | None = None,
) -> dict[str, Any]:
    scores = []
    raw_votes: list[list[int]] = []
    judge_consistency_values: list[float] = []

    for output in generated_outputs:
        for text in _extract_insight_texts(output):
            judge_result = _judge_actionability_item(text, judge_fn=judge_fn)
            raw_votes.append(judge_result["votes"])
            judge_consistency_values.append(judge_result["judge_consistency"])
            scores.append(judge_result["final_score"])

    return {
        "scores": scores,
        "mean_score": float(mean(scores)) if scores else 0.0,
        "raw_votes": raw_votes,
        "judge_consistency_mean": float(mean(judge_consistency_values)) if judge_consistency_values else 0.0,
        "judge_consistency_values": judge_consistency_values,
    }


def prepare_manual_rating_template(output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(
        columns=["query_id", "generation_run", "insight_text", "manual_rating", "rationale"]
    )
    df.to_csv(path, index=False)
    return path
