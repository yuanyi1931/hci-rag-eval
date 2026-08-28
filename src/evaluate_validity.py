from __future__ import annotations

import re
from collections import Counter
from typing import Any

from src.config import load_config


def split_claims(text: str) -> list[str]:
    if not text:
        return []
    clauses = re.split(r"(?<=[.!?])\s+", text)
    claims = [c.strip() for c in clauses if c.strip()]
    return claims or [text.strip()]


def _extract_claims(output: dict[str, Any]) -> list[tuple[str, list[str]]]:
    insights = output.get("insights")
    if isinstance(insights, list):
        rows: list[tuple[str, list[str]]] = []
        for insight in insights:
            if not isinstance(insight, dict):
                continue
            claim = str(insight.get("claim") or "").strip()
            support_ids = insight.get("supporting_paper_ids") or []
            if claim:
                rows.append((claim, support_ids if isinstance(support_ids, list) else [str(support_ids)]))
        if rows:
            return rows

    trend = output.get("trend")
    if isinstance(trend, str) and trend.strip():
        return [(claim, []) for claim in split_claims(trend)]
    return []


def _keyword_overlap(claim: str, source_text: str) -> bool:
    claim_tokens = set(re.findall(r"[a-zA-Z]+", claim.lower()))
    source_tokens = set(re.findall(r"[a-zA-Z]+", source_text.lower()))
    if not claim_tokens:
        return False
    overlap = claim_tokens & source_tokens
    return len(overlap) >= 1


def _get_judge_n_votes() -> int:
    config = load_config()
    evaluation_cfg = config.get("evaluation", {}) if isinstance(config, dict) else {}
    value = evaluation_cfg.get("judge_n_votes", 3)
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return 3


def _normalize_validity_vote(value: Any) -> str:
    normalized = str(value).strip().lower().replace("-", "_")
    aliases = {
        "supported": "entailed",
        "support": "entailed",
        "entailed": "entailed",
        "true": "entailed",
        "not_supported": "not_entailed",
        "unsupported": "not_entailed",
        "not_entailed": "not_entailed",
        "false": "not_entailed",
        "contradicted": "contradicted",
        "contradiction": "contradicted",
        "refuted": "contradicted",
    }
    return aliases.get(normalized, normalized)


def _majority_vote(votes: list[str]) -> tuple[str, float]:
    if not votes:
        return "not_entailed", 0.0
    counts = Counter(votes)
    majority_label, majority_count = max(counts.items(), key=lambda item: (item[1], item[0]))
    return majority_label, majority_count / len(votes)


def _judge_validity_claim(
    claim: str,
    source_text: str,
    judge_fn: Any | None = None,
    n_votes: int | None = None,
) -> dict[str, Any]:
    vote_count = _get_judge_n_votes() if n_votes is None else max(1, int(n_votes))
    votes: list[str] = []
    if judge_fn is None:
        for _ in range(vote_count):
            vote = "entailed" if _keyword_overlap(claim, source_text) else "not_entailed"
            votes.append(_normalize_validity_vote(vote))
    else:
        for _ in range(vote_count):
            raw_vote = judge_fn(claim=claim, source_text=source_text)
            votes.append(_normalize_validity_vote(raw_vote))

    majority_label, judge_consistency = _majority_vote(votes)
    return {
        "votes": votes,
        "majority_vote": majority_label,
        "judge_consistency": judge_consistency,
        "n_votes": len(votes),
    }


def evaluate_validity(
    generated_outputs: list[dict[str, Any]],
    retrieved_docs: list[dict[str, Any]],
    judge_fn: Any | None = None,
) -> dict[str, Any]:
    """Grounding rate = supported claims / all claims.

    A claim is considered grounded when the judge majority labels it as entailed. Each judge vote is
    preserved in the returned details so the project can report the judge's own consistency alongside
    the final majority decision.
    """
    total_claims = 0
    supported_claims = 0
    details = []
    consistency_values: list[float] = []

    for output in generated_outputs:
        for claim, support_ids in _extract_claims(output):
            total_claims += 1
            support_docs = []
            for doc in retrieved_docs:
                doc_id = str(doc.get("id") or doc.get("paper_id") or "")
                if support_ids and doc_id not in support_ids:
                    continue
                support_docs.append(doc)
            if not support_docs and support_ids:
                support_docs = retrieved_docs
            source_text = " ".join(
                f"{doc.get('title', '')} {doc.get('abstract', '')}" for doc in support_docs
            )
            if not source_text:
                source_text = " ".join(f"{doc.get('title', '')} {doc.get('abstract', '')}" for doc in retrieved_docs)

            judge_result = _judge_validity_claim(claim, source_text, judge_fn=judge_fn)
            supported = judge_result["majority_vote"] == "entailed"
            if supported:
                supported_claims += 1
            consistency_values.append(judge_result["judge_consistency"])
            details.append(
                {
                    "claim": claim,
                    "supported": supported,
                    "supporting_paper_ids": support_ids,
                    "votes": judge_result["votes"],
                    "majority_vote": judge_result["majority_vote"],
                    "judge_consistency": judge_result["judge_consistency"],
                }
            )

    grounding_rate = (supported_claims / total_claims) if total_claims else 0.0
    judge_consistency_mean = float(sum(consistency_values) / len(consistency_values)) if consistency_values else 0.0
    return {
        "grounding_rate": grounding_rate,
        "supported_claims": supported_claims,
        "total_claims": total_claims,
        "judge_consistency_mean": judge_consistency_mean,
        "details": details,
    }
