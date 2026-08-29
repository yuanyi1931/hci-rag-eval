import json
import pytest

import src.generate as generate_module
from src.generate import generate_insights


def fake_call_model(**kwargs):
    # produce a simple valid JSON content string
    payload = {"insights": [{"claim": "A", "supporting_paper_ids": [], "reasoning": "r"}], "overall_confidence": 0.5}
    return {"content": json.dumps(payload), "usage": {"input_tokens": 1, "output_tokens": 1}}


def test_generate_insights_returns_record_contract(monkeypatch, tmp_path):
    monkeypatch.setattr('src.generate.call_model', fake_call_model)
    monkeypatch.setattr(generate_module, "OUTPUT_PATH", tmp_path / "generations.jsonl")
    docs = [
        {"id": "p1", "title": "T1", "abstract": "A1"},
        {"id": "p2", "title": "T2", "abstract": "A2"},
    ]
    results = generate_insights(docs, reruns=2, temperature=0.0, model_name='test-model', query_id=1)
    assert isinstance(results, list)
    assert len(results) == 2
    for rec in results:
        assert isinstance(rec, dict)
        assert 'query_id' in rec
        assert 'run_index' in rec
        assert 'parsed_json' in rec
        assert 'token_usage' in rec
        assert isinstance(rec['parsed_json'], dict)
        assert rec['query_id'] == 1
    assert (tmp_path / "generations.jsonl").exists()


def test_generate_insights_keeps_parse_failure_instead_of_crashing(monkeypatch, tmp_path):
    def fake_bad_call_model(**kwargs):
        return {"content": '{"insights": [{"claim": "A", "supporting_paper_ids": [], "reasoning": "r"}, "overall_confidence": 0.5}', "usage": {"input_tokens": 1, "output_tokens": 1}}

    monkeypatch.setattr('src.generate.call_model', fake_bad_call_model)
    monkeypatch.setattr(generate_module, "OUTPUT_PATH", tmp_path / "generations.jsonl")
    docs = [
        {"id": "p1", "title": "T1", "abstract": "A1"},
        {"id": "p2", "title": "T2", "abstract": "A2"},
    ]
    results = generate_insights(docs, reruns=1, temperature=0.0, model_name='test-model', query_id=99)
    assert len(results) == 1
    assert results[0]["parsed_json"] == "parse_failure"
    assert "claim" in results[0]["raw_response"]
    assert (tmp_path / "generations.jsonl").exists()
