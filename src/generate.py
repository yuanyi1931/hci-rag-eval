from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from src.config import load_config
from src.llm_client import call_model, get_api_call_count as _llm_get_api_call_count, reset_api_usage

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "outputs" / "generations.jsonl"


def _extract_json_text(raw_text: str) -> dict[str, Any]:
    if isinstance(raw_text, (dict, list)):
        return raw_text

    cleaned = str(raw_text).strip()
    if not cleaned:
        raise ValueError("Model returned an empty response while generating insights.")

    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    for candidate in [cleaned]:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    first_brace = min((cleaned.find("{"), cleaned.find("[")), default=-1)
    if first_brace != -1:
        candidate = cleaned[first_brace:]
        if candidate and candidate[0] == "{":
            end = candidate.rfind("}")
            if end > 0:
                try:
                    return json.loads(candidate[: end + 1])
                except json.JSONDecodeError:
                    pass
        elif candidate and candidate[0] == "[":
            end = candidate.rfind("]")
            if end > 0:
                try:
                    return json.loads(candidate[: end + 1])
                except json.JSONDecodeError:
                    pass

    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Model response was not valid JSON: {cleaned[:500]}")


def _build_prompt(documents: Iterable[dict[str, Any]]) -> str:
    text = "Summarize the key research trend across these HCI papers.\n\n"
    documents = list(documents)
    if not documents:
        raise ValueError("_build_prompt received an empty document list.")

    for idx, doc in enumerate(documents, start=1):
        if not isinstance(doc, dict):
            raise TypeError(f"Document at index {idx} is not a dict: {type(doc).__name__}")
        doc_id = doc.get("id", f"<unknown-{idx}>")
        if "title" not in doc:
            raise KeyError(f"Document {doc_id} is missing the required 'title' field.")
        if "abstract" not in doc:
            raise KeyError(f"Document {doc_id} is missing the required 'abstract' field.")
        title = doc["title"]
        abstract = doc["abstract"]
        if not isinstance(title, str) or not title.strip():
            raise ValueError(f"Document {doc_id} has an empty or invalid 'title' field.")
        if not isinstance(abstract, str) or not abstract.strip():
            raise ValueError(f"Document {doc_id} has an empty or invalid 'abstract' field.")
        text += f"{idx}. [{doc_id}]: {title}\n{abstract}\n\n"
    text += (
        "Return ONLY valid JSON with double quotes around all keys and string values. "
        "Do not include markdown fences, explanations, or commentary before or after the JSON. "
        "The top-level object must have keys: 'insights' and 'overall_confidence'. "
        "'insights' must be a list of 3-5 objects, each with 'claim', 'supporting_paper_ids', and 'reasoning'. "
        "Each 'claim' should be a short single sentence, each 'reasoning' should be at most one sentence and very concise, and 'supporting_paper_ids' must only include paper ids from the supplied context. "
        "'overall_confidence' must be a float between 0 and 1. "
        "Example shape: {\"insights\": [{\"claim\": \"...\", \"supporting_paper_ids\": [\"id1\"], \"reasoning\": \"...\"}], \"overall_confidence\": 0.82}"
    )
    return text


def reset_api_call_count() -> None:
    reset_api_usage()


def get_api_call_count() -> int:
    return _llm_get_api_call_count()


def _get_generation_max_tokens() -> int:
    config = load_config()
    generation_cfg = config.get("generation", {}) if isinstance(config, dict) else {}
    value = generation_cfg.get("max_tokens", 4096)
    try:
        return max(256, int(value))
    except (TypeError, ValueError):
        return 4096


def _call_anthropic(prompt: str, model_name: str = "claude-sonnet-4-6", temperature: float = 0.7) -> dict[str, Any]:
    """Compatibility wrapper around the shared llm_client budget/caching implementation."""
    response = call_model(
        model=model_name,
        prompt=prompt,
        temperature=temperature,
        run_index=int(time.time() * 1000) % 1000000,
        max_tokens=_get_generation_max_tokens(),
        stage="generation",
    )
    if not isinstance(response, dict):
        raise TypeError(f"Expected dict response from llm_client, got {type(response).__name__}")
    raw_text = response.get("content", "")
    return _extract_json_text(raw_text)


def generate_insights(
    documents,
    reruns: int = 3,
    temperature: float = 0.7,
    model_name: str = "claude-sonnet-4-6",
    query_id: int | None = None,
):
    """Generate structured insight JSON for each rerun using the shared LLM client.

    Each call records the raw model output and token usage in outputs/generations.jsonl.
    """
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    if query_id == 1:
        try:
            OUTPUT_PATH.unlink()
        except FileNotFoundError:
            pass
    outputs = []
    for run_index in range(reruns):
        prompt = _build_prompt(documents)
        last_error: Exception | None = None
        raw_text = ""
        parsed: Any = "parse_failure"
        response: Any = None
        for attempt in range(2):
            try:
                response = call_model(
                    model=model_name,
                    prompt=prompt,
                    temperature=temperature if attempt == 0 else max(0.1, temperature * 0.5),
                    run_index=run_index * 10 + attempt,
                    max_tokens=_get_generation_max_tokens(),
                    stage="generation",
                )
                raw_text = response.get("content", "") if isinstance(response, dict) else str(response)
                parsed = _extract_json_text(raw_text)
                break
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                last_error = exc
                raw_text = str(response.get("content", "") if isinstance(response, dict) else response)
                parsed = "parse_failure"
                continue

        record = {
            "query_id": query_id,
            "run_index": run_index,
            "model": model_name,
            "temperature": temperature,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "raw_response": raw_text,
            "parsed_json": parsed,
            "token_usage": response.get("usage", {}) if isinstance(response, dict) else {},
        }
        outputs.append(record)

        with OUTPUT_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return outputs
