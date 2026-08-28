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
