from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from statistics import mean, median
from typing import Any

import pandas as pd

from src.config import load_config
from src.llm_client import call_model


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
            raise ValueError(f"Actionability input at index {idx} is not a record dict: got {type(output).__name__}.")
        if "parsed_json" not in output:
            raise ValueError(
                "Actionability input is using the legacy parsed-dict format; expected a record wrapper with 'parsed_json'. "
                f"Received keys: {sorted(output.keys())}."
            )
        payload = output.get("parsed_json")
        if not isinstance(payload, dict):
            parse_failures += 1
            continue
        normalized.append(payload)
    return normalized, parse_failures


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


_SCORE_LABEL_PATTERN = re.compile(r"(?:score|rating|answer)\s*(?:is|:|=)?\s*([1-5])\b")
# Matches a rubric range being echoed back (e.g. "1 to 5", "1-5", "1\u20135") so it is not
# mistaken for the intended rating.
_RANGE_PATTERN = re.compile(r"\b[1-5]\s*(?:-|\u2013|\u2014|to)\s*[1-5]\b")
# A digit 1-5 not adjacent to another digit (excludes multi-digit numbers like "10").
_STANDALONE_DIGIT_PATTERN = re.compile(r"(?<!\d)([1-5])(?!\d)")


def _parse_actionability_response(content: str) -> int | str:
    """Extract the intended 1-5 rating from a raw judge response, or "unparseable".

    Preference order: an explicit "score"/"rating"/"answer" label wins outright. Otherwise,
    any rubric-range mention (e.g. "on a scale of 1 to 5") is stripped before searching for a
    standalone digit, so the scale description itself is never mistaken for the answer. If no
    standalone digit remains, or more than one distinct standalone digit remains, the response
    is ambiguous and reported as "unparseable" rather than guessed.
    """
    text = str(content).strip().lower()
    if not text:
        return "unparseable"
    label_match = _SCORE_LABEL_PATTERN.search(text)
    if label_match:
        return int(label_match.group(1))
    cleaned = _RANGE_PATTERN.sub(" ", text)
    digits = _STANDALONE_DIGIT_PATTERN.findall(cleaned)
    distinct = set(digits)
    if len(distinct) == 1:
        return int(distinct.pop())
    return "unparseable"


def _normalize_actionability_vote(value: Any) -> int | str:
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
        return _parse_actionability_response(text)
    return max(1, min(5, score))


def _majority_score(votes: list[int | str]) -> tuple[int | str, float]:
    if not votes:
        return 1, 0.0
    counts = Counter(votes)
    # str() tie-break avoids comparing int and str vote labels (e.g. "unparseable") directly.
    majority_value, majority_count = max(counts.items(), key=lambda item: (item[1], str(item[0])))
    return majority_value, majority_count / len(votes)


def _llm_actionability_vote(text: str, vote_index: int) -> int | str:
    config = load_config()
    evaluation_cfg = config.get("evaluation", {}) if isinstance(config, dict) else {}
    model_name = str(evaluation_cfg.get("judge_model", "claude-sonnet-4-6"))
    temperature = float(evaluation_cfg.get("judge_temperature", 0.0))
    prompt = (
        "Score the following insight text on actionability for a research or product decision.\n"
        "Return exactly one integer from 1 to 5, where:\n"
        "1 = purely descriptive; 2 = vague direction; 3 = identifiable direction; 4 = actionable decision; 5 = very operational with clear next steps.\n\n"
        f"Insight text:\n{text[:4000]}\n\nInteger score:"
    )
    deterministic_seed = abs(sum((idx + 1) * ord(ch) for idx, ch in enumerate(f"{text[:128]}|vote={vote_index}"))) % 1_000_000_000
    response = call_model(
        model=model_name,
        prompt=prompt,
        temperature=temperature,
        run_index=deterministic_seed,
        max_tokens=32,
        stage="actionability",
    )
    content = response.get("content", "") if isinstance(response, dict) else str(response)
    return _parse_actionability_response(content)


def _judge_actionability_item(
    text: str,
    judge_fn: Any | None = None,
    n_votes: int | None = None,
) -> dict[str, Any]:
    vote_count = _get_judge_n_votes() if n_votes is None else max(1, int(n_votes))
    votes: list[int | str] = []
    if judge_fn is None:
        for vote_index in range(vote_count):
            votes.append(_llm_actionability_vote(text, vote_index=vote_index))
    else:
        for _ in range(vote_count):
            vote = judge_fn(text=text)
            votes.append(_normalize_actionability_vote(vote))

    numeric_votes = [vote for vote in votes if isinstance(vote, int)]
    majority_value, judge_consistency = _majority_score(votes)
    # "unparseable" votes are treated as missing for the final score: the median is taken
    # over numeric votes only. If every vote was unparseable, fall back to the rubric's
    # neutral midpoint (3) rather than raising, but this is recorded via n_unparseable so
    # it remains visible to callers rather than silently indistinguishable from a real "3".
    final_score = int(median(numeric_votes)) if numeric_votes else 3
    return {
        "votes": votes,
        "final_score": final_score,
        "majority_score": majority_value,
        "judge_consistency": judge_consistency,
        "n_votes": len(votes),
        "n_unparseable": len(votes) - len(numeric_votes),
    }


def evaluate_actionability(
    generated_outputs: list[dict[str, Any]],
    judge_fn: Any | None = None,
) -> dict[str, Any]:
    if generated_outputs and isinstance(generated_outputs[0], dict):
        print(f"evaluate_actionability first_input_keys={sorted(generated_outputs[0].keys())}")

    records, parse_failures = _normalize_generated_records(generated_outputs)

    scores = []
    raw_votes: list[list[int | str]] = []
    judge_consistency_values: list[float] = []
    n_unparseable_votes = 0
    n_items_no_valid_vote = 0

    for output in records:
        for text in _extract_insight_texts(output):
            judge_result = _judge_actionability_item(text, judge_fn=judge_fn)
            raw_votes.append(judge_result["votes"])
            judge_consistency_values.append(judge_result["judge_consistency"])
            scores.append(judge_result["final_score"])
            n_unparseable_votes += judge_result["n_unparseable"]
            if judge_result["n_unparseable"] == judge_result["n_votes"]:
                n_items_no_valid_vote += 1

    return {
        "scores": scores,
        "mean_score": float(mean(scores)) if scores else 0.0,
        "raw_votes": raw_votes,
        "judge_consistency_mean": float(mean(judge_consistency_values)) if judge_consistency_values else 0.0,
        "judge_consistency_values": judge_consistency_values,
        "n_parse_failures": parse_failures,
        "n_unparseable_votes": n_unparseable_votes,
        "n_items_no_valid_vote": n_items_no_valid_vote,
    }


def prepare_manual_rating_template(output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(
        columns=["query_id", "generation_run", "insight_text", "manual_rating", "rationale"]
    )
    df.to_csv(path, index=False)
    return path
