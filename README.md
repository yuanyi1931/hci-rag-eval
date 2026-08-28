# HCI RAG Eval

A compact Retrieval-Augmented Generation evaluation project for HCI literature. The project focuses on measuring the relationship between retrieval quality and generated output quality, with emphasis on:

- validity (grounding / faithfulness)
- reliability (consistency across repeated generations)
- actionability (how usable the insight is in research or product decisions)

## Project structure

```text
hci-rag-eval/
├── README.md
├── requirements.txt
├── config.yaml
├── .gitignore
├── main.py
├── data/
│   ├── raw/
│   │   ├── sample_abstracts.jsonl
│   │   └── abstracts.jsonl
│   ├── embeddings.npy
│   └── embeddings_ids.json
├── src/
│   ├── __init__.py
│   ├── fetch_data.py
│   ├── embed.py
│   ├── retrieve.py
│   ├── generate.py
│   ├── evaluate_validity.py
│   ├── evaluate_reliability.py
│   ├── evaluate_actionability.py
│   └── report.py
├── notebooks/
│   └── analysis.ipynb
├── outputs/
│   ├── results.csv
│   ├── manual_actionability_template.csv
│   ├── retrieval_vs_grounding.png
│   └── report.md
└── .venv/
```

## Setup

```bash
cd /path/to/hci-rag-eval
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Use the project virtual environment for all tests and Python entrypoints. In particular, run:

```bash
.venv/bin/python -m pytest
```

This avoids accidentally picking up the system or Anaconda `pytest`, which can resolve to a different environment and produce confusing failures.

Set your Anthropic API key:

```bash
export ANTHROPIC_API_KEY="your_api_key_here"
```

On Windows PowerShell:

```powershell
$env:ANTHROPIC_API_KEY="your_api_key_here"
```

## Run the pipeline

Run the default demo version (small, fast, no need to fetch the full arXiv corpus):

```bash
python main.py --demo
```

Run a lightweight real pipeline:

```bash
python main.py --max-papers 50 --queries 3 --reruns 3 --top-k 5
```

Run the full pipeline with a fetch + embed + retrieval + generation + evaluation flow:

```bash
python main.py --max-papers 100 --queries 5 --reruns 5 --top-k 5
```

## Notes

- `fetch_data.py` attempts to fetch arXiv `cs.HC` abstracts through the public API.
- `generate.py` is designed to rerun the same prompt multiple times so that reliability can be measured.
- If no Anthropic API key is configured, the generation step falls back to a deterministic demo output so the repo remains runnable for local testing and validation.
- The project keeps the evaluation logic explicit and interpretable, with formulas noted in code comments for later reporting or paper writing.

## Expected runtime

- Demo mode: a few seconds
- Small prototype: 1–5 minutes depending on model availability and network latency
- Larger full runs: can take longer because of repeated generation calls and embedding model download

## Useful extensions

- replace the default `all-MiniLM-L6-v2` embedding model with another sentence-transformer model
- compare LLM-as-judge vs a lightweight NLI model for grounding
- add more queries and measure how retrieval quality correlates with output validity
