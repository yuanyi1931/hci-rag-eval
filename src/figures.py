from __future__ import annotations

import io
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS_CSV_PATH = ROOT / "experiments" / "phase4_2026-08-29.md"
OUTPUTS_CSV_PATH = ROOT / "outputs" / "results.csv"
FIGURES_DIR = ROOT / "outputs" / "figures"

DPI = 150


def _extract_csv_block(md_text: str) -> str:
    """Pull the raw CSV text out of the '=== results.csv ===' ... '=== report.md ===' block."""
    start_marker = "=== results.csv ===\n"
    end_marker = "\n\n=== report.md ==="
    start = md_text.index(start_marker) + len(start_marker)
    end = md_text.index(end_marker, start)
    return md_text[start:end]


def load_results_dataframe() -> pd.DataFrame:
    """Load the Phase 4 (10x5) results.

    Prefers the archived, non-regenerable experiments/ export (the source of
    record for reported numbers). Falls back to outputs/results.csv, which is
    a working artifact that later pipeline runs (including --reuse-generations
    smoke tests) can and do overwrite.
    """
    if EXPERIMENTS_CSV_PATH.exists():
        md_text = EXPERIMENTS_CSV_PATH.read_text(encoding="utf-8")
        csv_text = _extract_csv_block(md_text)
        return pd.read_csv(io.StringIO(csv_text))
    if OUTPUTS_CSV_PATH.exists():
        return pd.read_csv(OUTPUTS_CSV_PATH)
    raise FileNotFoundError(
        f"Could not find results data at {EXPERIMENTS_CSV_PATH} or {OUTPUTS_CSV_PATH}."
    )


def plot_retrieval_vs_grounding(df: pd.DataFrame, output_path: Path) -> None:
    x = df["average_retrieval_similarity"].to_numpy(dtype=float)
    y = df["grounding_rate"].to_numpy(dtype=float)
    query_ids = df["query_id"].to_numpy()
    n = len(x)

    r, p = stats.pearsonr(x, y)
    slope, intercept = np.polyfit(x, y, 1)

    fig, ax = plt.subplots(figsize=(7, 5.5))

    ax.scatter(x, y, s=55, color="#4C6B8A", zorder=3)
    for xi, yi, qid in zip(x, y, query_ids):
        ax.annotate(
            str(qid),
            (xi, yi),
            textcoords="offset points",
            xytext=(6, 6),
            fontsize=8,
            color="#555555",
        )

    x_line = np.linspace(x.min(), x.max(), 100)
    y_line = slope * x_line + intercept
    ax.plot(x_line, y_line, linestyle="--", linewidth=1.3, color="#999999", alpha=0.6, zorder=2)

    ax.set_ylim(0, 1)
    ax.set_xlabel("Average retrieval similarity")
    ax.set_ylabel("Grounding rate")
    ax.set_title(f"r = {r:+.3f}, p = {p:.3f}, n = {n}", fontsize=10, color="#555555")
    fig.suptitle("Retrieval similarity vs. grounding rate", fontsize=13, y=0.99)
    ax.grid(True, linestyle=":", alpha=0.3)

    fig.text(
        0.5,
        0.01,
        f"Observed x range is narrow: {x.min():.3f}-{x.max():.3f} across these {n} queries.",
        ha="center",
        fontsize=8,
        color="#777777",
    )

    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    fig.savefig(output_path, dpi=DPI)
    plt.close(fig)


def plot_metrics_distribution(df: pd.DataFrame, output_path: Path) -> None:
    metrics = [
        ("grounding_rate", "Grounding rate"),
        ("semantic_consistency", "Semantic consistency"),
        ("claim_jaccard", "Claim Jaccard"),
        ("actionability_mean", "Actionability (mean)"),
    ]

    fig, axes = plt.subplots(2, 2, figsize=(9, 7.5))
    rng = np.random.default_rng(42)

    for ax, (col, label) in zip(axes.flat, metrics):
        values = df[col].to_numpy(dtype=float)
        mean = float(np.mean(values))
        sd = float(np.std(values, ddof=1))
        n = len(values)

        jitter = rng.uniform(-0.06, 0.06, size=n)
        ax.scatter(np.zeros(n) + jitter, values, s=45, color="#4C6B8A", alpha=0.8, zorder=3)

        ax.hlines(mean, -0.2, 0.2, color="#B23A48", linewidth=1.6, zorder=4)
        ax.vlines(0.2, mean - sd, mean + sd, color="#B23A48", linewidth=1.2, zorder=4)
        ax.hlines([mean - sd, mean + sd], 0.15, 0.25, color="#B23A48", linewidth=1.2, zorder=4)

        ax.set_xlim(-0.4, 0.4)
        ax.set_xticks([])
        ax.set_title(label, fontsize=10)
        ax.text(
            0.98,
            0.02,
            f"mean={mean:.3f}\nsd={sd:.3f}",
            transform=ax.transAxes,
            ha="right",
            va="bottom",
            fontsize=8,
            color="#555555",
        )
        ax.grid(True, axis="y", linestyle=":", alpha=0.3)

    fig.suptitle(f"Distribution of evaluation metrics (n={len(df)})", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(output_path, dpi=DPI)
    plt.close(fig)


def main() -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    df = load_results_dataframe()

    fig1_path = FIGURES_DIR / "retrieval_vs_grounding.png"
    fig2_path = FIGURES_DIR / "metrics_distribution.png"

    plot_retrieval_vs_grounding(df, fig1_path)
    plot_metrics_distribution(df, fig2_path)

    print(f"Wrote {fig1_path}")
    print(f"Wrote {fig2_path}")


if __name__ == "__main__":
    main()
