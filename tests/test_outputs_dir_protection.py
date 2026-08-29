from __future__ import annotations

import json
from pathlib import Path

import src.generate as generate_module
from src.generate import generate_insights

REAL_OUTPUTS_DIR = Path(__file__).resolve().parents[1] / "outputs"


def _snapshot(dir_path: Path) -> dict[str, tuple[int, int]]:
    if not dir_path.exists():
        return {}
    return {
        str(path.relative_to(dir_path)): (path.stat().st_mtime_ns, path.stat().st_size)
        for path in dir_path.rglob("*")
        if path.is_file()
    }


def test_generate_insights_does_not_modify_real_outputs_dir(monkeypatch, tmp_path):
    """Guards against regressions like the one that overwrote outputs/generations.jsonl.

    generate_insights() previously wrote to the real project outputs/ directory
    whenever a test called it without redirecting OUTPUT_PATH, silently destroying
    production pipeline artifacts. This test proves the real directory's contents
    are byte-for-byte unchanged before and after exercising generate_insights().
    """
    before = _snapshot(REAL_OUTPUTS_DIR)

    def fake_call_model(**kwargs):
        payload = {"insights": [], "overall_confidence": 0.5}
        return {"content": json.dumps(payload), "usage": {"input_tokens": 1, "output_tokens": 1}}

    monkeypatch.setattr(generate_module, "call_model", fake_call_model)
    # Intentionally do NOT redirect OUTPUT_PATH here: the autouse conftest fixture
    # is responsible for redirecting it, and this test verifies that safeguard.
    docs = [{"id": "p1", "title": "T", "abstract": "A"}]
    generate_insights(docs, reruns=2, temperature=0.0, model_name="test-model", query_id=1)

    after = _snapshot(REAL_OUTPUTS_DIR)
    assert before == after, "Running tests must never modify the real outputs/ directory"
