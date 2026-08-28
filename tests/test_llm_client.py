from __future__ import annotations

from src.config import load_config
from src.llm_client import make_cache_key


def test_config_includes_budget_runtime_and_judge_settings():
    config = load_config()

    assert config["budget"]["max_api_calls"] == 100
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
