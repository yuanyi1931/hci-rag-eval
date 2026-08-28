from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Iterable

try:
    from anthropic import Anthropic
except ImportError:  # pragma: no cover
    Anthropic = None

_API_CALL_COUNT = 0


def _extract_json_text(raw_text: str) -> dict[str, Any]:
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned)


def _build_prompt(documents: Iterable[dict[str, Any]]) -> str:
    text = "Summarize the key research trend across these HCI papers.\n\n"
    for idx, doc in enumerate(documents, start=1):
        text += f"{idx}. [{doc.get('id', 'paper')}]: {doc.get('title', '')}\n{doc.get('abstract', '')}\n\n"
    text += (
        "Return only a JSON object with keys: 'insights', 'overall_confidence'. "
        "'insights' must be a list of 3-5 objects, each with 'claim', 'supporting_paper_ids', and 'reasoning'. "
        "'supporting_paper_ids' must only include paper ids from the supplied context. "
        "'overall_confidence' must be a float between 0 and 1."
    )
    return text


def _require_api_key() -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Please set it in .env: ANTHROPIC_API_KEY=sk-ant-..."
        )
    if Anthropic is None:
        raise RuntimeError("The 'anthropic' package is not installed. Please install project dependencies before running the pipeline.")
    return api_key


def reset_api_call_count() -> None:
    global _API_CALL_COUNT
    _API_CALL_COUNT = 0


def get_api_call_count() -> int:
    return _API_CALL_COUNT


def _call_anthropic(prompt: str, model_name: str = "claude-sonnet-4-6", temperature: float = 0.7) -> dict[str, Any]:
    global _API_CALL_COUNT
    _require_api_key()

    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    for attempt in range(3):
        try:
            _API_CALL_COUNT += 1
            response = client.messages.create(
                model=model_name,
                max_tokens=800,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.content[0].text
            return _extract_json_text(content)
        except Exception as exc:
            if attempt == 2:
                raise RuntimeError(f"Anthropic generation failed: {exc}") from exc
            time.sleep(2 ** attempt)
    raise RuntimeError("Anthropic generation retries exhausted.")


def generate_insights(documents, reruns: int = 3, temperature: float = 0.7, model_name: str = "claude-sonnet-4-6"):
    """Generate structured insight JSON for each rerun using the Anthropic API.

    This function fails fast when the API key is missing; there is no mock or demo path.
    """
    reset_api_call_count()
    outputs = []
    for run_index in range(reruns):
        prompt = _build_prompt(documents)
        result = _call_anthropic(prompt, model_name=model_name, temperature=temperature)
        result["run_id"] = run_index
        outputs.append(result)
    return outputs
