from __future__ import annotations

import re
from typing import Any


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


def evaluate_validity(generated_outputs: list[dict[str, Any]], retrieved_docs: list[dict[str, Any]]) -> dict[str, Any]:
    """Grounding rate = supported claims / all claims.

    A claim is considered grounded when its content overlaps with at least one retrieved document.
    This is intentionally simple and transparent, making it easy to explain in a report and swap for an
    NLI model later.
    """
    total_claims = 0
    supported_claims = 0
    details = []

    for output in generated_outputs:
        for claim, support_ids in _extract_claims(output):
            total_claims += 1
            matched = False
            for doc in retrieved_docs:
                source_text = f"{doc.get('title', '')} {doc.get('abstract', '')}"
                if _keyword_overlap(claim, source_text):
                    matched = True
                    break
            if matched:
                supported_claims += 1
            details.append({"claim": claim, "supported": matched, "supporting_paper_ids": support_ids})

    grounding_rate = (supported_claims / total_claims) if total_claims else 0.0
    return {
        "grounding_rate": grounding_rate,
        "supported_claims": supported_claims,
        "total_claims": total_claims,
        "details": details,
    }
