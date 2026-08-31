# Statistical validation notes

This document records the methodological checks and corrective history for the reliability statistics used in this project. It is intended as a neutral technical record for later reporting and method sections. It is written without exaggeration and without omitting the earlier failures and incorrect assumptions.

## 1. ICC(2,1) axis-orientation bug

In the original implementation, `msr` was computed from "between rows," but the axis convention in effect at the time actually had rows = rater, not rows = item/target. As a result, the implementation computed the between-rater mean square, not the between-subject mean square defined by Shrout & Fleiss.

At the same time, the `k` and `n` in the denominator assumed the opposite axis convention: the same function mixed two different conventions at once, which made the output look numerically reasonable while answering the wrong question.

Before the fix, running Shrout & Fleiss (1979) Table 1 data produced:

- Original orientation (6 rows target × 4 columns judge): 0.161
- Transposed: 0.743
- Correct value: 0.290

Cross-checking against pingouin's full output shows these two incorrect numbers are each close to:

- `ICC(1,1) = 0.166`
- `ICC(C,1) = 0.715`

In other words, the faulty implementation was not producing random numbers — it was computing a different ICC variant. The values fell within a plausible range, but answered a different statistical question. This class of bug is not caught by a "does the result look reasonable" check.

Fix: standardized on rows = items/targets, columns = raters, and stated this convention explicitly in the docstring to prevent axis mixing.

## 2. Early return caused tests to lose their verification power

`icc_2_1` and `krippendorff_alpha` originally both had a perfect-agreement shortcut at the top of the function.

The two corresponding tests used perfectly identical data, so they hit the shortcut directly and returned `1.0`; the formula body itself was never executed. The tests passed, but they did not verify anything.

On derivation, both shortcuts turned out to be redundant:

- ICC: when every row is constant, `ss_error = 0` and `ss_cols = 0`, so `mse = 0` and `msc = 0`, and the numerator and denominator both converge to `msr`, giving a result of `1.0`.
- Krippendorff: when there is no mismatch, `D_o = 0`, so `alpha = 1`.

After removing the shortcuts, the original tests were renamed to `*_formula_converges_to_one`, and now genuinely verify the formula's convergence behavior at the boundary condition, instead of bypassing the formula.

## 3. Krippendorff's alpha was missing the finite-sample correction

The original implementation's expected disagreement used:

- `1 - Σ(n_c / n)^2`

But Krippendorff (2004)'s definition is:

- `(n^2 - Σ n_c^2) / (n(n - 1))`

Without the `(n - 1)` correction, the metric is actually closer to Scott's pi, and systematically underestimates alpha. This is not a minor difference — it is a deviation at the level of the definition itself.

The original docstring claimed to follow Krippendorff (2004), but the implementation did not match that definition; this inconsistency was identified and fixed during validation.

## 4. ICC naming convention cross-reference

This project uses Shrout & Fleiss (1979) naming; `pingouin` uses McGraw & Wong (1996) naming instead:

| Shrout & Fleiss | McGraw & Wong / pingouin | Model |
|---|---|---|
| ICC(1,1) | ICC(1,1) | One-way random effects |
| ICC(2,1) | ICC(A,1) | Two-way random effects, absolute agreement |
| ICC(3,1) | ICC(C,1) | Two-way mixed effects, consistency |

The rationale for choosing `ICC(2,1)` / `ICC(A,1)` in this project is as follows:

- The reliability analysis in this project measures numeric consistency across multiple generations of the same prompt, not merely rank-order consistency.
- Each generation output is treated as the "rating" of one rater; these "raters" are random sources sampled from all possible generation outputs, not fixed, specific raters.
- What we care about is whether the numeric values themselves agree (absolute agreement), not merely whether the ranking agrees (consistency).
- If two raters give different absolute scores, even with the same ranking, that still represents a different measurement outcome; this is a meaningful difference for evaluating generation quality.

Therefore, for this project, `ICC(2,1)` / `ICC(A,1)` is the choice that better fits the research question.

## 5. Cohen's kappa expected-value source problem

The expected value `0.40` in the test was at one point labeled as Cohen (1960)'s worked example, but the corresponding page, table, and confusion matrix could not be verified. Cohen (1960)'s main worked example commonly produces a result of `0.492`, while `0.40` is close to the lower bound of moderate agreement (`0.41`) in the Landis & Koch (1977) interpretation scale, so it is suspected the two were confused.

This error has been fixed: it is no longer claimed to come from Cohen (1960)'s literature example, and is instead labeled explicitly as a hand-calculated example.

The 2×2 matrix currently used is:

[[4, 1], [2, 3]]

Where:

- yes/yes = 4
- yes/no = 1
- no/yes = 2
- no/no = 3

The corresponding hand calculation is:

- `p_o = (4 + 3) / 10 = 0.70`
- `p_e = ((5/10) * (6/10)) + ((5/10) * (4/10)) = 0.50`
- `kappa = (p_o - p_e) / (1 - p_e) = (0.70 - 0.50) / (1.00 - 0.50) = 0.40`

This version is explicitly labeled as a hand calculation rather than a literature citation, so readers can verify the arithmetic themselves and are not misled into thinking the value has literature backing.

## 6. Current test coverage and sources

There are currently 10 tests, organized by source type as follows:

1. `test_icc_2_1_shrout_fleiss_1979_table_1` — published literature (Shrout & Fleiss Table 1)
2. `test_icc_2_1_perfect_agreement_formula_converges_to_one` — formula property (boundary condition)
3. `test_icc_2_1_random_like_data_near_zero` — formula property / sanity check
4. `test_icc_2_1_matches_pingouin_intraclass_corr` — independent-package cross-validation
5. `test_krippendorff_alpha_perfect_agreement_formula_converges_to_one` — formula property (boundary condition)
6. `test_krippendorff_alpha_random_like_data_near_zero` — formula property / sanity check
7. `test_jaccard_similarity_hand_calculated` — hand-calculated derivation
8. `test_krippendorff_alpha_level_not_nominal_raises` — spec constraint / unsupported case
9. `test_krippendorff_alpha_shape_error_message_is_generic` — validation behavior / input shape check
10. `test_cohens_kappa_hand_calculation_example` — hand-calculated derivation (explicit matrix and arithmetic)

The importance of this combination is that it does not rely on a single source alone:

- there is a literature benchmark
- there is independent-implementation cross-validation
- there are logical-property checks
- there is hand-calculated verifiability

This makes the validation more robust, and less easily masked by a single incorrect assumption.

## 7. Environment notes

Tests must be run with `.venv/bin/python -m pytest`, not directly with the system or Anaconda `pytest`.

The Anaconda environment on the system makes `which pytest` point to `/opt/anaconda3/bin/pytest`, which puts pytest and the package under test in different interpreters. In this situation, the `pingouin` cross-validation can be skipped for no apparent reason, producing the false appearance that "the tests look inconsistent." This is an environment bug, not a statistical bug.

This issue was identified during validation, and the project convention now explicitly requires running tests with the Python inside the virtual environment.

## Conclusion

The validation history of this project's statistics module revealed several real and critical problems:

1. The ICC axis-orientation bug changed the statistical question itself.
2. The early return left the tests unable to verify the formula.
3. Krippendorff's alpha was missing the finite-sample correction, so the definition and implementation did not match.
4. ICC naming conventions need to be explicitly cross-mapped, to avoid confusion with pingouin's output.
5. The source of Cohen's kappa's expected value needs to be labeled explicitly according to the literature and a verifiable calculation, not an unverified citation.

Current status: after the fixes, the statistics module passes its tests in the correct environment, and its validation record is sufficient to serve as the methods section for a later research report.

## Smoke-test observation (2026-08-28)

- During the 3×3 smoke run we observed a counterintuitive pattern: the query with the lowest average retrieval similarity (Query 3: 0.276) had the highest grounding rate (0.692). With only three queries this is anecdotal, not conclusive, but it directly challenges the simple hypothesis that "higher retrieval similarity implies better grounding" and is worth highlighting in the limitations/discussion section of the report.

Recorded (summary): Query 1 avg_sim=0.366 grounding=0.333; Query 2 avg_sim=0.359 grounding=0.667; Query 3 avg_sim=0.276 grounding=0.692.

Note: earlier runs returned `reliability_score = None` due to a data-structure mismatch between `generate_insights()` (which returns parsed JSON objects) and `evaluate_reliability()` (which expects records from `outputs/generations.jsonl` where the parsed payload is under the `parsed_json` key). That contract was fixed and validated; per-query reliability can be computed when the evaluator receives the logged JSONL records.

<!-- Removed: previous note about identical overall_confidence values — diagnostic in progress. -->

Diagnostic post-mortem (added 2026-08-28):

- The original `reliability_score = None` observed earlier was a real bug: `main.py` previously passed `generate_insights()`'s raw parsed JSON objects directly into `evaluate_reliability()` rather than the expected `record` format where each item is a wrapper dict containing `parsed_json`. This is a repeated interface mismatch problem (first seen between `retrieve`→`generate`, then here between `generate`→`evaluate`). The codebase was updated to enforce and validate the record contract and fail fast on mismatch.

- The previously-reported `confidence_sd = 1.36e-16` and `claim_jaccard = 0.0` were NOT actual pipeline bugs. They were produced by an independent diagnostic probe script that mistakenly mixed records from multiple queries (it did not filter by `query_id`) and computed statistics on the combined set. The pipeline, when run with the proper per-query records, yields `confidence_sd ≈ 0.0351` and `claim_jaccard ≈ 0.6667` for Query 1.

- Lesson learned: ad-hoc probes that take a different code path or a different input filtering strategy can produce misleading evidence. Diagnostic helpers should operate on the exact production execution path (or be invoked from inside it), and debug output should be controlled (logger + flag) so that reproductions are consistent.

## 8. Repeated record-shape mismatch across pipeline stages

The same interface contract bug reappeared in a second and then a third stage, even after earlier fixes: the system mixed two different payload shapes for the same data.

1. retrieve → generate: the retrieval layer was returning documents with id/title/score metadata, but the prompt builder expected the richer `title + abstract` record structure needed to ground the generation request.
2. generate → evaluate_reliability: `generate_insights()` emitted record wrappers like `{query_id, run_index, parsed_json, ...}`, but `evaluate_reliability()` still assumed it received a raw parsed JSON object or a flattened dict without the `parsed_json` envelope.
3. generate → evaluate_validity / evaluate_actionability: the same issue reappeared when the validity and actionability evaluators still read `output["insights"]` instead of `output["parsed_json"]["insights"]`. This led to empty outputs and zero judge counts even though the JSONL generation file itself was correct.

The underlying cause was not a statistical bug but a data-contract mismatch: each stage used the same conceptual object but at different layers of the message format. The fix was to validate the input shape at stage boundaries and raise a `ValueError` when the contract is broken instead of silently returning zeros.

Why the tests missed it:

- no test exercised the real inter-module boundary; they only called each evaluator with synthetic dicts shaped like the old format or a happy-path in isolation;
- the generation contract test covered `generate_insights()` itself, but not the downstream call sites that consume the record wrappers;
- the bug was effectively hidden because the invalid input path returned empty results rather than throwing, so the failure mode looked like a scoring issue instead of an interface violation.

This is the key lesson: pipeline tests must validate input/output contracts between modules, not just each module in isolation.

Update (2026-08-29):

- This exact contract drift has now appeared three times (`retrieve -> generate`, `main -> evaluate_reliability`, `main -> evaluate_validity/actionability`).
- The common pattern is that one module upgrades to a wrapper record shape while downstream modules still parse legacy payload fields directly.
- The reason tests missed all three is the same: there were no boundary contract tests that assert the exact cross-module payload schema at handoff points.
- Isolated unit tests passed because they used synthetic happy-path inputs and did not exercise the real handoff objects flowing through the pipeline.

## 9. Test suite polluting production `outputs/` directory

`tests/test_generate_contract.py` called `generate_insights()` without redirecting the module-level `OUTPUT_PATH` constant in `src/generate.py`. Because that constant defaults to the real `outputs/generations.jsonl`, running the test suite silently overwrote the production generation log — a 25-record clean dataset was reduced to 3 stray records (`query_id` 1 and 99) purely as a side effect of running `pytest`.

The test had a `tmp_path` fixture parameter, which created a false sense of isolation: the fixture existed but was never actually wired into the code path that performed the write. Declaring `tmp_path` does nothing by itself — it must be used to monkeypatch or redirect the exact constant/path the code under test writes to.

Fix: added an autouse fixture in `tests/conftest.py` that monkeypatches `src.generate.OUTPUT_PATH` to a path under `tmp_path` for every test, so no test can write to the real `outputs/` directory regardless of whether it remembers to do so explicitly. Added `tests/test_outputs_dir_protection.py`, which snapshots `(mtime_ns, size)` for every file under the real `outputs/` before and after running `generate_insights()` and asserts the snapshots are identical, as a regression guard against this exact failure mode recurring silently.

Lesson: an unused fixture parameter is not isolation. Verify that monkeypatched paths are actually consumed by the code path under test, and add an explicit regression test that asserts production artifacts are untouched, rather than trusting that "using tmp_path" implies safety.

## 10. Conflating contract violations with legitimate degraded runtime states

After fixing the record-shape contract in `evaluate_validity`/`evaluate_actionability` (see §8), a fresh full 5×5 pipeline run crashed with `ValueError: ... missing a valid 'parsed_json' object. Found type=str`. The crash was triggered by a genuine `parse_failure` sentinel record (a legitimate, expected runtime state when the LLM's JSON output failed to parse) being treated identically to a structurally malformed record (a genuine contract violation, e.g. a missing `parsed_json` key entirely or a non-dict record).

Both evaluators originally raised on any record where `parsed_json` was not a dict, without distinguishing "key is absent / record is the wrong type" (a real interface bug that should fail fast) from "key is present but its value is the `parse_failure` sentinel" (an expected degraded state that should be counted and skipped, not raised on). `evaluate_reliability.py` already had this distinction correctly implemented; `evaluate_validity.py`/`evaluate_actionability.py` did not.

Fix: `_normalize_generated_records()` in both evaluators now raises only for missing `parsed_json` key or non-dict records, and silently skips + increments a `parse_failures` counter (surfaced as `n_parse_failures` in the return dict) when `parsed_json` is present but not a dict.

Lesson: strict fail-fast validation must be scoped precisely to the actual contract (key presence and record shape), not to every value that looks "unexpected." Conflating the two makes the validation brittle against legitimate edge-case data that the rest of the pipeline is explicitly designed to produce and handle.

## 11. Cache-hit legitimacy verification (2026-08-29)

Concern: in the first clean 5×5 run, `llm_client` reported `api_calls=240` against `312 + 312` validity/actionability stage invocations (624 total) plus `28` generation invocations (`652` total stage invocations), with `412` cache hits. The worry was that generation reruns might be collapsing into the same cache key (i.e., `run_index` not actually being part of the cache key), which would silently defeat the "5 independent reruns" experimental design.

Verification: added per-stage cache-hit counters (`_STAGE_CACHE_HIT_COUNTS`, exposed via `get_stage_cache_hit_counts()`) alongside the existing per-stage call counters, then re-ran the pipeline with `--reuse-generations` (which by construction invokes the generation stage zero times — `generate_insights()` is never called). Result:

```
Stage call counts: generation=0, validity=312, actionability=312, total=0
Stage cache-hit counts: generation=0, validity=312, actionability=312
LLM usage summary: calls=0, cache_hits=624, ...
```

All 624 cache hits are attributable to the validity/actionability (judge) stages; zero to generation, because generation was not invoked at all in this run. This confirms the judge stages' cache hits are legitimate repeated-claim/repeated-vote lookups, not generation-rerun collisions. This is also structurally guaranteed by design: `make_cache_key()` includes `run_index`, `generate.py` computes a per-attempt-unique `run_index = run_index * 10 + attempt`, and the judge prompts (claim + source text) are entirely different content from generation prompts, so a cache collision between the two stages is not possible.

Also confirmed: `semantic_consistency` across the 5 queries in the reuse-generations recompute is `0.826, 0.890, 0.824, 0.850, 0.800` — none near `1.0`, which is additional evidence against the "reruns collapsed into one" hypothesis (a collapse would drive semantic consistency close to 1.0 for every query).

## 12. Documented hallucination case: query 1, run_index=1

`citation_validity_rate` for query 1 is `0.968`; all other queries are `1.0`. Root-caused via a script that filters `outputs/generations.jsonl` to `query_id == 1` and checks each insight's `supporting_paper_ids` against the query's actual top-5 retrieved ids.

Query 1 top-5 retrieved paper ids: `2008.04811v1, 2012.13961v1, 2008.02582v1, 2006.00372v2, 2007.10897v1`.

In `run_index=1`, two separate claims cite `2008.03582v1`, which is **not** in the retrieved set:

- claim: "Bridging the gap between remote or isolated participants and shared social or physical experiences is a recurring design challenge." — `supporting_paper_ids: ['2008.03582v1', '2007.10897v1', '2008.04811v1']`
- claim: "Exploratory and user-centered study designs are predominant, reflecting early-stage investigation of novel interaction paradigms." — `supporting_paper_ids: ['2008.04811v1', '2006.00372v2', '2008.03582v1']`

Both hallucinated citations are the same wrong id, `2008.03582v1`, which differs from the real retrieved id `2008.02582v1` by a single transposed/incremented digit (`035` vs `025`). This strongly suggests the model confused two visually similar arXiv identifiers rather than fabricating a citation from nothing — a plausible and specific failure mode worth noting for the discussion section (near-miss ID confusion vs. pure invention).

Two points worth emphasizing:

1. `2008.03582v1` is a **near-neighbor confusion**, not an invented-from-nothing id: it is a well-formed, plausible-looking arXiv identifier that differs from the real retrieved `2008.02582v1` by a single digit. This is a qualitatively different failure mode from fabricating a nonexistent-format citation, and matters for how this class of error should be characterized in the write-up.
2. This case was caught entirely by the deterministic, code-only citation-id check (`citation_validity_rate`) — no LLM call, no cost, no dependence on judge reliability. It demonstrates the value of the two-layer validity design: a cheap deterministic check can catch failure modes that an LLM judge might not reliably flag on its own (the judge is asked about claim-entailment, not id-membership in the retrieved set).

## 13. Retrieval similarity vs. grounding rate correlation (2026-08-29, n=5)

Computed `scipy.stats.pearsonr` between `average_retrieval_similarity` and `grounding_rate` across the 5-query results.csv (values below, from the `--reuse-generations` recompute):

| query_id | avg_sim | grounding_rate |
|---|---|---|
| 1 | 0.3660 | 0.4286 |
| 2 | 0.3586 | 0.4783 |
| 3 | 0.2763 | 0.4500 |
| 4 | 0.2525 | 0.7368 |
| 5 | 0.3436 | 0.9524 |

Result: **r = -0.147, p = 0.813** (n=5).

This is directionally consistent with the earlier 3×3 smoke-test observation (§ "Smoke-test observation (2026-08-28)": lowest-similarity query had the highest grounding rate there too), but the magnitude is notably weaker than an earlier expectation of `r ≈ -0.35` for this same dataset — that stronger figure is not reproduced by this computation and should not be cited without re-deriving it; `-0.147` is the actual computed value from the current `results.csv`. With `n=5` and `p=0.81`, this is not a statistically significant result and cannot support any causal or even correlational claim on its own.

The figure -0.35 came from an uncalculated visual estimate made during conversation; the actual computed value is -0.147. This is a case recorded in this project where a seemingly well-founded number came from an unreliable derivation process — structurally the same class of validity problem this study is trying to quantify.

One possible (unvalidated) explanation, offered as a hypothesis and not a finding: when retrieved papers are topically similar to each other (high average similarity), the model may tend toward cross-paper synthesis, producing more abstract claims that are harder to attribute to any single source paper and thus harder for the judge to mark as grounded. When retrieved papers are more topically dispersed (low average similarity), the model may be forced to make more paper-by-paper statements that stay closer to each source's original text and are therefore easier to judge as grounded. This has not been tested and should not be treated as established; it is recorded here only as a candidate explanation to investigate if/when the query set is expanded beyond n=5.

## 14. Phase 4 (10×5) provenance audit: cache-hit split and retry/rate-limit check

Two verification questions were raised before allowing the project to move to the reporting phase, both answered empirically against the run log (`/tmp/pipeline_full10.log`, produced with `--debug`) rather than assumed.

**Cache-hit split.** `main.py`'s printed `Stage cache-hit counts: generation=28` out of `Stage call counts: generation=53`. Cache keys are derived from `{model, prompt, temperature, run_index}`, so any query whose text, temperature (0.7), and run_index sequence already existed in `data/cache/` from the earlier 5×5 run (Phase 3, queries 1–5) is served without a new API call. Cross-checking `outputs/generations.jsonl` timestamps confirms this directly: queries 1–5 (25 records) each have all 5 `run_index` timestamps clustered within ~20–30ms of each other per query — far too fast to be real network round-trips — while queries 6–10 (25 records) show ~10–12s spacing between consecutive `run_index` values, consistent with genuine API latency. Conclusion: **all 25 records for queries 1–5 were served from the Phase 3 cache; only queries 6–10 (25 records) were newly generated in Phase 4.** This should be stated plainly wherever Phase 4 is described: the run performed 25 new generation calls, not 50.

The generation-stage call count of 53 (not 50) and cache-hit count of 28 (not 25) are 3 higher than the naive record count on both sides; 53 − 28 = 25 real calls either way, so the reconciliation is internally consistent. The extra 3 invocations are attributed to `generate.py`'s parse-retry path (a malformed/non-JSON response triggers a same-run_index retry, which counts as an additional stage invocation and cache lookup, but does not create an additional final record) — this matches the one documented `parse_failure` case (query_id=4) plus at least two silently-recovered retries. This has not been traced line-by-line to specific timestamps and is recorded as the best-available explanation, not a proven one.

**429 rate-limit check.** Extracting the literal HTTP status code from every `HTTP Request: POST ... "HTTP/1.1 <code>"` log line gives:

```
706 200
  1 503
```

Zero HTTP 429 responses occurred during the run. The earlier naive `grep -c "429"` (38 matches) and `grep -ciE "rate.?limit"` (1517 matches) are false positives: they match substrings inside embedding-vector floats (e.g. `0.429...`), idempotency keys (`...-8429-...`), and the `anthropic-ratelimit-*` response *headers* that Anthropic sends on every single response regardless of whether a limit was ever hit. The only non-200 response in the entire log is a single transient `503` that succeeded on the SDK's internal retry. **429 rate-limiting was not a factor in the 44.8-minute vs 13–15-minute runtime deviation.**

**The actual cause of the runtime deviation (new finding).** Comparing the wall-clock timestamps embedded in `outputs/generations.jsonl` across queries shows the real elapsed time of the run was **not** 44.8 minutes. Query 6 finishes at 16:55:16 and query 7 begins at 16:59:36 (a normal ~4m20s gap, consistent with the judge-evaluation calls for query 6 running in between). But query 7 finishes at 17:00:21 and query 8 does not begin until **23:14:50 — a gap of roughly 6 hours 14 minutes**, with smaller ~3–4 minute gaps between the remaining queries. The reported `provenance_execution_time_seconds = 2687.779` (44.8 min) clearly excludes this multi-hour gap, which is only visible in the raw timestamps, not in the reported duration.

The most likely explanation: `main.py` measures duration with `time.perf_counter()`, a monotonic clock that on macOS does not advance (or advances inconsistently) while the machine is asleep/suspended. This run was launched as a long, unattended background process; the laptop most likely went to sleep for several hours partway through and woke up later, resuming the same process. The monotonic timer picked up roughly where it left off, so the *reported* execution time reflects only the active/awake portion of the run, while the *real* wall-clock span (first request to last request) was closer to 6.5 hours.

This means the "3× deviation" framing given earlier (44.8 min vs 13–15 min estimate) is itself based on an unreliable metric for this particular run — the true wall-clock span was roughly 26–30× the estimate, not 3×, though the *productive* (awake) compute time may genuinely be close to the reported 44.8 minutes. Practical takeaway for scaling: the real bottleneck for long unattended runs on a laptop is **system sleep during background execution**, not API rate limiting. Future large-scale runs should either run on a machine/server that does not sleep, or wrap the invocation with `caffeinate` (macOS) to prevent suspension, and should log a wall-clock start/end timestamp pair (not just monotonic elapsed seconds) so this class of discrepancy is visible without needing to reconstruct it from per-record timestamps after the fact.

## 15. [Correlation results are inconsistent across three runs]

Three independent runs at three different scales have now each produced a Pearson correlation between `average_retrieval_similarity` and `grounding_rate`, and the three results disagree in direction and are all statistically non-significant:

| Run | n | r | p |
|---|---|---|---|
| 3×3 smoke test | 3 | direction negative (qualitative only — lowest-similarity query had the highest grounding rate; no r computed for n=3) | — |
| 5×5 | 5 | −0.147 | 0.813 |
| 10×5 | 10 | +0.222 | 0.538 |

All three p-values are far above the conventional 0.05 threshold, and the sign of the correlation flips between the 5×5 and 10×5 runs. **This should be reported as a genuine null/inconsistent result and must not be spun as evidence of a trend in either direction** — there is no reliable, reproducible relationship between retrieval similarity and grounding rate detectable under this experimental setup at these sample sizes.

Design-limitation caveat: across the 10 queries in the largest run, `average_retrieval_similarity` only ranges from 0.197 to 0.388 (sd = 0.065) — a narrow band that may simply be too small to produce a detectable effect on grounding rate even if a real relationship exists. Properly testing this hypothesis would require deliberately constructing a query set with much larger spread in retrieval quality (e.g. some queries designed to retrieve highly on-topic papers, others designed to retrieve marginally relevant ones), rather than relying on the incidental similarity range that happens to occur across a small set of naturally-chosen queries.

## 16. [Three subtypes of citation hallucination]

Across n=10 (50 generation records), exactly 3 citation hallucinations were found, and all 3 are **near-neighbor arXiv-id confusions with zero outright fabrications** — in every case the cited id is a real, well-formed arXiv identifier, just not one of the retrieved top-k papers, and it differs from an actually-retrieved id by a single small edit:

- **Digit swap**: `2008.03582v1` → `2008.02582v1`
- **Version suffix**: `2006.00372v1` → `2006.00372v2`
- **Year prefix**: `2005.02582v1` → `2008.02582v1`

arXiv identifiers follow a rigid `YYMM.NNNNN` + `vVERSION` structure, and this structure appears to make single-position digit or version errors especially plausible for the model to produce — the hallucinated id "looks" exactly as legitimate as the correct one, follows the same format, and could easily belong to some other real paper. This is precisely the failure mode an LLM-judge-based check might miss, since nothing about the hallucinated citation looks wrong in isolation; it requires knowing the *exact* set of ids that were actually retrieved for that query to catch it.

This is exactly what `citation_validity_rate` does: a pure deterministic top-k membership check (is the cited id literally in the retrieved set for this query?) catches all 3 cases with 100% reliability, at zero additional API/judge cost. This validates the project's two-layer validity design — the cheapest layer (no LLM call at all) catches the hardest-to-detect error type, while the more expensive LLM-judge layer is reserved for genuinely subjective judgments (e.g., is a claim actually supported by the cited text) that a deterministic check cannot make.

## 17. Phase 3 (5×5) raw results were lost before an archiving convention existed

The Phase 3 5×5 run's `outputs/results.csv` and `outputs/report.md` were overwritten by the Phase 4 10×5 run (and, unrelatedly, overwritten again later by a `--reuse-generations` smoke test run) before any raw export equivalent to `experiments/phase4_2026-08-29.md` was ever created for that run. At the time Phase 3 completed, the project had no convention of archiving a run's raw output outside of `outputs/`, which is a regenerable working directory that any later invocation of `main.py` is expected to overwrite.

The only Phase 3 5×5 numbers that survive are the ones already embedded in this file as dev notes: §11 (cache-hit legitimacy check: `generation=0, validity=312, actionability=312` stage counts, `624` cache hits, per-query `semantic_consistency` values) and §13 (the 5-query `average_retrieval_similarity` / `grounding_rate` table and the `r = -0.147, p = 0.813` correlation). These are real, computed numbers — not fabricated — but they were captured as narrative dev-notes text, not as a structured, non-regenerable archive file the way Phase 4's export is. Where the README cites 5×5 numbers, it must attribute them to "development notes (NOTES.md §13)," not to an archived experiment file, since no such file exists for Phase 3.

This is the same class of data-integrity failure already recorded twice in this document: §9 (the test suite silently overwriting production `outputs/generations.jsonl` because no path redirection was wired in) and the smoke-test overwrite of `outputs/report.md` noted when archiving Phase 4. In all three cases, a regenerable working artifact was treated, even briefly, as if it were durable, and got silently clobbered by a later, unrelated execution.

Lesson: experiment outputs should be archived immediately after the run that produced them, not deferred until the numbers are needed for a report. `outputs/` must be treated as scratch space that any run can and will overwrite; anything meant to be cited later needs to be copied out of it before the next invocation of the pipeline, not after.

## 18. Design decisions from the original specification (PROMPT.md) not carried into the implementation or documented elsewhere

`PROMPT.md`, the original Chinese-language project specification given to build this pipeline, was removed from the repository once it was confirmed to be superseded by the actual implementation (documented throughout this file) and by `README.md`. Its content was checked against both before removal. Two design decisions and one piece of stated rationale from that specification were not otherwise recorded anywhere, and are preserved here.

**Two query-source modes were designed, but only one was built.** The specification called for a config-switchable `query_mode` with two options: `held_out` (randomly sample a subset of the corpus to serve as queries, and exclude those same papers from the retrieval pool, so a query cannot trivially retrieve itself) and `manual` (a fixed list of hand-written topic sentences, specified as the default). Only `manual` was ever implemented — `config.yaml` has no `query_mode` field at all, and `src/retrieve.py` contains no pool-exclusion logic for held-out queries. The held-out mode was dropped at some point during implementation without this simplification being recorded as a deliberate decision anywhere else.

**The 3–5 insight range per generation was chosen for cross-run comparability.** `generate.py`'s prompt requires `'insights' must be a list of 3-5 objects`, matching the original specification. The rationale given in the specification, not restated anywhere else in this project: requesting a roughly fixed number of insights per run is intended to make cross-run comparison easier, since the reliability metrics (semantic consistency, claim-level Jaccard overlap, confidence ICC) all compare the insights produced by different reruns of the same query against each other.

**The actionability rubric's original 5-point wording was condensed before it reached the judge prompt.** The specification's rubric was:

| Score | Definition |
|---|---|
| 1 | Purely descriptive — restates what the paper does, with no way to act on it |
| 2 | Points to a general direction, but not concrete enough to plan around |
| 3 | Points to an identifiable research gap or design direction, but still needs substantial elaboration to execute |
| 4 | Concrete enough to become a research question or design decision, needing only minor refinement |
| 5 | Concrete enough to write directly into a research design, experiment plan, or product spec |

The judge prompt actually implemented in `evaluate_actionability.py` uses a condensed one-line version of the same five levels (`1 = purely descriptive; 2 = vague direction; 3 = identifiable direction; 4 = actionable decision; 5 = very operational with clear next steps`). Neither `README.md` nor the rest of this file previously recorded the original, more detailed rubric wording that the condensed version was derived from.

Everything else in the specification — the tech stack, project layout, phased build order, the per-module implementation details for `fetch_data.py`/`embed.py`, the cost-control and caching design, the two-layer validity design, the three-level reliability design, and the experiment-level (not per-query) ICC design — is already documented in this file and/or `README.md`, in most cases in more detail and with corrective history that the original specification, written before implementation, could not have contained.
