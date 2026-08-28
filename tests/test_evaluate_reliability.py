from __future__ import annotations

import json

import pytest

from src.evaluate_reliability import evaluate_confidence_icc, evaluate_reliability, evaluate_reliability_from_jsonl


def _make_record(query_id: str, run_index: int, claim: str, confidence: float, paper_ids: list[str] | None = None):
    if paper_ids is None:
        paper_ids = ["paper-1", "paper-2"]
    return {
        "query_id": query_id,
        "run_index": run_index,
        "parsed_json": {
            "insights": [
                {
                    "claim": claim,
                    "supporting_paper_ids": paper_ids,
                    "reasoning": "This is a consistent explanation supported by the papers.",
                }
            ],
            "overall_confidence": confidence,
        },
    }


def test_evaluate_reliability_normal_case():
    records = [
        _make_record("q1", 0, "The interface reduced task friction for expert users.", 0.82, ["paper-1", "paper-2"]),
        _make_record("q1", 1, "The interface reduced task friction for expert users.", 0.88, ["paper-1", "paper-2"]),
        _make_record("q1", 2, "The interface reduced task friction for expert users.", 0.90, ["paper-1", "paper-2"]),
    ]

    result = evaluate_reliability(records)

    assert result["n_valid_runs"] == 3
    assert result["semantic_consistency"] == pytest.approx(1.0, abs=1e-6)
    assert result["claim_jaccard"] == pytest.approx(1.0, abs=1e-6)
    assert result["confidence_sd"] > 0.0
    assert result["confidence_cv"] > 0.0
    assert result["krippendorff_alpha"] is not None


def test_evaluate_reliability_confidence_sd_varies_with_values():
    records = [
        _make_record("q1", 0, "Claim A", 0.20, ["paper-1"]),
        _make_record("q1", 1, "Claim A", 0.40, ["paper-1"]),
        _make_record("q1", 2, "Claim A", 0.60, ["paper-1"]),
    ]

    result = evaluate_reliability(records)

    assert result["confidence_sd"] is not None
    assert result["confidence_sd"] > 0.0
    assert result["confidence_cv"] is not None
    assert result["confidence_cv"] > 0.0


def test_evaluate_reliability_single_run_returns_none_metrics():
    records = [_make_record("q2", 0, "A single run has no inter-rater agreement signal.", 0.75)]

    result = evaluate_reliability(records)

    assert result["n_valid_runs"] == 1
    assert result["semantic_consistency"] is None
    assert result["claim_jaccard"] is None
    assert result["confidence_sd"] is None
    assert result["confidence_cv"] is None
    assert result["krippendorff_alpha"] is None
    assert "Need at least 2 valid runs" in result["reason"]


def test_evaluate_reliability_ignores_parse_failure_and_reads_jsonl(tmp_path):
    path = tmp_path / "generations.jsonl"
    payload = [
        _make_record("q3", 0, "The system improved shared awareness.", 0.71, ["paper-1"]),
        {"query_id": "q3", "run_index": 1, "parsed_json": "parse_failure"},
        _make_record("q3", 2, "The system improved shared awareness.", 0.72, ["paper-1"]),
    ]
    with path.open("w", encoding="utf-8") as fh:
        for row in payload:
            fh.write(json.dumps(row) + "\n")

    result = evaluate_reliability_from_jsonl(path)

    assert result["n_valid_runs"] == 2
    assert result["n_parse_failures"] == 1
    assert result["semantic_consistency"] == pytest.approx(1.0, abs=1e-6)
    assert result["claim_jaccard"] == pytest.approx(1.0, abs=1e-6)
    assert result["confidence_sd"] > 0.0


def test_evaluate_reliability_constant_confidence_has_zero_variation():
    records = [
        _make_record("q4", 0, "Learning support improved reflection.", 0.7, ["paper-1"]),
        _make_record("q4", 1, "Learning support improved reflection.", 0.7, ["paper-1"]),
        _make_record("q4", 2, "Learning support improved reflection.", 0.7, ["paper-1"]),
    ]

    result = evaluate_reliability(records)

    assert result["confidence_sd"] == pytest.approx(0.0, abs=1e-12)
    assert result["confidence_cv"] == pytest.approx(0.0, abs=1e-12)
    assert result["semantic_consistency"] == pytest.approx(1.0, abs=1e-6)
    assert result["claim_jaccard"] == pytest.approx(1.0, abs=1e-6)


def test_evaluate_reliability_empty_insights_is_handled():
    records = [
        {"query_id": "q5", "run_index": 0, "parsed_json": {"insights": [], "overall_confidence": 0.8}},
        {"query_id": "q5", "run_index": 1, "parsed_json": {"insights": [], "overall_confidence": 0.9}},
    ]

    result = evaluate_reliability(records)

    assert result["n_valid_runs"] == 2
    assert result["semantic_consistency"] is None
    assert result["claim_jaccard"] is None
    assert result["confidence_sd"] > 0.0
    assert result["confidence_cv"] > 0.0
    assert result["krippendorff_alpha"] is None


def test_evaluate_confidence_icc_uses_query_by_run_matrix():
    records = [
        {"query_id": "q1", "run_index": 0, "parsed_json": {"overall_confidence": 0.6}},
        {"query_id": "q1", "run_index": 1, "parsed_json": {"overall_confidence": 0.7}},
        {"query_id": "q2", "run_index": 0, "parsed_json": {"overall_confidence": 0.8}},
        {"query_id": "q2", "run_index": 1, "parsed_json": {"overall_confidence": 0.9}},
    ]

    result = evaluate_confidence_icc(records)

    assert result is not None
    assert result >= -1.0
    assert result <= 1.0


def test_evaluate_confidence_icc_skips_incomplete_rows():
    records = [
        {"query_id": "q1", "run_index": 0, "parsed_json": {"overall_confidence": 0.6}},
        {"query_id": "q1", "run_index": 1, "parsed_json": {"overall_confidence": 0.7}},
        {"query_id": "q2", "run_index": 0, "parsed_json": {"overall_confidence": 0.8}},
    ]

    result = evaluate_confidence_icc(records)

    assert result is None


def test_evaluate_reliability_single_paper_citation_returns_none():
    records = [
        _make_record("q6", 0, "Single-paper evidence persists across reruns.", 0.7, ["paper-1"]),
        _make_record("q6", 1, "Single-paper evidence persists across reruns.", 0.8, ["paper-1"]),
    ]

    result = evaluate_reliability(records)

    assert result["krippendorff_alpha"] is None
    assert "Citation agreement is undefined" in result["reason"]
