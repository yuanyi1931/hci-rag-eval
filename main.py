from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
import logging

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import load_config
from src.fetch_data import fetch_arxiv_abstracts
from src.embed import build_embeddings
from src.generate import generate_insights, get_api_call_count
from src.llm_client import get_stage_call_counts, reset_api_usage
from src.retrieve import build_query_from_text, compute_top_k, load_embeddings
from src.evaluate_validity import evaluate_validity
from src.evaluate_reliability import evaluate_reliability
from src.evaluate_actionability import evaluate_actionability
from src.report import write_summary_report


def _apply_config_defaults(args: argparse.Namespace, config: dict) -> None:
    if args.max_papers is None:
        args.max_papers = int(config.get("data", {}).get("max_papers", 100))
    if args.queries is None:
        args.queries = int(config.get("data", {}).get("queries", 5))
    if args.top_k is None:
        args.top_k = int(config.get("retrieval", {}).get("top_k", 5))
    if args.reruns is None:
        args.reruns = int(config.get("generation", {}).get("reruns", 5))
    if args.temperature is None:
        args.temperature = float(config.get("generation", {}).get("temperature", 0.7))
    if args.model_name is None:
        args.model_name = str(config.get("retrieval", {}).get("model_name", "all-MiniLM-L6-v2"))
    if not hasattr(args, "generation_model_name") or args.generation_model_name is None:
        args.generation_model_name = str(config.get("generation", {}).get("model_name", "claude-sonnet-4-6"))


def _config_hash(config: dict) -> str:
    payload = json.dumps(config, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:12]


def run_pipeline(args: argparse.Namespace) -> None:
    config = load_config()
    _apply_config_defaults(args, config)
    reset_api_usage()
    config_hash = _config_hash(config)
    start_time = time.perf_counter()

    raw_path = ROOT / config.get("data", {}).get("raw_path", "data/raw/abstracts.jsonl")
    embeddings_path = ROOT / config.get("data", {}).get("embeddings_path", "data/embeddings.npy")
    ids_path = ROOT / config.get("data", {}).get("embedding_ids_path", "data/embeddings_ids.json")
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    embeddings_path.parent.mkdir(parents=True, exist_ok=True)

    if args.force_refresh or not raw_path.exists():
        ok = fetch_arxiv_abstracts(raw_path, max_results=args.max_papers)
        if not ok:
            raise RuntimeError(
                "arXiv fetch failed and no fallback dataset is allowed. Please verify network access and retry."
            )

    if not raw_path.exists():
        raise FileNotFoundError(f"No paper corpus found at {raw_path}. Run the fetch step first.")

    if args.force_refresh or not embeddings_path.exists():
        build_embeddings(raw_path, embeddings_path=embeddings_path, ids_path=ids_path, model_name=args.model_name)

    embeddings, ids = load_embeddings(embeddings_path, ids_path, raw_path=raw_path)
    query_texts = config.get("manual_queries") or []
    if not query_texts:
        raise ValueError("manual_queries is empty in config.yaml. Add at least one HCI query.")
    if args.queries is not None and args.queries > 0:
        query_texts = query_texts[: args.queries]

    results = []
    provenance = {
        "model_name": config.get("generation", {}).get("model_name", "claude-sonnet-4-6"),
        "api_calls": 0,
        "generation_calls": 0,
        "validity_calls": 0,
        "actionability_calls": 0,
        "execution_time_seconds": 0.0,
        "config_hash": config_hash,
    }

    for idx, query in enumerate(query_texts, start=1):
        query_embedding = build_query_from_text(query, model_name=args.model_name)
        top_docs = compute_top_k(query_embedding, embeddings, ids, k=args.top_k)
        # If an outputs/generations.jsonl exists, prefer loading generated records
        # from disk for debugging / replay so we do not re-call the generation API.
        gens_path = ROOT / "outputs" / "generations.jsonl"
        if gens_path.exists():
            from src.evaluate_reliability import _load_generations_jsonl

            all_recs = _load_generations_jsonl(gens_path)
            # filter by this query id
            generated = [r for r in all_recs if r.get("query_id") == idx]
        else:
            generated = generate_insights(
                top_docs,
                reruns=args.reruns,
                temperature=args.temperature,
                model_name=args.generation_model_name,
                query_id=idx,
            )

        # Diagnostic debug print immediately before evaluate_reliability
        # (user-requested format) — use logger.debug so it's controlled by --debug
        records = list(generated)
        qid = idx
        logging.getLogger(__name__).debug("query=%s n_records=%s", qid, len(records))
        for r in records:
            pj = r.get("parsed_json") if isinstance(r, dict) else None
            n_claims = len(pj.get("insights", [])) if isinstance(pj, dict) else "NO_PARSED_JSON"
            conf = pj.get("overall_confidence") if isinstance(pj, dict) else None
            logging.getLogger(__name__).debug("  run=%s claims=%s conf=%s", r.get('run_index'), n_claims, conf)
        validity = evaluate_validity(generated, top_docs)
        reliability = evaluate_reliability(generated)
        actionability = evaluate_actionability(generated)

        results.append(
            {
                "query_id": idx,
                "query": query,
                "average_retrieval_similarity": float(sum(item["similarity"] for item in top_docs) / len(top_docs)),
                "grounding_rate": validity["grounding_rate"],
                "citation_validity_rate": validity["citation_validity_rate"],
                "reliability_score": reliability["reliability_score"],
                "actionability_mean": actionability["mean_score"],
                "top_papers": [item["id"] for item in top_docs],
                "provenance_model_name": provenance["model_name"],
                "provenance_api_calls": 0,
                "provenance_execution_time_seconds": 0.0,
                "provenance_config_hash": provenance["config_hash"],
            }
        )

    stage_counts = get_stage_call_counts()
    provenance["api_calls"] = get_api_call_count()
    provenance["generation_calls"] = stage_counts.get("generation", 0)
    provenance["validity_calls"] = stage_counts.get("validity", 0)
    provenance["actionability_calls"] = stage_counts.get("actionability", 0)
    provenance["execution_time_seconds"] = round(time.perf_counter() - start_time, 3)
    for row in results:
        row["provenance_model_name"] = provenance["model_name"]
        row["provenance_api_calls"] = provenance["api_calls"]
        row["provenance_execution_time_seconds"] = provenance["execution_time_seconds"]
        row["provenance_config_hash"] = provenance["config_hash"]

    write_summary_report(results, root=ROOT, provenance=provenance)
    print(f"Completed evaluation for {len(results)} queries.")
    print(
        "Stage call counts: "
        f"generation={provenance['generation_calls']}, "
        f"validity={provenance['validity_calls']}, "
        f"actionability={provenance['actionability_calls']}, total={provenance['api_calls']}"
    )
    print(f"Results written to {ROOT / 'outputs' / 'results.csv'} and {ROOT / 'outputs' / 'report.md'}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="HCI RAG evaluation pipeline")
    parser.add_argument("--demo", action="store_true", help="Use a smaller demo configuration")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--max-papers", type=int, default=None, help="Maximum papers to fetch from arXiv")
    parser.add_argument("--queries", type=int, default=None, help="Number of queries to evaluate")
    parser.add_argument("--reruns", type=int, default=None, help="Number of generation reruns per query")
    parser.add_argument("--top-k", type=int, default=None, help="Top-k retrieval results")
    parser.add_argument("--temperature", type=float, default=None, help="Sampling temperature for generation")
    parser.add_argument("--model-name", type=str, default=None, help="Sentence-transformer embedding model")
    parser.add_argument("--generation-model-name", type=str, default=None, help="LLM generation model")
    parser.add_argument("--force-refresh", action="store_true", help="Refetch and rebuild embeddings")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    logging.basicConfig(level=logging.DEBUG if getattr(args, "debug", False) else logging.INFO)
    config = load_config()
    if args.demo:
        args.max_papers = min(args.max_papers or int(config.get("data", {}).get("max_papers", 100)), 20)
        args.queries = min(args.queries or int(config.get("data", {}).get("queries", 5)), 3)
        args.reruns = min(args.reruns or int(config.get("generation", {}).get("reruns", 5)), 3)
        args.top_k = min(args.top_k or int(config.get("retrieval", {}).get("top_k", 5)), 5)

    if not config.get("manual_queries"):
        raise ValueError("Please define manual_queries in config.yaml before running the pipeline.")
    if not __import__("os").getenv("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY is not set. Please set it in .env: ANTHROPIC_API_KEY=sk-ant-...")
    run_pipeline(args)
