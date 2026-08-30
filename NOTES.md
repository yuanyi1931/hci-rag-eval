# Statistical validation notes

This document records the methodological checks and corrective history for the reliability statistics used in this project. It is intended as a neutral technical record for later reporting and method sections. It is written without exaggeration and without omitting the earlier failures and incorrect assumptions.

## 1. ICC(2,1) 軸向錯誤

原始實作中 `msr` 取自「列之間」，但當時的軸向約定實際上是列 = rater，而不是列 = item/target。結果是，實作計算的是評分者間均方，而不是 Shrout & Fleiss 所定義的受試者間均方。

同時，分母中的 `k`、`n` 也假設了相反方向的軸向約定：同一個函式內同時混用了兩套定義，這會讓輸出在數值上看起來合理，但卻回答錯了問題。

修正前，對 Shrout & Fleiss (1979) Table 1 的資料輸出為：

- 原方向（6 列 target × 4 欄 judge）：0.161
- 轉置後：0.743
- 正確值：0.290

對照 pingouin 的完整輸出可知，這兩個錯誤數字分別接近：

- `ICC(1,1) = 0.166`
- `ICC(C,1) = 0.715`

也就是說，錯誤實作並非產生亂數，而是計算了另一種 ICC 變體。數值落在合理範圍內，但回答的是不同的統計問題。這類錯誤不會被「結果看起來合理」的檢查攔截。

修正方式：統一為列 = items/targets、欄 = raters，並在 docstring 明示這個約定，以避免軸向混用。

## 2. Early return 使測試失去驗證力

`icc_2_1` 與 `krippendorff_alpha` 原本在函式開頭都有 perfect-agreement 捷徑。

這兩個對應的測試使用完全一致的資料，因此直接命中捷徑並回傳 `1.0`，公式本體從未被執行。測試通過，但沒有驗證任何東西。

經推導，兩個捷徑皆為冗餘：

- ICC：當每列常數時，`ss_error = 0` 且 `ss_cols = 0`，所以 `mse = 0`、`msc = 0`，分子與分母同時收斂為 `msr`，結果為 `1.0`。
- Krippendorff：當沒有 mismatch 時，`D_o = 0`，因此 `alpha = 1`。

移除捷徑後，原測試改名為 `*_formula_converges_to_one`，現在確實驗證公式在邊界條件下的收斂行為，而不是繞過公式。

## 3. Krippendorff's alpha 缺少有限樣本修正

原實作的期望不一致度使用：

- `1 - Σ(n_c / n)^2`

但 Krippendorff (2004) 的定義為：

- `(n^2 - Σ n_c^2) / (n(n - 1))`

缺少 `(n - 1)` 修正時，該指標實際上更接近 Scott's pi，且會系統性低估 alpha。這不是微小差異，而是定義層級上的偏差。

原本的 docstring 宣稱依據 Krippendorff (2004)，但實作與該定義並不一致；這個不一致在驗證階段被確認並修正。

## 4. ICC 命名法對照

本專案採用 Shrout & Fleiss (1979) 的命名；`pingouin` 則採用 McGraw & Wong (1996) 的命名：

| Shrout & Fleiss | McGraw & Wong / pingouin | 模型 |
|---|---|---|
| ICC(1,1) | ICC(1,1) | 單向隨機效應 |
| ICC(2,1) | ICC(A,1) | 雙向隨機效應，絕對一致 |
| ICC(3,1) | ICC(C,1) | 雙向混合效應，一致性 |

本專案選用 `ICC(2,1)` / `ICC(A,1)` 的理由如下：

- 本專案中的 reliability 分析衡量的是同一 prompt 在多次生成之間的數值一致性，而不是僅僅維持排序一致。
- 生成結果被視為一位「評分者」的評分；這些「評分者」是從所有可能生成結果之中抽樣出的隨機來源，而不是固定的特定評分者。
- 我們關心的是數值本身是否一致（absolute agreement），而非只要求排名一致（consistency）。
- 若兩位評分者給出不同的絕對分數，即使排序一致，仍然代表不同的 measurement outcome；這在生成品質評估中是有意義的差異。

因此，對本專案而言，`ICC(2,1)` / `ICC(A,1)` 是更符合研究問題的選擇。

## 5. Cohen's kappa 預期值的來源問題

測試中的預期值 `0.40` 一度被標註為 Cohen (1960) 的 worked example，但無法核實對應的頁碼、表格與混淆矩陣。Cohen (1960) 的主要 worked example 常見計算結果為 `0.492`，而 `0.40` 在 Landis & Koch (1977) 的解釋量表中接近 moderate agreement 的下界 `0.41`，因此推測為兩者混淆。

這個錯誤已被修正：不再宣稱它來自 Cohen (1960) 的文獻範例，而改成明確標示的手算範例。

目前使用的 2×2 矩陣為：

[[4, 1], [2, 3]]

其中：

- yes/yes = 4
- yes/no = 1
- no/yes = 2
- no/no = 3

對應手算如下：

- `p_o = (4 + 3) / 10 = 0.70`
- `p_e = ((5/10) * (6/10)) + ((5/10) * (4/10)) = 0.50`
- `kappa = (p_o - p_e) / (1 - p_e) = (0.70 - 0.50) / (1.00 - 0.50) = 0.40`

此版本明確標註為 hand calculation，而非文獻引用，讓讀者可以自行驗算，且不會誤導成「有文獻依據」的數值。

## 6. 現行測試覆蓋與來源

目前的測試共有 10 個，依來源類型整理如下：

1. `test_icc_2_1_shrout_fleiss_1979_table_1` — 發表文獻（Shrout & Fleiss Table 1）
2. `test_icc_2_1_perfect_agreement_formula_converges_to_one` — 公式性質（邊界條件）
3. `test_icc_2_1_random_like_data_near_zero` — 公式性質 / sanity check
4. `test_icc_2_1_matches_pingouin_intraclass_corr` — 獨立套件交叉驗證
5. `test_krippendorff_alpha_perfect_agreement_formula_converges_to_one` — 公式性質（邊界條件）
6. `test_krippendorff_alpha_random_like_data_near_zero` — 公式性質 / sanity check
7. `test_jaccard_similarity_hand_calculated` — 手算推導
8. `test_krippendorff_alpha_level_not_nominal_raises` — 規格限制 / 不支援情境
9. `test_krippendorff_alpha_shape_error_message_is_generic` — 驗證行為 / 輸入格式檢查
10. `test_cohens_kappa_hand_calculation_example` — 手算推導（明確矩陣與算式）

這種組合的重要性在於，它不是只依靠單一來源：

- 有文獻基準
- 有獨立實作交叉驗證
- 有邏輯性質檢查
- 有手算可驗證

這使得驗證更穩健，且更不容易被單一錯誤假設掩蓋。

## 7. 環境注意事項

測試必須以 `.venv/bin/python -m pytest` 執行，不能直接用系統或 Anaconda 的 `pytest`。

系統中的 Anaconda 環境會使 `which pytest` 指向 `/opt/anaconda3/bin/pytest`，從而令 pytest 與被測套件分處不同 interpreter。這種情況下，`pingouin` 交叉驗證可能被無故 skip，且表現出「測試看起來不一致」的假象。這是一個環境錯誤，不是統計錯誤。

這個問題在驗證過程中被確認，並且在專案規範中明確要求使用虛擬環境內的 Python 進行測試。

## 結論

本專案的統計模組驗證歷程揭露了幾個真實且關鍵的問題：

1. ICC 的軸向錯誤改變了統計問題本身。
2. early return 讓測試無法驗證公式。
3. Krippendorff alpha 缺少有限樣本修正，定義與實作不一致。
4. ICC 的命名法需要明確對照，以避免與 pingouin 的輸出混淆。
5. Cohen's kappa 的來源需要根據文獻與可驗算步驟明確標註，不能用未核實的引用。

目前的狀態是：經過修正後，統計模組已在正確環境下通過測試，且其驗證記錄足以作為後續研究報告的方法論章節。

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

-0.35 這個數字來自對話中未經計算的目視估計,實際計算為 -0.147。這是本專案記錄到的一個案例:看似有據的數值來自不可靠的推導程序,與本研究要量化的 validity 問題同構。

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

## 15. 【相關性的三次結果不一致】

Three independent runs at three different scales have now each produced a Pearson correlation between `average_retrieval_similarity` and `grounding_rate`, and the three results disagree in direction and are all statistically non-significant:

| Run | n | r | p |
|---|---|---|---|
| 3×3 smoke test | 3 | direction negative (qualitative only — lowest-similarity query had the highest grounding rate; no r computed for n=3) | — |
| 5×5 | 5 | −0.147 | 0.813 |
| 10×5 | 10 | +0.222 | 0.538 |

All three p-values are far above the conventional 0.05 threshold, and the sign of the correlation flips between the 5×5 and 10×5 runs. **This should be reported as a genuine null/inconsistent result and must not be spun as evidence of a trend in either direction** — there is no reliable, reproducible relationship between retrieval similarity and grounding rate detectable under this experimental setup at these sample sizes.

Design-limitation caveat: across the 10 queries in the largest run, `average_retrieval_similarity` only ranges from 0.197 to 0.388 (sd = 0.065) — a narrow band that may simply be too small to produce a detectable effect on grounding rate even if a real relationship exists. Properly testing this hypothesis would require deliberately constructing a query set with much larger spread in retrieval quality (e.g. some queries designed to retrieve highly on-topic papers, others designed to retrieve marginally relevant ones), rather than relying on the incidental similarity range that happens to occur across a small set of naturally-chosen queries.

## 16. 【citation hallucination 的三種子類型】

Across n=10 (50 generation records), exactly 3 citation hallucinations were found, and all 3 are **near-neighbor arXiv-id confusions with zero outright fabrications** — in every case the cited id is a real, well-formed arXiv identifier, just not one of the retrieved top-k papers, and it differs from an actually-retrieved id by a single small edit:

- **Digit swap**: `2008.03582v1` → `2008.02582v1`
- **Version suffix**: `2006.00372v1` → `2006.00372v2`
- **Year prefix**: `2005.02582v1` → `2008.02582v1`

arXiv identifiers follow a rigid `YYMM.NNNNN` + `vVERSION` structure, and this structure appears to make single-position digit or version errors especially plausible for the model to produce — the hallucinated id "looks" exactly as legitimate as the correct one, follows the same format, and could easily belong to some other real paper. This is precisely the failure mode an LLM-judge-based check might miss, since nothing about the hallucinated citation looks wrong in isolation; it requires knowing the *exact* set of ids that were actually retrieved for that query to catch it.

This is exactly what `citation_validity_rate` does: a pure deterministic top-k membership check (is the cited id literally in the retrieved set for this query?) catches all 3 cases with 100% reliability, at zero additional API/judge cost. This validates the project's two-layer validity design — the cheapest layer (no LLM call at all) catches the hardest-to-detect error type, while the more expensive LLM-judge layer is reserved for genuinely subjective judgments (e.g., is a claim actually supported by the cited text) that a deterministic check cannot make.
