from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import yaml
from sentence_transformers import SentenceTransformer
import logging

from src import stats
from src.config import load_config

_MODEL_CACHE: dict[str, SentenceTransformer] = {}
logger = logging.getLogger(__name__)


def _get_model(model_name: str = "all-MiniLM-L6-v2") -> SentenceTransformer:
    """Reuse a single SentenceTransformer instance rather than reloading per run."""
    if model_name not in _MODEL_CACHE:
        _MODEL_CACHE[model_name] = SentenceTransformer(model_name)
    return _MODEL_CACHE[model_name]


def _load_generations_jsonl(path: str | Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        records.append(json.loads(line))
    return records


def _extract_claims(parsed_json: Any) -> list[str]:
    if not isinstance(parsed_json, dict):
        return []
    insights = parsed_json.get("insights")
    claims: list[str] = []
    if isinstance(insights, list):
        for insight in insights:
            if not isinstance(insight, dict):
                continue
            claim = str(insight.get("claim") or "").strip()
            if claim:
                claims.append(claim)
    return claims


def _flatten_generation_text(parsed_json: Any) -> str:
    claims = _extract_claims(parsed_json)
    if not claims:
        return ""
    return " ".join(claims)


def _cosine_similarity_matrix(vectors: np.ndarray) -> np.ndarray:
    vectors = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1e-12, norms)
    normalized = vectors / norms
    return normalized @ normalized.T


def _pair_claim_jaccard(left: list[str], right: list[str], threshold: float, model: SentenceTransformer) -> float:
    """Jaccard on aligned claims using greedy threshold matching.

    We deliberately choose greedy matching rather than exact maximum-weight matching.
    The reason is that the claim list is short (typically 3-5 items), but the prompt only
    asks for a stable, deterministic overlap metric. Greedy matching by descending similarity
    keeps the computation fast, easy to explain, and robust under a clear threshold.
    Maximum-weight matching would be more globally optimal but also more complex and harder to
    reason about operationally in a reliability report.
    """
    logger.debug("_pair_claim_jaccard left_len=%d right_len=%d threshold=%s", len(left), len(right), threshold)
    if left:
        logger.debug("_pair_claim_jaccard left[0]=%r", left[0][:50])
    if right:
        logger.debug("_pair_claim_jaccard right[0]=%r", right[0][:50])

    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0

    left_emb = model.encode(left, show_progress_bar=False, convert_to_numpy=True, normalize_embeddings=True)
    right_emb = model.encode(right, show_progress_bar=False, convert_to_numpy=True, normalize_embeddings=True)
    similarity = _cosine_similarity_matrix(np.vstack([left_emb, right_emb]))
    n_left = len(left)
    n_right = len(right)
    pairwise = similarity[:n_left, n_left:]

    # debug: print pairwise matrix and counts above threshold
    try:
        logger.debug("_pair_claim_jaccard pairwise matrix:\n%s", np.array2string(pairwise, precision=6, separator=", "))
    except Exception:
        logger.debug("_pair_claim_jaccard (could not format matrix)")
    for t_check in (threshold, 0.6, 0.7, 0.8):
        try:
            cnt = int((pairwise >= t_check).sum())
        except Exception:
            cnt = None
        logger.debug("_pair_claim_jaccard pairs >= %s: %s", t_check, cnt)

    matched_left: set[int] = set()
    matched_right: set[int] = set()
    pending = []
    for i in range(n_left):
        for j in range(n_right):
            pending.append((float(pairwise[i, j]), i, j))
    pending.sort(key=lambda item: item[0], reverse=True)

    canonical_left: list[str] = []
    canonical_right: list[str] = []
    next_id = 0

    for score, i, j in pending:
        if score < threshold:
            continue
        if i in matched_left or j in matched_right:
            continue
        matched_left.add(i)
        matched_right.add(j)
        canonical_left.append(f"match_{next_id}")
        canonical_right.append(f"match_{next_id}")
        next_id += 1

    for i in range(n_left):
        if i not in matched_left:
            canonical_left.append(f"left_{i}")
    for j in range(n_right):
        if j not in matched_right:
            canonical_right.append(f"right_{j}")

    logger.debug("_pair_claim_jaccard canonical_left=%s", canonical_left)
    logger.debug("_pair_claim_jaccard canonical_right=%s", canonical_right)
    j = stats.jaccard_similarity(canonical_left, canonical_right)
    logger.debug("_pair_claim_jaccard jaccard=%s", j)
    return j


def _semantic_consistency(valid_records: list[dict[str, Any]], model_name: str = "all-MiniLM-L6-v2") -> float | None:
    texts = [_flatten_generation_text(record.get("parsed_json")) for record in valid_records]
    texts = [text for text in texts if text.strip()]
    if len(texts) < 2:
        return None

    model = _get_model(model_name)
    embeddings = model.encode(texts, show_progress_bar=False, convert_to_numpy=True, normalize_embeddings=True)
    pairwise = _cosine_similarity_matrix(embeddings)
    upper = pairwise[np.triu_indices(len(texts), k=1)]
    if upper.size == 0:
        return None
    return float(np.mean(upper))


def _claim_overlap(valid_records: list[dict[str, Any]], threshold: float, model_name: str = "all-MiniLM-L6-v2") -> float | None:
    claim_sets = [_extract_claims(record.get("parsed_json")) for record in valid_records]
    logger.debug("_claim_overlap claim_sets lengths: %s", [len(c) for c in claim_sets])
    for idx, cs in enumerate(claim_sets):
        if cs:
            logger.debug("_claim_overlap run %d first_claim=%r", idx, cs[0][:50])
    if all(not claims for claims in claim_sets):
        return None
    if len(claim_sets) < 2:
        return None

    model = _get_model(model_name)
    pairwise_scores: list[float] = []
    for idx, left in enumerate(claim_sets):
        for right in claim_sets[idx + 1 :]:
            val = _pair_claim_jaccard(left, right, threshold, model)
            pairwise_scores.append(val)
            logger.debug("_claim_overlap pair jaccard added: %s", val)
    if not pairwise_scores:
        return None
    return float(np.mean(pairwise_scores))


def _confidence_variance(valid_records: list[dict[str, Any]]) -> tuple[float | None, float | None]:
    confidences: list[float] = []
    for record in valid_records:
        parsed_json = record.get("parsed_json")
        if not isinstance(parsed_json, dict):
            continue
        conf_value = parsed_json.get("overall_confidence")
        if conf_value is None:
            continue
        try:
            value = float(conf_value)
        except (TypeError, ValueError):
            continue
        if not np.isfinite(value):
            continue
        confidences.append(value)

    if len(confidences) < 2:
        return None, None

    values = np.asarray(confidences, dtype=float)
    mean = float(np.mean(values))
    sd = float(np.std(values, ddof=1))
    cv = float(sd / abs(mean)) if abs(mean) > 1e-12 else None
    logger.debug("_confidence_variance confidences=%s", confidences)
    logger.debug("_confidence_variance mean=%s sd=%s cv=%s", mean, sd, cv)
    return sd, cv


def _resolve_claim_match_threshold(config_path: str | Path | None = None, override: float | None = None) -> float:
    if override is not None:
        return float(override)
    try:
        config = load_config(config_path)
    except (FileNotFoundError, yaml.YAMLError, OSError):
        return 0.8
    evaluation_cfg = config.get("evaluation", {}) if isinstance(config, dict) else {}
    threshold = evaluation_cfg.get("claim_match_threshold", 0.8)
    return float(threshold)


def evaluate_confidence_icc(generated_outputs: Iterable[dict[str, Any]]) -> float | None:
    """Compute ICC(2,1) across queries, not within a single query.

    The experiment-level matrix uses rows = query_id and columns = run_index. This is the only
    meaningful place to apply ICC because a single query with N repeated runs has only one item,
    and ICC is defined on variance among items. Within a single query, the correct descriptive
    summary is instead the standard deviation or coefficient of variation of confidence.
    """
    rows_by_query: dict[str, dict[int, float]] = {}
    for record in generated_outputs:
        if not isinstance(record, dict):
            continue
        query_id = record.get("query_id")
        if query_id is None:
            continue
        parsed_json = record.get("parsed_json")
        if not isinstance(parsed_json, dict):
            continue
        conf_value = parsed_json.get("overall_confidence")
        if conf_value is None:
            continue
        try:
            value = float(conf_value)
        except (TypeError, ValueError):
            continue
        if not np.isfinite(value):
            continue
        run_index = int(record.get("run_index", 0))
        rows_by_query.setdefault(str(query_id), {})[run_index] = value

    if not rows_by_query:
        return None

    run_indices = sorted({run_idx for query_rows in rows_by_query.values() for run_idx in query_rows})
    matrix: list[list[float]] = []
    for query_id in sorted(rows_by_query):
        row = [rows_by_query[query_id].get(run_idx, float("nan")) for run_idx in run_indices]
        if any(not np.isfinite(value) for value in row):
            continue
        matrix.append(row)

    if len(matrix) < 2 or len(matrix[0]) < 2:
        return None
    return float(stats.icc_2_1(matrix))


def _citation_krippendorff(valid_records: list[dict[str, Any]]) -> float | None:
    paper_sets = []
    for record in valid_records:
        parsed_json = record.get("parsed_json")
        if not isinstance(parsed_json, dict):
            continue
        citations: set[str] = set()
        for insight in parsed_json.get("insights", []):
            if not isinstance(insight, dict):
                continue
            for paper_id in insight.get("supporting_paper_ids", []):
                if paper_id is not None:
                    citations.add(str(paper_id))
        paper_sets.append(sorted(citations))

    if not paper_sets:
        return None
    as_sets = [set(run) for run in paper_sets]
    if all(not run for run in as_sets):
        return None
    if all(run == as_sets[0] for run in as_sets) and len(as_sets[0]) <= 1:
        return None

    all_papers = sorted({paper for run in paper_sets for paper in run})
    if not all_papers:
        return None

    # For citation agreement, rows = paper IDs (the items under comparison), columns = rerun
    # index (the raters). Each cell equals 1 if the rerun cited that paper, else 0.
    matrix = [[1 if paper in run else 0 for run in paper_sets] for paper in all_papers]
    if len(matrix) < 2 or len(matrix[0]) < 2:
        return None
    return float(stats.krippendorff_alpha(matrix, level="nominal"))


def _safe_mean(values: Iterable[float | None]) -> float | None:
    cleaned = []
    for value in values:
        if value is None:
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if not np.isfinite(numeric):
            continue
        cleaned.append(numeric)
    if not cleaned:
        return None
    return float(np.mean(cleaned))


def evaluate_reliability(generated_outputs: Iterable[dict[str, Any]], claim_match_threshold: float | None = None, model_name: str = "all-MiniLM-L6-v2") -> dict[str, Any]:
    """Compute query-level reliability for repeated generation results.

    This function is intentionally scoped to a single query. A single query with N repeated runs
    has only one item and therefore no between-item variance. As a result, ICC(2,1) is not defined
    at this level; we describe the confidence spread using standard deviation and coefficient of
    variation instead. The experiment-level ICC is computed separately by evaluate_confidence_icc
    across multiple queries.
    """
    threshold = _resolve_claim_match_threshold(override=claim_match_threshold)

    records = list(generated_outputs)
    # Input contract validation: each record must be a dict and include required keys
    if not records:
        return {
            "query_id": None,
            "n_runs": 0,
            "n_valid_runs": 0,
            "n_parse_failures": 0,
            "semantic_consistency": None,
            "claim_jaccard": None,
            "confidence_sd": None,
            "confidence_cv": None,
            "krippendorff_alpha": None,
            "reliability_score": None,
            "reason": "No records were provided.",
        }

    # Validate record structure strictly to avoid silent failures
    for idx, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"Record at index {idx} is not a dict (got {type(record).__name__}).")
        if "parsed_json" not in record:
            raise ValueError(f"Record at index {idx} missing required key 'parsed_json'.")
        if "query_id" not in record:
            raise ValueError(f"Record at index {idx} missing required key 'query_id'.")

    query_id = next((record.get("query_id") for record in records if isinstance(record, dict) and record.get("query_id") is not None), None)
    valid_records: list[dict[str, Any]] = []
    parse_failures = 0
    excluded: list[tuple[int, Any, str]] = []
    for idx, record in enumerate(records):
        if not isinstance(record, dict):
            parse_failures += 1
            excluded.append((idx, record, "not a dict"))
            continue
        payload = record.get("parsed_json")
        if payload in (None, "parse_failure"):
            parse_failures += 1
            excluded.append((idx, record, f"payload invalid: {payload!r}"))
            continue
        if not isinstance(payload, dict):
            parse_failures += 1
            excluded.append((idx, record, f"payload not dict: {type(payload).__name__}"))
            continue
        valid_records.append(record)

    logger.debug("evaluate_reliability total_records=%s valid_records=%s parse_failures=%s", len(records), len(valid_records), parse_failures)
    if excluded:
        logger.debug("evaluate_reliability excluded records details:")
        for ex in excluded:
            irec, rec, reason = ex
            logger.debug("  idx=%s run_index=%s reason=%s", irec, (rec.get('run_index') if isinstance(rec, dict) else rec), reason)

    if len(valid_records) < 2:
        return {
            "query_id": query_id,
            "n_runs": len(valid_records),
            "n_valid_runs": len(valid_records),
            "n_parse_failures": parse_failures,
            "semantic_consistency": None,
            "claim_jaccard": None,
            "confidence_sd": None,
            "confidence_cv": None,
            "krippendorff_alpha": None,
            "reliability_score": None,
            "reason": "Need at least 2 valid runs after excluding parse failures.",
        }

    semantic = _semantic_consistency(valid_records, model_name=model_name)
    claim_overlap = _claim_overlap(valid_records, threshold=threshold, model_name=model_name)
    confidence_sd, confidence_cv = _confidence_variance(valid_records)
    citation_alpha = _citation_krippendorff(valid_records)

    reason = "Metrics computed on valid runs only."
    if semantic is None:
        reason = "No usable claim text remained after excluding empty or parse-failed generations."
    elif claim_overlap is None:
        reason = "No valid claims were available for claim-level overlap."
    elif citation_alpha is None:
        reason = "Citation agreement is undefined when all runs have no usable citation signal or only a single paper."

    metric_values = [value for value in [semantic, claim_overlap] if value is not None]
    reliability_score = _safe_mean(metric_values)
    if reliability_score is None:
        reason = "No valid metrics remained after filtering None/NaN values."

    return {
        "query_id": query_id,
        "n_runs": len(valid_records),
        "n_valid_runs": len(valid_records),
        "n_parse_failures": parse_failures,
        "semantic_consistency": semantic,
        "claim_jaccard": claim_overlap,
        "confidence_sd": confidence_sd,
        "confidence_cv": confidence_cv,
        "krippendorff_alpha": citation_alpha,
        "reliability_score": reliability_score,
        "reason": reason,
    }


def evaluate_reliability_from_jsonl(path: str | Path, claim_match_threshold: float | None = None, model_name: str = "all-MiniLM-L6-v2") -> dict[str, Any]:
    """Load a generations.jsonl file and evaluate the query-level reliability scores."""
    records = _load_generations_jsonl(path)
    return evaluate_reliability(records, claim_match_threshold=claim_match_threshold, model_name=model_name)
