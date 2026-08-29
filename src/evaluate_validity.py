from __future__ import annotations

import re
from collections import Counter
from statistics import mean
from typing import Any

from src.config import load_config
from src.llm_client import call_model


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


def _normalize_generated_records(generated_outputs: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Validate the record-wrapper contract and separate parse failures from usable payloads.

    A missing 'parsed_json' key is a genuine interface contract violation (e.g. legacy
    parsed-dict input) and raises immediately. A 'parsed_json' value that is present but not
    a dict (typically the 'parse_failure' sentinel written by generate_insights when the model
    output could not be parsed) is a legitimate runtime state, not a contract violation, so it is
    skipped and counted rather than raised.
    """
    normalized: list[dict[str, Any]] = []
    parse_failures = 0
    for idx, output in enumerate(generated_outputs):
        if not isinstance(output, dict):
            raise ValueError(f"Validity input at index {idx} is not a record dict: got {type(output).__name__}.")
        if "parsed_json" not in output:
            raise ValueError(
                "Validity input is using the legacy parsed-dict format; expected a record wrapper with 'parsed_json'. "
                f"Received keys: {sorted(output.keys())}."
            )
        payload = output.get("parsed_json")
        if not isinstance(payload, dict):
            parse_failures += 1
            continue
        normalized.append(payload)
    return normalized, parse_failures


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
    budget_cfg = config.get("budget", {}) if isinstance(config, dict) else {}
    value = evaluation_cfg.get("judge_n_votes", 3)
    try:
        configured_votes = max(1, int(value))
    except (TypeError, ValueError):
        configured_votes = 3

    try:
        max_api_calls = max(1, int(budget_cfg.get("max_api_calls", 100)))
    except (TypeError, ValueError):
        max_api_calls = 100

    if max_api_calls < 100:
        return 1
    return configured_votes


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


def _llm_validity_vote(claim: str, source_text: str, vote_index: int) -> str:
    config = load_config()
    evaluation_cfg = config.get("evaluation", {}) if isinstance(config, dict) else {}
    model_name = str(evaluation_cfg.get("judge_model", "claude-sonnet-4-6"))
    temperature = float(evaluation_cfg.get("judge_temperature", 0.0))
    prompt = (
        "You are evaluating whether a claim is entailed by the source text.\n"
        "Return only one of the exact labels: entailed, not_entailed, or contradicted.\n\n"
        f"Claim: {claim}\n\nSource text:\n{source_text[:4000]}\n\nAnswer:"
    )
    deterministic_seed = abs(sum((idx + 1) * ord(ch) for idx, ch in enumerate(f"{claim[:128]}|{source_text[:128]}|vote={vote_index}"))) % 1_000_000_000
    response = call_model(
        model=model_name,
        prompt=prompt,
        temperature=temperature,
        run_index=deterministic_seed,
        max_tokens=64,
        stage="validity",
    )
    text = response.get("content", "") if isinstance(response, dict) else str(response)
    return _normalize_validity_vote(text.strip().lower().replace("\n", " ").split()[0])


def _judge_validity_claim(
    claim: str,
    source_text: str,
    judge_fn: Any | None = None,
    n_votes: int | None = None,
) -> dict[str, Any]:
    vote_count = _get_judge_n_votes() if n_votes is None else max(1, int(n_votes))
    votes: list[str] = []
    if judge_fn is None:
        for vote_index in range(vote_count):
            vote = _llm_validity_vote(claim, source_text, vote_index=vote_index)
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
    if generated_outputs and isinstance(generated_outputs[0], dict):
        print(f"evaluate_validity first_input_keys={sorted(generated_outputs[0].keys())}")

    records, parse_failures = _normalize_generated_records(generated_outputs)

    total_claims = 0
    supported_claims = 0
    details = []
    consistency_values: list[float] = []
    citation_rates: list[float] = []
    retrieved_ids = {str(doc.get("id") or doc.get("paper_id") or "") for doc in retrieved_docs}

    for output in records:
        for claim, support_ids in _extract_claims(output):
            total_claims += 1
            citation_rate = 1.0
            if support_ids:
                valid_citations = sum(1 for paper_id in support_ids if str(paper_id) in retrieved_ids)
                citation_rate = valid_citations / len(support_ids)
            citation_rates.append(citation_rate)

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
                    "citation_validity_rate": citation_rate,
                    "votes": judge_result["votes"],
                    "majority_vote": judge_result["majority_vote"],
                    "judge_consistency": judge_result["judge_consistency"],
                }
            )

    grounding_rate = (supported_claims / total_claims) if total_claims else 0.0
    judge_consistency_mean = float(sum(consistency_values) / len(consistency_values)) if consistency_values else 0.0
    citation_validity_rate = float(mean(citation_rates)) if citation_rates else 1.0
    return {
        "grounding_rate": grounding_rate,
        "citation_validity_rate": citation_validity_rate,
        "supported_claims": supported_claims,
        "total_claims": total_claims,
        "judge_consistency_mean": judge_consistency_mean,
        "details": details,
        "n_parse_failures": parse_failures,
    }
