from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def write_summary_report(results: list[dict], root: str | Path = ".", provenance: dict | None = None) -> None:
    root = Path(root)
    output_dir = root / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    provenance = provenance or {
        "model_name": "unknown",
        "api_calls": 0,
        "execution_time_seconds": 0.0,
        "config_hash": "unknown",
    }

    df = pd.DataFrame(results)
    if not df.empty:
        for key, value in {
            "provenance_model_name": provenance.get("model_name", "unknown"),
            "provenance_api_calls": provenance.get("api_calls", 0),
            "provenance_execution_time_seconds": provenance.get("execution_time_seconds", 0.0),
            "provenance_config_hash": provenance.get("config_hash", "unknown"),
        }.items():
            if key not in df.columns:
                df[key] = value

    csv_path = output_dir / "results.csv"
    df.to_csv(csv_path, index=False)

    if not df.empty:
        plt.figure(figsize=(7, 5))
        plt.scatter(df["average_retrieval_similarity"], df["grounding_rate"], s=60, alpha=0.8)
        plt.xlabel("Average retrieval similarity")
        plt.ylabel("Grounding rate")
        plt.title("Retrieval quality vs. validity")
        plt.grid(True, linestyle="--", alpha=0.3)
        plt.tight_layout()
        plt.savefig(output_dir / "retrieval_vs_grounding.png", dpi=160)
        plt.close()

    report_md = output_dir / "report.md"
    warning = ""
    if int(provenance.get("api_calls", 0)) == 0:
        warning = (
            "> WARNING: No Anthropic API calls were made. This report is not valid for evaluation. "
            "Please configure ANTHROPIC_API_KEY in .env and rerun the pipeline.\n\n"
        )

    summary_lines = [
        "# HCI RAG Evaluation Summary",
        "",
        warning.rstrip(),
        "",
        "This report compares retrieval quality with generation quality using the configured pipeline run.",
        "",
        "## Provenance",
        "",
        f"- Model: {provenance.get('model_name', 'unknown')}",
        f"- API calls: {provenance.get('api_calls', 0)}",
        f"- Execution time (s): {provenance.get('execution_time_seconds', 0.0)}",
        f"- Config hash: {provenance.get('config_hash', 'unknown')}",
        "",
        "## Key metrics",
        "",
        f"- Queries evaluated: {len(df)}",
        f"- Mean grounding rate: {df['grounding_rate'].mean() if not df.empty else 0.0:.3f}",
        f"- Mean reliability score: {df['reliability_score'].mean() if not df.empty else 0.0:.3f}",
        f"- Mean actionability score: {df['actionability_mean'].mean() if not df.empty else 0.0:.3f}",
        "",
        "## Interpretation",
        "",
        "- Higher average retrieval similarity does not guarantee better grounding if the retrieved papers are too broad or loosely related.",
        "- Reliability is most informative when repeated generations are compared using the same retrieval context and prompt.",
        "- Actionability captures whether the output is usable for a research or product decision, not just whether it is descriptive.",
    ]
    report_md.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    return None
