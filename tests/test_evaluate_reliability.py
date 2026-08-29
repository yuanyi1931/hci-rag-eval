from __future__ import annotations

import json

import pytest

from src.evaluate_actionability import evaluate_actionability
from src.evaluate_reliability import evaluate_confidence_icc, evaluate_reliability, evaluate_reliability_from_jsonl
from src.evaluate_validity import evaluate_validity
from src.generate import _build_prompt


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


def test_build_prompt_includes_document_abstract_text():
    docs = [
        {
            "id": "paper-1",
            "title": "Paper title",
            "abstract": "This abstract text must be present in the actual prompt.",
        },
        {
            "id": "paper-2",
            "title": "Another paper",
            "abstract": "Second abstract text should also be visible.",
        },
    ]

    prompt = _build_prompt(docs)

    assert "This abstract text must be present in the actual prompt." in prompt
    assert "Second abstract text should also be visible." in prompt


def test_build_prompt_rejects_missing_or_empty_abstract():
    docs = [{"id": "paper-1", "title": "Paper title", "abstract": ""}]

    with pytest.raises(ValueError, match="abstract"):
        _build_prompt(docs)

    with pytest.raises((KeyError, ValueError), match="abstract"):
        _build_prompt([{"id": "paper-2", "title": "Missing abstract doc"}])


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


def test_validity_records_three_votes_and_self_consistency():
    generated_outputs = [{
        "query_id": "q-validity-1",
        "run_index": 0,
        "parsed_json": {
            "insights": [{
                "claim": "The interface reduces friction for expert users.",
                "supporting_paper_ids": ["p1"],
                "reasoning": "Strong evidence.",
            }]
        },
    }]
    retrieved_docs = [{"id": "p1", "title": "Prototype study", "abstract": "Users reported less friction."}]
    seen_claims = []

    def fake_judge(*, claim, source_text):
        seen_claims.append(claim)
        return "entailed" if "friction" in claim.lower() else "not_entailed"

    result = evaluate_validity(generated_outputs, retrieved_docs, judge_fn=fake_judge)

    assert seen_claims == ["The interface reduces friction for expert users."] * 3
    assert result["details"][0]["votes"] == ["entailed", "entailed", "entailed"]
    assert result["details"][0]["judge_consistency"] == pytest.approx(1.0)


def test_actionability_records_three_votes_and_self_consistency():
    generated_outputs = [{
        "query_id": "q-actionability-1",
        "run_index": 0,
        "parsed_json": {
            "insights": [{
                "claim": "We should test a new interface.",
                "supporting_paper_ids": ["p1"],
                "reasoning": "This leads to an actionable recommendation.",
            }]
        },
    }]
    seen_texts = []

    def fake_judge(*, text):
        seen_texts.append(text)
        if "test" in text.lower():
            return 4
        if "recommendation" in text.lower():
            return 3
        return 4

    result = evaluate_actionability(generated_outputs, judge_fn=fake_judge)

    assert len(seen_texts) == 3
    assert all("We should test a new interface." in text for text in seen_texts)
    assert result["raw_votes"][0] == [4, 4, 4]
    assert result["judge_consistency_values"][0] == pytest.approx(1.0)


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


def test_evaluate_validity_rejects_legacy_parsed_dict_input():
    generated_outputs = [{
        "insights": [{
            "claim": "The interface reduces friction for expert users.",
            "supporting_paper_ids": ["p1"],
            "reasoning": "Strong evidence.",
        }]
    }]
    retrieved_docs = [{"id": "p1", "title": "Prototype study", "abstract": "Users reported less friction."}]

    with pytest.raises(ValueError, match="parsed_json"):
        evaluate_validity(generated_outputs, retrieved_docs)


def test_evaluate_actionability_rejects_legacy_parsed_dict_input():
    generated_outputs = [{
        "insights": [{
            "claim": "We should test a new interface.",
            "supporting_paper_ids": ["p1"],
            "reasoning": "This leads to an actionable recommendation.",
        }]
    }]

    with pytest.raises(ValueError, match="parsed_json"):
        evaluate_actionability(generated_outputs)


def test_evaluate_validity_skips_parse_failure_records_without_raising():
    generated_outputs = [
        {
            "query_id": "q8",
            "run_index": 0,
            "parsed_json": {
                "insights": [{
                    "claim": "The interface reduces friction for expert users.",
                    "supporting_paper_ids": ["p1"],
                    "reasoning": "Strong evidence.",
                }]
            },
        },
        {"query_id": "q8", "run_index": 1, "parsed_json": "parse_failure"},
    ]
    retrieved_docs = [{"id": "p1", "title": "Prototype study", "abstract": "Users reported less friction."}]

    def fake_judge(*, claim, source_text):
        return "entailed"

    result = evaluate_validity(generated_outputs, retrieved_docs, judge_fn=fake_judge)

    assert result["total_claims"] == 1
    assert result["n_parse_failures"] == 1


def test_evaluate_actionability_skips_parse_failure_records_without_raising():
    generated_outputs = [
        {
            "query_id": "q9",
            "run_index": 0,
            "parsed_json": {
                "insights": [{
                    "claim": "We should test a new interface.",
                    "supporting_paper_ids": ["p1"],
                    "reasoning": "This leads to an actionable recommendation.",
                }]
            },
        },
        {"query_id": "q9", "run_index": 1, "parsed_json": "parse_failure"},
    ]

    def fake_judge(*, text):
        return 4

    result = evaluate_actionability(generated_outputs, judge_fn=fake_judge)

    assert result["scores"] == [4]
    assert result["n_parse_failures"] == 1


def test_evaluate_actionability_accepts_record_wrapper_format():
    generated_outputs = [{
        "query_id": "q7",
        "run_index": 0,
        "parsed_json": {
            "insights": [{
                "claim": "We should test a new interface.",
                "supporting_paper_ids": ["p1"],
                "reasoning": "This leads to an actionable recommendation.",
            }]
        },
    }]

    def fake_judge(*, text):
        if "test" in text.lower():
            return 4
        return 4

    result = evaluate_actionability(generated_outputs, judge_fn=fake_judge)

    assert result["scores"] == [4]
    assert result["mean_score"] == pytest.approx(4.0)
