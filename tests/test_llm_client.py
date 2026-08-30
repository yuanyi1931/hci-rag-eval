from __future__ import annotations

from src.config import load_config
from src.llm_client import (
    call_model,
    get_api_call_count,
    get_cache_hit_count,
    get_stage_call_counts,
    make_cache_key,
    reset_api_usage,
)


def test_config_includes_budget_runtime_and_judge_settings():
    config = load_config()

    assert config["budget"]["max_api_calls"] == 1000
    assert config["budget"]["warn_at_calls"] == 50
    assert config["runtime"]["random_seed"] == 42
    assert config["runtime"]["cache_enabled"] is True
    assert config["runtime"]["cache_dir"] == "data/cache"

    assert config["evaluation"]["judge_model"] == "claude-sonnet-4-6"
    assert config["evaluation"]["judge_temperature"] == 0.0
    assert config["evaluation"]["judge_n_votes"] == 3
    assert config["evaluation"]["claim_match_threshold"] == 0.8
    assert config["evaluation"]["actionability"]["rubric_min"] == 1
    assert config["evaluation"]["actionability"]["rubric_max"] == 5


def test_cache_key_differs_when_run_index_changes():
    key_a = make_cache_key(
        model="claude-sonnet-4-6",
        prompt="same prompt",
        temperature=0.0,
        run_index=0,
    )
    key_b = make_cache_key(
        model="claude-sonnet-4-6",
        prompt="same prompt",
        temperature=0.0,
        run_index=1,
    )

    assert key_a != key_b


def test_call_model_counts_cache_hits_separately_from_api_calls(monkeypatch, tmp_path):
    reset_api_usage()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr("src.llm_client._get_runtime_config", lambda: {"cache_enabled": True, "cache_dir": str(tmp_path)})

    calls = {"count": 0}

    def fake_api_fn(**kwargs):
        calls["count"] += 1
        return {"content": "ok", "usage": {"input_tokens": 10, "output_tokens": 5}}

    first = call_model(model="claude-sonnet-4-6", prompt="same prompt", temperature=0.0, run_index=0, api_fn=fake_api_fn)
    second = call_model(model="claude-sonnet-4-6", prompt="same prompt", temperature=0.0, run_index=0, api_fn=fake_api_fn)

    assert first["content"] == "ok"
    assert second["content"] == "ok"
    assert calls["count"] == 1
    assert get_api_call_count() == 1
    assert get_cache_hit_count() == 1
    assert get_stage_call_counts()["generation"] == 2
