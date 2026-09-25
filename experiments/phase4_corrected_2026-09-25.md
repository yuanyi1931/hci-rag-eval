# Phase 4 corrected re-parse: judge-vote parser fix, cache-only replay (2026-09-25)

**This file is the archival source of record for the corrected numbers.** It does **not**
replace or invalidate [experiments/phase4_2026-08-29.md](phase4_2026-08-29.md), which remains the
archival record of the original Phase 4 run and is unchanged. This file records a **re-parse**,
not a re-generation: the underlying data (retrieved papers, generated insights, and every judge
LLM's raw response text) is byte-for-byte identical to the original Phase 4 run. Only the
post-hoc parsing logic that turns a judge's raw text response into a structured vote
(`entailed`/`not_entailed`/`contradicted` for validity, `1`-`5` for actionability) was changed.
See `NOTES.md` §19 for the full narrative writeup (root cause, what changed, what did not).

- **Run date:** 2026-09-25. Same `outputs/generations.jsonl` as the original Phase 4 run
  (`generations_mtime = 2026-08-29T16:24:32.859483`, loaded via `--reuse-generations`).
- **Command:** `.venv/bin/python main.py --reuse-generations` (config defaults: 10 queries × 5
  reruns, `judge_n_votes=3`, `judge_temperature=0.0`).
- **Cost: $0.000000, 0 real API calls.** `Stage call counts: generation=0, validity=657,
  actionability=657, total=0`; `Stage cache-hit counts: generation=0, validity=657,
  actionability=657`. Every one of the 657 validity votes and 657 actionability votes was
  served from the same `data/cache/*.json` files the original Phase 4 run wrote; the new
  parsers were applied to that already-cached raw text, nothing new was ever sent to the model.
- **Config hash: `70408b230329`** — identical to the original Phase 4 run's config hash. This
  confirms the only difference between the two archived files is the parsing code in
  `src/evaluate_validity.py` / `src/evaluate_actionability.py`, not a config change.
- **Note on the report.md warning banner:** `outputs/report.md` (reproduced below) includes the
  line "WARNING: No Anthropic API calls were made. This report is not valid for evaluation."
  That warning is a generic guard meant to catch accidental all-cache-miss runs (e.g. a
  misconfigured API key) and is a **false alarm** in this specific case: zero real calls is the
  intended and verified outcome of a pure cache-replay re-parse, not a failure.
- **Why `budget.max_api_calls` was left at `1000` instead of being set to `0`:**
  `src/evaluate_validity.py::_get_judge_n_votes()` reduces `judge_n_votes` to `1` whenever
  `budget.max_api_calls < 100`, as a defensive measure for low-budget runs. Setting it to `0` as
  a literal safety net would have silently collapsed every claim/item to a single judge vote
  instead of the original 3-vote majority scheme, making the "corrected" numbers incomparable to
  the original archive. Instead, the pre-flight cache-coverage check (`/tmp/scan_cache_full.py`,
  replaying the exact same prompt/seed construction as the production code) confirmed all 1314
  votes would be cache hits *before* running `main.py`, and the actual run's printed stage
  counts (`total=0` real calls) verified this held true in practice.

## Result summary (vs. original Phase 4)

| Metric | Original (phase4_2026-08-29.md) | Corrected (this file) |
|---|---|---|
| Mean grounding rate | 0.578 | 0.595 |
| Mean reliability score | 0.516 | 0.516 (unchanged) |
| Mean actionability score | 2.470 | 2.470 (unchanged) |
| Validity votes unparseable | 158 / 657 (24.05%) | 141 / 657 (21.46%) |
| Actionability votes unparseable | 0 / 657 (0.00%) | 0 / 657 (0.00%, unchanged) |
| Pearson r (avg_retrieval_similarity vs grounding_rate), n=10 | r = +0.222, p = 0.537 | r = +0.137, p = 0.705 |

Full numeric detail, including which 4 of 219 claims flipped their grounding verdict and why the
141 remaining unparseable votes are a genuine (not a parser) limitation, is in `NOTES.md` §19.

=== results.csv ===

```
query_id,query,average_retrieval_similarity,grounding_rate,citation_validity_rate,reliability_score,semantic_consistency,claim_jaccard,confidence_sd,confidence_cv,krippendorff_alpha,actionability_mean,top_papers,provenance_model_name,provenance_api_calls,provenance_execution_time_seconds,provenance_config_hash,provenance_generation_calls,provenance_validity_calls,provenance_actionability_calls,provenance_reuse_generations,provenance_generations_mtime
1,How can interactive systems support reflective learning and long-term behavior change in everyday digital work?,0.36603771448135375,0.42857142857142855,0.9682539682539683,0.4691389906974066,0.8263732194900513,0.11190476190476191,0.028809720581775892,0.03674709257879578,0.536,2.0476190476190474,"['2008.04811v1', '2012.13961v1', '2008.02582v1', '2006.00372v2', '2007.10897v1']",claude-sonnet-4-6,0,62.226,70408b230329,0,657,657,True,2026-08-29T16:24:32.859483
2,What design patterns improve trust calibration in human-AI collaboration for high-stakes decisions?,0.35859825611114504,0.4782608695652174,1.0,0.5911877994877952,0.8902327418327332,0.29214285714285715,0.01341640786499875,0.016687074458953666,1.0,2.652173913043478,"['1904.13333v1', '2012.13603v1', '2006.00372v2', '1904.08066v1', '2005.13714v1']",claude-sonnet-4-6,0,62.226,70408b230329,0,657,657,True,2026-08-29T16:24:32.859483
3,How do accessible interfaces and inclusive participatory design improve digital service engagement across diverse users?,0.27632897198200224,0.45,1.0,0.49050476125308445,0.8238666653633118,0.15714285714285714,0.021908902300206666,0.028980029497627863,1.0,2.45,"['2006.00372v2', '2008.02582v1', '1904.13333v1', '1904.08009v1', '2008.04811v1']",claude-sonnet-4-6,0,62.226,70408b230329,0,657,657,True,2026-08-29T16:24:32.859483
4,What evidence suggests that subtle friction can improve habit formation and sustainable digital routines?,0.25247651934623716,0.7368421052631579,1.0,0.4968370552416201,0.8501555919647217,0.14351851851851852,0.017320508075688787,0.021786802610929287,1.0,2.5789473684210527,"['2006.00372v2', '2008.04811v1', '1904.08009v1', '2012.12041v1', '2012.13961v1']",claude-sonnet-4-6,0,62.226,70408b230329,0,657,657,True,2026-08-29T16:24:32.859483
5,How can AI systems support shared mental models and team coordination in collaborative work?,0.3435986012220383,0.9523809523809523,1.0,0.4696574066366468,0.8000290989875793,0.1392857142857143,0.0,0.0,1.0,2.857142857142857,"['1904.13333v1', '1904.08066v1', '2007.10897v1', '2005.13714v1', '2012.13961v1']",claude-sonnet-4-6,0,62.226,70408b230329,0,657,657,True,2026-08-29T16:24:32.859483
6,What features make decision-support tools understandable and actionable for expert users?,0.35926724076271055,0.4166666666666667,1.0,0.6138000193096342,0.843076229095459,0.3845238095238095,0.008944271909999111,0.010961117536763616,1.0,2.5833333333333335,"['2005.13714v1', '2012.13603v1', '2008.03550v1', '1904.13333v1', '2012.12041v1']",claude-sonnet-4-6,0,62.226,70408b230329,0,657,657,True,2026-08-29T16:24:32.859483
7,How do multimodal feedback and adaptive interfaces improve user experience in complex task environments?,0.3875570297241211,0.8695652173913043,0.9782608695652174,0.5619461352106124,0.8798049688339233,0.24408730158730158,0.013416407864998751,0.017069221202288484,0.536,2.5652173913043477,"['2006.00372v2', '2007.10897v1', '2008.02582v1', '1904.13333v1', '2012.12041v1']",claude-sonnet-4-6,0,62.226,70408b230329,0,657,657,True,2026-08-29T16:24:32.859483
8,What design principles support transparent and accountable AI-assisted workflows in professional settings?,0.26230217814445494,0.7142857142857143,1.0,0.4747575731504531,0.8072532415390015,0.14226190476190476,1.2412670766236366e-16,1.5324284896588104e-16,1.0,2.2857142857142856,"['1904.13333v1', '1904.08066v1', '2008.03550v1', '2012.13961v1', '2006.00372v2']",claude-sonnet-4-6,0,62.226,70408b230329,0,657,657,True,2026-08-29T16:24:32.859483
9,How can HCI research methods help evaluate long-term adoption and behavior change in digital products?,0.19739797115325927,0.4,0.9866666666666667,0.5149975407691229,0.8180903196334839,0.21190476190476187,1.2412670766236366e-16,1.5324284896588104e-16,0.7211538461538461,2.36,"['2012.13603v1', '2006.00372v2', '2008.04811v1', '2008.03550v1', '2008.02582v1']",claude-sonnet-4-6,0,62.226,70408b230329,0,657,657,True,2026-08-29T16:24:32.859483
10,"What are the most promising directions for trustworthy, human-centered generative AI interfaces in knowledge work?",0.37388083934783933,0.5,1.0,0.48112334523882183,0.8283181190490723,0.13392857142857142,0.016733200530681485,0.020063789605133674,1.0,2.3181818181818183,"['1904.13333v1', '2007.09989v1', '1905.01984v1', '2012.13603v1', '2008.03550v1']",claude-sonnet-4-6,0,62.226,70408b230329,0,657,657,True,2026-08-29T16:24:32.859483
```

=== report.md ===

```
# HCI RAG Evaluation Summary

> WARNING: No Anthropic API calls were made. This report is not valid for evaluation. Please configure ANTHROPIC_API_KEY in .env and rerun the pipeline.
> (See "Note on the report.md warning banner" above — this is expected for a cache-only re-parse.)

This report compares retrieval quality with generation quality using the configured pipeline run.

## Provenance

- Model: claude-sonnet-4-6
- API calls: 0
- Generation calls: 0
- Validity calls: 657
- Actionability calls: 657
- Generation calls (total invocations): 0
- Generation calls served from cache: 0
- Generation calls newly made via API: 0
- Query IDs fully served from a previous run's cache: none
- Execution time, active (s): 62.226
- Wall-clock start: 2026-09-25T22:31:06.683726+00:00
- Wall-clock end: 2026-09-25T22:32:08.909541+00:00
- Wall-clock elapsed (s): 62.226
- Reused generations file: True
- Generations file mtime: 2026-08-29T16:24:32.859483
- Config hash: 70408b230329

## Key metrics

- Queries evaluated: 10
- Mean grounding rate: 0.595
- Mean reliability score: 0.516
- Mean actionability score: 2.470

## Interpretation

- Higher average retrieval similarity does not guarantee better grounding if the retrieved papers are too broad or loosely related.
- Reliability is most informative when repeated generations are compared using the same retrieval context and prompt.
- Actionability captures whether the output is usable for a research or product decision, not just whether it is descriptive.
```
