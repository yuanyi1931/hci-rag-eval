from __future__ import annotations

import atexit
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Callable

from src.config import load_config

API_CALL_LIMIT = 100
API_WARNING_THRESHOLD = 50
INPUT_TOKEN_PRICE_PER_1K = 0.003
OUTPUT_TOKEN_PRICE_PER_1K = 0.015

_API_CALL_COUNT = 0
_CACHE_HIT_COUNT = 0
_WARNED_AT_LIMIT = False
_INPUT_TOKENS = 0
_OUTPUT_TOKENS = 0
_STAGE_CALL_COUNTS = {
    "generation": 0,
    "validity": 0,
    "actionability": 0,
}
_STAGE_CACHE_HIT_COUNTS = {
    "generation": 0,
    "validity": 0,
    "actionability": 0,
}


def _get_runtime_config() -> dict[str, Any]:
    config = load_config()
    return config.get("runtime", {}) if isinstance(config, dict) else {}


def _get_budget_config() -> dict[str, Any]:
    config = load_config()
    return config.get("budget", {}) if isinstance(config, dict) else {}


def _resolve_cache_dir() -> Path:
    runtime = _get_runtime_config()
    cache_dir = runtime.get("cache_dir", "data/cache")
    path = Path(cache_dir)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[1] / path
    return path


def _get_api_call_limit() -> int:
    budget = _get_budget_config()
    value = budget.get("max_api_calls", API_CALL_LIMIT)
    try:
        return int(value)
    except (TypeError, ValueError):
        return API_CALL_LIMIT


def _get_warn_threshold() -> int:
    budget = _get_budget_config()
    value = budget.get("warn_at_calls", API_WARNING_THRESHOLD)
    try:
        return int(value)
    except (TypeError, ValueError):
        return API_WARNING_THRESHOLD


def _warn_if_needed() -> None:
    global _WARNED_AT_LIMIT
    if _API_CALL_COUNT >= _get_warn_threshold() and not _WARNED_AT_LIMIT:
        print(
            f"Warning: API usage reached {_API_CALL_COUNT} calls, threshold is {_get_warn_threshold()}. "
            f"Estimated remaining budget: {_get_api_call_limit() - _API_CALL_COUNT} calls."
        )
        _WARNED_AT_LIMIT = True


def _check_budget() -> None:
    limit = _get_api_call_limit()
    if _API_CALL_COUNT > limit:
        raise RuntimeError(
            f"API budget exceeded: used {_API_CALL_COUNT} / {limit} calls. "
            "The pipeline has been stopped to prevent runaway spend."
        )


def reset_api_usage() -> None:
    global _API_CALL_COUNT, _CACHE_HIT_COUNT, _WARNED_AT_LIMIT, _INPUT_TOKENS, _OUTPUT_TOKENS
    _API_CALL_COUNT = 0
    _CACHE_HIT_COUNT = 0
    _WARNED_AT_LIMIT = False
    _INPUT_TOKENS = 0
    _OUTPUT_TOKENS = 0
    for key in _STAGE_CALL_COUNTS:
        _STAGE_CALL_COUNTS[key] = 0
    for key in _STAGE_CACHE_HIT_COUNTS:
        _STAGE_CACHE_HIT_COUNTS[key] = 0


def get_api_call_count() -> int:
    return _API_CALL_COUNT


def get_cache_hit_count() -> int:
    return _CACHE_HIT_COUNT


def get_stage_call_counts() -> dict[str, int]:
    return dict(_STAGE_CALL_COUNTS)


def get_stage_cache_hit_counts() -> dict[str, int]:
    return dict(_STAGE_CACHE_HIT_COUNTS)


def get_token_usage() -> tuple[int, int]:
    return _INPUT_TOKENS, _OUTPUT_TOKENS


def _accumulate_tokens(usage: Any) -> None:
    global _INPUT_TOKENS, _OUTPUT_TOKENS
    if isinstance(usage, dict):
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
    else:
        input_tokens = getattr(usage, "input_tokens", None)
        output_tokens = getattr(usage, "output_tokens", None)

    if input_tokens is not None:
        try:
            _INPUT_TOKENS += int(input_tokens)
        except (TypeError, ValueError):
            pass
    if output_tokens is not None:
        try:
            _OUTPUT_TOKENS += int(output_tokens)
        except (TypeError, ValueError):
            pass


def _get_cost_estimate(input_tokens: int, output_tokens: int) -> float:
    input_cost = (input_tokens / 1000.0) * INPUT_TOKEN_PRICE_PER_1K
    output_cost = (output_tokens / 1000.0) * OUTPUT_TOKEN_PRICE_PER_1K
    return input_cost + output_cost


def print_usage_summary() -> None:
    total_cost = _get_cost_estimate(_INPUT_TOKENS, _OUTPUT_TOKENS)
    print(
        "LLM usage summary: "
        f"calls={_API_CALL_COUNT}, cache_hits={_CACHE_HIT_COUNT}, input_tokens={_INPUT_TOKENS}, output_tokens={_OUTPUT_TOKENS}, "
        f"estimated_cost_usd=${total_cost:.6f}"
    )


atexit.register(print_usage_summary)


def make_cache_key(model: str, prompt: str, temperature: float, run_index: int) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "temperature": temperature,
        "run_index": run_index,
    }
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "model_dump"):
        return _json_safe(value.model_dump())
    if hasattr(value, "dict") and callable(value.dict):
        return _json_safe(value.dict())
    if hasattr(value, "__dict__"):
        return {str(key): _json_safe(item) for key, item in vars(value).items()}
    return value


def _cache_file_for_key(cache_key: str) -> Path:
    cache_dir = _resolve_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{cache_key}.json"


def load_from_cache(model: str, prompt: str, temperature: float, run_index: int) -> Any | None:
    runtime = _get_runtime_config()
    if not runtime.get("cache_enabled", True):
        return None
    cache_key = make_cache_key(model, prompt, temperature, run_index)
    path = _cache_file_for_key(cache_key)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def save_to_cache(model: str, prompt: str, temperature: float, run_index: int, payload: Any) -> None:
    runtime = _get_runtime_config()
    if not runtime.get("cache_enabled", True):
        return
    cache_key = make_cache_key(model, prompt, temperature, run_index)
    path = _cache_file_for_key(cache_key)
    path.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, sort_keys=True), encoding="utf-8")


def _anthropic_call(model: str, prompt: str, temperature: float, max_tokens: int = 800) -> dict[str, Any]:
    try:
        from anthropic import Anthropic
        import inspect
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("The 'anthropic' package is not installed. Please install project dependencies before running the pipeline.") from exc

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set. Please set it in .env: ANTHROPIC_API_KEY=sk-ant-...")

    client = Anthropic(api_key=api_key)
    request_kwargs = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    try:
        if "temperature" in inspect.signature(client.messages.create).parameters:
            request_kwargs["temperature"] = temperature
    except Exception:
        pass
    response = client.messages.create(**request_kwargs)

    content_blocks = getattr(response, "content", []) if not isinstance(response, dict) else response.get("content", [])
    text_parts: list[str] = []
    for block in content_blocks:
        if isinstance(block, dict):
            if block.get("type") == "text":
                text_parts.append(str(block.get("text", "")))
        else:
            text = getattr(block, "text", None)
            if text:
                text_parts.append(str(text))
    raw_text = "".join(text_parts)

    usage = getattr(response, "usage", None) if not isinstance(response, dict) else response.get("usage", {})
    usage_json = _json_safe(usage)
    _accumulate_tokens(usage_json)
    return {"content": raw_text, "usage": usage_json}


def call_model(
    *,
    model: str,
    prompt: str,
    temperature: float,
    run_index: int,
    max_tokens: int = 800,
    cache_enabled: bool | None = None,
    api_fn: Callable[..., Any] | None = None,
    stage: str = "generation",
) -> Any:
    runtime = _get_runtime_config()
    if cache_enabled is None:
        cache_enabled = bool(runtime.get("cache_enabled", True))

    if stage in _STAGE_CALL_COUNTS:
        _STAGE_CALL_COUNTS[stage] += 1

    if cache_enabled:
        cached = load_from_cache(model, prompt, temperature, run_index)
        if cached is not None:
            global _CACHE_HIT_COUNT
            _CACHE_HIT_COUNT += 1
            if stage in _STAGE_CACHE_HIT_COUNTS:
                _STAGE_CACHE_HIT_COUNTS[stage] += 1
            return cached

    effective_api_fn = api_fn or _anthropic_call
    for attempt in range(1, 6):
        try:
            global _API_CALL_COUNT
            _API_CALL_COUNT += 1
            _warn_if_needed()
            _check_budget()
            response = effective_api_fn(model=model, prompt=prompt, temperature=temperature, max_tokens=max_tokens)
            if cache_enabled:
                save_to_cache(model, prompt, temperature, run_index, response)
            return response
        except Exception:
            if attempt == 5:
                raise
            time.sleep(2 ** (attempt - 1))

    raise RuntimeError("LLM call failed after retries.")
